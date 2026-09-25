import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests

from functions.argument_validation import throw_error_if_empty_string
from services.cloud_sql_admin_client import CloudSqlAdminClient

LOGGER = logging.getLogger(__name__)
HTTP_PRECONDITION_FAILED = 412
HTTP_CONFLICT = 409
_STORAGE_API_URL = "https://storage.googleapis.com/storage/v1"
_IAM_POLICY_RETRY_COUNT = 3
_EXPORT_PRECONDITION_RETRY_COUNT = 12
_EXPORT_PRECONDITION_RETRY_DELAY_SECONDS = 5


class DatabaseService:
    def __init__(  # noqa: PLR0913
        self,
        cloud_sql_client: CloudSqlAdminClient,
        database_name: str,
        export_bucket_name: str,
        export_prefix: str,
        operation_timeout_seconds: int,
        operation_poll_seconds: int,
    ):
        self._cloud_sql_client = cloud_sql_client
        self._database_name = database_name
        self._export_bucket_name = export_bucket_name
        self._export_prefix = export_prefix.strip("/")
        self._operation_timeout_seconds = operation_timeout_seconds
        self._operation_poll_seconds = operation_poll_seconds

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
        export_url = (
            f"{self._cloud_sql_client.instance_url(source_instance_name)}/export"
        )
        response: requests.Response | None = None
        for attempt in range(1, _EXPORT_PRECONDITION_RETRY_COUNT + 1):
            response = self._cloud_sql_client.request(
                method="post",
                url=export_url,
                json=self.__create_export_request_body(table_name, export_uri),
            )
            if response.status_code == HTTP_PRECONDITION_FAILED:
                LOGGER.error(
                    (
                        "Cloud SQL export precondition failed; table=%s source=%s "
                        "uri=%s attempt=%s/%s response=%s"
                    ),
                    table_name,
                    source_instance_name,
                    export_uri,
                    attempt,
                    _EXPORT_PRECONDITION_RETRY_COUNT,
                    response.text,
                )
            if response.status_code != HTTP_PRECONDITION_FAILED:
                break

            if self.__is_bucket_permission_error(response):
                LOGGER.error(
                    (
                        "Cloud SQL export failed due to bucket permissions; "
                        "skipping retries; table=%s source=%s uri=%s"
                    ),
                    table_name,
                    source_instance_name,
                    export_uri,
                )
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

        self._cloud_sql_client.raise_for_status_with_details(
            response, "Cloud SQL export"
        )
        operation_name = response.json().get("name")
        if not operation_name:
            raise ValueError(
                "Cloud SQL export succeeded but no operation name returned"
            )

        return str(operation_name)

    @staticmethod
    def __is_bucket_permission_error(response: requests.Response) -> bool:
        try:
            error = response.json().get("error", {})
        except requests.JSONDecodeError:
            return False

        if not isinstance(error, dict):
            return False

        message = str(error.get("message", "")).casefold()
        errors = error.get("errors", [])
        has_not_authorized_reason = isinstance(errors, list) and any(
            isinstance(item, dict) and item.get("reason") == "notAuthorized"
            for item in errors
        )
        return has_not_authorized_reason or "required permissions" in message

    def __import_table_from_gcs(
        self, destination_instance_name: str, export_uri: str
    ) -> str:
        response = self._cloud_sql_client.request(
            method="post",
            url=(
                f"{self._cloud_sql_client.instance_url(destination_instance_name)}"
                "/import"
            ),
            json=self.__create_import_request_body(export_uri),
        )
        self._cloud_sql_client.raise_for_status_with_details(
            response, "Cloud SQL import"
        )
        operation_name = response.json().get("name")
        if not operation_name:
            raise ValueError(
                "Cloud SQL import succeeded but no operation name returned"
            )

        return str(operation_name)

    def __wait_for_operation(self, operation_name: str) -> dict[str, Any]:
        return self._cloud_sql_client.wait_for_operation(
            operation_name=operation_name,
            timeout_seconds=self._operation_timeout_seconds,
            poll_interval_seconds=self._operation_poll_seconds,
        )

    def __build_export_uri(
        self, source_instance_name: str, destination_instance_name: str, table_name: str
    ) -> str:
        timestamp = datetime.now(tz=UTC).strftime("%Y/%m/%d/%H%M%S")
        source_instance = self._cloud_sql_client.normalize_instance_name(
            source_instance_name
        )
        destination_instance = self._cloud_sql_client.normalize_instance_name(
            destination_instance_name
        )
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
                f"serviceAccount:{service_account}",
            )

    def __get_instance_service_account(self, instance_name: str) -> str:
        response = self._cloud_sql_client.request(
            method="get",
            url=self._cloud_sql_client.instance_url(instance_name),
        )
        self._cloud_sql_client.raise_for_status_with_details(
            response, "Cloud SQL get instance"
        )
        service_account = response.json().get("serviceAccountEmailAddress")
        if not isinstance(service_account, str):
            return ""

        return service_account

    def __ensure_bucket_member_has_object_admin_role(self, member: str) -> None:
        bucket_iam_url = f"{_STORAGE_API_URL}/b/{self._export_bucket_name}/iam"
        set_policy_response: requests.Response | None = None

        for attempt in range(1, _IAM_POLICY_RETRY_COUNT + 1):
            get_policy_response = self._cloud_sql_client.request(
                method="get",
                url=bucket_iam_url,
                params={"optionsRequestedPolicyVersion": 3},
            )
            self._cloud_sql_client.raise_for_status_with_details(
                get_policy_response, "Cloud Storage get bucket IAM"
            )
            policy = dict(get_policy_response.json())
            bindings = policy.get("bindings", [])
            if not isinstance(bindings, list):
                bindings = []

            if self.__has_unconditional_member(bindings, member):
                return

            bindings.append(
                {
                    "role": "roles/storage.objectAdmin",
                    "members": [member],
                }
            )
            set_policy_payload: dict[str, Any] = {
                "bindings": bindings,
                "version": max(int(policy.get("version", 1)), 3),
            }
            for field in ("etag", "auditConfigs"):
                if field in policy:
                    set_policy_payload[field] = policy[field]

            set_policy_response = self._cloud_sql_client.request(
                method="put",
                url=bucket_iam_url,
                json=set_policy_payload,
            )
            if set_policy_response.status_code not in {
                HTTP_CONFLICT,
                HTTP_PRECONDITION_FAILED,
            }:
                self._cloud_sql_client.raise_for_status_with_details(
                    set_policy_response, "Cloud Storage set bucket IAM"
                )
                return

            LOGGER.warning(
                (
                    "Cloud Storage IAM policy changed concurrently; retrying; "
                    "bucket=%s member=%s attempt=%s/%s"
                ),
                self._export_bucket_name,
                member,
                attempt,
                _IAM_POLICY_RETRY_COUNT,
            )

        if set_policy_response is None:
            raise RuntimeError("Cloud Storage IAM policy update did not run")

        self._cloud_sql_client.raise_for_status_with_details(
            set_policy_response, "Cloud Storage set bucket IAM"
        )

    @staticmethod
    def __has_unconditional_member(bindings: list[Any], member: str) -> bool:
        return any(
            isinstance(binding, dict)
            and binding.get("role") == "roles/storage.objectAdmin"
            and "condition" not in binding
            and member in binding.get("members", [])
            for binding in bindings
        )

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
