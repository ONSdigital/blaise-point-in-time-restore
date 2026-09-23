import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests

from functions.argument_validation import throw_error_if_empty_string
from services.cloud_sql_admin_client import CloudSqlAdminClient

LOGGER = logging.getLogger(__name__)
HTTP_PRECONDITION_FAILED = 412
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
            if response.status_code != HTTP_PRECONDITION_FAILED:
                break

            if self.__is_bucket_permission_error(response):
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
