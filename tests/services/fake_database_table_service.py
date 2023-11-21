from mock_alchemy.mocking import UnifiedAlchemyMagicMock
from sqlalchemy.testing.schema import Table
from sqlalchemy.orm import Session

from services.database_table_service import DatabaseTableService


class FakeDatabaseTableService(DatabaseTableService):

    def __init__(self, table: Table, instance_name: str):
        self._table = table
        self._database_session = UnifiedAlchemyMagicMock()
        self._instance_name = instance_name

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self) -> [Table]:
        records = self._database_session.query(self._table).all()
        print(F'Fake service {self._instance_name}: get_records count {len(records)}')
        return records

    def add_record(self, record: Table):
        print(F'Fake service {self._instance_name}: add_record {record.Serial_Number}')
        self._database_session.add(record)

    def delete_records(self):
        print(F'Fake service {self._instance_name }: delete_records')
        pass
