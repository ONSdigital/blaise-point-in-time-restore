from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import Mock, call, patch

import pytest
import requests

from models.database_clone_model import DatabaseCloneModel
from services.database_clone_service import DatabaseCloneService

_EXPECTED_TRANSIENT_REQUEST_CALLS = 4
_EXPECTED_REPLACEMENT_SESSION_CALLS = 1
_EXPECTED_HTTP_STATUS_RETRY_CALLS = 2


@pytest.fixture
def authorisation_service() -> Mock:
    service = Mock()
    service.get_credentials_token.return_value = "token-123"
    return service


@pytest.fixture
def clone_service(authorisation_service: Mock) -> DatabaseCloneService:
    return DatabaseCloneService(
        authorisation_service=authorisation_service, project_id="proj"
    )


def test_create_clone_returns_operation_name(
    clone_service: DatabaseCloneService,
) -> None:
    clone_model = DatabaseCloneModel()
    clone_model.source_instance_name = "proj:region:source"
    clone_model.destination_instance_name = "clone-target"
    clone_model.point_in_time = datetime(2026, 7, 8, 14, 30, tzinfo=UTC)

    response = Mock()
    response.json.return_value = {"name": "op-create"}
    response.raise_for_status.return_value = None

    with patch(
        "services.database_clone_service.requests.Session.post", return_value=response
    ) as mock_post:
        operation = clone_service.create_clone(clone_model)

    assert operation == "op-create"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["timeout"] == (5.0, 30.0)


def test_create_clone_raises_when_no_operation_name(
    clone_service: DatabaseCloneService,
) -> None:
    clone_model = DatabaseCloneModel()
    clone_model.source_instance_name = "source"
    clone_model.destination_instance_name = "dest"
    clone_model.point_in_time = datetime(2026, 7, 8, 14, 30, tzinfo=UTC)

    response = Mock()
    response.json.return_value = {}
    response.raise_for_status.return_value = None

    with (
        patch(
            "services.database_clone_service.requests.Session.post",
            return_value=response,
        ),
        pytest.raises(ValueError, match="no operation name"),
    ):
        clone_service.create_clone(clone_model)


