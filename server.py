from flask import Flask, jsonify, abort, request
from flask.ext.sqlalchemy import SQLAlchemy
import flask.ext.restless

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)
db.engine.execute("PRAGMA foreign_keys=ON")


class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))
    child = db.relationship("Child", uselist=False, back_populates="parent")

    def serialize(self):
        return {
            'email': self.email,
            'child': self.child
        }


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent.id'), nullable=True)
    parent = db.relationship("Parent", back_populates="child")
    quests = db.relationship("Quest", back_populates="child")


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    child = db.relationship("Child", back_populates="quests")




@app.route('/parent/', methods=['GET'])
def index():
    return jsonify({'parents': [p.serialize() for p in Parent.query.all()]})


@app.route('/parent/<int:id>/')
def get_parent(id):
    p = Parent.query.get(id)
    if p is None:
        abort(404)
    return jsonify({'parent': Parent.query.get(id).serialize()})


@app.route('/quest/', methods=['POST'])
def create_quest():
    required_json = ['title', 'child_id']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    # allow database to store quests from people only using the child edition
    quest = Quest(title=json['title'], child_id=json['child_id'])

    db.session.add(quest)
    db.session.commit()
    return 'Added'


@app.route('/child/', methods=['POST'])
def create_child():
    required_json = ['email']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    child = Child(email=json['email'])
    db.session.add(child)
    db.session.commit()
    return 'Added child'


@app.route('/child/<int:id>/parent', methods=['POST'])
def add_parent_to_child(id):
    required_json = ['email']
    json = request.json

    if not valid_json(json, required_json):
        abort(400)

    child = Child.query.get(id)
    if child.parent_id is not None:
        abort(409)

    parent = Parent(email=json['email'])
    db.session.add(parent)
    db.session.flush()
    child.parent_id = parent.id
    db.session.commit()
    return 'Added parent'


def valid_json(json, required_json):
    if not json:
        return False
    elif any(x not in json for x in required_json):
        return False
    else:
        return True


if __name__ == '__main__':
    manager = flask.ext.restless.APIManager(app, session=db.session)

    manager.create_api(Parent, methods=['GET'])
    manager.create_api(Child, methods=['GET'])
    manager.create_api(Quest, methods=['GET'])

    app.run(host='0.0.0.0')
