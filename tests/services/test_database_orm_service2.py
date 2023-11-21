import pytest

from functions.factories.table_factory import TableFactory
from services.database_orm_service2 import DatabaseOrmService2
from tests.services.fake_database_service import FakeDatabaseService


class TestOrmFunctionality:
    fake_source_database = FakeDatabaseService("source")
    fake_destination_database = FakeDatabaseService("destination")
    
    @pytest.fixture()
    def service_under_test(self) -> DatabaseOrmService2:
        return DatabaseOrmService2(self.fake_source_database, self.fake_destination_database)

    def test_copy_table_data_copies_source_to_destination(self, service_under_test):
        # arrange
        table_name = "LMS2211_FML"
        table = TableFactory.create_form_table_model(table_name)
        self.fake_source_database.add_record(table(FormID=1, Serial_Number=900001))
        self.fake_source_database.add_record(table(FormID=2, Serial_Number=900002))
        self.fake_source_database.add_record(table(FormID=3, Serial_Number=900003))
        expected = self.fake_source_database.get_records(table_name)

        # act
        service_under_test.copies_table_data(table_name)

        actual = self.fake_destination_database.get_records(table_name)

        # assert
        assert len(actual) == 3
        assert all([a == b for a, b in zip(actual, expected)])

    def test_copy_table_data_deletes_any_existing_data_from_the_destination_table(self, service_under_test):
        # arrange
        table_name = "LMS2211_FML"
        table = TableFactory.create_form_table_model(table_name)
        self.fake_source_database.add_record(table(FormID=1, Serial_Number=900001))
        self.fake_source_database.add_record(table(FormID=2, Serial_Number=900002))
        self.fake_source_database.add_record(table(FormID=3, Serial_Number=900003))
        expected = self.fake_source_database.get_records(table_name)

        self.fake_destination_database.add_record(table(FormID=4, Serial_Number=900004))
        self.fake_destination_database.add_record(table(FormID=5, Serial_Number=900005))
        self.fake_destination_database.add_record(table(FormID=6, Serial_Number=900006))

        # act
        service_under_test.copies_table_data(table_name)

        actual = self.fake_destination_database.get_records(table_name)

        # assert
        assert len(actual) == 3
        assert all([a == b for a, b in zip(actual, expected)])
