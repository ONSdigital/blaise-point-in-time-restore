import functions_framework
import os
import sqlalchemy
import pymysql

from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy.sql import text
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, insert

from models.database_connection_model import DatabaseConnectionModel
from services.database_service import DatabaseService


def connect_with_connector(instance_connection_name) -> sqlalchemy.engine.base.Engine:
    db_user = 'my-db-user'
    db_pass = 'my-db-password'
    db_name = 'my-database'

    ip_type = IPTypes.PUBLIC

    connector = Connector(ip_type)

    def get_connection() -> pymysql.connections.Connection:
        conn: pymysql.connections.Connection = connector.connect(
            instance_connection_name,
            "pymysql",
            user=db_user,
            password=db_pass,
            db=db_name,
        )
        return conn

    pool = sqlalchemy.create_engine(
        "mysql+pymysql://",
        creator=get_connection,
        pool_pre_ping=True
    )
    return pool


@functions_framework.http
def hello_http(request):
    source_connection_model = DatabaseConnectionModel()
    source_database_service = DatabaseService(source_connection_model)

    destination_connection_model = DatabaseConnectionModel()
    destination_database_service = DatabaseService(destination_connection_model)

    # declare tables
    table_name = "table"
    # select truncate and insert loop
    table_data = source_database_service.get_table_data(table_name)
    destination_database_service.write_table_data(table_name, table_data)

    return "yo yo yo"
