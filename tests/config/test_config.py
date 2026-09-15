import importlib
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

_EXPECTED_HOUR = 14
_EXPECTED_POLL_SECONDS = 5
_EXPECTED_TIMEOUT_SECONDS = 1800
_EXPECTED_CONNECT_TIMEOUT_SECONDS = 5.0
_EXPECTED_READ_TIMEOUT_SECONDS = 30.0


class FakeResponse:
    def __init__(
        self, status_code: int = 200, payload: dict[str, object] | None = None
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _load_config_module() -> types.ModuleType:
    sys.modules.pop("config", None)
    return importlib.import_module("config")


def _load_config_module_with_safe_defaults() -> types.ModuleType:
    def default_requests_get(
        url: str, headers: dict[str, str], timeout: int
    ) -> FakeResponse:
        _ = timeout
        if "/instances/" in url and url.endswith("/databases"):
            return FakeResponse(payload={"items": [{"name": "blaise"}]})

        if url.endswith("/instances"):
            return FakeResponse(
                payload={
                    "items": [
                        {
                            "name": "blaise-dev-abc12345",
                            "connectionName": "project-1:region:blaise-dev-abc12345",
                        }
                    ]
                }
            )

        return FakeResponse(payload={"items": []})

    with (
        patch("google.auth.default", return_value=(Mock(), "project-1")),
        patch("requests.get", side_effect=default_requests_get),
        patch(
            "google.cloud.secretmanager.SecretManagerServiceClient"
        ) as mock_secret_client,
    ):
        secret_client = Mock()
        secret_client.access_secret_version.return_value = SimpleNamespace(
            payload=SimpleNamespace(data=b"password")
        )
        mock_secret_client.return_value = secret_client
        return _load_config_module()


def test_parse_uk_local_timestamp_attaches_london_timezone() -> None:
    config_module = _load_config_module_with_safe_defaults()
    parsed = config_module.parse_uk_local_timestamp("2026-07-08 14:30:00")

    assert parsed.tzinfo is not None
    assert str(parsed.tzinfo) == "Europe/London"


def test_parse_uk_local_timestamp_accepts_t_separator_and_preserves_aware() -> None:
    config_module = _load_config_module_with_safe_defaults()
    parsed = config_module.parse_uk_local_timestamp("2026-07-08T14:30:00+00:00")

    assert parsed.tzinfo is not None
    assert parsed.hour == _EXPECTED_HOUR


def test_discover_project_id_from_google_auth() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with patch("config.google.auth.default", return_value=(Mock(), "project-auth")):
        project_id = config_module.discover_project_id()

    assert project_id == "project-auth"


def test_discover_project_id_from_gcloud_fallback() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch("config.google.auth.default", side_effect=RuntimeError("adc error")),
        patch(
            "config.subprocess.run",
            return_value=SimpleNamespace(stdout="project-gcloud\n"),
        ),
    ):
        project_id = config_module.discover_project_id()

    assert project_id == "project-gcloud"


def test_discover_project_id_exits_when_not_found() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch("config.google.auth.default", side_effect=RuntimeError("adc error")),
        patch(
            "config.subprocess.run", return_value=SimpleNamespace(stdout="(unset)\n")
        ),
        pytest.raises(SystemExit, match="Could not determine the active GCP project"),
    ):
        config_module.discover_project_id()


def test_discover_project_id_exits_when_gcloud_lookup_raises_exception() -> None:
    config_module = _load_config_module_with_safe_defaults()

    with (
        patch("config.google.auth.default", return_value=(Mock(), None)),
        patch("config.subprocess.run", side_effect=RuntimeError("gcloud failed")),
        pytest.raises(SystemExit, match="Could not determine the active GCP project"),
    ):
        config_module.discover_project_id()


def test_discover_access_token_from_google_auth() -> None:
    config_module = _load_config_module_with_safe_defaults()
    credentials = SimpleNamespace(token="token-from-auth")
    credentials.refresh = Mock()

    with patch("config.google.auth.default", return_value=(credentials, "project")):
        token = config_module._discover_access_token()

    assert token == "token-from-auth"


def test_discover_access_token_from_gcloud_fallback() -> None:
    config_module = _load_config_module_with_safe_defaults()
    credentials = SimpleNamespace(token="")
    credentials.refresh = Mock(side_effect=RuntimeError("adc error"))

    with (
        patch("config.google.auth.default", return_value=(credentials, "project")),
        patch(
            "config.subprocess.run",
            return_value=SimpleNamespace(stdout="token-gcloud\n"),
        ),
    ):
        token = config_module._discover_access_token()

    assert token == "token-gcloud"


def test_discover_access_token_exits_when_unavailable() -> None:
    config_module = _load_config_module_with_safe_defaults()
    credentials = SimpleNamespace(token="")
    credentials.refresh = Mock(side_effect=RuntimeError("adc error"))

    with (
        patch("config.google.auth.default", return_value=(credentials, "project")),
        patch("config.subprocess.run", side_effect=RuntimeError("gcloud error")),
        pytest.raises(SystemExit, match="Could not acquire GCP access token"),
    ):
        config_module._discover_access_token()


