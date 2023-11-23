import sqlalchemy
from google.cloud.sql.connector import Connector
from sqlalchemy import Engine

from models.database_connection_model import DatabaseConnectionModel


class DatabaseConnectionService:
    def __init__(self, connection_model: DatabaseConnectionModel):
        self._connection_model = connection_model

    def get_database(self) -> Engine:
        return sqlalchemy.create_engine(
            url=self._connection_model.database_url,
            creator=self.get_connector,
            pool_pre_ping=True
        )

    def get_connector(self) -> Connector:
        connector = Connector(self._connection_model.database_ip_connection_type)
        return connector.connect(
            instance_connection_string=self._connection_model.instance_name,
            driver=self._connection_model.database_driver,
            user=self._connection_model.database_username,
            password=self._connection_model.database_password,
            db=self._connection_model.database_name,
        )
