from sqlalchemy import Table
from sqlalchemy.orm import Session


class DatabaseService:
    def __init__(self, database_session: Session):
        self._database_session = database_session

    @property
    def session(self) -> Session:
        return self._database_session

    def get_records(self, table: Table) -> [Table]:
        return self._database_session.query(table).all()

    def add_record(self, record: Table):
        self._database_session.merge(record)

    def delete_records(self, table: Table):
        return self._database_session.query(table).delete()
