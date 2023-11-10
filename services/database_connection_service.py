import pymysql
import sqlalchemy
from google.cloud.sql.connector import Connector, IPTypes

from models.database_connection_model import SqlConnectionModel


class SqlCloudService:
    def get_database(self, sql_connection: SqlConnectionModel) -> sqlalchemy.engine.base.Engine:

        connection = self.__get_connection(sql_connection)

        pool = sqlalchemy.create_engine(
            sql_connection.database_url,
            creator=connection,
            pool_pre_ping=True
        )
        return pool

    @staticmethod
    def __get_connection(sql_connection: SqlConnectionModel) -> pymysql.connections.Connection:
        connector = Connector(sql_connection.ip_connection_type)

        connection: pymysql.connections.Connection = connector.connect(
            sql_connection.database_instance_name,
            sql_connection.database_driver,
            user=sql_connection.database_username,
            password=sql_connection.database_password,
            db=sql_connection.database_name,
        )
        return connection
