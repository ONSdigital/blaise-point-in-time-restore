import functions_framework

from models.database_connection_model import DatabaseConnectionModel
from services.database_service2 import DatabaseService2


class DatabaseRestoreService2:

    @staticmethod
    def database_restore(self, connection_model: DatabaseConnectionModel,  table_names: [str], source_instance: str, destination_instance: str):
        database_service = DatabaseService2(connection_model)

        for table_name in table_names:
            database_service.copy_table_data(table_name, source_instance, destination_instance)

        return
