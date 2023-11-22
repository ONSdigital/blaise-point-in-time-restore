from functions.factories.table_factory import TableFactory
from models.database_connection_model import DatabaseConnectionModel
from services.database_orm_service import DatabaseOrmService
from services.database_service import DatabaseService


class DatabaseRestoreService:

    def __init__(self, table_factory: TableFactory, database_orm_service: DatabaseOrmService):
        self._table_factory = table_factory
        self._database_orm_service = database_orm_service

    def restore_data_for_questionnaire(self, questionnaire_name: str):

        questionnaire_tables = self._table_factory.get_table_models(questionnaire_name)
        for table in questionnaire_tables:
            self._database_orm_service.copy_table_data(table)
