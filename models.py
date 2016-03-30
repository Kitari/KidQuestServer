from flask.ext.sqlalchemy import SQLAlchemy
from itsdangerous import JSONWebSignatureSerializer, SignatureExpired, BadSignature
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy.orm import object_session

from config import SECRET_KEY

db = SQLAlchemy()


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
            'parent_pin': self.parent_pin
        }

    def serialize_recursive(self):
        return {
            'id': self.id,
            'email': self.email,
            'quests': [q.serialize() for q in self.quests]
        }


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

    def serialize(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'confirmed': self.confirmed,
            'difficultyLevel': self.difficulty_level,
            'xp_reward': self.xp_reward,
            'gold_reward': self.gold_reward
        }


class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User", back_populates="rewards")

    def serialize(self):
        return dict(id=self.id, name=self.name, cost=self.cost, completed=self.completed)
