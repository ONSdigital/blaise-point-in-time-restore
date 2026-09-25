import logging
import random
import threading
import time
from typing import Any

import google.auth
import requests
from google.auth.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession

LOGGER = logging.getLogger(__name__)
_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_TRANSIENT_RETRY_COUNT = 3
_TRANSIENT_RETRY_BASE_DELAY_SECONDS = 1
_TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class CloudSqlAdminClient:
    def __init__(
        self,
        project_id: str,
        sql_admin_api_url: str = "https://sqladmin.googleapis.com/sql/v1beta4",
        http_connect_timeout_seconds: float = 5.0,
        http_read_timeout_seconds: float = 30.0,
        credentials: Credentials | None = None,
    ):
        if credentials is None:
            credentials, _ = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])

        self._credentials = credentials
        self._project_id = project_id
        self._sql_admin_api_url = sql_admin_api_url.rstrip("/")
        self._http_timeout = (
            http_connect_timeout_seconds,
            http_read_timeout_seconds,
        )
        self._thread_local = threading.local()
        self._thread_local.session = self.__create_session()

    def close(self) -> None:
        session = getattr(self._thread_local, "session", None)
        if session is not None:
            session.close()
            del self._thread_local.session

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        retryable = method.casefold() == "get"
        for attempt in range(_TRANSIENT_RETRY_COUNT + 1):
            try:
                request_method = getattr(self.__get_session(), method)
                response = request_method(
                    url=url,
                    timeout=self._http_timeout,
                    **kwargs,
                )
                if (
                    not retryable
                    or response.status_code not in _TRANSIENT_HTTP_STATUS_CODES
                ):
                    return response

                if attempt == _TRANSIENT_RETRY_COUNT:
                    return response

                self.__log_retry(
                    url=url,
                    retry_number=attempt + 1,
                    error_type="HttpStatusError",
                    error=f"HTTP {response.status_code}",
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                if not retryable or attempt == _TRANSIENT_RETRY_COUNT:
                    raise

                self.__reset_session()
                self.__log_retry(
                    url=url,
                    retry_number=attempt + 1,
                    error_type=type(error).__name__,
                    error=str(error),
                )

            time.sleep(self.__retry_delay_seconds(attempt))

        raise RuntimeError("Cloud SQL API request retry loop exited unexpectedly")

    def wait_for_operation(
        self,
        operation_name: str,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        started_at = time.monotonic()
        last_status = "UNKNOWN"

        while True:
            response = self.request(
                method="get",
                url=self.operation_url(operation_name),
            )
            self.raise_for_status_with_details(response, "Cloud SQL operation poll")
            operation = dict(response.json())
            status = str(operation.get("status", "UNKNOWN"))

            if status != last_status:
                LOGGER.info(
                    (
                        "Cloud SQL operation status changed; operation=%s "
                        "status=%s elapsed_seconds=%.2f"
                    ),
                    operation_name,
                    status,
                    time.monotonic() - started_at,
                )
                last_status = status

            if status == "DONE":
                operation_error = operation.get("error")
                if operation_error:
                    raise RuntimeError(f"Cloud SQL operation failed: {operation_error}")
                return operation

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for Cloud SQL operation: {operation_name}"
                )

            time.sleep(poll_interval_seconds)

    def instance_url(self, instance_name: str) -> str:
        normalized = self.normalize_instance_name(instance_name)
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/instances/"
            f"{normalized}"
        )

    def operation_url(self, operation_name: str) -> str:
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/operations/"
            f"{operation_name}"
        )

    @staticmethod
    def normalize_instance_name(instance_identifier: str) -> str:
        return instance_identifier.rsplit(":", maxsplit=1)[-1]

    @staticmethod
    def raise_for_status_with_details(
        response: requests.Response, request_name: str
    ) -> None:
        if response.ok:
            return

        LOGGER.error(
            "%s request failed; status_code=%s response=%s",
            request_name,
            response.status_code,
            response.text,
        )
        response.raise_for_status()

    def __create_session(self) -> AuthorizedSession:
        return AuthorizedSession(self._credentials)

    def __get_session(self) -> AuthorizedSession:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = self.__create_session()
            self._thread_local.session = session
        return session

    def __reset_session(self) -> None:
        session = self.__get_session()
        session.close()
        self._thread_local.session = self.__create_session()

    @staticmethod
    def __retry_delay_seconds(attempt: int) -> float:
        maximum_delay = _TRANSIENT_RETRY_BASE_DELAY_SECONDS * (2**attempt)
        return random.uniform(maximum_delay / 2, maximum_delay)

    @staticmethod
    def __log_retry(
        url: str,
        retry_number: int,
        error_type: str,
        error: str,
    ) -> None:
        LOGGER.warning(
            (
                "Transient Cloud SQL API request failure; retrying with exponential "
                "backoff; url=%s retry=%s/%s error_type=%s error=%s"
            ),
            url,
            retry_number,
            _TRANSIENT_RETRY_COUNT,
            error_type,
            error,
        )