def test_discover_destination_instance_name_from_api() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={
            "items": [
                {
                    "name": "blaise-dev-abc12345",
                    "connectionName": "project-1:region:blaise-dev-abc12345",
                }
            ]
        }
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
    ):
        instance_name = config_module.discover_destination_instance_name("project-1")

    assert instance_name == "project-1:region:blaise-dev-abc12345"


def test_discover_destination_instance_name_falls_back_to_gcloud() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch(
            "config._discover_access_token", side_effect=RuntimeError("api token error")
        ),
        patch(
            "config.subprocess.run",
            return_value=SimpleNamespace(
                stdout="project-1:region:blaise-dev-abc12345\n"
            ),
        ),
    ):
        instance_name = config_module.discover_destination_instance_name("project-1")

    assert instance_name == "project-1:region:blaise-dev-abc12345"


def test_discover_destination_instance_name_selects_single_pattern_match() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={
            "items": [
                {
                    "name": "pitr-clone",
                    "connectionName": "project-1:region:pitr-clone",
                },
                {
                    "name": "blaise-dev-abc12345",
                    "connectionName": "project-1:region:blaise-dev-abc12345",
                },
            ]
        }
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
    ):
        instance_name = config_module.discover_destination_instance_name("project-1")

    assert instance_name == "project-1:region:blaise-dev-abc12345"


def test_discover_destination_instance_name_exits_when_ambiguous() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={
            "items": [
                {
                    "name": "blaise-dev-aa11bb22",
                    "connectionName": "project-1:region:blaise-dev-aa11bb22",
                },
                {
                    "name": "blaise-stage-cc33dd44",
                    "connectionName": "project-1:region:blaise-stage-cc33dd44",
                },
            ]
        }
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
        pytest.raises(
            SystemExit,
            match="Multiple Cloud SQL instances matched expected naming convention",
        ),
    ):
        config_module.discover_destination_instance_name("project-1")


def test_discover_destination_instance_name_exits_when_none_match_pattern() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={
            "items": [
                {
                    "name": "mysql-shared",
                    "connectionName": "project-1:region:mysql-shared",
                }
            ]
        }
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
        pytest.raises(SystemExit, match="No Cloud SQL instance matched expected"),
    ):
        config_module.discover_destination_instance_name("project-1")


def test_discover_destination_instance_name_exits_when_none_found() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch("config._discover_access_token", side_effect=RuntimeError("api fail")),
        patch("config.subprocess.run", side_effect=RuntimeError("gcloud fail")),
        pytest.raises(SystemExit, match="Could not discover a Cloud SQL instance"),
    ):
        config_module.discover_destination_instance_name("project-1")


def test_discover_destination_instance_name_uses_legacy_gcloud_fallback() -> None:
    config_module = _load_config_module_with_safe_defaults()

    def subprocess_side_effect(*args: object, **kwargs: object) -> SimpleNamespace:
        command = args[0] if args else kwargs.get("args")
        if isinstance(command, list) and "--format=json" in command:
            raise RuntimeError("json format unsupported")
        return SimpleNamespace(stdout="project-1:region:blaise-dev-abc12345\n")

    with (
        patch("config._discover_access_token", side_effect=RuntimeError("api fail")),
        patch("config.subprocess.run", side_effect=subprocess_side_effect),
    ):
        instance_name = config_module.discover_destination_instance_name("project-1")

    assert instance_name == "project-1:region:blaise-dev-abc12345"


def test_discover_destination_instance_name_filters_json_instance_list() -> None:
    config_module = _load_config_module_with_safe_defaults()

    json_instances = [
        {
            "name": "blaise-dev-abc12345",
            "connectionName": "project-1:region:blaise-dev-abc12345",
        },
        {"name": "missing-connection"},
        "not-a-dict",
    ]

    with (
        patch("config._discover_access_token", side_effect=RuntimeError("api fail")),
        patch(
            "config.subprocess.run",
            return_value=SimpleNamespace(stdout=json.dumps(json_instances)),
        ),
    ):
        instance_name = config_module.discover_destination_instance_name("project-1")

    assert instance_name == "project-1:region:blaise-dev-abc12345"


def test_discover_destination_instance_name_exits_when_gcloud_json_is_not_list() -> (
    None
):
    config_module = _load_config_module_with_safe_defaults()

    def subprocess_side_effect(*args: object, **kwargs: object) -> SimpleNamespace:
        command = args[0] if args else kwargs.get("args")
        if isinstance(command, list) and "--format=json" in command:
            return SimpleNamespace(stdout=json.dumps({"items": []}))
        return SimpleNamespace(stdout="project-1:region:blaise-dev-abc12345\n")

    with (
        patch("config._discover_access_token", side_effect=RuntimeError("api fail")),
        patch("config.subprocess.run", side_effect=subprocess_side_effect),
        pytest.raises(SystemExit, match="Could not discover a Cloud SQL instance"),
    ):
        config_module.discover_destination_instance_name("project-1")


