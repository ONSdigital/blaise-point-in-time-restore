import pytest
from google.cloud.sql.connector import IPTypes
from sqlalchemy import Engine

from models.database_connection_model import DatabaseConnectionModel
from services.database_connection_service import DatabaseConnectionService
from services.database_orm_service import DatabaseOrmService


class TestOrmFunctionality:
    @pytest.fixture()
    def connection_model(self):
        return DatabaseConnectionModel(
            instance_name="ons-blaise-v2-dev-b4team:europe-west2:bens-clone2",
            database_name="blaise",
            database_driver="pymysql",
            database_url="mysql+pymysql://",
            database_username="blaise",
            database_password="6Nf6nOoLPQ96ETpU",
            database_ip_connection_type=IPTypes.PUBLIC
        )

    @pytest.fixture()
    def mock_source_database(self, connection_model) -> Engine:
        database_connection_service = DatabaseConnectionService(connection_model)
        return database_connection_service.get_database()

    @pytest.fixture()
    def service_under_test(self) -> DatabaseOrmService:
        return DatabaseOrmService()

    def test_get_table_data_returns_expected_data(self, service_under_test, mock_source_database):
        # arrange
        questionnaire_name = "LMS2310_GP1_Form"
        expected = [900001, 900021]

        # act
        actual = service_under_test.get_case_ids(questionnaire_name, mock_source_database)

        # assert
        assert len(actual) == len(expected)
        assert all([a == b for a, b in zip(actual, expected)])
