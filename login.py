from flask_login import LoginManager
from werkzeug.security import check_password_hash
from wtforms import form, fields, validators

from models import db, User


login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)


class LoginForm(form.Form):
    login = fields.StringField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if not check_password_hash(user.password, self.password.data):
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        return db.session.query(User).filter_by(login=self.login.data).first()