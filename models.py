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

    def serialize(self):
        if self.parent is None:
            p = None
            session = object_session(self)
            d = session.query(User).filter_by(parent_id=self.id).all()
            c = [children.serialize2() for children in d]
        else:
            p = self.parent.serialize2()
            c = None

        return {
            'id': self.id,
            'email': self.email,
            'quests': [q.serialize() for q in self.quests],
            'parent': p,
            'children': c
        }

    def serialize2(self):
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
            'confirmed': self.confirmed,
        }

