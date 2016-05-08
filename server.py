import datetime
import re

from flask import Flask, jsonify, abort, request, g, Blueprint
from flask.ext.httpauth import HTTPBasicAuth
from gcm import GCM
from sqlalchemy import func

from config import GCM_API_KEY
from models import User, Quest, db, Reward

auth = HTTPBasicAuth()
api = Blueprint('api', __name__, url_prefix="/api")

LEVEL_GAIN = 0.04


def create_app(config_file='config.py', debug=False):
    app = Flask(__name__)
    app.debug = debug
    app.config.from_pyfile(config_file)

    db.init_app(app)

    with app.app_context():
        db.create_all()

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
        abort(400)
    # Check if logged in user is the same as parameterized user.
    if g.user is not None and g.user is c:
        return True
    if g.user is c.parent:
        return True
    else:
        abort(401)


@api.route('/token/')
@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token()

    user_is_parent = g.user.is_parent()

    if user_is_parent:
        user_id = g.user.get_child().id
        parent_pin = g.user.get_child().parent_pin
    else:
        user_id = g.user.id
        parent_pin = g.user.parent_pin

    return jsonify({'token': token.decode('ascii'), 'id': user_id, 'parent_pin': parent_pin,
                    'is_parent': user_is_parent})


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
        abort(409, "Email already exists")  # existing user

    user = User(email=email, gcm_id=json.get('gcm_id'), character_name=json.get('character_name'),
                parent_pin=json.get('parent_pin'))
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
        query = db.session.query(User).filter_by(id=user_id)
        if 'parent_id' in json:
            query.update({"parent_id": json['parent_id']})

        if 'gcm_id' in json:
            if user == g.user:
                query.update({"gcm_id": json['gcm_id']})
            else:
                query2 = db.session.query(User).filter_by(id=user.parent_id)
                query2.update({"gcm_id": json['gcm_id']})

        if 'character_name' in json:
            query.update({"character_name": json['character_name']})

        if 'parent_pin' in json:
            query.update({"parent_pin": json['parent_pin']})

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

        diff = json.get('difficulty_level')
        quest = Quest(title=json.get('title'), user_id=user_id, difficulty_level=diff)
        if 'expiry_date' in json:
            quest.expiry_date = json.get('expiry_date')
        quest.xp_reward = calculate_xp_reward(diff, user)
        quest.gold_reward = calc_triangular_difficulty(diff)

        if json['description']:
            quest.description = json['description']

        db.session.add(quest)
        db.session.commit()

        notify_if_partner("A new quest is available!")

        return jsonify(quest.serialize()), 201


@api.route('/users/<int:user_id>/quests/<int:quest_id>/', methods=['GET', 'PUT'])
@auth.login_required
def user_quests(user_id, quest_id):
    user = User.query.get(user_id)
    verify_user(user)

    quest = Quest.query.get(quest_id)
    if quest is None:
        abort(400)

    if quest not in user.quests:
        abort(401)

    if request.method == 'GET':
        return jsonify(quest.serialize())
    elif request.method == 'PUT':
        json = request.json

        quest = db.session.query(Quest).filter_by(id=quest_id)
        if 'completed' in json:
            complete_quest(quest.first())
        if 'confirmed' in json:
            confirm_quest(quest.first())
            # notifies in the method
        db.session.commit()

        return jsonify(quest.first().serialize())


@api.route('/users/<int:user_id>/rewards/', methods=['GET', 'POST'])
@auth.login_required
def user_rewards(user_id):
    # Get the user account relevant to the user_id parameter
    user = User.query.get(user_id)
    # Verify the logged in user is actually the user or an attached user.
    verify_user(user)

    if request.method == 'GET':
        # Return the user's rewards in JSON format.
        return jsonify(rewards=[r.serialize() for r in user.rewards])
    elif request.method == 'POST':
        required_json = ['name', 'cost']
        json = request.json

        if not valid_json(json, required_json):
            abort(400)

        reward = Reward(name=json.get('name'), cost=json.get('cost'), user_id=user_id)

        db.session.add(reward)
        db.session.commit()

        notify_if_partner("A new reward is available in the store!")

        return jsonify(reward.serialize()), 201