def test_delete_clone_returns_operation_name(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.status_code = 200
    response.text = ""
    response.raise_for_status.return_value = None
    response.json.return_value = {"name": "op-delete"}

    with patch(
        "services.database_clone_service.requests.Session.delete", return_value=response
    ) as mock_delete:
        operation = clone_service.delete_clone("clone-instance")

    assert operation == "op-delete"
    assert mock_delete.call_args.kwargs["timeout"] == (5.0, 30.0)


def test_delete_clone_handles_deletion_protection(
    clone_service: DatabaseCloneService,
) -> None:
    protected_delete = Mock()
    protected_delete.status_code = 400
    protected_delete.text = "Instance is protected"
    protected_delete.raise_for_status.return_value = None

    successful_delete = Mock()
    successful_delete.status_code = 200
    successful_delete.text = ""
    successful_delete.raise_for_status.return_value = None
    successful_delete.json.return_value = {"name": "op-delete"}

    with (
        patch(
            "services.database_clone_service.requests.Session.delete",
            side_effect=[protected_delete, successful_delete],
        ) as mock_delete,
        patch(
            "services.database_clone_service.requests.Session.patch",
        ) as mock_patch,
        patch.object(clone_service, "wait_for_operation") as mock_wait,
    ):
        patch_response = Mock()
        patch_response.status_code = 200
        patch_response.text = ""
        patch_response.raise_for_status.return_value = None
        patch_response.json.return_value = {"name": "op-disable-protection"}
        mock_patch.return_value = patch_response

        operation = clone_service.delete_clone("clone-instance")

    assert operation == "op-delete"
    expected_calls = 2
    assert mock_delete.call_count == expected_calls
    mock_wait.assert_called_once_with("op-disable-protection", timeout_seconds=300)


def test_disable_deletion_protection_waits_for_patch_operation(
    clone_service: DatabaseCloneService,
) -> None:
    patch_response = Mock()
    patch_response.status_code = 200
    patch_response.raise_for_status.return_value = None
    patch_response.json.return_value = {"name": "op-disable-protection"}

    with (
        patch(
            "services.database_clone_service.requests.Session.patch",
            return_value=patch_response,
        ) as mock_patch,
        patch.object(clone_service, "wait_for_operation") as mock_wait,
    ):
        clone_service.disable_deletion_protection("clone-instance")

    assert mock_patch.call_args.kwargs["json"] == {
        "settings": {"deletionProtectionEnabled": False}
    }
    mock_wait.assert_called_once_with("op-disable-protection", timeout_seconds=300)


def test_delete_clone_retries_patch_when_instance_stopped(
    clone_service: DatabaseCloneService,
) -> None:
    protected_delete = Mock()
    protected_delete.status_code = 400
    protected_delete.text = "protected"
    protected_delete.raise_for_status.return_value = None

    successful_delete = Mock()
    successful_delete.status_code = 200
    successful_delete.text = ""
    successful_delete.raise_for_status.return_value = None
    successful_delete.json.return_value = {"name": "op-delete"}

    first_patch = Mock()
    first_patch.status_code = 400
    first_patch.text = "instance is stopped"
    first_patch.raise_for_status.return_value = None

    second_patch = Mock()
    second_patch.status_code = 200
    second_patch.text = ""
    second_patch.raise_for_status.return_value = None
    second_patch.json.return_value = {"name": "op-patch"}

    with (
        patch(
            "services.database_clone_service.requests.Session.delete",
            side_effect=[protected_delete, successful_delete],
        ),
        patch(
            "services.database_clone_service.requests.Session.patch",
            side_effect=[first_patch, second_patch],
        ) as mock_patch,
        patch.object(clone_service, "wait_for_operation") as mock_wait,
    ):
        clone_service.delete_clone("clone-instance")

    expected_calls = 2
    assert mock_patch.call_count == expected_calls
    mock_wait.assert_called_once_with("op-patch", timeout_seconds=300)


def test_delete_clone_raises_when_operation_name_missing(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.status_code = 200
    response.text = ""
    response.raise_for_status.return_value = None
    response.json.return_value = {}

    with (
        patch(
            "services.database_clone_service.requests.Session.delete",
            return_value=response,
        ),
        pytest.raises(ValueError, match="no operation name"),
    ):
        clone_service.delete_clone("clone-instance")


def test_get_instance_returns_payload(clone_service: DatabaseCloneService) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"name": "i1", "connectionName": "proj:reg:i1"}

    with patch(
        "services.database_clone_service.requests.Session.get", return_value=response
    ) as mock_get:
        instance = clone_service.get_instance("i1")

    assert instance["name"] == "i1"
    assert mock_get.call_args.kwargs["timeout"] == (5.0, 30.0)


def test_instance_exists_returns_false_on_404(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.status_code = 404

    with patch(
        "services.database_clone_service.requests.Session.get", return_value=response
    ) as mock_get:
        exists = clone_service.instance_exists("missing")

    assert exists is False
    assert mock_get.call_args.kwargs["timeout"] == (5.0, 30.0)


def test_instance_exists_returns_true_for_existing_instance(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch(
        "services.database_clone_service.requests.Session.get", return_value=response
    ):
        exists = clone_service.instance_exists("exists")

    assert exists is True


def test_wait_for_operation_returns_when_done(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"status": "DONE", "name": "op1"}

    with patch(
        "services.database_clone_service.requests.Session.get", return_value=response
    ) as mock_get:
        operation = clone_service.wait_for_operation("op1", timeout_seconds=30)

    assert operation["status"] == "DONE"
    assert mock_get.call_args.kwargs["timeout"] == (5.0, 30.0)


def test_clone_service_supports_custom_http_timeouts(
    authorisation_service: Mock,
) -> None:
    clone_service = DatabaseCloneService(
        authorisation_service=authorisation_service,
        project_id="proj",
        http_connect_timeout_seconds=3.0,
        http_read_timeout_seconds=45.0,
    )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"name": "i1", "connectionName": "proj:reg:i1"}

    with patch(
        "services.database_clone_service.requests.Session.get", return_value=response
    ) as mock_get:
        clone_service.get_instance("i1")

    assert mock_get.call_args.kwargs["timeout"] == (3.0, 45.0)


def test_wait_for_operation_raises_for_operation_error(
    clone_service: DatabaseCloneService,
) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"status": "DONE", "error": {"message": "boom"}}

    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            return_value=response,
        ),
        pytest.raises(RuntimeError, match="operation failed"),
    ):
        clone_service.wait_for_operation("op1", timeout_seconds=30)


