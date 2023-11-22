from sqlalchemy import Table
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory


class DatabaseService:
    def __init__(self, database_session: Session, table_factory: TableFactory):
        self._database_session = database_session
        self._table_factory = table_factory

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self, table_name: str) -> [Table]:
        table = self._table_factory.get_form_table_model(table_name)
        return self._database_session.query(table).all()

    def add_record(self, record: Table):
        self._database_session.merge(record)

    def delete_records(self, table_name: str):
        table = self._table_factory.get_form_table_model(table_name)
        return self._database_session.query(table).delete()
