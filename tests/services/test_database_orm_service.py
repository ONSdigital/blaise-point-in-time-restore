from unittest.mock import MagicMock, call, Mock

import pytest
from sqlalchemy.testing.schema import Table

from functions.factories.table_factory import TableFactory
from services.database_orm_service import DatabaseOrmService
from services.database_service import DatabaseService


class TestOrmFunctionality:
    table_name = "LMS2211_FML"

    @pytest.fixture()
    def mock_source_session(self):
        return MagicMock()

    @pytest.fixture()
    def mock_destination_session(self):
        return MagicMock()

    @pytest.fixture()
    def mock_source_database(self, mock_source_session) -> DatabaseService:
        return DatabaseService(mock_source_session, TableFactory())

    @pytest.fixture()
    def mock_destination_database(self, mock_destination_session) -> DatabaseService:
        return DatabaseService(mock_destination_session, TableFactory())

    @pytest.fixture()
    def service_under_test(self, mock_source_database, mock_destination_database) -> DatabaseOrmService:
        return DatabaseOrmService(mock_source_database, mock_destination_database)

    @pytest.fixture()
    def mock_source_records(self) -> [Table]:
        table = TableFactory.create_form_table_model(self.table_name)

        records = [table(FormID=1, Serial_Number=900001),
                   table(FormID=2, Serial_Number=900002),
                   table(FormID=3, Serial_Number=900003)]

        return records

    def test_copy_table_data_copies_source_database_records_to_destination_database(self,
                                                                                    service_under_test,
                                                                                    mock_source_session,
                                                                                    mock_destination_session,
                                                                                    mock_source_records):
        # arrange
        mock_source_session.query().all.return_value = mock_source_records

        expected_destination_database_calls = []
        for record in mock_source_records:
            expected_destination_database_calls.append(call(record))

        # act
        service_under_test.copies_table_data(self.table_name)

        # assert
        mock_destination_session.merge.assert_has_calls(expected_destination_database_calls)

    def test_copy_table_data_removes_any_existing_data_from_the_destination_database_before_copying(self,
                                                                                                    service_under_test,
                                                                                                    mock_source_session,
                                                                                                    mock_destination_session,
                                                                                                    mock_source_records):
        # arrange
        mock_source_session.query().all.return_value = mock_source_records

        # set up a mock parent so that we can inspect the order of calls made
        mock_order = MagicMock()
        mock_order.attach_mock(mock_destination_session.query().delete, "delete")
        mock_order.attach_mock(mock_destination_session.merge, "merge")

        expected_destination_database_calls = []
        expected_destination_database_calls.append(call.delete)
        for record in mock_source_records:
            expected_destination_database_calls.append(call.merge(record))

        # act
        service_under_test.copies_table_data(self.table_name)

        # assert
        mock_order.assert_has_calls(expected_destination_database_calls, any_order=False)

    def test_copy_table_data_calls_begin_method_on_destination_database_session_to_ensure_transaction(self,
                                                                                                      service_under_test,
                                                                                                      mock_source_session,
                                                                                                      mock_destination_session,
                                                                                                      mock_source_records):
        # arrange
        mock_source_session.query().all.return_value = mock_source_records

        # act
        service_under_test.copies_table_data(self.table_name)

        # assert
        assert mock_destination_session.begin.called
        assert not mock_destination_session.rollback.called