def test_wait_for_operation_times_out(clone_service: DatabaseCloneService) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"status": "RUNNING"}

    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            return_value=response,
        ),
        patch(
            "services.database_clone_service.time.monotonic",
            side_effect=[0.0, 0.0, 10.0, 10.0],
        ),
        patch("services.database_clone_service.time.sleep") as mock_sleep,
        pytest.raises(TimeoutError, match="Timed out"),
    ):
        clone_service.wait_for_operation(
            "op1", timeout_seconds=5, poll_interval_seconds=1
        )

    mock_sleep.assert_not_called()


def test_wait_for_operation_polls_until_done(
    clone_service: DatabaseCloneService,
) -> None:
    running_response = Mock()
    running_response.raise_for_status.return_value = None
    running_response.json.return_value = {"status": "RUNNING"}

    done_response = Mock()
    done_response.raise_for_status.return_value = None
    done_response.json.return_value = {"status": "DONE", "name": "op1"}

    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            side_effect=[running_response, done_response],
        ),
        patch(
            "services.database_clone_service.time.monotonic",
            side_effect=[0.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
        ),
        patch("services.database_clone_service.time.sleep") as mock_sleep,
    ):
        operation = clone_service.wait_for_operation(
            "op1", timeout_seconds=10, poll_interval_seconds=2
        )

    assert operation["status"] == "DONE"
    mock_sleep.assert_called_once_with(2)


def test_wait_for_operation_retries_once_when_unauthorized(
    clone_service: DatabaseCloneService,
) -> None:
    unauthorized_response = Mock()
    unauthorized_response.status_code = 401

    done_response = Mock()
    done_response.status_code = 200
    done_response.raise_for_status.return_value = None
    done_response.json.return_value = {"status": "DONE", "name": "op1"}

    with patch(
        "services.database_clone_service.requests.Session.get",
        side_effect=[unauthorized_response, done_response],
    ) as mock_get:
        operation = clone_service.wait_for_operation("op1", timeout_seconds=30)

    assert operation["status"] == "DONE"
    expected_get_calls = 2
    assert mock_get.call_count == expected_get_calls


def test_wait_for_operation_retries_three_transient_connection_failures(
    clone_service: DatabaseCloneService,
) -> None:
    done_response = Mock()
    done_response.status_code = 200
    done_response.raise_for_status.return_value = None
    done_response.json.return_value = {"status": "DONE", "name": "op1"}

    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            side_effect=[
                requests.ConnectionError("connection failed"),
                requests.Timeout("request timed out"),
                requests.ConnectionError("TLS connection closed"),
                done_response,
            ],
        ) as mock_get,
        patch(
            "services.database_clone_service.random.uniform",
            side_effect=[0.5, 1.5, 3.5],
        ),
        patch("services.database_clone_service.time.sleep") as mock_sleep,
    ):
        operation = clone_service.wait_for_operation("op1", timeout_seconds=90)

    assert operation["status"] == "DONE"
    assert mock_get.call_count == _EXPECTED_TRANSIENT_REQUEST_CALLS
    assert mock_sleep.call_args_list == [call(0.5), call(1.5), call(3.5)]


