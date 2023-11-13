import functions_framework

from models.database_connection_model import DatabaseConnectionModel
from services.database_service import DatabaseService


class DatabaseRestoreService:

    @staticmethod
    def restore_tables(self, connection_model: DatabaseConnectionModel,  table_names: [str], source_instance: str, destination_instance: str):
        database_service = DatabaseService(connection_model)

        for table_name in table_names:
            database_service.copy_table_data(table_name, source_instance, destination_instance)

        return

