import functions_framework

from models.database_connection_model import DatabaseConnectionModel
from services.database_service import DatabaseService


class DatabaseRestoreService:

    def __init__(self, database_service: DatabaseService):
        self._database_service = database_service

    def restore_questionnaire_data(self, questionnaire_names: [str], source_instance_name: str, destination_instance_name: str):

        if not questionnaire_names:
            raise Exception(
                'You must provide a Questionnaire name'
            )

        if not source_instance_name or not source_instance_name.strip():
            raise Exception(
                'You must provide a source instance name'
            )

        if not destination_instance_name or not destination_instance_name.strip():
            raise Exception(
                'You must provide a destination instance name'
            )

        table_names = []
        for name in questionnaire_names:
            table_names.append(F'{name}_DML')
            table_names.append(F'{name}_FORM')

        self.__restore_tables(table_names, source_instance_name, destination_instance_name)

    def __restore_tables(self, table_names: [str], source_instance: str, destination_instance: str):

        for table_name in table_names:
            self._database_service.copy_table_data(table_name, source_instance, destination_instance)

        return
