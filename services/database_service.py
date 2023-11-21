from sqlalchemy import Table
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory


class DatabaseService:
    def __init__(self, source_database_session: Session, table_factory: TableFactory):
        self._table_factory = table_factory
        self._database_session = source_database_session

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self, table_name: str) -> [Table]:
        print("Real service: get_records")
        table = self._table_factory.create_form_table_model(table_name)
        return self._database_session.query(table).all()

    def add_record(self, record: Table):
        print("Real service: add_record")
        self._database_session.merge(record)

    def delete_records(self):
        print("Real service: delete_records")
        pass
