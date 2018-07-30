from flask import Flask
from flask_migrate import Migrate

import config as cfg
from admin import admin
from bot import init_bot
from index import index_bp
from login import login_manager
from models import db
from webhook import webhook_bp


def create_app(config=cfg.current_config):
    app = Flask(__name__, static_folder=config.IMAGE_DIR)
    app.config.from_object(config)

    db.app = app
    db.init_app(app)
    Migrate(app, db)
    admin.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    app.register_blueprint(index_bp, url_prefix='/')

    app.before_first_request(init_bot)

    return app
