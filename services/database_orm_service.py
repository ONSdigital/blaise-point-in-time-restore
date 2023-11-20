from sqlalchemy import select, Engine
from sqlalchemy.orm import sessionmaker

from functions.factories.table_factory import TableFactory


class DatabaseOrmService:
    def get_case_ids(self, table_name: str, source_database: Engine) -> [int]:

        source_session = sessionmaker(source_database)
        case_id_list = []
        with source_session.begin() as session:
            questionnaire_table = TableFactory().create_form_table_model(table_name)
            select_statement = select(questionnaire_table)
            table_rows = session.scalars(select_statement).all()
            for table_row in table_rows:
                case_id_list.append(table_row.Serial_Number)
                print(table_row.Serial_Number)

        return case_id_list