@api.route('/users/<int:user_id>/rewards/<int:reward_id>/', methods=['GET', 'PUT'])
@auth.login_required
def user_reward(user_id, reward_id):
    user = User.query.get(user_id)
    verify_user(user)

    reward = Reward.query.get(reward_id)
    if reward is None:
        abort(400, "Reward not found")

    if reward not in user.rewards:
        abort(401, "Not your reward")

    if request.method == 'GET':
        return jsonify(reward.serialize())
    elif request.method == 'PUT':
        json = request.json

        if 'completed' in json:
            reward = db.session.query(Reward).filter_by(id=reward_id).first()
            complete_reward(reward)
            notify_if_partner("A child you are monitoring has purchased a reward from the store")

        return jsonify(reward.serialize())


def valid_json(json, required_json):
    """

    :rtype: bool
    """
    if not json:
        return False
    elif any(x not in json for x in required_json):
        return False
    else:
        return True


@api.route('/quests/getTrending/', methods=['GET'])
def trending_quests():
    quests = db.session.query(Quest.title, func.count(Quest.title)).group_by(Quest.title).all()
    qs = [dict(title=q.title, difficultyLevel="Medium") for q in quests]
    return jsonify(quests=qs)


@api.route('/quests/getStaffPick/', methods=['GET'])
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


def complete_reward(reward):
    user = reward.user

    if not user.gold >= reward.cost:
        abort(400, "Not enough gold")

    user.gold -= reward.cost
    reward.completed = True

    db.session.commit()


def check_level_up(user):
    if user.xp >= user.xp_to_next_level():
        user.xp -= user.xp_to_next_level()
        user.character_level += 1
        db.session.commit()

        check_level_up(user)

        notify_child(user, "You have levelled up!")


def confirm_quest(quest):
    quest.confirmed = True

    user = quest.user

    gold_reward = quest.get_current_reward()

    quest.actual_reward = gold_reward
    user.gold += quest.gold_reward
    user.xp += quest.xp_reward

    check_level_up(user)

    db.session.commit()

    notify_if_partner("You have completed a quest!")


def complete_quest(quest):
    quest.completed = True
    quest.completed_date = datetime.datetime.utcnow()
    db.session.commit()
    notify_if_partner("A child you are monitoring has completed a task and requires approval")


def calc_triangular_difficulty(diff):
    if diff == 'Very Easy' or diff == 'VERY_EASY':
        reward = 100
    elif diff == 'Easy' or diff == 'EASY':
        reward = 300
    elif diff == 'Medium' or diff == 'MEDIUM':
        reward = 600
    elif diff == 'Hard' or diff == 'HARD':
        reward = 1000
    elif diff == 'Very Hard' or diff == 'VERY_HARD':
        reward = 1500
    else:
        raise ValueError("No difficulty level match for quest. Found diff: " + diff)

    return reward


def calculate_xp_reward(diff, owner):
    reward = calc_triangular_difficulty(diff)

    reward *= ((owner.character_level - 1) / 100 + 1)  # Slightly increase gold reward based on level

    return reward


def notify_if_partner(message):
    u = get_partnered_user(g.user)
    if u:
        notify_user(u, message)


def notify_child(user, message):
    if user.is_parent():
        user = user.get_child()
    notify_user(user, message)


def notify_user(destination_user, message):
    gcm = GCM(GCM_API_KEY)
    reg_id = [destination_user.gcm_id]

    data = {'message': message}

    print('Notification sent to test account, destination=' + destination_user.email + ', message=' + message)
    if destination_user.gcm_id != 'TESTACCOUNT':
        response = gcm.json_request(registration_ids=reg_id, data=data)

        # TODO: Check response for errors


def get_partnered_user(user):
    if user.parent is not None:
        return user.parent
    d = db.session.query(User).filter_by(parent_id=user.id).all()
    if len(d) > 0:
        return d[0]


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0')
