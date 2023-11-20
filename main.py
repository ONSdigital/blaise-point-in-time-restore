from google.cloud.sql.connector import IPTypes
from sqlalchemy.orm import Session

from models.database_connection_model import DatabaseConnectionModel
from services.database_connection_service import DatabaseConnectionService
from services.database_orm_service import DatabaseOrmService

connection_model = DatabaseConnectionModel(
    instance_name="ons-blaise-v2-dev-b4team:europe-west2:bens-clone2",
    database_name="blaise",
    database_driver="pymysql",
    database_url="mysql+pymysql://",
    database_username="blaise",
    database_password="6Nf6nOoLPQ96ETpU",
    database_ip_connection_type=IPTypes.PUBLIC
)

source_database = DatabaseConnectionService(connection_model).get_database()
session = Session(source_database)
databaseOrmService = DatabaseOrmService()
databaseOrmService.get_case_ids("LMS2310_GP1_Form", session)
