from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import Mock, call, patch

import pytest
import requests

from services.pitr_orchestrator_service import (
    PitrOrchestratorService,
    PitrRequest,
    build_clone_instance_name,
)

_CLOUD_SQL_MAX_NAME_LENGTH = 98


@pytest.fixture
def clone_service() -> Mock:
    service = Mock()
    service.instance_exists.return_value = False
    service.create_clone.return_value = "clone-op"
    service.get_instance.side_effect = [
        {"name": "source"},
        {"name": "destination"},
        {"connectionName": "proj:reg:clone-conn"},
    ]
    service.delete_clone.return_value = "delete-op"
    return service


@pytest.fixture
def restore_service() -> Mock:
    return Mock()


@pytest.fixture
def pitr_request() -> PitrRequest:
    return PitrRequest(
        request_id="request-1",
        questionnaire_name="LMS2601_KX2",
        timestamp=datetime(2026, 7, 8, 13, 30, 0, tzinfo=UTC),
        source_instance_name="proj:reg:source",
        destination_instance_name="proj:reg:dest",
        clone_instance_name="pitr-lms2601-kx2-20260708133000",
        operation_timeout_seconds=120,
        operation_poll_seconds=2,
    )


def test_restore_questionnaire_from_point_in_time_happy_path(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    clone_service.get_instance.assert_has_calls(
        [
            call(pitr_request.source_instance_name),
            call(pitr_request.destination_instance_name),
        ]
    )
    clone_service.create_clone.assert_called_once()
    clone_service.wait_for_operation.assert_has_calls(
        [
            call("clone-op", timeout_seconds=120, poll_interval_seconds=2),
            call("delete-op", timeout_seconds=120, poll_interval_seconds=2),
        ]
    )
    restore_service.restore_questionnaire_tables.assert_called_once_with(
        "LMS2601_KX2",
        source_instance_name="proj:reg:clone-conn",
        destination_instance_name="proj:reg:dest",
    )


def test_deletion_protection_is_disabled_before_restore(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.get_instance.side_effect = [
        {"name": "source"},
        {"name": "destination"},
        {
            "connectionName": "proj:reg:clone-conn",
            "settings": {"deletionProtectionEnabled": True},
        },
    ]
    parent = Mock()
    parent.attach_mock(clone_service.disable_deletion_protection, "disable")
    parent.attach_mock(restore_service.restore_questionnaire_tables, "restore")

    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    assert parent.mock_calls[:2] == [
        call.disable(pitr_request.clone_instance_name),
        call.restore(
            "LMS2601_KX2",
            source_instance_name="proj:reg:clone-conn",
            destination_instance_name="proj:reg:dest",
        ),
    ]


def test_restore_continues_when_proactive_protection_disable_fails(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.get_instance.side_effect = [
        {"name": "source"},
        {"name": "destination"},
        {
            "connectionName": "proj:reg:clone-conn",
            "settings": {"deletionProtectionEnabled": True},
        },
    ]
    clone_service.disable_deletion_protection.side_effect = requests.ConnectionError(
        "connection failed"
    )
    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    restore_service.restore_questionnaire_tables.assert_called_once()


def test_existing_stale_clone_is_deleted_before_recreate(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.instance_exists.return_value = True
    clone_service.delete_clone.side_effect = ["stale-delete-op", "final-delete-op"]

    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    clone_service.wait_for_operation.assert_has_calls(
        [
            call("stale-delete-op", timeout_seconds=120, poll_interval_seconds=2),
            call("clone-op", timeout_seconds=120, poll_interval_seconds=2),
            call("final-delete-op", timeout_seconds=120, poll_interval_seconds=2),
        ]
    )


def test_fallback_clone_name_used_when_stale_clone_delete_fails(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.instance_exists.return_value = True
    clone_service.delete_clone.side_effect = [
        RuntimeError("cannot delete"),
        "delete-op",
    ]

    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    with patch(
        "services.pitr_orchestrator_service.time.time", return_value=1_725_000_000
    ):
        service.restore_questionnaire_from_point_in_time(pitr_request)

    clone_model_used = clone_service.create_clone.call_args.args[0]
    assert clone_model_used.destination_instance_name.endswith("-1725000000")


def test_restore_failure_is_reraised_even_if_clone_cleanup_also_fails(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    restore_service.restore_questionnaire_tables.side_effect = RuntimeError(
        "restore failed"
    )
    clone_service.delete_clone.side_effect = RuntimeError("cleanup failed")

    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    with pytest.raises(RuntimeError, match="restore failed"):
        service.restore_questionnaire_from_point_in_time(pitr_request)


def test_cleanup_failure_does_not_fail_a_successful_restore(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.delete_clone.side_effect = RuntimeError("cleanup failed")
    clone_service.instance_exists.side_effect = [False, True, True, True, True, True]

    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    clone_service.delete_clone.assert_called_once()


def test_cleanup_uses_request_retry_layer_when_clone_still_exists(
    clone_service: Mock,
    restore_service: Mock,
    pitr_request: PitrRequest,
) -> None:
    clone_service.instance_exists.side_effect = [False, True]
    clone_service.delete_clone.side_effect = requests.ConnectionError(
        "TLS connection closed"
    )
    service = PitrOrchestratorService(
        clone_service=clone_service, restore_service=restore_service
    )

    service.restore_questionnaire_from_point_in_time(pitr_request)

    clone_service.delete_clone.assert_called_once()


def test_retry_clone_name_is_truncated_to_cloud_sql_limit() -> None:
    base_name = "pitr-" + ("x" * 200)

    with patch("services.pitr_orchestrator_service.time.time", return_value=1234567890):
        retry_name = cast(
            Any, PitrOrchestratorService
        )._PitrOrchestratorService__build_retry_clone_name(base_name)

    assert len(retry_name) <= _CLOUD_SQL_MAX_NAME_LENGTH
    assert retry_name.endswith("-1234567890")


def test_build_clone_instance_name_normalizes_and_truncates() -> None:
    timestamp = datetime(2026, 7, 8, 13, 30, 0, tzinfo=UTC)
    long_questionnaire = "  LMS 2601 KX2 !!! " + ("ABC" * 50)
    short_questionnaire = "LMS2601_KX2"

    clone_name = build_clone_instance_name("pitr", long_questionnaire, timestamp)
    short_clone_name = build_clone_instance_name("pitr", short_questionnaire, timestamp)

    assert clone_name.startswith("pitr-lms-2601-kx2")
    assert len(clone_name) <= _CLOUD_SQL_MAX_NAME_LENGTH
    assert short_clone_name.endswith("20260708133000")
