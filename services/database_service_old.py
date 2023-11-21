import pymysql
import sqlalchemy

from google.cloud.sql.connector import Connector
from sqlalchemy import MetaData, Table, text, insert, Engine
from sqlalchemy.orm import Session

from models.database_connection_model import DatabaseConnectionModel


class DatabaseService:

    def __init__(self, connection_model: DatabaseConnectionModel):
        self._connection_model = connection_model

    def copy_table_data(self, table_name: str, source_instance_name: str, destination_instance_name: str):
        source_database_engine = self.__get_database(source_instance_name)
        destination_database_engine = self.__get_database(destination_instance_name)
        source_table = self.__get_table(source_database_engine, table_name)
        destination_table = self.__get_table(destination_database_engine, table_name)

        with Session(source_database_engine) as source_session:
            print('source_session ', source_session)
            table_data = source_session.execute(source_table.select())

            with Session(destination_database_engine) as destination_session:
                print('destination_session ', destination_session)
                destination_session.begin()
                destination_session.execute(destination_table.delete())
                for row in table_data:
                    insert_statement = insert(destination_table).values(row)
                    print(insert_statement)
                    destination_session.execute(insert_statement)
                destination_session.commit()

    def __get_database(self, instance_name: str) -> Engine:
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
        connector = Connector(sql_connection.database_ip_connection_type)

        return connector.connect(
            instance_connection_string=instance_name,
            driver=sql_connection.database_driver,
            user=sql_connection.database_username,
            password=sql_connection.database_password,
            db=sql_connection.database_name,
        )
