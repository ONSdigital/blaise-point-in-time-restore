import pymysql
import sqlalchemy
from google.cloud.sql.connector import Connector
from sqlalchemy import select, Engine, create_engine
from sqlalchemy.orm import sessionmaker

from models.database_connection_model import DatabaseConnectionModel
from models.questionnaire_form_table import CreateTableModelFactory


class DatabaseOrmService:
    def __init__(self, connection_model: DatabaseConnectionModel):
        self._connection_model = connection_model

    def get_table_data(self, table_name: str):
        source_database_engine = self.__get_database_engine()

        source_session = sessionmaker(source_database_engine)
        with source_session.begin() as session:
            questionnaire_table = CreateTableModelFactory().create_form_table_model(table_name)
            select_statement = select(questionnaire_table)
            table_rows = session.scalars(select_statement).all()
            for table_row in table_rows:
                print(table_row.Serial_Number)

    def __get_database_engine(self) -> Engine:
        return create_engine(
            url=self._connection_model.database_url,
            creator=self.__get_connection,
            pool_pre_ping=True
        )

    def __get_connection(self) -> Connector:
        connector = Connector(self._connection_model.database_ip_connection_type)

        connector = connector.connect(
            instance_connection_string=self._connection_model.instance_name,
            driver=self._connection_model.database_driver,
            user=self._connection_model.database_username,
            password=self._connection_model.database_password,
            db=self._connection_model.database_name,
        )

        return connector
