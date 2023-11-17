from google.cloud.sql.connector import IPTypes

from models.database_connection_model import DatabaseConnectionModel
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

databaseOrmService = DatabaseOrmService(connection_model)

databaseOrmService.get_table_data("LMS2310_GP1_Form")
