from sqlalchemy import Column, String, Integer, BigInteger, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
import database

class Router(database.Base):
    __tablename__ = 'router'

    launcher_id = Column(String(64), primary_key=True, unique=True)
    current_coin_id = Column(String(64))
    current_height = Column(BigInteger)
    network = Column(String)

class Pair(database.Base):
    __tablename__ = 'pairs'

    launcher_id = Column(String(64), primary_key=True, unique=True)
    name = Column(String)
    short_name = Column(String)
    image_url = Column(String)
    verified = Column(Boolean)
    asset_id = Column(String(64))
    liquidity_asset_id = Column(String(64))
    current_coin_id = Column(String(64))
    xch_reserve = Column(BigInteger)
    token_reserve = Column(BigInteger)
    liquidity = Column(BigInteger)
    trade_volume = Column(BigInteger, default=0)

class Transaction(database.Base):
    __tablename__ = 'transactions'

    coin_id = Column(String(64), primary_key=True, unique=True)
    pair_launcher_id = Column(String(64))
    operation = Column(String)
    input = Column(JSON)
    output = Column(JSON)
    height = Column(BigInteger)
