import functions_framework
import os
import sqlalchemy
import pymysql

from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy.sql import text
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, insert


def connect_with_connector(instance_connection_name) -> sqlalchemy.engine.base.Engine:
    db_user = 'my-db-user'
    db_pass = 'my-db-password'
    db_name = 'my-database'

    ip_type = IPTypes.PUBLIC

    connector = Connector(ip_type)

    def getconn() -> pymysql.connections.Connection:
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
        creator=getconn,
        pool_pre_ping=True
    )
    return pool


@functions_framework.http
def hello_http(request):
    source = connect_with_connector('db:instance:source ')
    source_meta = MetaData()
    source_meta.reflect(bind=source)
    source_connection = source.connect()

    destination = connect_with_connector('db:instance:dest ')
    dest_meta = MetaData()
    dest_meta.reflect(bind=destination)
    dest_connection = destination.connect()

    # declare tables
    table = 'db_table'
    src_table = Table(table, source_meta)
    dest_table = Table(table, dest_meta)

    # select truncate and insert loop
    sel = src_table.select()
    res = source_connection.execute(sel)

    dest_connection.begin()
    dest_connection.execute(text("truncate " + table))
    for row in res:
        stmt = insert(dest_table).values(row)
        dest_connection.execute(stmt)

    dest_connection.commit()

    return "yo yo"



