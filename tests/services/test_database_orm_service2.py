import pytest

from services.database_orm_service2 import DatabaseOrmService2
from tests.services.fake_database_table_service import FakeDatabaseTableService


class TestOrmFunctionality:

    @pytest.fixture()
    def service_under_test(self) -> DatabaseOrmService2:
        return DatabaseOrmService2()

    @pytest.fixture()
    def mock_source_database_table_service(self) -> FakeDatabaseTableService:
        mock_source_database_table_service = FakeDatabaseTableService()
        mock_source_database_table_service.add_record(mock_source_database_table_service.table(FormID=1, Serial_Number=900001))
        mock_source_database_table_service.add_record(mock_source_database_table_service.table(FormID=1, Serial_Number=900002))
        mock_source_database_table_service.add_record(mock_source_database_table_service.table(FormID=1, Serial_Number=900003))
        return mock_source_database_table_service

    @pytest.fixture()
    def mock_destination_database_table_service(self) -> FakeDatabaseTableService:
        mock_destination_database_table_service = FakeDatabaseTableService()
        return mock_destination_database_table_service

    def test_copy_table_data_copies_source_to_destination(self,
                                                          service_under_test,
                                                          mock_source_database_table_service,
                                                          mock_destination_database_table_service):
        # arrange
        expected = [900001, 900002, 900003]

        # act
        service_under_test.copies_table_data(mock_source_database_table_service,
                                             mock_destination_database_table_service)

        actual_table = mock_source_database_table_service.get_records()
        actual = []
        for table_row in actual_table:
            actual.append(table_row.Serial_Number)

        # assert
        assert len(actual) == len(expected)
        assert all([a == b for a, b in zip(actual, expected)])


