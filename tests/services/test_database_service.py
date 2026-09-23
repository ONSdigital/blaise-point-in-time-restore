from typing import Any, cast
from unittest.mock import Mock, call, patch

import pytest

from services.database_service import DatabaseService

_EXPECTED_REQUEST_COUNT = 3
_EXPECTED_IAM_CALL_COUNT = 4
_IAM_POLICY_VERSION = 3


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
            export_prefix="database-table-pitr",
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
    assert export_uri.startswith("gs://ons-blaise-v2-dev-backups/database-table-pitr/")
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


def test_copy_table_data_does_not_retry_bucket_permission_failure() -> None:
    service, client = _build_service()
    permission_response = Mock(status_code=412, ok=False)
    permission_response.json.return_value = {
        "error": {
            "message": (
                "The service account does not have the required permissions "
                "for the bucket."
            ),
            "errors": [{"reason": "notAuthorized"}],
        }
    }
    client.request.return_value = permission_response
    client.raise_for_status_with_details.side_effect = PermissionError(
        "bucket permission denied"
    )

    with (
        patch("services.database_service.time.sleep") as mock_sleep,
        pytest.raises(PermissionError, match="bucket permission denied"),
    ):
        service.copy_table_data("TABLE_DML", "source", "dest")

    client.request.assert_called_once()
    mock_sleep.assert_not_called()


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


def test_ensure_bucket_permissions_adds_runtime_instance_accounts() -> None:
    service, client = _build_service()
    source_response = Mock(status_code=200, ok=True)
    source_response.json.return_value = {
        "serviceAccountEmailAddress": (
            "source@gcp-sa-cloud-sql.iam.gserviceaccount.com"
        )
    }
    destination_response = Mock(status_code=200, ok=True)
    destination_response.json.return_value = {
        "serviceAccountEmailAddress": (
            "destination@gcp-sa-cloud-sql.iam.gserviceaccount.com"
        )
    }
    policy_response = Mock(status_code=200, ok=True)
    policy_response.json.return_value = {
        "bindings": [],
        "etag": "etag-1",
        "version": 3,
    }
    set_policy_response = Mock(status_code=200, ok=True)
    client.request.side_effect = [
        source_response,
        destination_response,
        policy_response,
        set_policy_response,
        policy_response,
        set_policy_response,
    ]

    service.ensure_bucket_permissions_for_instances("clone", "destination")

    iam_calls = [
        call
        for call in client.request.call_args_list
        if call.kwargs["url"].endswith("/b/ons-blaise-v2-dev-backups/iam")
    ]
    assert len(iam_calls) == _EXPECTED_IAM_CALL_COUNT
    assert iam_calls[0].kwargs["params"] == {"optionsRequestedPolicyVersion": 3}
    set_policy_payloads = [
        call.kwargs["json"] for call in iam_calls if "json" in call.kwargs
    ]
    assert all(
        payload["version"] == _IAM_POLICY_VERSION for payload in set_policy_payloads
    )
    assert all(payload["etag"] == "etag-1" for payload in set_policy_payloads)
    policy_members = {
        member
        for payload in set_policy_payloads
        for binding in payload["bindings"]
        for member in binding["members"]
    }
    assert policy_members == {
        "serviceAccount:source@gcp-sa-cloud-sql.iam.gserviceaccount.com",
        "serviceAccount:destination@gcp-sa-cloud-sql.iam.gserviceaccount.com",
    }


def test_ensure_bucket_permissions_does_not_duplicate_unconditional_member() -> None:
    service, client = _build_service()
    instance_response = Mock(status_code=200, ok=True)
    instance_response.json.return_value = {
        "serviceAccountEmailAddress": "sql@gcp-sa-cloud-sql.iam.gserviceaccount.com"
    }
    policy_response = Mock(status_code=200, ok=True)
    policy_response.json.return_value = {
        "bindings": [
            {
                "role": "roles/storage.objectAdmin",
                "members": [
                    "serviceAccount:sql@gcp-sa-cloud-sql.iam.gserviceaccount.com"
                ],
            }
        ],
        "version": 3,
    }
    client.request.side_effect = [instance_response, instance_response, policy_response]

    service.ensure_bucket_permissions_for_instances("clone", "destination")

    assert client.request.call_count == _EXPECTED_REQUEST_COUNT
