import pytest
from google.cloud.sql.connector import IPTypes
from mock_alchemy.mocking import UnifiedAlchemyMagicMock
from sqlalchemy import Engine

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
    def mock_table(self):
        return TableFactory.create_form_table_model("LMS2310_GP1_Form")

    @pytest.fixture()
    def mock_source_session(self, mock_table):
        session = UnifiedAlchemyMagicMock()
        session.merge(mock_table(FormID=1, Serial_Number=900001))
        session.merge(mock_table(FormID=2, Serial_Number=900002))
        session.merge(mock_table(FormID=2, Serial_Number=900003))
        return session

    @pytest.fixture()
    def mock_destination_session(self, mock_table):
        return UnifiedAlchemyMagicMock()

    def old_test_get_table_data_returns_expected_data_old(self,
                                                  service_under_test,
                                                  mock_table,
                                                  mock_source_session):
        # arrange
        expected = [900001, 900002, 900003]

        # act
        actual = service_under_test.get_case_ids(mock_table, mock_source_session)

        # assert
        assert len(actual) == len(expected)
        assert all([a == b for a, b in zip(actual, expected)])

    def old_test_copy_table_data_copies_source_to_destination_old(self,
                                                          service_under_test,
                                                          mock_table,
                                                          mock_source_session,
                                                          mock_destination_session):
        # arrange
        expected = mock_source_session.query(mock_table).all()

        # act
        service_under_test.copies_table_data(mock_table, mock_source_session, mock_destination_session)


        # assert
        assert len(mock_destination_session.query(mock_table).all()) == len(expected)
