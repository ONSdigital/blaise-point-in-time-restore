from unittest.mock import Mock

import pytest

from services.database_service import DatabaseService


@pytest.fixture
def service_under_test() -> DatabaseService:
    return DatabaseService(
        cloud_sql_client=Mock(),
        database_name="blaise",
        export_bucket_name="ons-blaise-v2-dev-backups",
        export_prefix="questionnaire-pitr",
        operation_timeout_seconds=120,
        operation_poll_seconds=2,
    )


@pytest.mark.parametrize("table_name", [None, "", " ", "   "])
def test_copy_table_data_raises_for_empty_table_name(
    service_under_test: DatabaseService,
    table_name: str,
) -> None:
    with pytest.raises(ValueError, match="table_name cannot be empty or none"):
        service_under_test.copy_table_data(
            table_name,
            "project-1:region:source",
            "project-1:region:destination",
        )