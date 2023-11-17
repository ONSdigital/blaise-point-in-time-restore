from datetime import datetime
from typing import Optional, Any

from sqlalchemy import BIGINT, Integer, String, DateTime, BLOB
from sqlalchemy.orm import Mapped, mapped_column

from models.base_table import Base


class TableFactory:
    @staticmethod
    def create_form_table_model(table_name: str):

        class QuestionnaireFormTable(Base):

            __tablename__ = table_name
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

        return QuestionnaireFormTable
