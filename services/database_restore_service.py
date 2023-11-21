from functions.argument_validation import throw_error_if_empty_list, throw_error_if_empty_string
from services.database_service_old import DatabaseService


class DatabaseRestoreService:

    def __init__(self, database_service: DatabaseService):
        self._database_service = database_service

    def restore_questionnaire_data(self, questionnaire_names: [str], source_instance_name: str, destination_instance_name: str):

        throw_error_if_empty_list(questionnaire_names, 'questionnaire_names')
        throw_error_if_empty_string(source_instance_name, 'source_instance_name')
        throw_error_if_empty_string(destination_instance_name, 'destination_instance_name')

        table_names = []
        for name in questionnaire_names:
            table_names.append(F'{name}_DML')
            table_names.append(F'{name}_FORM')

        self.__restore_tables(table_names, source_instance_name, destination_instance_name)

    def __restore_tables(self, table_names: [str], source_instance: str, destination_instance: str):

        for table_name in table_names:
            self._database_service.copy_table_data(table_name, source_instance, destination_instance)

        return
