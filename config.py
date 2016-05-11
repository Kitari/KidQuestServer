import os

basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.sqlite')
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')
DEBUG = True
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = "Nw0IhH326OTYNCRZx04d6Q263c7mnNgJ"

GCM_API_KEY = "AIzaSyBO6iNSbCZtRWJeFBu1oHOJLtJQS_0YTu8"