def test_transient_connection_failure_replaces_session(
    clone_service: DatabaseCloneService,
) -> None:
    failed_session = Mock()
    failed_session.get.side_effect = requests.ConnectionError("TLS connection closed")
    replacement_session = Mock()
    replacement_session.get.return_value.status_code = 200
    replacement_session.get.return_value.raise_for_status.return_value = None
    replacement_session.get.return_value.json.return_value = {
        "status": "DONE",
        "name": "op1",
    }
    clone_service._session = failed_session

    with (
        patch.object(
            clone_service,
            "_DatabaseCloneService__create_session",
            return_value=replacement_session,
        ),
        patch("services.database_clone_service.random.uniform", return_value=0.5),
        patch("services.database_clone_service.time.sleep"),
    ):
        clone_service.wait_for_operation("op1", timeout_seconds=30)

    failed_session.close.assert_called_once()
    assert replacement_session.get.call_count == _EXPECTED_REPLACEMENT_SESSION_CALLS


def test_wait_for_operation_retries_transient_http_status(
    clone_service: DatabaseCloneService,
) -> None:
    unavailable_response = Mock()
    unavailable_response.status_code = 503

    done_response = Mock()
    done_response.status_code = 200
    done_response.raise_for_status.return_value = None
    done_response.json.return_value = {"status": "DONE", "name": "op1"}

    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            side_effect=[unavailable_response, done_response],
        ) as mock_get,
        patch(
            "services.database_clone_service.random.uniform", return_value=0.5
        ),
        patch("services.database_clone_service.time.sleep") as mock_sleep,
    ):
        operation = clone_service.wait_for_operation("op1", timeout_seconds=30)

    assert operation["status"] == "DONE"
    assert mock_get.call_count == _EXPECTED_HTTP_STATUS_RETRY_CALLS
    mock_sleep.assert_called_once_with(0.5)


def test_wait_for_operation_raises_after_three_transient_retries(
    clone_service: DatabaseCloneService,
) -> None:
    with (
        patch(
            "services.database_clone_service.requests.Session.get",
            side_effect=requests.Timeout("request timed out"),
        ) as mock_get,
        patch(
            "services.database_clone_service.random.uniform",
            side_effect=[0.5, 1.5, 3.5],
        ),
        patch("services.database_clone_service.time.sleep") as mock_sleep,
        pytest.raises(requests.Timeout, match="request timed out"),
    ):
        clone_service.wait_for_operation("op1", timeout_seconds=90)

    assert mock_get.call_count == _EXPECTED_TRANSIENT_REQUEST_CALLS
    assert mock_sleep.call_args_list == [call(0.5), call(1.5), call(3.5)]


def test_create_clone_request_body_normalizes_to_utc_z_suffix() -> None:
    clone_model = DatabaseCloneModel()
    clone_model.source_instance_name = "source"
    clone_model.destination_instance_name = "dest"
    clone_model.point_in_time = datetime(2026, 7, 8, 14, 30, 0)

    body = cast(
        Any, DatabaseCloneService
    )._DatabaseCloneService__create_clone_request_body(clone_model)

    assert body["cloneContext"]["destinationInstanceName"] == "dest"
    assert body["cloneContext"]["pointInTime"].endswith("Z")


def test_instance_api_url_normalizes_connection_name(
    clone_service: DatabaseCloneService,
) -> None:
    url = cast(Any, clone_service)._DatabaseCloneService__get_instance_api_url(
        "proj:region:instance1"
    )

    assert url.endswith("/projects/proj/instances/instance1")


def test_operation_api_url_uses_project(clone_service: DatabaseCloneService) -> None:
    url = cast(Any, clone_service)._DatabaseCloneService__get_operation_api_url("op-1")

    assert url.endswith("/projects/proj/operations/op-1")


def test_headers_include_bearer_token(clone_service: DatabaseCloneService) -> None:
    headers = cast(
        Any, clone_service
    )._DatabaseCloneService__create_authorisation_headers()

    assert headers == {
        "Authorization": "Bearer token-123",
        "Content-Type": "application/json",
    }
