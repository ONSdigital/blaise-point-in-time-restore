import pymysql
import sqlalchemy
from google.cloud.sql.connector import Connector

from models.database_connection_model import DatabaseConnectionModel


class DatabaseConnectionService:
    def get_database(self, sql_connection: DatabaseConnectionModel) -> sqlalchemy.engine.base.Engine:
        connection = self.__get_connection(sql_connection)

        return sqlalchemy.create_engine(
            url=sql_connection.database_url,
            creator=connection,
            pool_pre_ping=True
        )

    @staticmethod
    def __get_connection(sql_connection: DatabaseConnectionModel) -> pymysql.connections.Connection:
        connector = Connector(sql_connection.ip_connection_type)

        return connector.connect(
            instance_connection_string=sql_connection.database_instance_name,
            driver=sql_connection.database_driver,
            user=sql_connection.database_username,
            password=sql_connection.database_password,
            db=sql_connection.database_name,
        )
