import datetime
import uuid

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased

import bot_constants as const


db = SQLAlchemy()


class LinkProvider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default='Description')
    url = db.Column(db.String(256), unique=True, nullable=False)
    image = db.Column(db.String(128), unique=True)

    def __repr__(self):
        return '<LinkProvider {!r}>'.format(self.name)


class Steps(db.Model):
    chat_id = db.Column(db.Integer, primary_key=True)
    step = db.Column(db.Integer, nullable=False)
    entered_on = db.Column(db.DateTime, default=datetime.datetime.utcnow())

    def __repr__(self):
        return '<Step {!r}.{!r}>'.format(self.chat_id, self.step)

    @staticmethod
    def set_chat_step(chat_id, step):
        current_step = db.session.query(Steps).filter_by(chat_id=chat_id).one_or_none()
        if not current_step:
            current_step = Steps(chat_id=chat_id, step=step.value)
        else:
            current_step.step = step.value
        db.session.add(current_step)
        db.session.commit()


class TmUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(32), unique=True, nullable=False)
    last_name = db.Column(db.String(32), nullable=True)
    username = db.Column(db.String(32), nullable=True)
    token = db.Column(db.String(32), unique=True, nullable=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('tm_user.id'), nullable=True)
    invited_by = db.relationship('TmUser', remote_side=[id], backref=db.backref('invited', lazy=True))

    def __repr__(self):
        return '<TmUser {!r}>'.format(self.id)

    @hybrid_property
    def name(self):
        if self.username:
            return '@' + self.username
        else:
            return self.first_name + (self.last_name or '')

    @staticmethod
    def generate_invitation_token(user):
        user_obj = db.session.query(TmUser).filter_by(id=user.id).one_or_none()
        if not user_obj:
            user_obj = TmUser(id=user.id, first_name=user.first_name, last_name=user.last_name, username=user.username)
        if not user_obj.token:
            user_obj.token = uuid.uuid4().hex
            db.session.add(user_obj)
            db.session.commit()
        return user_obj.token

    @staticmethod
    def parse_invitation_token(user, token):
        user_obj = db.session.query(TmUser).filter_by(id=user.id).one_or_none()
        if not user_obj:
            user_obj = TmUser(id=user.id, first_name=user.first_name, last_name=user.last_name, username=user.username)
        elif user_obj.invited_by or user_obj.token == token:
            # don't modify inviter if the user has already been invited by someone else or he has invited itself
            return

        inviter = db.session.query(TmUser).filter_by(token=token).one_or_none()
        if inviter:
            user_obj.invited_by = inviter
        db.session.add(user_obj)
        db.session.commit()

    @staticmethod
    def get_invited_friends(user):
        friends = {
            1: [],
            2: [],
            3: []
        }
        user_obj = db.session.query(TmUser).filter_by(id=user.id).one_or_none()
        if not user_obj or not user_obj.token:
            return None

        friends_1st_level = db.session.query(TmUser).filter_by(invited_by=user_obj).all()
        if not friends_1st_level:
            return friends
        friends[1] = friends_1st_level

        Users1stLevel = aliased(TmUser, name='users_1st_level')
        friends_2nd_level = db.session.query(Users1stLevel).join(TmUser, Users1stLevel.invited_by_id == TmUser.id).\
            filter(TmUser.invited_by == user_obj).all()
        if not friends_2nd_level:
            return friends
        friends[2] = friends_2nd_level

        Users2ndLevel = aliased(TmUser, name='users_2nd_level')
        friends_3rd_level = db.session.query(Users2ndLevel).\
            join(Users1stLevel, Users2ndLevel.invited_by_id == Users1stLevel.id).\
            join(TmUser, Users1stLevel.invited_by_id == TmUser.id).filter(TmUser.invited_by == user_obj).all()
        friends[3] = friends_3rd_level
        return friends

    @staticmethod
    def get_balance(user):
        user_obj = db.session.query(TmUser).filter_by(id=user.id).one_or_none()
        if not user_obj or not user_obj.token:
            return 0

        reward_1st_level = db.session.query(TmUser).filter_by(invited_by=user_obj).count() * \
                           const.REWARD_1ST_LEVEL_INVITE
        if not reward_1st_level:
            return 0

        Users1stLevel = aliased(TmUser, name='users_1st_level')
        reward_2nd_level = db.session.query(Users1stLevel).join(TmUser, Users1stLevel.invited_by_id == TmUser.id). \
            filter(TmUser.invited_by == user_obj).count() * const.REWARD_2ND_LEVEL_INVITE
        if not reward_2nd_level:
            return reward_1st_level

        Users2ndLevel = aliased(TmUser, name='users_2nd_level')
        reward_3rd_level = db.session.query(Users2ndLevel). \
            join(Users1stLevel, Users2ndLevel.invited_by_id == Users1stLevel.id). \
            join(TmUser, Users1stLevel.invited_by_id == TmUser.id).\
                                filter(TmUser.invited_by == user_obj).count() * const.REWARD_3RD_LEVEL_INVITE
        return reward_1st_level + reward_2nd_level + reward_3rd_level


class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invitation_description = db.Column(db.Text, nullable=False, default=const.DEFAULT_INVITATION_DESCRIPTION)
    order_description = db.Column(db.Text, nullable=False, default=const.DEFAULT_ORDER_DESCRIPTION)
    admin_tm = db.Column(db.String(32), nullable=True)
    admin_email = db.Column(db.String(64), nullable=True)

    @staticmethod
    def get_settings():
        return db.session.query(SiteSettings).first()

    @staticmethod
    def get_invitation_description():
        return SiteSettings.get_settings().invitation_description

    @staticmethod
    def get_order_description():
        return SiteSettings.get_settings().order_description


class UserDetails(db.Model):
    __table_args__ = (db.UniqueConstraint('user_id', 'chat_id', name='_user_chat_uc'), )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    chat_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    tm_name = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)

    @staticmethod
    def get_current_user_input(chat_id, user):
        user_input = db.session.query(UserDetails).filter_by(user_id=user.id, chat_id=chat_id).one_or_none()
        if not user_input:
            user_input = UserDetails(user_id=user.id, chat_id=chat_id)
            db.session.add(user_input)
            db.session.commit()
        return user_input

    def save(self):
        db.session.add(self)
        db.session.commit()

    def __str__(self):
        return "Имя: {name}\nТелефон: {phone}\n@TM: {tm}\nemail: {email}".format(name=self.name, phone=self.phone,
                                                                                 tm=self.tm_name, email=self.email)


class AdminContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, nullable=False, unique=True)
    tm_username = db.Column(db.String(32), nullable=False, unique=True)

    @staticmethod
    def update_admin_contact(username, chat_id):
        admin = db.session.query(AdminContact).filter_by(tm_username=username).one_or_none()
        if admin:
            admin.chat_id = chat_id
        else:
            admin = AdminContact(chat_id=chat_id, tm_username=username)
        db.session.add(admin)
        db.session.commit()

    @staticmethod
    def get_admin_chat_id(username):
        admin = db.session.query(AdminContact).filter(
            func.lower(AdminContact.tm_username) == func.lower(username)).one_or_none()
        if admin:
            return admin.chat_id


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    password = db.Column(db.String(64))

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    # Required for administrative interface
    def __unicode__(self):
        return self.username
