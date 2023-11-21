from sqlalchemy import Table
from sqlalchemy.orm import Session

from services.database_table_service import DatabaseTableService


class DatabaseOrmService2:
    def copies_table_data(self, source_database: DatabaseTableService, destination_database: DatabaseTableService) -> None:
        with source_database.session.begin():
            table_rows = source_database.get_records()

            with destination_database.session.begin():
                for table_row in table_rows:
                    destination_database.add_record(table_row)






