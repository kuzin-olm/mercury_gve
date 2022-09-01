import json
from peewee import Model, SqliteDatabase, AutoField, IntegerField, CharField, ForeignKeyField, TextField

from merc_gve.settings import DATABASE_PATH

database = SqliteDatabase(
    DATABASE_PATH,
    pragmas={
        "journal_mode": "wal",  # WAL-mode.
        "cache_size": -64 * 1000,  # 64MB cache.
        "foreign_keys": 1,
        "ignore_check_constraints": 0,
        "synchronous": 0,
    }
)


class BaseModel(Model):
    pk = AutoField(unique=True, primary_key=True)

    class Meta:
        database = database


class User(BaseModel):
    telegram_id = IntegerField(unique=True, null=False)


class Config(BaseModel):
    user = ForeignKeyField(User, backref="configurations")
    mercury_login = CharField(null=False, max_length=255)
    mercury_password = CharField(null=False, max_length=255)
    mercury_cookies = TextField(default=json.dumps(dict()))
