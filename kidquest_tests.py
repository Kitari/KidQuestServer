from base64 import b64encode

from flask import json
from flask.ext.testing import TestCase

from models import User, Quest
from server import create_app, db

TEST_EMAIL = 'mike@mike.com'
TEST_PASSWORD = 'potatoes'

TEST_PARENT_EMAIL = 'mikesdad@mike.com'
TEST_PARENT_PASSWORD = 'cabbages'

TEST_QUEST_DATA = {
    'title': 'Test Quest',
    'difficulty_level': 'Easy',
    'description': 'Clean your room'
}


class MyTestCase(TestCase):
    def create_app(self):
        return create_app(config_file='test-config.py', debug=True)

    @staticmethod
    def setUp():
        db.session.remove()
        db.drop_all()
        db.create_all()

    @staticmethod
    def tearDown():
        db.session.remove()
        db.drop_all()

    @staticmethod
    def test_database_addition():
        user = User()
        user.email = TEST_EMAIL
        user.hash_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()

        assert user in db.session

    def test_add_user(self):
        data = {
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }

        # Test adding a user
        # occasionally false positive if previous test run wasn't properly closed
        rv = self.client.post('/api/users/', data=json.dumps(data), content_type='application/json')
        self.assertStatus(rv, 201)

        # Test failing a duplicate email
        rv = self.client.post('/api/users/', data=json.dumps(data), content_type='application/json')
        self.assertStatus(rv, 409)

        # Test accessing auth token
        rv = self.client.get('/api/token/', headers=get_auth_header(TEST_EMAIL, TEST_PASSWORD))
        self.assert200(rv)

        user_id = str(rv.json.get('id'))
        token = rv.json.get('token')

        # Test using auth token to auth
        url = '/api/users/' + user_id + '/'
        rv = self.client.get(url, headers=get_auth_header(token, "nopassword"))
        self.assert200(rv)

        # Test invalid email
        rv = self.client.post('/api/users/', data=json.dumps(dict(email="bademail", password="password")),
                              content_type='application/json')
        self.assert400(rv)

    def test_disallowed_user_methods(self):
        rv = self.client.get('/api/users/')
        self.assert405(rv)

        rv = self.client.delete('/api/users/')
        self.assert405(rv)

        rv = self.client.put('/api/users/')
        self.assert405(rv)

        # Test no auth details
        child = create_child(self)
        rv = self.client.get('/api/users/' + child['id'] + '/')
        self.assert401(rv)

    def test_adding_parent(self):
        child = create_child(self)

        parent_data = {
            'email': TEST_PARENT_EMAIL,
            'password': TEST_PARENT_PASSWORD
        }
        # create parent account and get token
        self.client.post('/api/users/', data=json.dumps(parent_data), content_type='application/json')
        rv = self.client.get('/api/token/', headers=get_auth_header(TEST_PARENT_EMAIL, TEST_PARENT_PASSWORD))
        self.assert200(rv)
        parent_id = str(rv.json.get('id'))
        parent_token = rv.json.get('token')

        data = {
            'parent_id': parent_id
        }
        rv = self.client.put('/api/users/' + child['id'] + '/', data=json.dumps(data),
                             headers=get_auth_header(child['token'], 'nopassword'),
                             content_type='application/json')
        self.assert200(rv)

        # Test db
        dbchild = db.session.query(User).filter_by(id=child['id']).first()
        dbparent = db.session.query(User).filter_by(id=parent_id).first()
        self.assertEqual(dbchild.parent, dbparent)

        # Test parent accessing child account
        rv = self.client.get('/api/users/' + child['id'] + '/', headers=get_auth_header(parent_token, 'nopassword'))
        self.assert200(rv)

    def test_adding_quest(self):
        child = create_child(self)

        rv = self.client.post('/api/users/' + child['id'] + '/quests/', data=json.dumps(TEST_QUEST_DATA),
                              content_type='application/json', headers=get_auth_header(child['token'], 'nopassword'))
        self.assertStatus(rv, 201)
        quest_id = str(rv.json.get('id'))

        # Check quest is saved
        quest = db.session.query(Quest).filter_by(id=quest_id).first()
        self.assertEqual(rv.json, quest.serialize())

        # Test quest confirming
        data = dict(confirmed=True)
        rv = self.client.put('api/users/' + child['id'] + '/quests/' + quest_id + '/', data=json.dumps(data),
                             headers=get_auth_header(child['token']), content_type='application/json')
        self.assert200(rv)
        quest = db.session.query(Quest).filter_by(id=quest_id).first()
        self.assertEqual(quest.confirmed, True)

        db_user = db.session.query(User).filter_by(id=child['id']).first()
        old_gold = db_user.gold
        old_xp = db_user.xp

        # Test children can complete quest
        data = dict(completed=True)
        rv = self.client.put('api/users/' + child['id'] + '/quests/' + quest_id + '/', data=json.dumps(data),
                             headers=get_auth_header(child['token']), content_type='application/json')
        self.assert200(rv)
        quest = db.session.query(Quest).filter_by(id=quest_id).first()
        self.assertEqual(quest.completed, True)

        db_user = db.session.query(User).filter_by(id=child['id']).first()

        # Test XP and Gold Gain
        self.assertTrue(db_user.gold > old_gold)
        self.assertTrue(db_user.xp > old_xp)

    def test_parent_adding_quest(self):
        child = create_child(self)
        parent = create_parent(self)
        self.client.put('/api/users/' + child['id'] + '/', data=json.dumps(dict(parent_id=parent['id'])),
                        headers=get_auth_header(child['token'], 'nopassword'),
                        content_type='application/json')

        rv = send_post_request(self, '/api/users/' + child['id'] + '/quests/', TEST_QUEST_DATA,
                               headers=get_auth_header(parent['token'], "nopassword"))
        self.assertStatus(rv, 201)
        quest_id = str(rv.json.get('id'))

        quest = db.session.query(Quest).filter_by(id=quest_id).first()
        self.assertEqual(quest.completed, False)

        # Test parent adding quest to wrong child
        child2 = create_child(self, email="test2@test.com")
        rv = send_post_request(self, '/api/users/' + child2['id'] + '/quests/', TEST_QUEST_DATA,
                               headers=get_auth_header(parent['token'], "nopassword"))
        self.assertStatus(rv, 401)

        # test parent completing the quest
        data = dict(completed=True)
        rv = self.client.put('/api/users/' + child['id'] + '/quests/' + quest_id + '/', data=json.dumps(data),
                             headers=get_auth_header(parent['token']), content_type='application/json')
        self.assert200(rv)

        quest = db.session.query(Quest).filter_by(id=quest_id).first()
        self.assertEqual(quest.completed, True)

    def test_rewards(self):
        child = create_child(self)

        user_url = '/api/users/' + child['id']

        # check no rewards exist
        rv = self.client.get(user_url + '/rewards/', headers=get_auth_header(child['token']))
        self.assert200(rv)
        self.assertEqual(len(rv.json.get('rewards')), 0)

        reward_data = dict(name="New Toy", cost="150")

        # add reward
        rv = send_post_request(self, user_url + '/rewards/', reward_data, get_auth_header(child['token']))
        self.assert_status(rv, 201)

        # check reward exists in database
        db_user = db.session.query(User).filter_by(id=child['id']).first()
        self.assertEqual(len(db_user.rewards), 1)
        reward = db_user.rewards[0]
        self.assertEqual(reward.name, reward_data['name'])
        self.assertEqual(str(reward.cost), reward_data['cost'])  # Convert db value to string to compare to JSON

        # complete reward with no gold
        url = user_url + '/rewards/' + str(reward.id) + '/'
        rv = self.client.put(url, data=json.dumps(dict(completed=True)), content_type='application/json',
                             headers=get_auth_header(child['token']))
        self.assert400(rv, "Not enough gold")
        db_user = db.session.query(User).filter_by(id=child['id']).first()
        reward = db_user.rewards[0]
        self.assertFalse(reward.completed)

        # Add gold and try again
        db.session.query(User).filter_by(id=child['id']).update({"gold": 200})
        db.session.commit()

        rv = self.client.put(url, data=json.dumps(dict(completed=True)), content_type='application/json',
                             headers=get_auth_header(child['token']))
        self.assert200(rv)
        db_user = db.session.query(User).filter_by(id=child['id']).first()
        reward = db_user.rewards[0]
        self.assertTrue(reward.completed)
        self.assertEqual(db_user.gold, 50)


