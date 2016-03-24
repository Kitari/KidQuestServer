import re

from flask import Flask, jsonify, abort, request, g, Blueprint
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.sqlalchemy import SQLAlchemy, orm
from sqlalchemy import func

from models import User, Quest, db

auth = HTTPBasicAuth()
api = Blueprint('api', __name__, url_prefix="/api")

def create_app(config_file='config.py', debug=False):
    app = Flask(__name__)
    app.debug = debug
    app.config.from_pyfile(config_file)

    db.init_app(app)

    with app.app_context():
        db.create_all()


    # db.engine.execute("PRAGMA foreign_keys=ON")
    # sm = orm.sessionmaker(bind=db, autoflush=True, autocommit=True, expire_on_commit=True)
    # session = orm.scoped_session(sm)
    app.register_blueprint(api)
    return app


@auth.verify_password
def verify_password(email_or_token, password):
    user = User.verify_auth_token(email_or_token)
    if not user:
        # try to authenticate with email and password
        user = User.query.filter_by(email=email_or_token).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True


def verify_user(c):
    if c is None:
        abort(404)
    # Check if logged in user is the same as parameterized user.
    if g.user is None or g.user is not c:
        abort(401)


@api.route('/token/')
@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token()
    id = g.user.id
    return jsonify({'token': token.decode('ascii'), 'id': id})


@api.route('/users/', methods=['POST'])
def create_user():
    required_json = ['email', 'password']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    email = json.get('email')
    password = json.get('password')

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        abort(400, "Invalid email")

    if User.query.filter_by(email=email).first() is not None:
        abort(409)  # existing user

    user = User(email=email)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.serialize()), 201


@api.route('/users/<int:user_id>/', methods=['GET', 'PUT'])
@auth.login_required
def detail_user(user_id):
    user = User.query.get(user_id)
    verify_user(user)

    if request.method == 'GET':
        return jsonify(user.serialize())

    elif request.method == 'PUT':
        json = request.json
        if 'parent_id' in json:
            db.session.query(User).filter_by(id=user_id).update({"parent_id": json['parent_id']})

        db.session.commit()
        return jsonify(user.serialize())


@api.route('/users/<int:user_id>/quests/', methods=['POST', 'GET'])
@auth.login_required
def add_quest_to_user(user_id):
    user = User.query.get(user_id)
    verify_user(user)

    if request.method == 'GET':
        return jsonify(quests=[q.serialize() for q in user.quests])

    elif request.method == 'POST':
        required_json = ['title', 'difficulty_level']
        json = request.json

        if not valid_json(json, required_json):
            abort(400)

        quest = Quest(title=json.get('title'), user_id=user_id, difficulty_level=json.get('difficulty_level'))

        if json['description']:
            quest.description = json['description']

        db.session.add(quest)
        db.session.commit()

        return jsonify(quest.serialize()), 201


@api.route('/users/<int:user_id>/quests/<int:quest_id>/', methods=['GET', 'PUT'])
@auth.login_required
def user_quests(user_id, quest_id):
    user = User.query.get(user_id)
    verify_user(user)

    quest = Quest.query.get(quest_id)
    if quest is None:
        abort(404)

    if quest not in user.quests:
        abort(401)

    if request.method == 'GET':
        return jsonify(quest.serialize())
    elif request.method == 'PUT':
        json = request.json

        quest = db.session.query(Quest).filter_by(id=quest_id)
        if 'confirmed' in json:
            quest.update({"confirmed": json['confirmed']})
        if 'completed' in json:
            quest.update({"completed": json['completed']})
        db.session.commit()

        return jsonify(quest.first().serialize())


def valid_json(json, required_json):
    if not json:
        return False
    elif any(x not in json for x in required_json):
        return False
    else:
        return True


@api.route('/quests/trending/', methods=['GET'])
def trending_quests():
    quests = db.session.query(Quest.title, func.count(Quest.title)).group_by(Quest.title).all()
    qs = [dict(title=q.title, difficulty_level="Medium") for q in quests]
    return jsonify(quests=qs)


@api.route('/quests/staff_pick/', methods=['GET'])
def get_staff_pick():
    staff_pick = [
        {"title": "Clean your room",
         "difficulty_level": "Easy"},
        {"title": "Read a book",
         "difficulty_level": "Medium"},
        {"title": "Get an A in Maths",
         "difficulty_level": "Very Hard"},
        {"title": "Shovel snow off the driveway",
         "difficulty_level": "Easy"},
        {"title": "Wash the dishes",
         "difficulty_level": "Very Easy"}
    ]
    return jsonify(quests=staff_pick)


def complete_quest(quest):
    user = quest.user
    character = user.character

    gold = 100  # TODO: determine gold reward
    xp = 100  # TODO: determine xp reward

    character.gold += gold
    character.xp += xp

    character.update({'gold': character.gold})
    character.update({'xp': character.xp})

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0')
