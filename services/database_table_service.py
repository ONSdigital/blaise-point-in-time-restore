from sqlalchemy import Table
from sqlalchemy.orm import Session


class DatabaseTableService:
    def __init__(self, table: Table, source_database_session: Session):
        self._table = table
        self._source_database_session = source_database_session
        pass

    def session(self) -> Session:
        return self._source_database_session

    def get_records(self) -> [Table]:
        return self._source_database_session.query(self._table).all()

    def add_record(self, record: Table):
        self._source_database_session.merge(record)

    def delete_records(self):
        pass

