from unittest.mock import Mock, call, MagicMock

import pytest

from functions.factories.table_factory import TableFactory
from services.database_orm_service import DatabaseOrmService
from services.database_restore_service import DatabaseRestoreService


class TestDatabaseRestoreService:

    @pytest.fixture
    def table_factory(self):
        return TableFactory()

    @pytest.fixture
    def mock_database_orm_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def service_under_test(self, table_factory: TableFactory, mock_database_orm_service: DatabaseOrmService):
        return DatabaseRestoreService(table_factory, mock_database_orm_service)

    def test_database_restore_service_restores_data_for_all_tables_related_to_questionnaire(self, service_under_test,
                                                                                            mock_database_orm_service,
                                                                                            table_factory):
        pass
        # Arrange
        questionnaire_name = 'LMS2211_FML'
        questionnaire_tables = table_factory.get_table_models(questionnaire_name)

        expected_calls = []
        for table in questionnaire_tables:
            expected_calls.append(call(table))

        # Act
        service_under_test.restore_data_for_questionnaire(questionnaire_name)

        # Assert
        mock_database_orm_service.copy_table_data.assert_has_calls(expected_calls)
