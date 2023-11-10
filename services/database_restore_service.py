import functions_framework

from models.database_connection_model import DatabaseConnectionModel
from services.database_service import DatabaseService


class DatabaseRestoreService:

    @staticmethod
    def database_restore(self, source_connection_model: DatabaseConnectionModel, destination_connection_model: DatabaseConnectionModel, table_name: str):
        source_database_service = DatabaseService(source_connection_model)
        destination_database_service = DatabaseService(destination_connection_model)

        # select truncate and insert loop
        table_data = source_database_service.get_table_data(table_name)
        destination_database_service.write_table_data(table_name, table_data)

        return
