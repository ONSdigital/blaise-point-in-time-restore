import pytest
from google.cloud.sql.connector import IPTypes

from models.database_connection_model import DatabaseConnectionModel
from services.database_service import DatabaseService


class TestCopyFunctionality:
    @pytest.fixture()
    def connection_model(self):
        return DatabaseConnectionModel(
            database_name='blaise',
            database_username='blaise_user',
            database_password='password_12345',
            database_driver='pymsql',
            ip_connection_type=IPTypes.PRIVATE,
            database_url='mysql+pymysql://'
        )

    @pytest.fixture()
    def service_under_test(self, connection_model) -> DatabaseService:
        return DatabaseService(
            connection_model=connection_model
        )

    def test_copy_database_table_deletes_all_existing_data(self, service_under_test, mocked_session):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        delete_statement = F'truncate {table_name}'

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        mocked_session.execute.assert_called_with(delete_statement)

