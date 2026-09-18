import logging
import random
import time
from datetime import UTC
from typing import Any

import requests

from models.database_clone_model import DatabaseCloneModel
from services.authorisation_service import AuthorisationService

LOGGER = logging.getLogger(__name__)
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
_TRANSIENT_RETRY_COUNT = 3
_TRANSIENT_RETRY_BASE_DELAY_SECONDS = 1
_TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class DatabaseCloneService:
    def __init__(
        self,
        authorisation_service: AuthorisationService,
        project_id: str,
        sql_admin_api_url: str = "https://sqladmin.googleapis.com/sql/v1beta4",
        http_connect_timeout_seconds: float = 5.0,
        http_read_timeout_seconds: float = 30.0,
    ):
        self._authorisation_service = authorisation_service
        self._project_id = project_id
        self._sql_admin_api_url = sql_admin_api_url.rstrip("/")
        self._http_timeout = (
            http_connect_timeout_seconds,
            http_read_timeout_seconds,
        )
        self._session = self.__create_session()

    def close(self) -> None:
        self._session.close()

    def create_clone(self, database_clone_model: DatabaseCloneModel) -> str:
        clone_api_url = self.__get_instance_api_url(
            database_clone_model.source_instance_name
        )
        response = self.__request_with_authorisation_retry(
            method="post",
            url=f"{clone_api_url}/clone",
            json=self.__create_clone_request_body(database_clone_model),
        )
        response.raise_for_status()

        response_body = response.json()
        operation_name = response_body.get("name")
        if not operation_name:
            raise ValueError(
                "Clone request succeeded but no operation name was returned"
            )

        LOGGER.info(
            "Clone requested; source=%s destination=%s point_in_time=%s operation=%s",
            database_clone_model.source_instance_name,
            database_clone_model.destination_instance_name,
            database_clone_model.point_in_time.isoformat(),
            operation_name,
        )

        return str(operation_name)

    def delete_clone(self, instance_name: str) -> str:
        response = self.__request_with_authorisation_retry(
            method="delete",
            url=self.__get_instance_api_url(instance_name),
        )

        if (
            response.status_code == HTTP_BAD_REQUEST
            and "protected" in response.text.lower()
        ):
            LOGGER.info(
                "Delete blocked by deletion protection; instance=%s", instance_name
            )
            self.disable_deletion_protection(instance_name)
            response = self.__request_with_authorisation_retry(
                method="delete",
                url=self.__get_instance_api_url(instance_name),
            )

        response.raise_for_status()

        response_body = response.json()
        operation_name = response_body.get("name")
        if not operation_name:
            raise ValueError(
                "Delete clone request succeeded but no operation name was returned"
            )

        LOGGER.info(
            "Clone delete requested; instance=%s operation=%s",
            instance_name,
            operation_name,
        )

        return str(operation_name)

    def get_instance(self, instance_name: str) -> dict[str, Any]:
        response = self.__request_with_authorisation_retry(
            method="get",
            url=self.__get_instance_api_url(instance_name),
        )
        response.raise_for_status()

        instance = response.json()
        LOGGER.info("Cloud SQL instance located; instance=%s", instance_name)

        return dict(instance)

    def instance_exists(self, instance_name: str) -> bool:
        response = self.__request_with_authorisation_retry(
            method="get",
            url=self.__get_instance_api_url(instance_name),
        )
        if response.status_code == HTTP_NOT_FOUND:
            LOGGER.info("Cloud SQL instance not found; instance=%s", instance_name)
            return False

        response.raise_for_status()
        LOGGER.info("Cloud SQL instance exists; instance=%s", instance_name)
        return True

    def wait_for_operation(
        self,
        operation_name: str,
        timeout_seconds: int,
        poll_interval_seconds: int = 5,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        started_at = time.monotonic()
        last_status = "UNKNOWN"

        LOGGER.info(
            (
                "Waiting for Cloud SQL operation; operation=%s timeout_seconds=%s "
                "poll_interval_seconds=%s"
            ),
            operation_name,
            timeout_seconds,
            poll_interval_seconds,
        )

        while True:
            response = self.__request_with_authorisation_retry(
                method="get",
                url=self.__get_operation_api_url(operation_name),
            )
            response.raise_for_status()
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
                    LOGGER.error(
                        "Cloud SQL operation failed; operation=%s error=%s",
                        operation_name,
                        operation_error,
                    )
                    raise RuntimeError(f"Cloud SQL operation failed: {operation_error}")

                LOGGER.info(
                    "Cloud SQL operation completed; operation=%s elapsed_seconds=%.2f",
                    operation_name,
                    time.monotonic() - started_at,
                )
                return operation

            if time.monotonic() >= deadline:
                LOGGER.error(
                    (
                        "Cloud SQL operation timed out; operation=%s "
                        "last_status=%s timeout_seconds=%s"
                    ),
                    operation_name,
                    status,
                    timeout_seconds,
                )
                raise TimeoutError(
                    f"Timed out waiting for Cloud SQL operation: {operation_name}"
                )

            time.sleep(poll_interval_seconds)

    def disable_deletion_protection(self, instance_name: str) -> None:
        """Disable deletion protection, starting a STOPPED instance if required."""
        patch_body: dict[str, Any] = {"settings": {"deletionProtectionEnabled": False}}

        response = self.__request_with_authorisation_retry(
            method="patch",
            url=self.__get_instance_api_url(instance_name),
            json=patch_body,
        )

        if (
            response.status_code == HTTP_BAD_REQUEST
            and "stopped" in response.text.lower()
        ):
            LOGGER.info(
                (
                    "Instance is stopped while disabling deletion protection; "
                    "requesting start and patch; instance=%s"
                ),
                instance_name,
            )
            patch_body["settings"] = {
                "deletionProtectionEnabled": False,
                "activationPolicy": "ALWAYS",
            }
            response = self.__request_with_authorisation_retry(
                method="patch",
                url=self.__get_instance_api_url(instance_name),
                json=patch_body,
            )

        response.raise_for_status()
        patch_operation = response.json().get("name")
        if patch_operation:
            LOGGER.info(
                "Deletion protection disable requested; instance=%s operation=%s",
                instance_name,
                patch_operation,
            )
            self.wait_for_operation(patch_operation, timeout_seconds=300)

    def __create_authorisation_headers(self) -> dict[str, str]:
        token = self._authorisation_service.get_credentials_token()

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def __request_with_authorisation_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        for attempt in range(_TRANSIENT_RETRY_COUNT + 1):
            try:
                request_method = getattr(self._session, method)
                response = request_method(
                    url=url,
                    headers=self.__create_authorisation_headers(),
                    timeout=self._http_timeout,
                    **kwargs,
                )
                if response.status_code in _TRANSIENT_HTTP_STATUS_CODES:
                    if attempt == _TRANSIENT_RETRY_COUNT:
                        return response

                    self.__log_transient_request_retry(
                        url=url,
                        retry_number=attempt + 1,
                        error_type="HttpStatusError",
                        error=f"HTTP {response.status_code}",
                    )
                    time.sleep(self.__transient_retry_delay_seconds(attempt))
                    continue

                if response.status_code != HTTP_UNAUTHORIZED:
                    return response

                LOGGER.warning(
                    "Unauthorized response from SQL Admin API; retrying once; url=%s",
                    url,
                )
                return request_method(
                    url=url,
                    headers=self.__create_authorisation_headers(),
                    timeout=self._http_timeout,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt == _TRANSIENT_RETRY_COUNT:
                    raise

                self.__reset_session()
                self.__log_transient_request_retry(
                    url=url,
                    retry_number=attempt + 1,
                    error_type=type(error).__name__,
                    error=str(error),
                )
                time.sleep(self.__transient_retry_delay_seconds(attempt))

        raise RuntimeError("SQL Admin API request retry loop exited unexpectedly")

    @staticmethod
    def __create_session() -> requests.Session:
        return requests.Session()

    def __reset_session(self) -> None:
        self._session.close()
        self._session = self.__create_session()

    @staticmethod
    def __transient_retry_delay_seconds(attempt: int) -> float:
        maximum_delay = _TRANSIENT_RETRY_BASE_DELAY_SECONDS * (2**attempt)
        return random.uniform(maximum_delay / 2, maximum_delay)

    @staticmethod
    def __log_transient_request_retry(
        url: str,
        retry_number: int,
        error_type: str,
        error: str,
    ) -> None:
        LOGGER.warning(
            (
                "Transient SQL Admin API request failure; retrying with exponential "
                "backoff; url=%s retry=%s/%s error_type=%s error=%s"
            ),
            url,
            retry_number,
            _TRANSIENT_RETRY_COUNT,
            error_type,
            error,
        )

    def __get_instance_api_url(self, instance_name: str) -> str:
        normalized_instance_name = self.__normalize_instance_name(instance_name)
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/instances/"
            f"{normalized_instance_name}"
        )

    def __get_operation_api_url(self, operation_name: str) -> str:
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/operations/"
            f"{operation_name}"
        )

    @staticmethod
    def __normalize_instance_name(instance_identifier: str) -> str:
        return instance_identifier.rsplit(":", maxsplit=1)[-1]

    @staticmethod
    def __create_clone_request_body(
        database_clone_model: DatabaseCloneModel,
    ) -> dict[str, Any]:
        point_in_time = database_clone_model.point_in_time
        if point_in_time.tzinfo is None:
            point_in_time = point_in_time.replace(tzinfo=UTC)

        point_in_time_utc = point_in_time.astimezone(UTC)

        return {
            "cloneContext": {
                "kind": "sql#cloneContext",
                "destinationInstanceName": (
                    database_clone_model.destination_instance_name
                ),
                "pointInTime": point_in_time_utc.isoformat().replace("+00:00", "Z"),
            }
        }
