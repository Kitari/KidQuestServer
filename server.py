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


@app.route('/see_entries', methods=['GET'])
def hello_world():
    cur = g.db.execute('SELECT id, title FROM quests ORDER BY id desc')
    entries = []
    for row in cur.fetchall():
        entries.append(dict(id=row[0], title=row[1]))
        print(row[0])
        print(row[1])
    print(jsonify(entries))
    return jsonify(quests=entries)


@app.route('/add', methods=['POST'])
def add_quest():
    print(request.json)
    if not request.json or 'title' not in request.json:
        abort(400)
    g.db.execute('insert into quests (title) values (?)', [request.json['title']])
    g.db.commit()
    flash('New quest submitted')
    return 200


if __name__ == '__main__':
    app.run(host='0.0.0.0')
