from google.cloud.sql.connector import IPTypes


class DatabaseConnectionModel:

    def __init__(self,
                 instance_name: str, database_name: str, database_username: str, database_password: str,
                 database_ip_connection_type: IPTypes, database_driver: str, database_url: str):
        self.instance_name = instance_name
        self.database_name = database_name
        self.database_username = database_username
        self.database_password = database_password
        self.database_ip_connection_type = database_ip_connection_type
        self.database_driver = database_driver
        self.database_url = database_url


