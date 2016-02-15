import sqlite3
from contextlib import closing

from flask import Flask, g, request, flash, jsonify, abort

# config
DATABASE = 'C:\\Users\\m_por\\Databases\\KidQuest.db'
DEBUG = True
SECRET_KEY = 'DEVKEY'
USERNAME = 'admin'
PASSWORD = 'default'

app = Flask(__name__)
app.config.from_object(__name__)


def connect_db():
    return sqlite3.connect('C:\\Users\\m_por\\Databases\\KidQuest.db')


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
    entries = []
    for row in cur.fetchall():
        entries.append(dict(id=row[0], title=row[1]))
        print(row[0])
        print(row[1])
    print(jsonify(entries))
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


if __name__ == '__main__':
    app.run(host='0.0.0.0')
