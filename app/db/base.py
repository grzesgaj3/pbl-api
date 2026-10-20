from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


PRIMARY_KEY_TYPE = Integer().with_variant(BigInteger, "mysql")
