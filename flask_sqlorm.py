from sqlorm import Engine, Model as _Model, get_current_session, init_db, migrate, create_all
from sqlorm.engine import session_context
import sqlorm
import abc
import os
import click
from flask import g, abort, has_request_context
from flask.cli import AppGroup
from werkzeug.local import LocalProxy


class FlaskSQLORM:
    def __init__(self, app=None, *args, **kwargs):
        if app:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, database_uri="sqlite://:memory:", **engine_kwargs):
        self.app = app

        for key in dir(sqlorm):
            if not key.startswith("_") and not hasattr(self, key):
                setattr(self, key, getattr(sqlorm, key))

        config = app.config.get_namespace("SQLORM_")
        database_uri = config.pop("uri", database_uri)
        for key, value in engine_kwargs.items():
            config.setdefault(key, value)
        config.setdefault("logger", app.logger)
        if database_uri.startswith("sqlite://"):
            config.setdefault("fine_tune", True)

        self.engine = Engine.from_uri(database_uri, **config)
        self.session = LocalProxy(get_current_session)
        self.Model = Model.bind(self.engine)

        @app.before_request
        def start_db_session():
            g.sqlorm_session = self.engine.make_session()
            session_context.push(g.sqlorm_session)

        @app.after_request
        def close_db_session(response):
            session_context.pop()
            g.sqlorm_session.close()
            return response
        
        cli = AppGroup("db", help="Commands to manage your database")

        @cli.command()
        def init():
            """Initializes the database, either creating tables for models or running migrations if some exists"""
            self.init_db()

        @cli.command()
        def create_all():
            """Create all tables associated to models"""
            self.create_all()

        @cli.command()
        @click.option("--from", "from_", type=int)
        @click.option("--to", type=int)
        @click.option("--dryrun", is_flag=True)
        @click.option("--ignore-schema-version", is_flag=True)
        def migrate(from_, to, dryrun, ignore_schema_version):
            """Run database migrations from the migrations folder in your app root path"""
            self.migrate(from_version=from_, to_version=to, dryrun=dryrun, use_schema_version=not ignore_schema_version)

        app.cli.add_command(cli)

    def __enter__(self):
        if has_request_context():
            return g.sqlorm_session.__enter__()
        return self.engine.__enter__()

    def __exit__(self, exc_type, exc_value, exc_tb):
        if has_request_context():
            g.sqlorm_session.__exit__(exc_type, exc_value, exc_tb)
        else:
            self.engine.__exit__(exc_type, exc_value, exc_tb)

    def create_all(self, **kwargs):
        kwargs.setdefault("model_registry", self.Model.__model_registry__)
        with self.engine:
            create_all(**kwargs)

    def init_db(self, **kwargs):
        kwargs.setdefault("path", os.path.join(self.app.root_path, "migrations"))
        kwargs.setdefault("model_registry", self.Model.__model_registry__)
        kwargs.setdefault("logger", self.app.logger)
        with self.engine:
            init_db(**kwargs)

    def migrate(self, **kwargs):
        kwargs.setdefault("path", os.path.join(self.app.root_path, "migrations"))
        kwargs.setdefault("logger", self.app.logger)
        with self.engine:
            migrate(**kwargs)
    

class Model(_Model, abc.ABC):
    @classmethod
    def find_one_or_404(cls, *args, **kwargs):
        obj = cls.find_one(*args, **kwargs)
        if not obj:
            abort(404)
        return obj

    @classmethod
    def get_or_404(cls, *args, **kwargs):
        obj = cls.get(*args, **kwargs)
        if not obj:
            abort(404)
        return obj
