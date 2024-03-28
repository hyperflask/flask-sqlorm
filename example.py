from flask import Flask, render_template_string, request, redirect, url_for
from flask_sqlorm import FlaskSQLORM
import logging


app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
db = FlaskSQLORM(app)


class Task(db.Model):
    id: db.PrimaryKey[int]
    title: str
    done: bool

    def toggle(self):
        "UPDATE Task SET done = not done WHERE id = %(self.id)s RETURNING done"


db.create_all()


@app.route("/")
def index():
    tasks = Task.find_all()
    return render_template_string("""
        <ul>
            {% for task in tasks %}
                <li>
                    <form action="{{url_for("toggle", task_id=task.id)}}" method="post">
                        <label>
                            <input type="checkbox" {% if task.done %}checked{% endif %} onchange="event.target.form.submit()">
                            {{task.title}}
                        </label>
                    </form>
                </li>
            {% endfor %}
        </ul>
        <form method="post" action="{{url_for("create")}}">
            <input type="text" name="title">
            <button type="submit">Add</button>
        </form>
    """, tasks=tasks)


@app.post("/create")
def create():
    with db:
        Task.create(title=request.form["title"], done=False)
    return redirect(url_for("index"))


@app.post("/toggle/<task_id>")
def toggle(task_id):
    with db:
        task = Task.get_or_404(task_id)
        task.toggle()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=6600)