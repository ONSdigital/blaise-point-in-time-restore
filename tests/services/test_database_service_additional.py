from typing import Any, cast
from unittest.mock import Mock, call, patch

import pytest

from services.database_service import DatabaseService

_EXPECTED_REQUEST_COUNT = 3


def _instance_url(name: str) -> str:
    return (
        "https://sqladmin.googleapis.com/sql/v1beta4/projects/proj/instances/"
        f"{name.rsplit(':', maxsplit=1)[-1]}"
    )


def _normalize_instance_name(name: str) -> str:
    return name.rsplit(":", maxsplit=1)[-1]


def _build_service() -> tuple[DatabaseService, Mock]:
    client = Mock()
    client.instance_url.side_effect = _instance_url
    client.normalize_instance_name.side_effect = _normalize_instance_name
    return (
        DatabaseService(
            cloud_sql_client=client,
            database_name="blaise",
            export_bucket_name="ons-blaise-v2-dev-backups",
            export_prefix="questionnaire-pitr",
            operation_timeout_seconds=60,
            operation_poll_seconds=1,
        ),
        client,
    )


def _operation_response(operation_name: str) -> Mock:
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"name": operation_name}
    return response


def test_copy_table_data_exports_then_imports_using_same_gcs_uri() -> None:
    service, client = _build_service()
    client.request.side_effect = [
        _operation_response("export-op"),
        _operation_response("import-op"),
    ]

    service.copy_table_data(
        table_name="LMS2601_KX2_Dml",
        source_instance_name="proj:region:clone",
        destination_instance_name="proj:region:dest",
    )

    first_call, second_call = client.request.call_args_list
    assert first_call.kwargs["url"].endswith("/instances/clone/export")
    assert second_call.kwargs["url"].endswith("/instances/dest/import")
    export_uri = first_call.kwargs["json"]["exportContext"]["uri"]
    assert export_uri.startswith(
        "gs://ons-blaise-v2-dev-backups/questionnaire-pitr/"
    )
    assert second_call.kwargs["json"]["importContext"]["uri"] == export_uri
    assert client.wait_for_operation.call_args_list == [
        call(
            operation_name="export-op",
            timeout_seconds=60,
            poll_interval_seconds=1,
        ),
        call(
            operation_name="import-op",
            timeout_seconds=60,
            poll_interval_seconds=1,
        ),
    ]


def test_copy_table_data_raises_when_export_operation_name_missing() -> None:
    service, client = _build_service()
    client.request.return_value = _operation_response("")

    with pytest.raises(ValueError, match="export succeeded but no operation name"):
        service.copy_table_data("TABLE_DML", "source", "dest")


def test_copy_table_data_retries_export_when_precondition_fails() -> None:
    service, client = _build_service()
    client.request.side_effect = [
        Mock(status_code=412, ok=False),
        _operation_response("export-op"),
        _operation_response("import-op"),
    ]

    with patch("services.database_service.time.sleep") as mock_sleep:
        service.copy_table_data("TABLE_DML", "source", "dest")

    assert client.request.call_count == _EXPECTED_REQUEST_COUNT
    mock_sleep.assert_called_once_with(5)


def test_wait_for_operation_uses_configured_values() -> None:
    service, client = _build_service()
    client.wait_for_operation.return_value = {"status": "DONE"}

    result = cast(Any, service)._DatabaseService__wait_for_operation("op-1")

    assert result == {"status": "DONE"}
    client.wait_for_operation.assert_called_once_with(
        operation_name="op-1",
        timeout_seconds=60,
        poll_interval_seconds=1,
    )


def test_create_export_request_body_contains_expected_table_and_database() -> None:
    service, _ = _build_service()

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