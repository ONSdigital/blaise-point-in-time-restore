from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import Mock, call

import pytest

from models.database_clone_model import DatabaseCloneModel
from services.database_clone_service import DatabaseCloneService


def _instance_url(name: str) -> str:
    return (
        "https://sqladmin.googleapis.com/sql/v1beta4/projects/proj/instances/"
        f"{name.rsplit(':', maxsplit=1)[-1]}"
    )


@pytest.fixture
def cloud_sql_client() -> Mock:
    client = Mock()
    client.instance_url.side_effect = _instance_url
    return client


@pytest.fixture
def clone_service(cloud_sql_client: Mock) -> DatabaseCloneService:
    return DatabaseCloneService(cloud_sql_client=cloud_sql_client)


def _clone_model() -> DatabaseCloneModel:
    model = DatabaseCloneModel()
    model.source_instance_name = "proj:region:source"
    model.destination_instance_name = "clone-target"
    model.point_in_time = datetime(2026, 7, 8, 14, 30, tzinfo=UTC)
    return model


def test_create_clone_returns_operation_name(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    response = Mock()
    response.json.return_value = {"name": "op-create"}
    cloud_sql_client.request.return_value = response

    operation = clone_service.create_clone(_clone_model())

    assert operation == "op-create"
    cloud_sql_client.request.assert_called_once_with(
        method="post",
        url=(
            "https://sqladmin.googleapis.com/sql/v1beta4/projects/proj/"
            "instances/source/clone"
        ),
        json={
            "cloneContext": {
                "kind": "sql#cloneContext",
                "destinationInstanceName": "clone-target",
                "pointInTime": "2026-07-08T14:30:00Z",
            }
        },
    )


def test_create_clone_raises_when_operation_name_missing(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    cloud_sql_client.request.return_value.json.return_value = {}

    with pytest.raises(ValueError, match="no operation name"):
        clone_service.create_clone(_clone_model())


def test_delete_clone_handles_deletion_protection(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    instance_url = (
        "https://sqladmin.googleapis.com/sql/v1beta4/projects/proj/"
        "instances/clone-instance"
    )
    protected_delete = Mock(status_code=400, text="Instance is protected")
    patch_response = Mock(status_code=200, text="")
    patch_response.json.return_value = {"name": "op-disable-protection"}
    successful_delete = Mock(status_code=200, text="")
    successful_delete.json.return_value = {"name": "op-delete"}
    cloud_sql_client.request.side_effect = [
        protected_delete,
        patch_response,
        successful_delete,
    ]

    operation = clone_service.delete_clone("clone-instance")

    assert operation == "op-delete"
    assert cloud_sql_client.request.call_args_list == [
        call(method="delete", url=instance_url),
        call(
            method="patch",
            url=instance_url,
            json={"settings": {"deletionProtectionEnabled": False}},
        ),
        call(method="delete", url=instance_url),
    ]
    cloud_sql_client.wait_for_operation.assert_called_once_with(
        operation_name="op-disable-protection",
        timeout_seconds=300,
        poll_interval_seconds=5,
    )


def test_disable_deletion_protection_starts_stopped_instance(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    stopped_response = Mock(status_code=400, text="instance is stopped")
    successful_response = Mock(status_code=200, text="")
    successful_response.json.return_value = {"name": "op-patch"}
    cloud_sql_client.request.side_effect = [stopped_response, successful_response]

    clone_service.disable_deletion_protection("clone-instance")

    assert cloud_sql_client.request.call_args_list[-1].kwargs["json"] == {
        "settings": {
            "deletionProtectionEnabled": False,
            "activationPolicy": "ALWAYS",
        }
    }


def test_get_instance_returns_payload(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    cloud_sql_client.request.return_value.json.return_value = {
        "name": "i1",
        "connectionName": "proj:reg:i1",
    }

    instance = clone_service.get_instance("i1")

    assert instance["connectionName"] == "proj:reg:i1"


def test_instance_exists_returns_false_on_404(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    cloud_sql_client.request.return_value.status_code = 404

    assert clone_service.instance_exists("missing") is False


def test_instance_exists_checks_other_statuses(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    cloud_sql_client.request.return_value.status_code = 200

    assert clone_service.instance_exists("existing") is True
    cloud_sql_client.request.return_value.raise_for_status.assert_called_once()


def test_wait_for_operation_delegates_to_client(
    clone_service: DatabaseCloneService, cloud_sql_client: Mock
) -> None:
    cloud_sql_client.wait_for_operation.return_value = {"status": "DONE"}

    operation = clone_service.wait_for_operation(
        "op1", timeout_seconds=30, poll_interval_seconds=2
    )

    assert operation == {"status": "DONE"}
    cloud_sql_client.wait_for_operation.assert_called_once_with(
        operation_name="op1",
        timeout_seconds=30,
        poll_interval_seconds=2,
    )


def test_create_clone_request_body_normalizes_to_utc_z_suffix() -> None:
    clone_model = _clone_model()
    clone_model.point_in_time = datetime(2026, 7, 8, 14, 30)

    body = cast(
        Any, DatabaseCloneService
    )._DatabaseCloneService__create_clone_request_body(clone_model)

    assert body["cloneContext"]["pointInTime"].endswith("Z")
