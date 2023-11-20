from sqlalchemy import Table
from sqlalchemy.orm import Session


class DatabaseOrmService:
    def get_case_ids(self, table: Table, source_database_session: Session) -> [int]:

        case_id_list = []
        table_rows = source_database_session.query(table).all()
        for table_row in table_rows:
            case_id_list.append(table_row.Serial_Number)
            print(table_row.Serial_Number)

        return case_id_list

    def copies_table_data(self, table: Table, source_database_session: Session, destination_database_session: Session) -> None:
        table_rows = source_database_session.query(table).all()

        for table_row in table_rows:
            local_table_row = destination_database_session.merge(table_row)
            destination_database_session.merge(local_table_row)


