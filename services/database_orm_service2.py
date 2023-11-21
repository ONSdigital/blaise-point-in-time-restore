
from services.database_service import DatabaseService


class DatabaseOrmService2:
    def __init__(self, source_database: DatabaseService, destination_database: DatabaseService):
        self._source_database = source_database
        self._destination_database = destination_database

    def copies_table_data(self, table_name: str) -> None:
        with self._source_database.session.begin():
            table_rows = self._source_database.get_records(table_name)

            with self._destination_database.session.begin():
                for table_row in table_rows:
                    self._destination_database.add_record(table_row)