def test_discover_database_name_single_user_database() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(payload={"items": [{"name": "blaise"}]})

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
    ):
        database_name = config_module.discover_database_name("project-1", "p:r:i")

    assert database_name == "blaise"


def test_discover_database_name_prefers_blaise_when_multiple_user_databases() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={"items": [{"name": "alpha"}, {"name": "blaise"}]}
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
    ):
        database_name = config_module.discover_database_name("project-1", "p:r:i")

    assert database_name == "blaise"


def test_discover_database_name_exits_when_multiple_without_preferred_name() -> None:
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(
        payload={"items": [{"name": "zeta"}, {"name": "alpha"}]}
    )

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
        pytest.raises(SystemExit, match="Multiple non-system databases found"),
    ):
        config_module.discover_database_name("project-1", "p:r:i")


def test_discover_database_name_returns_system_database_when_no_user_databases() -> (
    None
):
    config_module = _load_config_module_with_safe_defaults()
    api_response = FakeResponse(payload={"items": [{"name": "mysql"}]})

    with (
        patch("config._discover_access_token", return_value="token"),
        patch("config.requests.get", return_value=api_response),
        pytest.raises(SystemExit, match="No non-system database found"),
    ):
        config_module.discover_database_name("project-1", "p:r:i")


def test_discover_database_name_uses_gcloud_fallback() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch("config._discover_access_token", side_effect=RuntimeError("token error")),
        patch("config.subprocess.run", return_value=SimpleNamespace(stdout="blaise\n")),
    ):
        database_name = config_module.discover_database_name("project-1", "p:r:i")

    assert database_name == "blaise"


def test_discover_database_name_exits_when_none_found() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch("config._discover_access_token", side_effect=RuntimeError("token error")),
        patch("config.subprocess.run", side_effect=RuntimeError("gcloud error")),
        pytest.raises(SystemExit, match="Could not discover the destination database"),
    ):
        config_module.discover_database_name("project-1", "p:r:i")


def test_discover_database_username_returns_expected_value() -> None:
    config_module = _load_config_module_with_safe_defaults()
    assert config_module.discover_database_username() == "blaise"


def test_discover_database_password_from_secret_manager() -> None:
    config_module = _load_config_module_with_safe_defaults()
    secret_client = Mock()
    secret_client.access_secret_version.return_value = SimpleNamespace(
        payload=SimpleNamespace(data=b"secret-password")
    )

    with patch(
        "config.secretmanager.SecretManagerServiceClient", return_value=secret_client
    ):
        password = config_module.discover_database_password("project-1")

    assert password == "secret-password"


def test_discover_database_password_from_gcloud_fallback() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch(
            "config.secretmanager.SecretManagerServiceClient",
            side_effect=RuntimeError("secret manager error"),
        ),
        patch(
            "config.subprocess.run",
            return_value=SimpleNamespace(stdout="gcloud-secret\n"),
        ),
    ):
        password = config_module.discover_database_password("project-1")

    assert password == "gcloud-secret"


def test_discover_database_password_exits_when_unavailable() -> None:
    config_module = _load_config_module_with_safe_defaults()
    with (
        patch(
            "config.secretmanager.SecretManagerServiceClient",
            side_effect=RuntimeError("secret manager error"),
        ),
        patch("config.subprocess.run", side_effect=RuntimeError("gcloud error")),
        pytest.raises(
            SystemExit, match="Could not discover destination database password"
        ),
    ):
        config_module.discover_database_password("project-1")


def test_discover_restore_bucket_name_uses_environment_from_instance_name() -> None:
    config_module = _load_config_module_with_safe_defaults()

    bucket_name = config_module.discover_restore_bucket_name(
        "project-1:region:blaise-dev-abc12345"
    )

    assert bucket_name == "ons-blaise-v2-dev-backups"


def test_discover_restore_bucket_name_exits_for_unexpected_instance_name() -> None:
    config_module = _load_config_module_with_safe_defaults()

    with pytest.raises(SystemExit, match="Could not infer environment"):
        config_module.discover_restore_bucket_name("project-1:region:mysql-shared")


def test_settings_class_is_initialized_with_discovered_values() -> None:
    config_module = _load_config_module()

    with (
        patch.object(config_module, "discover_project_id", return_value="project-1"),
        patch.object(
            config_module,
            "discover_destination_instance_name",
            return_value="project-1:region:blaise-dev-abc12345",
        ),
        patch.object(config_module, "discover_database_name", return_value="blaise"),
        patch.object(
            config_module,
            "discover_restore_bucket_name",
            return_value="ons-blaise-v2-dev-backups",
        ),
    ):
        settings = config_module.Settings

        assert settings.DEST_PROJECT_ID == "project-1"
        assert settings.DEST_INSTANCE_NAME == "project-1:region:blaise-dev-abc12345"
        assert settings.RESTORE_SOURCE_INSTANCE_NAME == settings.DEST_INSTANCE_NAME
        assert settings.DEST_DB_NAME == "blaise"
        assert settings.RESTORE_GCS_BUCKET == "ons-blaise-v2-dev-backups"
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
