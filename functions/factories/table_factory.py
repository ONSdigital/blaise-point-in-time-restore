from datetime import datetime
from typing import Optional

from sqlalchemy import BIGINT, Integer, String, DateTime, BLOB, Table
from sqlalchemy.orm import Mapped, mapped_column

from models.base_table import Base


class TableFactory:
    tables: dict[str, Table] = {}

    def get_form_table_model(self, table_name: str):
        class QuestionnaireFormTable(Base):
            __tablename__ = table_name
            __table_args__ = {'extend_existing': True}
            Serial_Number: Mapped[int] = mapped_column(BIGINT())
            FormID: Mapped[int] = mapped_column(BIGINT(), primary_key=True, autoincrement=True)
            ValidationStatus: Mapped[Optional[int]] = mapped_column(Integer())
            Mode: Mapped[Optional[str]] = mapped_column(String(255))
            DataEntryBehaviour: Mapped[Optional[str]] = mapped_column(String(255))
            SaveStatus: Mapped[Optional[str]] = mapped_column(String(255))
            IdentityName: Mapped[Optional[str]] = mapped_column(String(255))
            SourceInfo: Mapped[Optional[str]] = mapped_column(String(255))
            TimeCreated: Mapped[Optional[datetime]] = mapped_column(DateTime())
            LastModification: Mapped[Optional[datetime]] = mapped_column(DateTime())
            DataStream = mapped_column(BLOB())

        if table_name not in self.tables.keys():
            self.tables[table_name] = QuestionnaireFormTable

        return self.tables[table_name]
