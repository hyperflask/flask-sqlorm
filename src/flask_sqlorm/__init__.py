from sqlorm import Engine, EngineDispatcher, Model as _Model, get_current_session, init_db, migrate, create_all, PrimaryKey as PrimaryKey
from sqlorm.engine import session_context
from sqlorm.schema import create_initial_migration, set_schema_version
import sqlorm
import abc
import os
import click
from flask import g, abort
from flask.signals import appcontext_pushed, appcontext_tearing_down
from flask.cli import AppGroup
from werkzeug.local import LocalProxy


try:
    from .encrypted import Encrypted
except ImportError:
    Encrypted = None


session = LocalProxy(get_current_session)


class FlaskSQLORM:
    def __init__(self, app=None, *args, **kwargs):
        for key in dir(sqlorm):
            if not key.startswith("_") and not hasattr(self, key):
                setattr(self, key, getattr(sqlorm, key))
        self.Model = Model
        self.Encrypted = Encrypted
        self.session = session
        if app:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, database_uri="sqlite://:memory:", migrations_folder="migrations", alt_engines=None,
                 engine_dispatcher_class=EngineDispatcher, **engine_kwargs):
        self.app = app

        config = app.config.get_namespace("SQLORM_")
        self.migrations_folder = os.path.join(app.root_path, config.pop("migrations_folder", migrations_folder))
        alt_engines = config.pop("engines", alt_engines or {})

        database_uri = config.pop("uri", database_uri)
        for key, value in engine_kwargs.items():
            config.setdefault(key, value)   
        self.engine = self.create_engine(database_uri, **config)

        self.engines = engine_dispatcher_class()
        self.engines.register(self.engine, default=True)
        for params in alt_engines.items():
            if isinstance(params, Engine):
                self.engines.register(params)
                continue
            if isinstance(params, (list, tuple)):
                self.engines.register(*params)
                continue
            engine_kwargs = dict(params)
            tags = engine_kwargs.pop("tags", [])
            engine = self.create_engine(engine_kwargs.pop("uri"), **engine_kwargs)
            self.engines.register(engine, tags)

        def on_appcontext_pushed(app, **kw):
            g.sqlorm_session = self.engines.select().make_session()
            session_context.push(g.sqlorm_session)
        appcontext_pushed.connect(on_appcontext_pushed, weak=False)

        def on_appcontext_tearing_down(app, **kw):
            session_context.pop()
            g.sqlorm_session.close()
        appcontext_tearing_down.connect(on_appcontext_tearing_down, weak=False)
        
        cli = AppGroup("db", help="Commands to manage your database")

        @cli.command()
        def init():
            """Initializes the database, either creating tables for models or running migrations if some exists"""
            self.init_db()

        @cli.command()
        @click.argument("models", nargs=-1)
        @click.option("--version", default=None)
        @click.option("--set-version", is_flag=True)
        def init_migrations(models, version, set_version):
            """Initializes migrations"""
            header, version, name = self.init_migrations(models=models, version=version, set_version=set_version)
            click.echo(f"Created migration: {version}_{name}.sql ({header})")

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

    def create_engine(self, database_uri, **engine_kwargs):
        engine_kwargs.setdefault("logger", self.app.logger)
        if database_uri.startswith("sqlite://"):
            engine_kwargs.setdefault("fine_tune", True)
            engine_kwargs.setdefault("foreign_keys", True)
        return Engine.from_uri(database_uri, **engine_kwargs)

    def __enter__(self):
        return self.engine.__enter__()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.engine.__exit__(exc_type, exc_value, exc_tb)

    def create_all(self, **kwargs):
        kwargs.setdefault("model_registry", self.Model.__model_registry__)
        with self.app.app_context(), self.engine:
            create_all(**kwargs)

    def init_db(self, **kwargs):
        kwargs.setdefault("path", self.migrations_folder)
        kwargs.setdefault("model_registry", self.Model.__model_registry__)
        kwargs.setdefault("logger", self.app.logger)
        with self.app.app_context(), self.engine:
            init_db(**kwargs)

    def init_migrations(self, models=None, version=None, set_version=False, **kwargs):
        os.makedirs(self.migrations_folder, exist_ok=True)
        kwargs.setdefault("path", self.migrations_folder)
        kwargs.setdefault("model_registry", self.Model.__model_registry__)
        header, version, name = create_initial_migration(version=version, models=models, **kwargs)
        if set_version:
            with self.engine:
                set_schema_version(version)
        return (header, version, name)

    def migrate(self, **kwargs):
        kwargs.setdefault("path", self.migrations_folder)
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
