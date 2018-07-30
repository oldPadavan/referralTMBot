import os

from flask import url_for, redirect, request
from flask_admin import Admin, AdminIndexView, form, expose, helpers
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, login_user, logout_user
from jinja2 import Markup
from wtforms.validators import URL

from config import current_config
from login import LoginForm
from models import db, LinkProvider, SiteSettings


image_dir_path = os.path.join(os.path.dirname(__file__), current_config.IMAGE_DIR)
try:
    os.mkdir(image_dir_path)
except OSError:
    pass


class MyAdminIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for('.login_view'))
        return super(MyAdminIndexView, self).index()

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        # handle user login
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login_user(user)

        if current_user.is_authenticated:
            return redirect(url_for('.index'))
        self._template_args['form'] = form
        return super(MyAdminIndexView, self).index()

    @expose('/logout/')
    def logout_view(self):
        logout_user()
        return redirect(url_for('.index'))


class AuthModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated


class LinkProviderModelView(AuthModelView):
    form_args = {
        'url': {'validators': [URL()]}
    }

    def _list_thumbnail(self, context, model, name):
        if not model.image:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form.thumbgen_filename(model.image)))

    column_formatters = {
        'image': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'image': form.ImageUploadField('Image',
                                       base_path=image_dir_path,
                                       thumbnail_size=(100, 100, False))
    }


class SiteSettingsModelView(AuthModelView):
    can_create = False
    can_delete = False

    column_editable_list = ['invitation_description', 'order_description', 'admin_email', 'admin_tm']


admin = Admin(name='Bot administration', index_view=MyAdminIndexView(), base_template='base.html')
admin.add_view(LinkProviderModelView(LinkProvider, db.session))
admin.add_view(SiteSettingsModelView(SiteSettings, db.session))
