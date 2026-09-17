import importlib
import sys
import types
from unittest.mock import patch

import pytest

_EXPECTED_HOUR = 14
_EXPECTED_POLL_SECONDS = 5
_EXPECTED_TIMEOUT_SECONDS = 1800
_EXPECTED_CONNECT_TIMEOUT_SECONDS = 5.0
_EXPECTED_READ_TIMEOUT_SECONDS = 30.0


def _load_config_module() -> types.ModuleType:
    sys.modules.pop("config", None)
    return importlib.import_module("config")


def test_parse_uk_local_timestamp_attaches_london_timezone() -> None:
    config_module = _load_config_module()
    parsed = config_module.parse_uk_local_timestamp("2026-07-08 14:30:00")

    assert parsed.tzinfo is not None
    assert str(parsed.tzinfo) == "Europe/London"


def test_parse_uk_local_timestamp_accepts_t_separator_and_preserves_aware() -> None:
    config_module = _load_config_module()
    parsed = config_module.parse_uk_local_timestamp("2026-07-08T14:30:00+00:00")

    assert parsed.tzinfo is not None
    assert parsed.hour == _EXPECTED_HOUR


def test_settings_reads_required_environment_variables() -> None:
    config_module = _load_config_module()
    environment = {
        "PROJECT_ID": "project-1",
        "DEST_INSTANCE_NAME": "project-1:region:blaise-dev-abc12345",
        "DEST_DB_NAME": "blaise",
        "RESTORE_GCS_BUCKET": "ons-blaise-v2-dev-backups",
    }

    with patch.dict("os.environ", environment, clear=True):
        settings = config_module.Settings

        assert settings.PROJECT_ID == environment["PROJECT_ID"]
        assert settings.DEST_INSTANCE_NAME == environment["DEST_INSTANCE_NAME"]
        assert settings.RESTORE_SOURCE_INSTANCE_NAME == settings.DEST_INSTANCE_NAME
        assert settings.DEST_DB_NAME == environment["DEST_DB_NAME"]
        assert settings.RESTORE_GCS_BUCKET == environment["RESTORE_GCS_BUCKET"]
        assert settings.RESTORE_GCS_PREFIX == "questionnaire-pitr"
        assert settings.CLONE_NAME_PREFIX == "pitr"
        assert settings.CLONE_OPERATION_POLL_SECONDS == _EXPECTED_POLL_SECONDS
        assert settings.CLONE_OPERATION_TIMEOUT_SECONDS == _EXPECTED_TIMEOUT_SECONDS
        assert (
            settings.CLONE_HTTP_CONNECT_TIMEOUT_SECONDS
            == _EXPECTED_CONNECT_TIMEOUT_SECONDS
        )
        assert (
            settings.CLONE_HTTP_READ_TIMEOUT_SECONDS == _EXPECTED_READ_TIMEOUT_SECONDS
        )


@pytest.mark.parametrize(
    "setting_name",
    [
        "PROJECT_ID",
        "DEST_INSTANCE_NAME",
        "DEST_DB_NAME",
        "RESTORE_GCS_BUCKET",
    ],
)
def test_settings_raises_for_missing_required_environment_variable(
    setting_name: str,
) -> None:
    config_module = _load_config_module()

    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(
            RuntimeError,
            match=f"Required environment variable {setting_name} is not configured",
        ),
    ):
        getattr(config_module.Settings, setting_name)


def test_settings_reads_environment_lazily() -> None:
    config_module = _load_config_module()

    with patch.dict("os.environ", {}, clear=True):
        assert config_module.Settings.RESTORE_GCS_PREFIX == "questionnaire-pitr"
