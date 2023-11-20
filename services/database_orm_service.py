from sqlalchemy import select, Engine
from sqlalchemy.orm import sessionmaker

from functions.factories.table_factory import TableFactory


class DatabaseOrmService:
    def get_case_ids1(self, table_name: str, source_database: Engine) -> [int]:
        source_session = sessionmaker(source_database)
        questionnaire_table_model = TableFactory().create_form_table_model(table_name)
        case_id_list = self.get_case_ids2(source_session, questionnaire_table_model)
        return case_id_list

    def get_case_ids2(self, source_session: sessionmaker, questionnaire_table) -> [int]:

        case_id_list = []
        with source_session.begin() as session:
            select_statement = select(questionnaire_table)
            table_rows = session.scalars(select_statement).all()
            for table_row in table_rows:
                case_id_list.append(table_row.Serial_Number)
                print(table_row.Serial_Number)

        return case_id_list
