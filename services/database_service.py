import pymysql
import sqlalchemy
from google.cloud.sql.connector import Connector
from sqlalchemy import MetaData, Table, CursorResult, text, insert

from models.database_connection_model import DatabaseConnectionModel


class DatabaseService:

    def __init__(self, connection_model: DatabaseConnectionModel):
        self._connection_model = connection_model
        self._database = self.__get_database(self._connection_model)
        self._meta = MetaData()
        self._meta.reflect(bind=self._database)

    def get_table_data(self, table_name: str) -> CursorResult:
        table = Table(table_name, self._meta)
        select_statement = table.select()
        with self._database.connect() as connection:
            return connection.execute(select_statement)

    def write_table_data(self, table_name: str, table_data: CursorResult):
        table = Table(table_name, self._meta)
        with self._database.connect() as connection:
            connection.execute(text("truncate " + table_name))
            for row in table_data:
                insert_statement = insert(table).values(row)
                connection.execute(insert_statement)

            connection.commit()

    def __get_database(self, sql_connection: DatabaseConnectionModel) -> sqlalchemy.engine.base.Engine:
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
