from flask.ext.sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy.orm import object_session

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    parent = db.relation("User", remote_side=[id])
    quests = db.relationship("Quest", back_populates="user")
    password_hash = db.Column(db.String(128))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def update_with_json(self, json):
        if 'email' in json:
            self.email = json['email']
        if 'parent_id' in json:
            self.parent = User.query.get(json['parent_id'])
        if 'password_hash' in json:
            self.hash_password(json['password'])

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
            'children': c
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

    def serialize(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'confirmed': self.confirmed
        }

    def update_with_json(self, json):
        if 'confirmed' in json:
            self.confirmed = json['confirmed']
        if 'completed' in json:
            self.completed = json['completed']
            # if 'difficulty_level' in json:
            # self.difficulty_level = json['difficulty_level']
