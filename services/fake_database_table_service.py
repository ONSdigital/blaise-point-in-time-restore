from sqlalchemy.orm import Session

from services.database_table_service import DatabaseTableService


class FakeDatabaseTableService(DatabaseTableService):
    table_records = []
    throw_error = False

    def throw_error_on_call(self):
        self.throw_error = True
        pass

    def __init__(self):
        # connect to database
        pass

    def session(self) -> Session:
        pass

    def get_records(self) -> [str]:
        return self.table_records

    def add_record(self, record: str):
        if self.throw_error:
            raise Exception("")

        self.table_records.append(record)
        pass

    def delete_records(self):
        self.table_records.clear()
        pass

