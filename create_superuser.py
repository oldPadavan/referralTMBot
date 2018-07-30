from getpass import getpass

from sqlalchemy.sql import exists
from werkzeug.security import generate_password_hash

from bot_app import create_app, db
from models import User


def main():
    app = create_app()
    with app.app_context():
        if db.session.query(User.query.exists()).scalar():
            print('A user already exists! Create another? (y/n):')
            create = input()
            if create == 'n':
                return

        print('Enter username: ')
        login = input()
        print('Enter email address: ')
        email = input()
        password = getpass()
        assert password == getpass('Password (again):')

        user = User(login=login, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print('User added')


if __name__ == '__main__':
    main()
