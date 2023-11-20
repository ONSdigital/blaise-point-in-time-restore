from google.cloud.sql.connector import IPTypes
from sqlalchemy.orm import Session

from functions.factories.table_factory import TableFactory
from models.database_connection_model import DatabaseConnectionModel
from services.database_connection_service import DatabaseConnectionService
from services.database_orm_service import DatabaseOrmService

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

source_database = DatabaseConnectionService(connection_model_source).get_database()
destination_database = DatabaseConnectionService(connection_model_destination).get_database()
source_session = Session(source_database)
destination_session = Session(destination_database)
databaseOrmService = DatabaseOrmService()
source_table_model = TableFactory.create_form_table_model("LMS2310_GP1_Form")
# destination_table_model = TableFactory.create_form_table_model("LMS2310_GP1_Form")

# databaseOrmService.get_case_ids(source_table_model, source_session)
# databaseOrmService.get_case_ids(destination_table_model, destination_session)

databaseOrmService.copies_table_data(source_table_model, source_session, destination_session)
