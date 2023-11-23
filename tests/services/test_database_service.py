from unittest.mock import Mock, call, MagicMock

import pytest
from sqlalchemy.orm import Session
from functions.factories.table_factory import TableFactory
from services.database_service import DatabaseService


class TestDatabaseService:

    @pytest.fixture
    def table_factory(self) -> TableFactory:
        return TableFactory()

    @pytest.fixture
    def mock_session(self) -> Session:
        return MagicMock()

    @pytest.fixture
    def service_under_test(self, table_factory: TableFactory, mock_session: Session) -> DatabaseService:
        return DatabaseService(mock_session)

    def test_database_service_get_records_calls_correct_method_in_session(self, service_under_test: DatabaseService,
                                                                          mock_session: Session,
                                                                          table_factory: TableFactory):
        # Arrange
        questionnaire_name = 'LMS2211_FML'
        questionnaire_tables = table_factory.get_table_models(questionnaire_name)
        table = questionnaire_tables[0]

        # Act
        service_under_test.get_records(table)

        # Assert
        mock_session.assert_has_calls([call.query(table), call.query().all()])


    def test_database_service_add_record_calls_correct_method_in_session(self, service_under_test: DatabaseService,
                                                                          mock_session: Session,
                                                                          table_factory: TableFactory):
        # Arrange
        questionnaire_name = 'LMS2211_FML'
        questionnaire_tables = table_factory.get_table_models(questionnaire_name)
        table = questionnaire_tables[0]

        # Act
        service_under_test.add_record(table)

        # Assert
        mock_session.assert_has_calls([call.merge(table)])



    def test_database_service_delete_records_calls_correct_method_in_session(self, service_under_test: DatabaseService,
                                                                          mock_session: Session,
                                                                          table_factory: TableFactory):
        # Arrange
        questionnaire_name = 'LMS2211_FML'
        questionnaire_tables = table_factory.get_table_models(questionnaire_name)
        table = questionnaire_tables[0]

        # Act
        service_under_test.delete_records(table)

        # Assert
        mock_session.assert_has_calls([call.query(table), call.query().delete()])
