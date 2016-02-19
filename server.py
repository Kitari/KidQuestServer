from flask.ext.httpauth import HTTPBasicAuth

from flask import Flask, jsonify, abort, request, g
from flask.ext.sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)
db.engine.execute("PRAGMA foreign_keys=ON")

auth = HTTPBasicAuth()


class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))
    child = db.relationship("Child", uselist=False, back_populates="parent")
    password_hash = db.Column(db.String(120))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def serialize(self):
        return {
            'email': self.email,
            'child': self.child.serialize()
        }


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent.id'), nullable=True)
    parent = db.relationship("Parent", back_populates="child")
    quests = db.relationship("Quest", back_populates="child")
    password_hash = db.Column(db.String(128))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def serialize(self):
        return {
            'id': self.id,
            'email': self.email,
            'quests': [q.serialize for q in self.quests]
        }


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    child = db.relationship("Child", back_populates="quests")

    def serialize(self):
        return {
            'id': self.id,
            'title': self.title
        }


@auth.verify_password
def verify_password(email, password):
    child = Child.query.filter_by(email=email).first()
    parent = Parent.query.filter_by(email=email).first()

    if child and child.verify_password(password):
        g.parent = None
        g.child = child
        return True
    if parent and parent.verify_password(password):
        g.parent = parent
        g.child = None
        return True


# Verify the user is not a child and is authorized.
def verify_parent(p):
    if g.parent is None or g.parent is not p:
        abort(401)


def verify_child(c):
    if g.child is None or g.child is not c:
        abort(401)


@app.route('/child/', methods=['POST'])
def create_child():
    required_json = ['email', 'password']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    email = json.get('email')
    password = json.get('password')

    if Child.query.filter_by(email=email).first() is not None:
        abort(400)  # existing user

    child = Child(email=email)
    child.hash_password(password)
    db.session.add(child)
    db.session.commit()
    return jsonify(child.serialize()), 201


@app.route('/child/<int:id>/parent', methods=['POST'])
@auth.login_required
def add_parent_to_child(id):
    required_json = ['email', 'password']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    # verify the creds are for the right child
    child = Child.query.get(id)
    verify_child(child)

    email = json.get('email')
    password = json.get('password')

    if Parent.query.filter_by(email=email).first() is not None:
        abort(400)

    if child.parent_id is not None:
        abort(409)

    parent = Parent(email=json['email'])
    parent.hash_password(password)
    db.session.add(parent)
    db.session.flush()
    child.parent_id = parent.id
    db.session.commit()
    return 'Added parent'


@app.route('/parent/<int:id>/', methods=['GET'])
@auth.login_required
def get_parent(id):
    p = Parent.query.get(id)
    verify_parent(p)
    if p is None:
        abort(404)
    return jsonify({'parent': Parent.query.get(id).serialize()})


@app.route('/quest/', methods=['POST'])
@auth.login_required
def create_quest():
    required_json = ['title', 'child_id']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    # allow database to store quests from people only using the child edition
    quest = Quest(title=json['title'], child_id=json['child_id'])

    db.session.add(quest)
    db.session.commit()
    return jsonify(quest.serialize()), 201


@app.route('/child/<int:id>/quest/', methods=['POST'])
@auth.login_required
def add_quest_to_child(id):
    required_json = ['title']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    child = Child.query.get(id)
    verify_child(child)

    quest = Quest(title=json.get('title'), child_id=id)
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


if __name__ == '__main__':
    app.run(host='0.0.0.0')
