import os


class Config:
    DEBUG = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True
    API_TOKEN = 'token'
    WEB_HOOK_URL = 'webhook'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SECRET_KEY = 'dev secret key'
    BOT_NAME = 'your bot name'
    IMAGE_DIR = 'files'
    SENDGRID_API_KEY = 'sendgrid api ley'


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'secret'
    BOT_NAME = 'testBot'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    DB_PATH = 'test.db'
    IMAGE_DIR = 'images'


current_config = DevelopmentConfig
