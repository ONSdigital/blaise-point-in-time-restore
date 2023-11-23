from unittest.mock import call,  patch
import pytest
import sqlalchemy
from google.cloud.sql.connector import IPTypes, Connector

from models.database_connection_model import DatabaseConnectionModel
from services.database_connection_service import DatabaseConnectionService


class TestDatabaseConnectionFunctionality:
    @pytest.fixture()
    def connection_model(self):
        return DatabaseConnectionModel(
            instance_name="b4team:europe-west2:blaise-dev-test-clone",
            database_name="testuser",
            database_driver="pymysql",
            database_url="mysql+pymysql://",
            database_username="blaise",
            database_password="test123",
            database_ip_connection_type=IPTypes.PUBLIC
        )

    @pytest.fixture()
    def service_under_test(self, connection_model) -> DatabaseConnectionService:
        return DatabaseConnectionService(
            connection_model=connection_model
        )

    @patch.object(Connector, 'connect')
    def test_get_connector_uses_the_connection_model_to_connect_to_the_database(self,
                                                                                mock_connector,
                                                                                service_under_test,
                                                                                connection_model):
        # arrange

        # act
        service_under_test.get_connector()

        # assert
        mock_connector.assert_has_calls(
            [call(instance_connection_string=connection_model.instance_name,
                  driver=connection_model.database_driver,
                  user=connection_model.database_username,
                  password=connection_model.database_password,
                  db=connection_model.database_name)],
            any_order=True)

    @patch.object(sqlalchemy, 'create_engine')
    def test_get_database_uses_the_connection_model_database_url_aand_connector_to_create_an_engine(self,
                                                                                                    mock_engine,
                                                                                                    service_under_test,
                                                                                                    connection_model):
        # arrange

        # act
        service_under_test.get_database()

        # assert
        mock_engine.assert_has_calls(
            [call(url=connection_model.database_url, creator=service_under_test.get_connector, pool_pre_ping=True)])
