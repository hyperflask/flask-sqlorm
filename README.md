# Flask-SQLORM

Flask integration for [sqlorm](https://github.com/hyperflask/sqlorm)

## Setup

Install:

    $ pip install flask-sqlorm

Setup:

```python
from flask import Flask
from flask_sqlorm import FlaskSQLORM

app = Flask()
db = FlaskSQLORM(app, "sqlite://:memory:")
```

## Usage

All exports from the `sqlorm` package are available from the extension instance.

Define some models:

```python
class Task(db.Model):
    id: db.PrimaryKey[int]
    title: str
    done: bool = db.Column(default=False)
```

Start a transaction using the db object:

```python
with db:
    Task.create(title="first task")
```

In views, the current session is available using `db.session`

## Configuration

Configure the sqlorm engine using the extension's constructor or `init_app()`. Configuration of the engine is performed using the URI method.
Additional engine parameters can be provided as keyword arguments.

Configuration can also be provided via the app config under the `SQLORM_` namespace. Use `SQLORM_URI` to define the database URI.

## Additional utilities provided by Flask-SQLORM

Model classes have the additional methods:

 - `find_one_or_404`: same as `find_one` but throw a 404 when no results are returned
 - `get_or_404`: same as `get` but throw a 404 when no results are returned

## Managing the schema

Some CLI commands are available under the *db* command group. Check out `flask db --help` for a list of subcommands.