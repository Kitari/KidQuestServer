import datetime

from flask.ext.sqlalchemy import SQLAlchemy
from itsdangerous import JSONWebSignatureSerializer, SignatureExpired, BadSignature
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy import desc
from sqlalchemy.orm import object_session

from config import SECRET_KEY

db = SQLAlchemy()

XP_REQUIRED_COEFFICIENT = 100


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    parent = db.relation("User", remote_side=[id])
    quests = db.relationship("Quest", back_populates="user")
    password_hash = db.Column(db.String(128))
    character_name = db.Column(db.String(64))
    character_level = db.Column(db.Integer, default=1)
    gold = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    rewards = db.relationship("Reward", back_populates="user")
    gcm_id = db.Column(db.String(128), nullable=True)
    parent_pin = db.Column(db.String(4), nullable=True)

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = JSONWebSignatureSerializer(SECRET_KEY)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        s = JSONWebSignatureSerializer(SECRET_KEY)
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None  # valid token but expired
        except BadSignature:
            return None  # invalid token
        user = User.query.get(data['id'])
        return user

    def serialize(self):
        if self.parent is None:
            p = None
            session = object_session(self)
            d = session.query(User).filter_by(parent_id=self.id).all()
            c = [children.serialize_recursive() for children in d]
        else:
            p = self.parent.serialize_recursive()
            c = None

        return {
            'id': self.id,
            'email': self.email,
            'quests': [q.serialize() for q in self.quests],
            'parent': p,
            'children': c,
            'character_name': self.character_name,
            'character_level': self.character_level,
            'xp': self.xp,
            'gold': self.gold,
            'parent_pin': self.parent_pin,
            'xp_required': self.xp_to_next_level()
        }

    def serialize_recursive(self):
        return {
            'id': self.id,
            'email': self.email,
            'quests': [q.serialize() for q in self.quests]
        }

    def is_parent(self):
        """
        :rtype: bool
        """
        if self.parent is not None:
            # Is a child
            return False
        session = object_session(self)
        d = session.query(User).filter_by(parent_id=self.id).all()
        if len(d) > 0:
            # Has children, must be a parent
            return True

        return False

    def get_child(self):
        if not self.is_parent():
            return None
        session = object_session(self)
        d = session.query(User).filter_by(parent_id=self.id).all()

        return d[0]

    def xp_to_next_level(self):
        """ Returns the XP needed for next level """
        sum_ = 0
        for i in range(self.character_level + 1):
            sum_ += i

        return sum_ * XP_REQUIRED_COEFFICIENT


def calc_expiry():
    utcnow = datetime.datetime.utcnow()
    timedelta = datetime.timedelta(days=7)
    return utcnow + timedelta


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User", back_populates="quests")
    completed = db.Column(db.Boolean, nullable=False, default=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.String(120), nullable=True)
    difficulty_level = db.Column(db.String(50), nullable=False, default="Medium")
    xp_reward = db.Column(db.Integer, nullable=False)
    gold_reward = db.Column(db.Integer, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=False, default=calc_expiry())
    completed_date = db.Column(db.DateTime, nullable=True)
    actual_reward = db.Column(db.Integer, nullable=True)

    def serialize(self):
        quest = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'confirmed': self.confirmed,
            'difficultyLevel': self.difficulty_level,
            'xp_reward': self.xp_reward,
            'gold_reward': self.gold_reward,
            'created_date': None,
            'expiryDate': None,
            'completed_date': None,
            'current_reward': self.get_current_reward()
        }

        if self.created_date is not None:
            quest['created_date'] = self.created_date.strftime("%Y-%m-%d %H:%M:%S")
        if self.expiry_date is not None:
            quest['expiryDate'] = self.expiry_date.strftime("%Y-%m-%d %H:%M:%S")
        if self.completed_date is not None:
            quest['completed_date'] = self.completed_date.strftime("%Y-%m-%d %H:%M:%S")

        return quest

    def get_current_reward(self):
        if datetime.datetime.utcnow() > self.expiry_date:
            return 0

        time_left = self.expiry_date - datetime.datetime.now()
        total = self.expiry_date - self.created_date

        time_multiplier = (time_left / total) * 2

        # means quest rewards don't diminish until half time is left
        if time_multiplier > 1:
            time_multiplier = 1

        # gets last 5 quests where completed
        quests = self.get_last_5_quests()

        # just give max reward if user hasn't finished/failed more than 5 quests
        if len(quests) < 5:
            return self.gold_reward * time_multiplier
        else:

            base_coefficient = 0.6
            first_coefficient = 0.25
            second_coefficient = 0.15
            third_coefficient = 0
            fourth_coefficient = 0
            fifth_coefficient = 0

            base_reward = base_coefficient * self.gold_reward
            first_reward = self.calc_closed_loop_per_quest(first_coefficient, quests[0])
            second_reward = self.calc_closed_loop_per_quest(second_coefficient, quests[1])
            third_reward = self.calc_closed_loop_per_quest(third_coefficient, quests[2])
            fourth_reward = self.calc_closed_loop_per_quest(fourth_coefficient, quests[3])
            fifth_reward = self.calc_closed_loop_per_quest(fifth_coefficient, quests[4])

            reward = base_reward + first_reward + second_reward + third_reward + fourth_reward + fifth_reward
            return reward * time_multiplier

    def get_last_5_quests(self):
        session = object_session(self)

        completed_quests = session.query(Quest).filter_by(user=self.user).filter_by(confirmed=True).filter(
            Quest.id != self.id).order_by(desc(Quest.completed_date)).limit(5).all()

        # gets last 5 quests that were not completed and have expired
        current_time = datetime.datetime.now()
        expired_quests = session.query(Quest).filter_by(user=self.user).filter_by(confirmed=False).filter(
            Quest.expiry_date < current_time).order_by(desc(Quest.expiry_date)).limit(5).all()

        quests = completed_quests
        for q in expired_quests:
            q.completed_date = q.expiry_date
            q.actual_reward = 0
            quests.append(q)
        quests.sort(key=lambda x: x.completed_date, reverse=True)
        return quests[:5]

    def calc_closed_loop_per_quest(self, coefficient, old_quest):
        return coefficient * old_quest.actual_reward / old_quest.gold_reward * self.gold_reward


class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User", back_populates="rewards")

    def serialize(self):
        return dict(id=self.id, name=self.name, cost=self.cost, completed=self.completed)
