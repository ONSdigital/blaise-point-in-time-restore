from google.cloud.sql.connector import IPTypes


class DatabaseConnectionModel:

    def __init__(self,
                 database_name: str, database_username: str, database_password: str,
                 ip_connection_type: IPTypes, database_driver: str, database_url: str):
        self.database_name = database_name
        self.database_username = database_username
        self.database_password = database_password
        self.ip_connection_type = ip_connection_type
        self.database_driver = database_driver
        self.database_url = database_url


