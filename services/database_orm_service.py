from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from models.questionnaire_form_table import QuestionnaireFormTable


class DatabaseOrmService:

    def get_connection(self):
        connector = Connector()

        conn = connector.connect(
            "ons-blaise-v2-dev-b4team:europe-west2:bens-clone2",
            "pymysql",
            user="blaise",
            password="6Nf6nOoLPQ96ETpU",
            db="blaise"
        )
        return conn

    def get_table_data(self, table_name):
        # create connection pool
        pool = create_engine(
            "mysql+pymysql://",
            creator=self.get_connection,
        )

        Session = sessionmaker(pool)
        with Session.begin() as session:
            statement = select(QuestionnaireFormTable(table_name))
            table_objects = session.scalars(statement).all()
            for to in table_objects:
                print(to)
