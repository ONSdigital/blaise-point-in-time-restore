import pymysql
import sqlalchemy
from google.cloud.sql.connector import Connector
from sqlalchemy import MetaData, Table, text, insert

from models.database_connection_model import DatabaseConnectionModel


class DatabaseService2:

    def __init__(self, connection_model: DatabaseConnectionModel):
        self._connection_model = connection_model

    def copy_table_data(self, table_name: str, source_instance_name: str, destination_instance_name: str):
        source_database = self.__get_database(source_instance_name)
        dest_database = self.__get_database(destination_instance_name)
        source_table = self.__get_table(source_database, table_name)
        dest_table = self.__get_table(dest_database, table_name)

        with source_database.connect() as source_connection:
            table_data = source_connection.execute(source_table.select())

            with dest_database.connect() as dest_connection:
                dest_connection.execute(text("truncate " + table_name))
                for row in table_data:
                    insert_statement = insert(dest_table).values(row)
                    dest_connection.execute(insert_statement)

                dest_connection.commit()

    def __get_database(self, instance_name: str) -> sqlalchemy.engine.base.Engine:
        connection = self.__get_connection(instance_name, self._connection_model)

        return sqlalchemy.create_engine(
            url=self._connection_model.database_url,
            creator=connection,
            pool_pre_ping=True
        )

    @staticmethod
    def __get_table(database, table_name: str):
        meta_data = MetaData()
        meta_data.reflect(bind=database)

        return Table(table_name, meta_data)

    @staticmethod
    def __get_connection(instance_name: str, sql_connection: DatabaseConnectionModel) -> pymysql.connections.Connection:
        connector = Connector(sql_connection.ip_connection_type)

        return connector.connect(
            instance_connection_string=instance_name,
            driver=sql_connection.database_driver,
            user=sql_connection.database_username,
            password=sql_connection.database_password,
            db=sql_connection.database_name,
        )