def create_child(self, email=None, password=None):
    if email is None:
        email = TEST_EMAIL
    if password is None:
        password = TEST_PASSWORD

    data = {
        'email': email,
        'password': password
    }

    # create child account and get token
    self.client.post('/api/users/', data=json.dumps(data), content_type='application/json')
    rv = self.client.get('/api/token/', headers=get_auth_header(email, password))
    child_id = str(rv.json.get('id'))
    token = rv.json.get('token')

    return dict(id=child_id, token=token)


def create_parent(self, email=None, password=None):
    if email is None:
        email = TEST_PARENT_EMAIL
    if password is None:
        password = TEST_PARENT_PASSWORD

    data = {
        'email': email,
        'password': password
    }

    # create child account and get token
    self.client.post('/api/users/', data=json.dumps(data), content_type='application/json')
    rv = self.client.get('/api/token/', headers=get_auth_header(email, password))
    parent_id = str(rv.json.get('id'))
    token = rv.json.get('token')

    return dict(id=parent_id, token=token)


def get_auth_header(email, password=None):
    if password is None:
        # stops b64 whinging about token auth
        password = "nopassword"
    return {'Authorization': 'Basic ' + b64encode((email + ':' + password).encode('utf-8')).decode('utf-8')}


def send_post_request(self, url, data, headers):
    return self.client.post(url, data=json.dumps(data), content_type='application/json', headers=headers)
