from mock_alchemy.mocking import UnifiedAlchemyMagicMock
from sqlalchemy import Table
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory
from services.database_table_service import DatabaseTableService

class FakeDatabaseTableService(DatabaseTableService):

    table = TableFactory.create_form_table_model("MockTable")

    def __init__(self):
        self._database_session = UnifiedAlchemyMagicMock()

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self) -> [Table]:
        return self._database_session.query(self.table).all()

    def add_record(self, record: Table):
        self._database_session.add(record)

    def delete_records(self):
        pass
