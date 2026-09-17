import os
from datetime import datetime
from zoneinfo import ZoneInfo

def parse_uk_local_timestamp(value: str) -> datetime:
    cleaned = value.strip()
    normalized = cleaned.replace("T", " ")

    local_naive = datetime.fromisoformat(normalized)
    if local_naive.tzinfo is not None:
        return local_naive

    return local_naive.replace(tzinfo=ZoneInfo("Europe/London"))


def _required_environment_variable(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not configured")
    return value


class _SettingsMeta(type):
    @property
    def PROJECT_ID(cls) -> str:
        return _required_environment_variable("PROJECT_ID")

    @property
    def DEST_INSTANCE_NAME(cls) -> str:
        return _required_environment_variable("DEST_INSTANCE_NAME")

    @property
    def RESTORE_SOURCE_INSTANCE_NAME(cls) -> str:
        return cls.DEST_INSTANCE_NAME

    @property
    def DEST_DB_NAME(cls) -> str:
        return _required_environment_variable("DEST_DB_NAME")

    @property
    def RESTORE_GCS_BUCKET(cls) -> str:
        return _required_environment_variable("RESTORE_GCS_BUCKET")


class Settings(metaclass=_SettingsMeta):
    RESTORE_GCS_PREFIX = "questionnaire-pitr"

    CLONE_NAME_PREFIX = "pitr"
    CLONE_OPERATION_POLL_SECONDS = 5
    CLONE_OPERATION_TIMEOUT_SECONDS = 1800
    CLONE_HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
    CLONE_HTTP_READ_TIMEOUT_SECONDS = 30.0
