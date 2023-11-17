from services.database_orm_service import DatabaseOrmService

databaseOrmService = DatabaseOrmService()
print(databaseOrmService)
databaseOrmService.get_table_data("LMS2310_GP1_Form")