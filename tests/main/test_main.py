import http
import importlib
import sys
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import flask


def _fake_parse_timestamp(_value: str) -> datetime:
    return datetime(2026, 7, 8, 13, 30, 0, tzinfo=UTC)


class FakeSettings:
    PROJECT_ID = "project-1"
    DEST_INSTANCE_NAME = "project-1:region:dest"
    RESTORE_SOURCE_INSTANCE_NAME = "project-1:region:source"
    RESTORE_GCS_BUCKET = "ons-blaise-v2-dev-backups"
    RESTORE_GCS_PREFIX = "questionnaire-pitr"
    CLONE_NAME_PREFIX = "pitr"
    CLONE_OPERATION_POLL_SECONDS = 5
    CLONE_OPERATION_TIMEOUT_SECONDS = 1800
    CLONE_HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
    CLONE_HTTP_READ_TIMEOUT_SECONDS = 30.0


def _load_main_module() -> ModuleType:
    fake_config = SimpleNamespace(
        Settings=FakeSettings,
        parse_uk_local_timestamp=_fake_parse_timestamp,
    )

    sys.modules["config"] = cast(ModuleType, fake_config)
    sys.modules.pop("main", None)

    return importlib.import_module("main")


def test_json_error_includes_optional_fields() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with app.app_context():
        response, status = main_module._json_error(
            code="code-1",
            message="message-1",
            status=400,
            details="details-1",
            request_id="request-1",
        )
        payload = response.get_json()

    assert status == http.HTTPStatus.BAD_REQUEST
    assert payload == {
        "error": {
            "code": "code-1",
            "message": "message-1",
            "details": "details-1",
            "request_id": "request-1",
        }
    }


def test_json_error_omits_optional_fields_when_not_provided() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with app.app_context():
        response, _ = main_module._json_error(
            code="code-1",
            message="message-1",
            status=400,
        )
        payload = response.get_json()

    assert payload == {"error": {"code": "code-1", "message": "message-1"}}


def test_run_restore_builds_request_and_calls_orchestrator() -> None:
    main_module = _load_main_module()
    parsed_ts = datetime(2026, 7, 8, 14, 30, 0, tzinfo=UTC)
    mock_orchestrator = Mock()

    with (
        patch.object(main_module, "parse_uk_local_timestamp", return_value=parsed_ts),
        patch.object(
            main_module, "build_clone_instance_name", return_value="clone-name"
        ),
        patch.object(
            main_module, "_get_orchestrator", return_value=mock_orchestrator
        ) as mock_get_orchestrator,
    ):
        main_module.run_restore(
            "LMS2601_KX2", "2026-07-08 14:30:00", database_name="blaise"
        )

    request = mock_orchestrator.restore_table_from_point_in_time.call_args.args[0]
    mock_get_orchestrator.assert_called_once_with("blaise")
    assert request.table_name == "LMS2601_KX2"
    assert request.timestamp == parsed_ts
    assert request.source_instance_name == FakeSettings.RESTORE_SOURCE_INSTANCE_NAME
    assert request.destination_instance_name == FakeSettings.DEST_INSTANCE_NAME
    assert request.clone_instance_name == "clone-name"
    assert (
        request.operation_timeout_seconds
        == FakeSettings.CLONE_OPERATION_TIMEOUT_SECONDS
    )
    assert request.operation_poll_seconds == FakeSettings.CLONE_OPERATION_POLL_SECONDS


def test_restore_table_from_point_in_time_returns_400_for_missing_fields() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with app.test_request_context(
        json={
            "table_name": "LMS2601_KX2",
            "timestamp": "2026-07-08 14:30:00",
        }
    ):
        response, status = main_module.restore_table_from_point_in_time(flask.request)
        payload = response.get_json()

    assert status == http.HTTPStatus.BAD_REQUEST
    assert payload["error"]["code"] == "missing_parameters"
    assert payload["error"]["details"] == (
        "Expected table_name, timestamp, and database_name."
    )


def test_restore_table_from_point_in_time_rejects_legacy_questionnaire_name() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with app.test_request_context(
        json={
            "questionnaire_name": "LMS2601_KX2",
            "timestamp": "2026-07-08 14:30:00",
            "database_name": "blaise",
        }
    ):
        response, status = main_module.restore_table_from_point_in_time(flask.request)
        payload = response.get_json()

    assert status == http.HTTPStatus.BAD_REQUEST
    assert payload["error"]["code"] == "missing_parameters"


def test_restore_table_from_point_in_time_returns_400_for_bad_timestamp() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with (
        app.test_request_context(
            json={
                "table_name": "LMS2601_KX2",
                "timestamp": "bad-ts",
                "database_name": "blaise",
            }
        ),
        patch.object(
            main_module, "run_restore", side_effect=ValueError("bad timestamp")
        ),
        patch("main.uuid.uuid4", return_value="request-id-1"),
    ):
        response, status = main_module.restore_table_from_point_in_time(flask.request)
        payload = response.get_json()

    assert status == http.HTTPStatus.BAD_REQUEST
    assert payload["error"]["code"] == "invalid_timestamp"
    assert payload["error"]["request_id"] == "request-id-1"


def test_restore_table_from_point_in_time_returns_500_for_unexpected_error() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with (
        app.test_request_context(
            json={
                "table_name": "LMS2601_KX2",
                "timestamp": "2026-07-08 14:30:00",
                "database_name": "blaise",
            }
        ),
        patch.object(main_module, "run_restore", side_effect=RuntimeError("boom")),
        patch("main.uuid.uuid4", return_value="request-id-2"),
    ):
        response, status = main_module.restore_table_from_point_in_time(flask.request)
        payload = response.get_json()

    assert status == http.HTTPStatus.INTERNAL_SERVER_ERROR
    assert payload["error"]["code"] == "restore_failed"
    assert payload["error"]["request_id"] == "request-id-2"


def test_restore_table_from_point_in_time_returns_200_on_success() -> None:
    main_module = _load_main_module()
    app = flask.Flask(__name__)

    with (
        app.test_request_context(
            json={
                "table_name": "LMS2601_KX2",
                "timestamp": "2026-07-08 14:30:00",
                "database_name": "blaise",
            }
        ),
        patch.object(main_module, "run_restore", return_value=None),
        patch("main.uuid.uuid4", return_value="request-id-3"),
    ):
        body, status = main_module.restore_table_from_point_in_time(flask.request)
        main_module.run_restore.assert_called_once_with(
            "LMS2601_KX2",
            "2026-07-08 14:30:00",
            database_name="blaise",
            request_id="request-id-3",
        )

    assert status == http.HTTPStatus.OK
    assert body == "OK"
