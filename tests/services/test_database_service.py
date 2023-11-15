import mock
from unittest.mock import call, MagicMock
import pytest
import sqlalchemy
from google.cloud.sql.connector import IPTypes, Connector

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

    @mock.patch.object(sqlalchemy, 'Connection')
    @mock.patch.object(sqlalchemy, 'create_engine')
    @mock.patch.object(Connector, 'connect')
    def test_copy_database_table_uses_the_connection_model_to_connect_to_the_database(self,
                                                                                      mock_connector,
                                                                                      __mock_engine,
                                                                                      __mock_connection,
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

    @mock.patch.object(sqlalchemy, 'Connection')
    @mock.patch.object(sqlalchemy, 'create_engine')
    @mock.patch.object(Connector, 'connect')
    def test_copy_database_table_uses_the_connection_model_database_url_to_create_an_engine(self,
                                                                                            mock_connector,
                                                                                            mock_engine,
                                                                                            __mock_connection,
                                                                                            service_under_test,
                                                                                            connection_model):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        mock_source_database_engine = MagicMock()
        mock_destination_database_engine = MagicMock()
        mock_connector.side_effect = [
            mock_source_database_engine,
            mock_destination_database_engine
        ]

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        mock_engine.assert_has_calls(
            [call(url=connection_model.database_url, creator=mock_source_database_engine, pool_pre_ping=True),
             call(url=connection_model.database_url, creator=mock_destination_database_engine, pool_pre_ping=True)])

    @mock.patch.object(sqlalchemy, 'Connection')
    @mock.patch.object(sqlalchemy, 'create_engine')
    @mock.patch.object(Connector, 'connect')
    def test_copy_database_table_selects_table_data_from_the_source_database_instance(self,
                                                                                      mock_connector,
                                                                                      mock_engine,
                                                                                      mock_connection,
                                                                                      service_under_test,
                                                                                      connection_model):
        # arrange
        table_name = 'LMS2301_DD1_FORM'
        source_instance_name = 'b4team:europe-west2:blaise-dev-test-clone'
        destination_instance_name = 'blaise-dev-test'

        mock_source_database_engine = MagicMock()
        mock_destination_database_engine = MagicMock()
        mock_connector.side_effect = [
            mock_source_database_engine,
            mock_destination_database_engine
        ]

        mock_source_engine_connection = MagicMock()
        mock_source_database_engine.connect().return_value = mock_source_engine_connection

        # act
        service_under_test.copy_table_data(table_name, source_instance_name, destination_instance_name)

        # assert
        mock_source_engine_connection.execute.assert_called_with()
