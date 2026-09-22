import logging
import time
import uuid
from functools import cache

import flask

from config import Settings, parse_uk_local_timestamp
from services.cloud_sql_admin_client import CloudSqlAdminClient
from services.database_clone_service import DatabaseCloneService
from services.database_restore_service import DatabaseRestoreService
from services.database_service import DatabaseService
from services.pitr_orchestrator_service import (
    PitrOrchestratorService,
    PitrRequest,
    build_clone_instance_name,
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


@cache
def _get_orchestrator(database_name: str) -> PitrOrchestratorService:
    cloud_sql_client = CloudSqlAdminClient(
        project_id=Settings.PROJECT_ID,
        http_connect_timeout_seconds=Settings.CLONE_HTTP_CONNECT_TIMEOUT_SECONDS,
        http_read_timeout_seconds=Settings.CLONE_HTTP_READ_TIMEOUT_SECONDS,
    )
    clone_service = DatabaseCloneService(cloud_sql_client=cloud_sql_client)
    database_service = DatabaseService(
        cloud_sql_client=cloud_sql_client,
        database_name=database_name,
        export_bucket_name=Settings.RESTORE_GCS_BUCKET,
        export_prefix=Settings.RESTORE_GCS_PREFIX,
        operation_timeout_seconds=Settings.CLONE_OPERATION_TIMEOUT_SECONDS,
        operation_poll_seconds=Settings.CLONE_OPERATION_POLL_SECONDS,
    )
    database_restore_service = DatabaseRestoreService(
        database_service=database_service,
        database_name=database_name,
    )
    return PitrOrchestratorService(
        clone_service=clone_service,
        restore_service=database_restore_service,
    )


def run_restore(
    table_name: str,
    restore_timestamp_input: str,
    database_name: str,
    request_id: str | None = None,
) -> None:
    correlation_id = request_id or str(uuid.uuid4())
    started_at = time.monotonic()
    restore_timestamp = parse_uk_local_timestamp(restore_timestamp_input)

    clone_instance_name = build_clone_instance_name(
        prefix=Settings.CLONE_NAME_PREFIX,
        table_name=table_name,
        timestamp=restore_timestamp,
    )

    restore_request = PitrRequest(
        request_id=correlation_id,
        table_name=table_name,
        timestamp=restore_timestamp,
        source_instance_name=Settings.RESTORE_SOURCE_INSTANCE_NAME,
        destination_instance_name=Settings.DEST_INSTANCE_NAME,
        clone_instance_name=clone_instance_name,
        operation_timeout_seconds=Settings.CLONE_OPERATION_TIMEOUT_SECONDS,
        operation_poll_seconds=Settings.CLONE_OPERATION_POLL_SECONDS,
    )

    LOGGER.info(
        (
            "Restore request parsed; request_id=%s "
            "table=%s uk_local_timestamp=%s clone=%s"
        ),
        correlation_id,
        table_name,
        restore_timestamp_input,
        clone_instance_name,
    )

    _get_orchestrator(database_name).restore_table_from_point_in_time(
        restore_request
    )
    LOGGER.info(
        (
            "Restore request finished; request_id=%s "
            "table=%s duration_seconds=%.2f"
        ),
        correlation_id,
        table_name,
        time.monotonic() - started_at,
    )


def _json_error(
    code: str,
    message: str,
    status: int,
    details: str | None = None,
    request_id: str | None = None,
) -> tuple[flask.Response, int]:
    error_body: dict[str, str] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error_body["details"] = details
    if request_id is not None:
        error_body["request_id"] = request_id

    body: dict[str, dict[str, str]] = {"error": error_body}

    return flask.jsonify(body), status


def restore_table_from_point_in_time(
    request: flask.Request,
) -> tuple[flask.Response | str, int]:
    """Cloud Function HTTP entry point."""
    request_id = str(uuid.uuid4())
    data = request.get_json(silent=True) or {}
    table_name = str(data.get("table_name", "")).strip()
    timestamp_str = str(data.get("timestamp", "")).strip()
    database_name = str(data.get("database_name", "")).strip()
    if not table_name or not timestamp_str or not database_name:
        LOGGER.error(
            (
                "Restore request rejected; request_id=%s reason=missing_parameters "
                "table_name=%r timestamp=%r database_name=%r"
            ),
            request_id,
            table_name,
            timestamp_str,
            database_name,
        )
        return _json_error(
            code="missing_parameters",
            message="Missing required fields.",
            details="Expected table_name, timestamp, and database_name.",
            status=400,
            request_id=request_id,
        )

    LOGGER.info(
        (
            "Restore request accepted; request_id=%s table=%s "
            "timestamp=%s database_name=%s"
        ),
        request_id,
        table_name,
        timestamp_str,
        database_name,
    )

    try:
        run_restore(
            table_name,
            timestamp_str,
            database_name=database_name,
            request_id=request_id,
        )
    except ValueError:
        LOGGER.warning(
            (
                "Restore request rejected; request_id=%s reason=invalid_timestamp "
                "table=%s timestamp=%s"
            ),
            request_id,
            table_name,
            timestamp_str,
        )
        return _json_error(
            code="invalid_timestamp",
            message="Timestamp is invalid.",
            details=(
                "Use ISO-like format such as 'YYYY-MM-DD HH:MM:SS' or "
                "'YYYY-MM-DDTHH:MM:SS'."
            ),
            status=400,
            request_id=request_id,
        )
    except Exception:
        LOGGER.exception(
            "Restore execution failed; request_id=%s table=%s timestamp=%s",
            request_id,
            table_name,
            timestamp_str,
        )
        return _json_error(
            code="restore_failed",
            message="Restore operation failed.",
            details="See Cloud Function logs with the provided request_id.",
            status=500,
            request_id=request_id,
        )

    LOGGER.info(
        "Restore request completed successfully; request_id=%s table=%s",
        request_id,
        table_name,
    )
    return "OK", 200
