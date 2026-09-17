from typing import Any, cast
from unittest.mock import Mock, call, patch

import pytest
import requests

from services.database_service import DatabaseService

_EXPECTED_POST_CALLS = 2
_EXPECTED_RETRY_POST_CALLS = 3
_EXPECTED_TRANSIENT_REQUEST_CALLS = 4


def _build_service() -> DatabaseService:
    auth_service = Mock()
    auth_service.get_credentials_token.return_value = "token-123"
    return DatabaseService(
        authorisation_service=auth_service,
        project_id="proj",
        database_name="blaise",
        export_bucket_name="ons-blaise-v2-dev-backups",
        export_prefix="questionnaire-pitr",
        operation_timeout_seconds=60,
        operation_poll_seconds=1,
    )


def _response_with_operation(operation_name: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"name": operation_name}
    return response


def test_copy_table_data_exports_then_imports_using_same_gcs_uri() -> None:
    service = _build_service()

    with (
        patch(
            "services.database_service.requests.post",
            side_effect=[
                _response_with_operation("export-op"),
                _response_with_operation("import-op"),
            ],
        ) as mock_post,
        patch("services.database_service.requests.get") as mock_get,
    ):
        done_response = Mock()
        done_response.raise_for_status.return_value = None
        done_response.json.side_effect = [
            {"status": "DONE", "name": "export-op"},
            {"status": "DONE", "name": "import-op"},
        ]
        mock_get.return_value = done_response

        service.copy_table_data(
            table_name="LMS2601_KX2_DML",
            source_instance_name="proj:region:clone",
            destination_instance_name="proj:region:dest",
        )

    assert mock_post.call_count == _EXPECTED_POST_CALLS
    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]

    assert first_call.kwargs["url"].endswith("/projects/proj/instances/clone/export")
    assert second_call.kwargs["url"].endswith("/projects/proj/instances/dest/import")

    export_uri = first_call.kwargs["json"]["exportContext"]["uri"]
    assert export_uri.startswith("gs://ons-blaise-v2-dev-backups/questionnaire-pitr/")
    assert "lms2601_kx2_dml" in export_uri

    import_uri = second_call.kwargs["json"]["importContext"]["uri"]
    assert import_uri == export_uri


def test_copy_table_data_raises_when_export_operation_name_missing() -> None:
    service = _build_service()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {}

    with (
        patch("services.database_service.requests.post", return_value=response),
        pytest.raises(ValueError, match="export succeeded but no operation name"),
    ):
        service.copy_table_data("TABLE_DML", "proj:region:source", "proj:region:dest")


def test_copy_table_data_retries_export_when_precondition_fails() -> None:
    service = _build_service()

    precondition_response = Mock()
    precondition_response.status_code = 412
    precondition_response.ok = False
    precondition_response.text = "instance not ready"
    precondition_response.raise_for_status = Mock(side_effect=AssertionError)

    with (
        patch(
            "services.database_service.requests.post",
            side_effect=[
                precondition_response,
                _response_with_operation("export-op"),
                _response_with_operation("import-op"),
            ],
        ) as mock_post,
        patch("services.database_service.requests.get") as mock_get,
        patch("services.database_service.time.sleep") as mock_sleep,
    ):
        done_response = Mock()
        done_response.status_code = 200
        done_response.ok = True
        done_response.raise_for_status.return_value = None
        done_response.json.side_effect = [
            {"status": "DONE", "name": "export-op"},
            {"status": "DONE", "name": "import-op"},
        ]
        mock_get.return_value = done_response

        service.copy_table_data("TABLE_DML", "proj:region:source", "proj:region:dest")

    assert mock_post.call_count == _EXPECTED_RETRY_POST_CALLS
    mock_sleep.assert_called_once_with(5)


def test_wait_for_operation_raises_on_operation_error() -> None:
    service = _build_service()

    error_response = Mock()
    error_response.raise_for_status.return_value = None
    error_response.json.return_value = {
        "status": "DONE",
        "error": {"message": "failed"},
    }

    with (
        patch("services.database_service.requests.get", return_value=error_response),
        pytest.raises(RuntimeError, match="Cloud SQL operation failed"),
    ):
        cast(Any, service)._DatabaseService__wait_for_operation("op-1")


def test_wait_for_operation_times_out() -> None:
    auth_service = Mock()
    auth_service.get_credentials_token.return_value = "token-123"
    service = DatabaseService(
        authorisation_service=auth_service,
        project_id="proj",
        database_name="blaise",
        export_bucket_name="ons-blaise-v2-dev-backups",
        export_prefix="questionnaire-pitr",
        operation_timeout_seconds=1,
        operation_poll_seconds=1,
    )

    running_response = Mock()
    running_response.raise_for_status.return_value = None
    running_response.json.return_value = {"status": "RUNNING"}

    with (
        patch("services.database_service.requests.get", return_value=running_response),
        patch(
            "services.database_service.time.monotonic",
            side_effect=[0.0, 0.0, 2.0, 2.0],
        ),
        pytest.raises(TimeoutError, match="Timed out"),
    ):
        cast(Any, service)._DatabaseService__wait_for_operation("op-1")


def test_create_export_request_body_contains_expected_table_and_database() -> None:
    service = _build_service()

    body = cast(Any, service)._DatabaseService__create_export_request_body(
        "TABLE_DML", "gs://bucket/path/table.sql.gz"
    )

    assert body == {
        "exportContext": {
            "fileType": "SQL",
            "uri": "gs://bucket/path/table.sql.gz",
            "databases": ["blaise"],
            "sqlExportOptions": {
                "tables": ["TABLE_DML"],
                "schemaOnly": False,
            },
        }
    }


def test_request_with_authorisation_retry_retries_once_on_unauthorized() -> None:
    service = _build_service()
    unauthorized_response = Mock()
    unauthorized_response.status_code = 401

    success_response = Mock()
    success_response.status_code = 200

    with patch(
        "services.database_service.requests.get",
        side_effect=[unauthorized_response, success_response],
    ) as mock_get:
        response = cast(
            Any, service
        )._DatabaseService__request_with_authorisation_retry(
            "get",
            "https://sqladmin.googleapis.com/test",
        )

    assert response is success_response
    assert mock_get.call_count == _EXPECTED_POST_CALLS


def test_request_retries_three_transient_failures_before_success() -> None:
    service = _build_service()
    success_response = Mock()
    success_response.status_code = 200

    with (
        patch(
            "services.database_service.requests.get",
            side_effect=[
                requests.ConnectionError("connection failed"),
                requests.Timeout("request timed out"),
                requests.ConnectionError("TLS connection closed"),
                success_response,
            ],
        ) as mock_get,
        patch("services.database_service.time.sleep") as mock_sleep,
    ):
        response = cast(
            Any, service
        )._DatabaseService__request_with_authorisation_retry(
            "get",
            "https://sqladmin.googleapis.com/test",
        )

    assert response is success_response
    assert mock_get.call_count == _EXPECTED_TRANSIENT_REQUEST_CALLS
    assert mock_sleep.call_args_list == [call(20), call(20), call(20)]
