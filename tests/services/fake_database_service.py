from mock_alchemy.mocking import UnifiedAlchemyMagicMock
from sqlalchemy.testing.schema import Table
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory
from services.database_service import DatabaseService


class FakeDatabaseService(DatabaseService):

    def __init__(self, instance_name: str):
        self._table_factory = TableFactory
        self._database_session = UnifiedAlchemyMagicMock()
        self._instance_name = instance_name

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self, table_name: str) -> [Table]:
        table = self._table_factory.create_form_table_model(table_name)
        records = self._database_session.query(table).all()
        print(F'Fake service {self._instance_name}: get_records count {len(records)}')
        return records

    def add_record(self, record: Table):
        print(F'Fake service {self._instance_name}: add_record {record.Serial_Number}')
        self._database_session.add(record)

    def delete_records(self):
        print(F'Fake service {self._instance_name }: delete_records')
        pass
