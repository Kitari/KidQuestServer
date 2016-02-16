import sqlite3
from contextlib import closing

from flask import Flask, g, request, flash, jsonify, abort

app = Flask(__name__)
app.config.from_object('linux-dev-settings')


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.before_request
def before_request():
    conn = connect_db()
    g.db = conn


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/quest', methods=['GET'])
def get_quests():
    cur = g.db.execute('SELECT id, title FROM quests ORDER BY id DESC')
    entries = [dict(id=row[0], title=row[1]) for row in cur.fetchall()]
    return jsonify(quests=entries)


@app.route('/quest', methods=['POST'])
def add_quest():
    print(request.json)
    if not request.json or 'title' not in request.json:
        abort(400)
    g.db.execute('INSERT INTO quests (title) VALUES (?)', [request.json['title']])
    g.db.commit()
    flash('New quest submitted')
    return "Saved"


@app.route('/quest/get_staff_pick', methods=['GET'])
def get_staff_pick():
    staff_pick = [
        {"title": "Clean your room",
         "difficultyLevel": "Easy"},
        {"title": "Read a book",
         "difficultyLevel": "Medium"},
        {"title": "Get an A in Maths",
         "difficultyLevel": "Very Hard"},
        {"title": "Shovel snow off the driveway",
         "difficultyLevel": "Easy"},
        {"title": "Wash the dishes",
         "difficultyLevel": "Very Easy"}
    ]
    return jsonify(quests=staff_pick)


@app.route('/quest/get_trending', methods=['GET'])
def get_trending():
    cur = g.db.execute('SELECT title, count(title) FROM quests GROUP BY title ORDER BY count(title) DESC LIMIT 5')
    trending = [dict(title=row[0]) for row in cur.fetchall()]
    return jsonify(quests=trending)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
