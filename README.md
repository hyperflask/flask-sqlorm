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

A session is automatically started everytime an app context is created. Perform queries directly in your endpoints:

```python
@app.route("/tasks")
def list_tasks():
    tasks = Task.find_all()
    return render_template("tasks.html", tasks=tasks)
```

The session is rollbacked at the end of the request.

To commit some data, start a transaction using the db object:

```python
@app.route("/tasks", methods=["POST"])
def create_task():
    with db:
        task = Task.create(title=request.form["title"])
    return render_template("task.html", task=task)
```

The current session is available using `db.session`

## Additional utilities provided by Flask-SQLORM

Model classes have the additional methods:

 - `find_one_or_404`: same as `find_one` but throw a 404 when no results are returned
 - `get_or_404`: same as `get` but throw a 404 when no results are returned

## Managing the schema

Some CLI commands are available under the *db* command group. Check out `flask db --help` for a list of subcommands.

## Configuration

Configure the sqlorm engine using the extension's constructor or `init_app()`. Configuration of the engine is performed using the URI method.
Additional engine parameters can be provided as keyword arguments.

Configuration can also be provided via the app config under the `SQLORM_` namespace. Use `SQLORM_URI` to define the database URI.

## Using multiple engines

You can setup multiple engines via the config and use an [`EngineDispatcher`](https://hyperflask.github.io/sqlorm/engine/#engine-dispatcher) to select an engine to use.

```py
db = FlaskSQLORM(app, "sqlite://:memory:", alt_engines=[{"uri": "sqlite://:memory", "tags": ["readonly"]}])

with db.engines.readonly:
    # Execute on an engine randomly selected from the one matching the readonly tag

with db.engines:
    # Uses the default engine
```

The context can be used inside other contexts:

```py
@app.route()
def endpoint():
    objs = MyModel.find_all() # uses the default engine (in a non commit transaction)

    with db.engines.master: # uses a random engine matching the master tag (in a committed transaction)
        obj = MyModel.create()

    with db.engines.readonly.session(): # uses a random engine matching the readonly tag (in a non commit transaction)
        objs = MyModel.find_all()
```

You can create more advanced use case by subclassing `EngineDispatcher`. For example, to implement selection based on an http header that can be set by a load balancer to use the closest geographic replica. And use the primary server for write.

```py
from sqlorm import EngineDispatcher

class HeaderEngineDispatcher(EngineDispatcher):
    def select_all(self, tag=None):
        if not tag and self.header and has_request_context() and self.header in request.headers:
            return self.select_all(request.headers[self.header])
        return super().select_all(tag)

db = FlaskSQLORM(app, "postgresql://primary", engine_dispatcher_class=HeaderEngineDispatcher,
                 alt_engines=[{"uri": "postresql://replica1", "tags": ["usa"]},
                              {"uri": "postresql://replica2", "tags": ["europe"]}])

@app.route()
def endpoint():
    MyModel.find_all() # execute on engine selected via header
    with db:
        MyModel.create() # execute on default engine
```