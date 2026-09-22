from unittest.mock import Mock, patch

import pytest
import requests

from services.cloud_sql_admin_client import CloudSqlAdminClient


@pytest.fixture
def credentials() -> Mock:
    return Mock()


@pytest.fixture
def session() -> Mock:
    return Mock()


@pytest.fixture
def client(credentials: Mock, session: Mock) -> CloudSqlAdminClient:
    with patch(
        "services.cloud_sql_admin_client.AuthorizedSession", return_value=session
    ):
        return CloudSqlAdminClient(project_id="project-1", credentials=credentials)


def test_uses_adc_cloud_platform_scope_when_credentials_not_supplied() -> None:
    credentials = Mock()

    with (
        patch(
            "services.cloud_sql_admin_client.google.auth.default",
            return_value=(credentials, "project-1"),
        ) as mock_default,
        patch("services.cloud_sql_admin_client.AuthorizedSession") as mock_session,
    ):
        CloudSqlAdminClient(project_id="project-1")

    mock_default.assert_called_once_with(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    mock_session.assert_called_once_with(credentials)


def test_request_uses_configured_timeout(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    session.get.return_value.status_code = 200

    client.request("get", "https://sqladmin.googleapis.com/test")

    session.get.assert_called_once_with(
        url="https://sqladmin.googleapis.com/test",
        timeout=(5.0, 30.0),
    )


def test_request_retries_transient_http_status(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    unavailable = Mock(status_code=503)
    success = Mock(status_code=200)
    session.get.side_effect = [unavailable, success]

    with (
        patch("services.cloud_sql_admin_client.random.uniform", return_value=0.5),
        patch("services.cloud_sql_admin_client.time.sleep") as mock_sleep,
    ):
        response = client.request("get", "https://sqladmin.googleapis.com/test")

    assert response is success
    mock_sleep.assert_called_once_with(0.5)


def test_request_replaces_session_after_connection_failure(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    session.get.side_effect = requests.ConnectionError("connection failed")
    replacement_session = Mock()
    replacement_session.get.return_value.status_code = 200

    with (
        patch.object(
            client,
            "_CloudSqlAdminClient__create_session",
            return_value=replacement_session,
        ),
        patch("services.cloud_sql_admin_client.random.uniform", return_value=0.5),
        patch("services.cloud_sql_admin_client.time.sleep"),
    ):
        client.request("get", "https://sqladmin.googleapis.com/test")

    session.close.assert_called_once()
    replacement_session.get.assert_called_once()


def test_wait_for_operation_polls_until_done(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    running = Mock(status_code=200, ok=True)
    running.json.return_value = {"status": "RUNNING"}
    done = Mock(status_code=200, ok=True)
    done.json.return_value = {"status": "DONE", "name": "op-1"}
    session.get.side_effect = [running, done]

    with patch("services.cloud_sql_admin_client.time.sleep") as mock_sleep:
        operation = client.wait_for_operation("op-1", 30, 2)

    assert operation["status"] == "DONE"
    mock_sleep.assert_called_once_with(2)


def test_wait_for_operation_raises_operation_error(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {
        "status": "DONE",
        "error": {"message": "failed"},
    }
    session.get.return_value = response

    with pytest.raises(RuntimeError, match="Cloud SQL operation failed"):
        client.wait_for_operation("op-1", 30, 2)


def test_wait_for_operation_times_out(
    client: CloudSqlAdminClient, session: Mock
) -> None:
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"status": "RUNNING"}
    session.get.return_value = response

    with (
        patch(
            "services.cloud_sql_admin_client.time.monotonic",
            side_effect=[0.0, 0.0, 2.0, 2.0],
        ),
        pytest.raises(TimeoutError, match="Timed out"),
    ):
        client.wait_for_operation("op-1", 1, 1)


def test_builds_instance_and_operation_urls(client: CloudSqlAdminClient) -> None:
    assert client.instance_url("project:region:instance-1").endswith(
        "/projects/project-1/instances/instance-1"
    )
    assert client.operation_url("op-1").endswith(
        "/projects/project-1/operations/op-1"
    )