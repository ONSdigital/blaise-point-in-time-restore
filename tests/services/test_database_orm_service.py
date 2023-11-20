import pytest
from google.cloud.sql.connector import IPTypes
from mock_alchemy.mocking import AlchemyMagicMock
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from functions.factories.table_factory import TableFactory
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

    @pytest.fixture()
    def mock_session(self) -> sessionmaker:
        session = AlchemyMagicMock()
        test_table_model = TableFactory().create_form_table_model('test_table')
        session.add(test_table_model(Serial_Number='900001'))
        session.add(test_table_model(Serial_Number='900002'))
        return session

    def test_get_table_data_returns_expected_data(self, service_under_test):
        # arrange
        questionnaire_table = "test_table"
        mock_session = AlchemyMagicMock()
        test_table_model = TableFactory().create_form_table_model(questionnaire_table)
        mock_session.add(test_table_model(FormID=1, Serial_Number=900001))
        mock_session.add(test_table_model(FormID=2, Serial_Number=900002))
        expected = [900001, 900021]

        # act
        actual = service_under_test.get_case_ids2(mock_session, test_table_model)

        # assert
        assert len(actual) == len(expected)
        assert all([a == b for a, b in zip(actual, expected)])
