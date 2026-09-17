import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests

from functions.argument_validation import throw_error_if_empty_string
from services.authorisation_service import AuthorisationService

LOGGER = logging.getLogger(__name__)
HTTP_UNAUTHORIZED = 401
HTTP_PRECONDITION_FAILED = 412
_EXPORT_PRECONDITION_RETRY_COUNT = 12
_EXPORT_PRECONDITION_RETRY_DELAY_SECONDS = 5
_TRANSIENT_RETRY_COUNT = 3
_TRANSIENT_RETRY_DELAY_SECONDS = 20
_STORAGE_API_URL = "https://storage.googleapis.com/storage/v1"


class DatabaseService:
    def __init__(  # noqa: PLR0913
        self,
        authorisation_service: AuthorisationService,
        project_id: str,
        database_name: str,
        export_bucket_name: str,
        export_prefix: str,
        operation_timeout_seconds: int,
        operation_poll_seconds: int,
        sql_admin_api_url: str = "https://sqladmin.googleapis.com/sql/v1beta4",
        http_connect_timeout_seconds: float = 5.0,
        http_read_timeout_seconds: float = 30.0,
    ):
        self._authorisation_service = authorisation_service
        self._project_id = project_id
        self._database_name = database_name
        self._export_bucket_name = export_bucket_name
        self._export_prefix = export_prefix.strip("/")
        self._operation_timeout_seconds = operation_timeout_seconds
        self._operation_poll_seconds = operation_poll_seconds
        self._sql_admin_api_url = sql_admin_api_url.rstrip("/")
        self._http_timeout = (
            http_connect_timeout_seconds,
            http_read_timeout_seconds,
        )

    def copy_table_data(
        self, table_name: str, source_instance_name: str, destination_instance_name: str
    ) -> None:
        throw_error_if_empty_string(table_name, "table_name")
        throw_error_if_empty_string(source_instance_name, "source_instance_name")
        throw_error_if_empty_string(
            destination_instance_name, "destination_instance_name"
        )

        started_at = time.monotonic()
        LOGGER.info(
            "Copying table data started; table=%s source=%s destination=%s",
            table_name,
            source_instance_name,
            destination_instance_name,
        )

        export_uri = self.__build_export_uri(
            source_instance_name=source_instance_name,
            destination_instance_name=destination_instance_name,
            table_name=table_name,
        )
        LOGGER.info(
            "Starting Cloud SQL export; table=%s source=%s uri=%s",
            table_name,
            source_instance_name,
            export_uri,
        )

        export_operation = self.__export_table_to_gcs(
            source_instance_name=source_instance_name,
            table_name=table_name,
            export_uri=export_uri,
        )
        self.__wait_for_operation(export_operation)

        LOGGER.info(
            "Starting Cloud SQL import; table=%s destination=%s uri=%s",
            table_name,
            destination_instance_name,
            export_uri,
        )
        import_operation = self.__import_table_from_gcs(
            destination_instance_name=destination_instance_name,
            export_uri=export_uri,
        )
        self.__wait_for_operation(import_operation)

        LOGGER.info(
            (
                "Copying table data completed; table=%s source=%s destination=%s "
                "export_uri=%s duration_seconds=%.2f"
            ),
            table_name,
            source_instance_name,
            destination_instance_name,
            export_uri,
            time.monotonic() - started_at,
        )

    def __export_table_to_gcs(
        self, source_instance_name: str, table_name: str, export_uri: str
    ) -> str:
        export_url = f"{self.__get_instance_api_url(source_instance_name)}/export"
        response: requests.Response | None = None
        for attempt in range(1, _EXPORT_PRECONDITION_RETRY_COUNT + 1):
            response = self.__request_with_authorisation_retry(
                method="post",
                url=export_url,
                json=self.__create_export_request_body(table_name, export_uri),
            )
            if response.status_code != HTTP_PRECONDITION_FAILED:
                break

            if attempt == _EXPORT_PRECONDITION_RETRY_COUNT:
                break

            LOGGER.warning(
                (
                    "Cloud SQL export precondition not met; retrying; table=%s "
                    "source=%s attempt=%s/%s"
                ),
                table_name,
                source_instance_name,
                attempt,
                _EXPORT_PRECONDITION_RETRY_COUNT,
            )
            time.sleep(_EXPORT_PRECONDITION_RETRY_DELAY_SECONDS)

        if response is None:
            raise RuntimeError("Cloud SQL export request did not return a response")

        self.__raise_for_status_with_details(response, "Cloud SQL export")
        operation_name = response.json().get("name")
        if not operation_name:
            raise ValueError(
                "Cloud SQL export succeeded but no operation name returned"
            )

        return str(operation_name)

    def __import_table_from_gcs(
        self, destination_instance_name: str, export_uri: str
    ) -> str:
        response = self.__request_with_authorisation_retry(
            method="post",
            url=f"{self.__get_instance_api_url(destination_instance_name)}/import",
            json=self.__create_import_request_body(export_uri),
        )
        self.__raise_for_status_with_details(response, "Cloud SQL import")
        operation_name = response.json().get("name")
        if not operation_name:
            raise ValueError(
                "Cloud SQL import succeeded but no operation name returned"
            )

        return str(operation_name)

    def __wait_for_operation(self, operation_name: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._operation_timeout_seconds
        started_at = time.monotonic()
        last_status = "UNKNOWN"

        while True:
            response = self.__request_with_authorisation_retry(
                method="get",
                url=self.__get_operation_api_url(operation_name),
            )
            self.__raise_for_status_with_details(
                response,
                "Cloud SQL operation poll",
            )
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

            time.sleep(self._operation_poll_seconds)

    def __build_export_uri(
        self, source_instance_name: str, destination_instance_name: str, table_name: str
    ) -> str:
        timestamp = datetime.now(tz=UTC).strftime("%Y/%m/%d/%H%M%S")
        source_instance = self.__normalize_instance_name(source_instance_name)
        destination_instance = self.__normalize_instance_name(destination_instance_name)
        safe_table = table_name.lower()
        object_name = (
            f"{source_instance}-to-{destination_instance}/{timestamp}/"
            f"{safe_table}-{int(time.time())}.sql.gz"
        )
        if self._export_prefix:
            return (
                f"gs://{self._export_bucket_name}/{self._export_prefix}/{object_name}"
            )

        return f"gs://{self._export_bucket_name}/{object_name}"

    def __create_authorisation_headers(self) -> dict[str, str]:
        token = self._authorisation_service.get_credentials_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def __request_with_authorisation_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        request_method = getattr(requests, method)
        for attempt in range(_TRANSIENT_RETRY_COUNT + 1):
            try:
                response = request_method(
                    url=url,
                    headers=self.__create_authorisation_headers(),
                    timeout=self._http_timeout,
                    **kwargs,
                )
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

                LOGGER.warning(
                    (
                        "Transient SQL Admin API request failure; retrying in %s "
                        "seconds; url=%s retry=%s/%s error_type=%s error=%s"
                    ),
                    _TRANSIENT_RETRY_DELAY_SECONDS,
                    url,
                    attempt + 1,
                    _TRANSIENT_RETRY_COUNT,
                    type(error).__name__,
                    error,
                )
                time.sleep(_TRANSIENT_RETRY_DELAY_SECONDS)

        raise RuntimeError("SQL Admin API request retry loop exited unexpectedly")

    @staticmethod
    def __raise_for_status_with_details(
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

    def __get_instance_api_url(self, instance_name: str) -> str:
        normalized = self.__normalize_instance_name(instance_name)
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/instances/"
            f"{normalized}"
        )

    def __get_operation_api_url(self, operation_name: str) -> str:
        return (
            f"{self._sql_admin_api_url}/projects/{self._project_id}/operations/"
            f"{operation_name}"
        )

    def ensure_bucket_permissions_for_instances(
        self, source_instance_name: str, destination_instance_name: str
    ) -> None:
        source_service_account = self.__get_instance_service_account(
            source_instance_name
        )
        destination_service_account = self.__get_instance_service_account(
            destination_instance_name
        )

        service_accounts = {
            source_service_account,
            destination_service_account,
        }
        for service_account in service_accounts:
            if not service_account:
                continue

            self.__ensure_bucket_member_has_object_admin_role(
                f"serviceAccount:{service_account}"
            )

    def __get_instance_service_account(self, instance_name: str) -> str:
        response = self.__request_with_authorisation_retry(
            method="get",
            url=self.__get_instance_api_url(instance_name),
        )
        self.__raise_for_status_with_details(
            response,
            "Cloud SQL get instance",
        )
        service_account = response.json().get("serviceAccountEmailAddress")
        if not isinstance(service_account, str):
            return ""

        return service_account

    def __ensure_bucket_member_has_object_admin_role(self, member: str) -> None:
        bucket_iam_url = f"{_STORAGE_API_URL}/b/{self._export_bucket_name}/iam"

        get_policy_response = self.__request_with_authorisation_retry(
            method="get",
            url=bucket_iam_url,
        )
        self.__raise_for_status_with_details(
            get_policy_response,
            "Cloud Storage get bucket IAM",
        )
        policy = dict(get_policy_response.json())
        bindings = policy.get("bindings", [])
        if not isinstance(bindings, list):
            bindings = []

        object_admin_binding: dict[str, Any] | None = None
        for binding in bindings:
            if (
                isinstance(binding, dict)
                and binding.get("role") == "roles/storage.objectAdmin"
            ):
                object_admin_binding = binding
                break

        if object_admin_binding is None:
            object_admin_binding = {
                "role": "roles/storage.objectAdmin",
                "members": [],
            }
            bindings.append(object_admin_binding)

        members = object_admin_binding.get("members", [])
        if not isinstance(members, list):
            members = []
            object_admin_binding["members"] = members

        if member in members:
            return

        members.append(member)

        set_policy_payload: dict[str, Any] = {
            "bindings": bindings,
        }
        if "etag" in policy:
            set_policy_payload["etag"] = policy["etag"]
        if "version" in policy:
            set_policy_payload["version"] = policy["version"]

        set_policy_response = self.__request_with_authorisation_retry(
            method="put",
            url=bucket_iam_url,
            json=set_policy_payload,
        )
        self.__raise_for_status_with_details(
            set_policy_response,
            "Cloud Storage set bucket IAM",
        )

    @staticmethod
    def __normalize_instance_name(instance_identifier: str) -> str:
        return instance_identifier.rsplit(":", maxsplit=1)[-1]

    def __create_export_request_body(
        self, table_name: str, export_uri: str
    ) -> dict[str, Any]:
        return {
            "exportContext": {
                "fileType": "SQL",
                "uri": export_uri,
                "databases": [self._database_name],
                "sqlExportOptions": {
                    "tables": [table_name],
                    "schemaOnly": False,
                },
            }
        }

    def __create_import_request_body(self, export_uri: str) -> dict[str, Any]:
        return {
            "importContext": {
                "fileType": "SQL",
                "uri": export_uri,
                "database": self._database_name,
            }
        }
