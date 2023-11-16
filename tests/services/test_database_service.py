from unittest.mock import call, MagicMock, patch, Mock
import pytest
import sqlalchemy
from google.cloud.sql.connector import IPTypes, Connector
from sqlalchemy import Table
from sqlalchemy.orm import Session

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

    @patch.object(sqlalchemy, 'create_engine')
    @patch.object(Connector, 'connect')
    def test_copy_database_table_uses_the_connection_model_to_connect_to_the_database(self,
                                                                                      mock_connector,
                                                                                      __mock_engine,
                                                                                      service_under_test,
                                                                                      connection_model):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        mock_connector.assert_has_calls(
            [call(instance_connection_string=source_instance_name,
                  driver=connection_model.database_driver,
                  user=connection_model.database_username,
                  password=connection_model.database_password,
                  db=connection_model.database_name),
             call(instance_connection_string=destination_instance_name,
                  driver=connection_model.database_driver,
                  user=connection_model.database_username,
                  password=connection_model.database_password,
                  db=connection_model.database_name)],
            any_order=True)

    @patch.object(sqlalchemy, 'create_engine')
    @patch.object(Connector, 'connect')
    def test_copy_database_table_uses_the_connection_model_database_url_to_create_an_engine(self,
                                                                                            mock_connector,
                                                                                            mock_engine,
                                                                                            service_under_test,
                                                                                            connection_model):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        mock_source_database_connection = MagicMock()
        mock_destination_database_connection = MagicMock()
        mock_connector.side_effect = [
            mock_source_database_connection,
            mock_destination_database_connection
        ]

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        mock_engine.assert_has_calls(
            [call(url=connection_model.database_url, creator=mock_source_database_connection, pool_pre_ping=True),
             call(url=connection_model.database_url, creator=mock_destination_database_connection, pool_pre_ping=True)])

    @patch.object(Table, 'select')
    @patch.object(Session, 'execute')
    @patch.object(sqlalchemy, 'create_engine')
    @patch.object(Connector, 'connect')
    def test_copy_database_table_selects_the_correct_table_data_to_copy_from(self,
                                                                             __mock_connector,
                                                                             __mock_engine,
                                                                             mock_session_execute,
                                                                             mock_table_select,
                                                                             service_under_test):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        table_select = F'select * from {table_name}'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        mock_session_execute_source = MagicMock()
        mock_session_execute_destination = MagicMock()

        mock_session_execute.side_effect = [
            mock_session_execute_source,
            mock_session_execute_destination
        ]

        mock_table_select.return_value = table_select

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        print(mock_session_execute_source)
        mock_session_execute_source.assert_called_with(table_select)

