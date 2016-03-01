from flask import Flask, jsonify, abort, request, g
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import func

from models import User, Quest

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)
db.init_app(app)
db.engine.execute("PRAGMA foreign_keys=ON")

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(email, password):
    user = User.query.filter_by(email=email).first()

    if user and user.verify_password(password):
        g.user = user
        return True


def verify_user(c):
    # Check if logged in user is the same as parameterized user.
    if g.user is None or g.user is not c:
        abort(401)


@app.route('/users/', methods=['POST'])
def create_child():
    required_json = ['email', 'password']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    email = json.get('email')
    password = json.get('password')

    if User.query.filter_by(email=email).first() is not None:
        abort(409)  # existing user

    child = User(email=email)
    child.hash_password(password)
    db.session.add(child)
    db.session.commit()
    return jsonify(child.serialize()), 201


@app.route('/users/<int:user_id>/', methods=['GET', 'PUT'])
@auth.login_required
def detail_user(user_id):
    user = User.query.get(user_id)
    verify_user(user)

    if user is None:
        abort(404)

    if request.method == 'GET':
        return jsonify(user.serialize()), 201

    elif request.method == 'PUT':
        if 'email' in request.json:
            user.email = request.json['email']
            db.session.add(user)
            db.session.commit()
        if 'parent_id' in request.json:
            parent = User.query.get(request.json['parent_id'])
            user.parent = parent
            user.save()
        return jsonify(user.serialize()), 201


@app.route('/users/<int:user_id>/quests/', methods=['POST'])
@auth.login_required
def add_quest_to_child(user_id):
    required_json = ['title']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    child = User.query.get(user_id)
    verify_user(child)

    quest = Quest(title=json.get('title'), user_id=user_id)
    db.session.add(quest)
    db.session.commit()
    return jsonify(quest.serialize()), 201


def valid_json(json, required_json):
    if not json:
        return False
    elif any(x not in json for x in required_json):
        return False
    else:
        return True


@app.route('/quests/trending/', methods=['GET'])
def trending_quests():
    quests = db.session.query(Quest.title, func.count(Quest.title)).group_by(Quest.title).all()
    qs = [dict(title=q.title, difficultyLevel="Medium") for q in quests]
    return jsonify(quests=qs)


@app.route('/quests/staff_pick', methods=['GET'])
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
