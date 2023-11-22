from google.cloud.sql.connector import IPTypes
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory
from models.database_connection_model import DatabaseConnectionModel
from services.database_connection_service import DatabaseConnectionService
from services.database_orm_service import DatabaseOrmService
from services.database_service import DatabaseService

connection_model_source = DatabaseConnectionModel(
    instance_name="ons-blaise-v2-dev-b4team:europe-west2:bens-clone2",
    database_name="blaise",
    database_driver="pymysql",
    database_url="mysql+pymysql://",
    database_username="blaise",
    database_password="6Nf6nOoLPQ96ETpU",
    database_ip_connection_type=IPTypes.PUBLIC
)

connection_model_destination = DatabaseConnectionModel(
    instance_name="ons-blaise-v2-dev-b4team:europe-west2:blaise-dev-0aa908fa",
    database_name="blaise",
    database_driver="pymysql",
    database_url="mysql+pymysql://",
    database_username="blaise",
    database_password="6Nf6nOoLPQ96ETpU",
    database_ip_connection_type=IPTypes.PUBLIC
)
table_factory = TableFactory()

source_database = DatabaseConnectionService(connection_model_source).get_database()
source_session = Session(source_database)
source_database_service = DatabaseService(source_session, table_factory)

destination_database = DatabaseConnectionService(connection_model_destination).get_database()
destination_session = Session(destination_database)
destination_database_service = DatabaseService(destination_session, table_factory)

databaseOrmService = DatabaseOrmService(source_database_service, destination_database_service)

databaseOrmService.copy_table_data("LMS2310_GP1_Form")
