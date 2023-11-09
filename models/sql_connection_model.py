from google.cloud.sql.connector import IPTypes


class SqlConnectionModel:
    database_instance_name: str
    database_name: str
    database_username: str
    database_password: str
    ip_connection_type: IPTypes
    database_driver: str
    database_url: str