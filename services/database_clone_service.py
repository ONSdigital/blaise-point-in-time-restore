import logging
from datetime import UTC
from typing import Any

from models.database_clone_model import DatabaseCloneModel
from services.cloud_sql_admin_client import CloudSqlAdminClient

LOGGER = logging.getLogger(__name__)
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400


class DatabaseCloneService:
    def __init__(
        self,
        cloud_sql_client: CloudSqlAdminClient,
    ):
        self._cloud_sql_client = cloud_sql_client

    def close(self) -> None:
        self._cloud_sql_client.close()

    def create_clone(self, database_clone_model: DatabaseCloneModel) -> str:
        clone_api_url = self._cloud_sql_client.instance_url(
            database_clone_model.source_instance_name
        )
        response = self._cloud_sql_client.request(
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
        response = self._cloud_sql_client.request(
            method="delete",
            url=self._cloud_sql_client.instance_url(instance_name),
        )

        if (
            response.status_code == HTTP_BAD_REQUEST
            and "protected" in response.text.lower()
        ):
            LOGGER.info(
                "Delete blocked by deletion protection; instance=%s", instance_name
            )
            self.disable_deletion_protection(instance_name)
            response = self._cloud_sql_client.request(
                method="delete",
                url=self._cloud_sql_client.instance_url(instance_name),
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
        response = self._cloud_sql_client.request(
            method="get",
            url=self._cloud_sql_client.instance_url(instance_name),
        )
        response.raise_for_status()

        instance = response.json()
        LOGGER.info("Cloud SQL instance located; instance=%s", instance_name)

        return dict(instance)

    def instance_exists(self, instance_name: str) -> bool:
        response = self._cloud_sql_client.request(
            method="get",
            url=self._cloud_sql_client.instance_url(instance_name),
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
        return self._cloud_sql_client.wait_for_operation(
            operation_name=operation_name,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    def disable_deletion_protection(self, instance_name: str) -> None:
        """Disable deletion protection, starting a STOPPED instance if required."""
        patch_body: dict[str, Any] = {"settings": {"deletionProtectionEnabled": False}}

        response = self._cloud_sql_client.request(
            method="patch",
            url=self._cloud_sql_client.instance_url(instance_name),
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
            response = self._cloud_sql_client.request(
                method="patch",
                url=self._cloud_sql_client.instance_url(instance_name),
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
