from datetime import datetime
from typing import Optional, Any

from sqlalchemy import BIGINT, Integer, String, DateTime, BLOB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class QuestionnaireFormTable(Base):

    def __init__(self, table_name: str, **kw: Any):
        super().__init__(**kw)
        super.__tablename__ = table_name


    #__tablename__ = 'LMS2310_GP1_Form'
    #__tablename__ = ""
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