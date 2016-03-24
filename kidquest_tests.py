import os

from flask.ext.testing import TestCase

from server import create_app, db


class MyTestCase(TestCase):
    def create_app(self):
        return create_app(config_file='test-config.py', debug=True)

    def setUp(self):
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_stuff(self):
        self.assertTrue(True)
        self.assertTrue(False)
