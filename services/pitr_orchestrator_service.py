import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from models.database_clone_model import DatabaseCloneModel
from services.database_clone_service import DatabaseCloneService
from services.database_restore_service import DatabaseRestoreService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PitrRequest:
    request_id: str
    questionnaire_name: str
    timestamp: datetime
    source_instance_name: str
    destination_instance_name: str
    clone_instance_name: str
    operation_timeout_seconds: int
    operation_poll_seconds: int


class PitrOrchestratorService:
    def __init__(
        self,
        clone_service: DatabaseCloneService,
        restore_service: DatabaseRestoreService,
    ):
        self._clone_service = clone_service
        self._restore_service = restore_service

    def restore_questionnaire_from_point_in_time(self, request: PitrRequest) -> None:
        started_at = time.monotonic()
        LOGGER.info(
            (
                "PITR started; request_id=%s questionnaire=%s "
                "source=%s destination=%s clone=%s timestamp=%s"
            ),
            request.request_id,
            request.questionnaire_name,
            request.source_instance_name,
            request.destination_instance_name,
            request.clone_instance_name,
            request.timestamp.isoformat(),
        )

        LOGGER.info(
            (
                "Validating source and destination instances; request_id=%s "
                "source=%s destination=%s"
            ),
            request.request_id,
            request.source_instance_name,
            request.destination_instance_name,
        )
        self._clone_service.get_instance(request.source_instance_name)
        self._clone_service.get_instance(request.destination_instance_name)

        clone_model = DatabaseCloneModel()
        clone_model.source_instance_name = request.source_instance_name
        clone_model.point_in_time = request.timestamp
        clone_instance_name = self.__resolve_clone_instance_name(request, clone_model)

        LOGGER.info(
            (
                "Requesting clone creation; request_id=%s source=%s clone=%s "
                "point_in_time=%s"
            ),
            request.request_id,
            request.source_instance_name,
            clone_instance_name,
            request.timestamp.isoformat(),
        )
        clone_operation = self._clone_service.create_clone(clone_model)
        LOGGER.info(
            "Waiting for clone creation to finish; request_id=%s operation=%s clone=%s",
            request.request_id,
            clone_operation,
            clone_instance_name,
        )
        self._clone_service.wait_for_operation(
            clone_operation,
            timeout_seconds=request.operation_timeout_seconds,
            poll_interval_seconds=request.operation_poll_seconds,
        )
        LOGGER.info(
            "Clone is ready; request_id=%s clone=%s",
            request.request_id,
            clone_instance_name,
        )
        clone_instance = self._clone_service.get_instance(clone_instance_name)
        clone_connection_name = str(
            clone_instance.get("connectionName", clone_instance_name)
        )
        clone_settings = clone_instance.get("settings", {})
        if isinstance(clone_settings, dict) and clone_settings.get(
            "deletionProtectionEnabled"
        ):
            self.__prepare_clone_for_cleanup(request, clone_instance_name)

        LOGGER.info(
            (
                "Resolved clone connection for restore; request_id=%s "
                "clone=%s connection=%s"
            ),
            request.request_id,
            clone_instance_name,
            clone_connection_name,
        )

        restore_error: Exception | None = None
        try:
            LOGGER.info(
                (
                    "Starting questionnaire data restore; request_id=%s "
                    "questionnaire=%s source=%s destination=%s"
                ),
                request.request_id,
                request.questionnaire_name,
                clone_connection_name,
                request.destination_instance_name,
            )
            self._restore_service.restore_questionnaire_tables(
                request.questionnaire_name,
                source_instance_name=clone_connection_name,
                destination_instance_name=request.destination_instance_name,
            )
            LOGGER.info(
                (
                    "Questionnaire table restore completed; request_id=%s "
                    "questionnaire=%s tables=%s"
                ),
                request.request_id,
                request.questionnaire_name,
                f"{request.questionnaire_name}_Dml,{request.questionnaire_name}_Form",
            )
        except Exception as error:
            restore_error = error
            LOGGER.exception(
                "Restore failed; request_id=%s clone=%s destination=%s. "
                "Inspect prior Cloud SQL export/import logs for the failing "
                "table and operation details.",
                request.request_id,
                clone_instance_name,
                request.destination_instance_name,
            )
            raise
        finally:
            self.__cleanup_temporary_clone(
                request=request,
                clone_instance_name=clone_instance_name,
                restore_error=restore_error,
                started_at=started_at,
            )

        LOGGER.info(
            ("PITR finished; request_id=%s questionnaire=%s duration_seconds=%.2f"),
            request.request_id,
            request.questionnaire_name,
            time.monotonic() - started_at,
        )

    def __prepare_clone_for_cleanup(
        self, request: PitrRequest, clone_instance_name: str
    ) -> None:
        try:
            LOGGER.info(
                (
                    "Disabling deletion protection on temporary clone; "
                    "request_id=%s clone=%s"
                ),
                request.request_id,
                clone_instance_name,
            )
            self._clone_service.disable_deletion_protection(clone_instance_name)
            LOGGER.info(
                (
                    "Deletion protection disabled on temporary clone; "
                    "request_id=%s clone=%s"
                ),
                request.request_id,
                clone_instance_name,
            )
        except Exception as error:
            LOGGER.warning(
                (
                    "Could not proactively disable deletion protection; cleanup "
                    "will retry after restore; request_id=%s clone=%s "
                    "error_type=%s error=%s"
                ),
                request.request_id,
                clone_instance_name,
                type(error).__name__,
                error,
            )

    def __resolve_clone_instance_name(
        self, request: PitrRequest, clone_model: DatabaseCloneModel
    ) -> str:
        clone_instance_name = request.clone_instance_name
        clone_model.destination_instance_name = clone_instance_name

        LOGGER.info(
            "Checking whether clone already exists; request_id=%s clone=%s",
            request.request_id,
            clone_instance_name,
        )
        if not self._clone_service.instance_exists(clone_instance_name):
            return clone_instance_name

        LOGGER.info(
            "Clone exists and will be replaced; request_id=%s clone=%s",
            request.request_id,
            clone_instance_name,
        )
        try:
            stale_delete_operation = self._clone_service.delete_clone(
                clone_instance_name
            )
            LOGGER.info(
                (
                    "Waiting for stale clone deletion; request_id=%s "
                    "operation=%s clone=%s"
                ),
                request.request_id,
                stale_delete_operation,
                clone_instance_name,
            )
            self._clone_service.wait_for_operation(
                stale_delete_operation,
                timeout_seconds=request.operation_timeout_seconds,
                poll_interval_seconds=request.operation_poll_seconds,
            )
            return clone_instance_name
        except Exception:
            fallback_clone_name = self.__build_retry_clone_name(
                request.clone_instance_name
            )
            clone_model.destination_instance_name = fallback_clone_name
            LOGGER.warning(
                (
                    "Stale clone delete failed; request_id=%s stale_clone=%s "
                    "fallback_clone=%s"
                ),
                request.request_id,
                request.clone_instance_name,
                fallback_clone_name,
            )
            return fallback_clone_name

    def __cleanup_temporary_clone(
        self,
        request: PitrRequest,
        clone_instance_name: str,
        restore_error: Exception | None,
        started_at: float,
    ) -> None:
        LOGGER.info(
            (
                "Starting temporary clone cleanup; request_id=%s clone=%s "
                "elapsed_seconds=%.2f"
            ),
            request.request_id,
            clone_instance_name,
            time.monotonic() - started_at,
        )
        try:
            delete_operation = self._clone_service.delete_clone(clone_instance_name)
            LOGGER.info(
                (
                    "Waiting for temporary clone deletion; request_id=%s "
                    "operation=%s clone=%s"
                ),
                request.request_id,
                delete_operation,
                clone_instance_name,
            )
            self._clone_service.wait_for_operation(
                delete_operation,
                timeout_seconds=request.operation_timeout_seconds,
                poll_interval_seconds=request.operation_poll_seconds,
            )
            LOGGER.info(
                "Temporary clone deleted; request_id=%s clone=%s",
                request.request_id,
                clone_instance_name,
            )
        except Exception as cleanup_error:
            try:
                if not self._clone_service.instance_exists(clone_instance_name):
                    LOGGER.info(
                        (
                            "Temporary clone deletion confirmed after an uncertain "
                            "response; request_id=%s clone=%s"
                        ),
                        request.request_id,
                        clone_instance_name,
                    )
                    return
            except Exception:
                pass

            LOGGER.error(
                "Temporary clone cleanup could not be confirmed; request_id=%s "
                "clone=%s elapsed_seconds=%.2f error_type=%s error=%s",
                request.request_id,
                clone_instance_name,
                time.monotonic() - started_at,
                type(cleanup_error).__name__,
                cleanup_error,
            )
            if restore_error is not None:
                return

    @staticmethod
    def __build_retry_clone_name(base_name: str) -> str:
        retry_suffix = str(int(time.time()))
        available_length = 98 - len(retry_suffix) - 1
        truncated_base = base_name[:available_length]
        return f"{truncated_base}-{retry_suffix}"


def build_clone_instance_name(
    prefix: str, questionnaire_name: str, timestamp: datetime
) -> str:
    timestamp_utc = timestamp.astimezone(UTC)
    compact_timestamp = timestamp_utc.strftime("%Y%m%d%H%M%S")
    safe_questionnaire = "".join(
        character.lower() if character.isalnum() else "-"
        for character in questionnaire_name.strip()
    ).strip("-")

    raw_name = f"{prefix}-{safe_questionnaire}-{compact_timestamp}"
    collapsed = "-".join(part for part in raw_name.split("-") if part)

    return collapsed[:98]
