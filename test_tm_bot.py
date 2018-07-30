import os
import random
import string
import tempfile
import unittest
from unittest.mock import patch

from telebot import types

import bot_constants as const
import models
from bot import bot, get_step
from bot_app import create_app
from config import TestingConfig
from models import db


def create_random_string(length=10):
    return ''.join([random.choice(string.ascii_letters) for _ in range(length)])


def create_user(**kwargs):
    return types.User(id=kwargs.get('id') or random.randint(1, 100),
                      is_bot=False,
                      first_name=kwargs.get('first_name') or create_random_string(),
                      username=kwargs.get('username') or create_random_string())


def create_chat(**kwargs):
    return types.Chat(id=kwargs.get('id') or random.randint(1, 100), type='private')


def create_text_message(text, **kwargs):
    params = {'text': text}
    return types.Message(message_id=kwargs.get('message_id') or random.randint(1, 100),
                         from_user=kwargs.get('from_user') or create_user(),
                         date=None,
                         chat=kwargs.get('chat') or create_chat(),
                         content_type=kwargs.get('content_type') or 'text',
                         options=params,
                         json_string="")


def markup_to_list(markup):
    return [button['text'] for row in markup.keyboard for button in row]


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.db = db
        self.db.create_all(app=self.app)
        self.bot = bot
        self.send_message_patcher = patch('telebot.apihelper.send_message')
        self.send_message_mock = self.send_message_patcher.start()
        self.de_json_patcher = patch('telebot.types.Message.de_json')
        self.de_json_patcher.start()

        self.site_settings = models.SiteSettings(invitation_description='Invitation description',
                                                 order_description='Order description',
                                                 admin_tm='admin',
                                                 admin_email='admin@admin.admin')
        self.db.session.add(self.site_settings)
        self.db.session.commit()

    def tearDown(self):
        self.send_message_patcher.stop()
        self.de_json_patcher.stop()
        self.db.session.remove()
        self.db.drop_all()


class StartMenuTests(BaseTestCase):
    def test_start_command_wo_args(self):
        msg = create_text_message('/start')
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called_once()
        call_args = self.send_message_mock.call_args[0]
        markup = call_args[5]
        choices = markup_to_list(markup)
        self.assertEqual(len(choices), 3)
        self.assertIn(const.INVITATIONS, choices)
        self.assertIn(const.ORDER, choices)
        self.assertIn(const.EARN_MONEY, choices)
        self.assertEqual(get_step(msg.chat.id), const.Steps.start)

    def test_start_command_with_valid_token(self):
        inviter = create_user(id=1, first_name='user1', username='username1')
        token = models.TmUser.generate_invitation_token(inviter)
        inviter_obj = self.db.session.query(models.TmUser).filter_by(id=1).one_or_none()
        self.assertIsNotNone(inviter_obj)
        self.assertIsNotNone(inviter_obj.token)
        invited = create_user(id=2, first_name='user2', username='username2')
        msg = create_text_message('/start ' + token, from_user=invited)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()
        self.assertEqual(get_step(msg.chat.id), const.Steps.start)
        invited_obj = self.db.session.query(models.TmUser).filter_by(id=2).one_or_none()
        self.assertIsNotNone(invited_obj)
        self.assertEqual(invited_obj.invited_by, inviter_obj)

    def test_start_command_already_invited(self):
        inviter_obj = models.TmUser(id=1, first_name='user1', token='token1')
        self.db.session.add(inviter_obj)
        self.db.session.commit()
        invited_obj = models.TmUser(id=2, first_name='user2', invited_by=inviter_obj)
        self.db.session.add(invited_obj)
        self.db.session.commit()
        other_user_obj = models.TmUser(id=3, first_name='user3', token='token3')
        self.db.session.add(other_user_obj)
        self.db.session.commit()
        invited = create_user(id=2, first_name='user2', username='username2')
        msg = create_text_message('/start ' + other_user_obj.token, from_user=invited)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()
        invited_obj = self.db.session.query(models.TmUser).filter_by(id=2).one_or_none()
        self.assertEqual(invited_obj.invited_by, inviter_obj)
        self.assertEqual(get_step(msg.chat.id), const.Steps.start)

    def test_start_command_invite_itself(self):
        inviter = create_user(id=1, first_name='user1', username='username1')
        token = models.TmUser.generate_invitation_token(inviter)
        inviter_obj = self.db.session.query(models.TmUser).filter_by(id=1).one_or_none()
        self.assertIsNotNone(inviter_obj)
        self.assertIsNotNone(inviter_obj.token)
        msg = create_text_message('/start ' + token, from_user=inviter)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()

        inviter_obj = self.db.session.query(models.TmUser).filter_by(id=1).one_or_none()
        self.assertIsNotNone(inviter_obj)
        self.assertIsNone(inviter_obj.invited_by)
        self.assertEqual(get_step(msg.chat.id), const.Steps.start)

    def test_new_token_is_not_generated_if_exists(self):
        user = create_user(id=1, first_name='user1', username='username1')
        user_obj = models.TmUser(id=1, first_name='user1', token='token1')
        self.db.session.add(user_obj)
        self.db.session.commit()
        token = user_obj.token
        models.TmUser.generate_invitation_token(user)
        self.assertEqual(db.session.query(models.TmUser).filter_by(id=1).one_or_none().token, token)


class TestEarnMoney(BaseTestCase):
    def setUp(self):
        super().setUp()
        f, image_path = tempfile.mkstemp()
        os.close(f)
        self.link_provider_1 = models.LinkProvider(name='name', description='description', url='http://url.com',
                                                   image=image_path)
        self.db.session.add(self.link_provider_1)
        self.db.session.commit()
        self.chat = create_chat()

    def test_show_link_providers(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.start)
        msg = create_text_message(const.EARN_MONEY, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()
        call_args = self.send_message_mock.call_args[0]
        markup = call_args[5]
        providers = markup_to_list(markup)
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0], self.link_provider_1.name)
        self.assertEqual(get_step(self.chat.id), const.Steps.earnings_list)

    @patch('telebot.TeleBot.send_photo')
    def test_valid_link_provider(self, send_photo_mock):
        models.Steps.set_chat_step(self.chat.id, const.Steps.earnings_list)
        msg = create_text_message(self.link_provider_1.name, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 3)
        calls = self.send_message_mock.call_args_list
        self.assertEqual(calls[0][0][2], self.link_provider_1.description)
        self.assertEqual(calls[1][0][2], self.link_provider_1.url)
        send_photo_mock.assert_called()
        self.assertEqual(get_step(self.chat.id), const.Steps.start)

    @patch('telebot.TeleBot.send_photo')
    def test_invalid_link_provider(self, send_photo_mock):
        models.Steps.set_chat_step(self.chat.id, const.Steps.earnings_list)
        msg = create_text_message('not-exists', chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 2)
        self.assertEqual(get_step(self.chat.id), const.Steps.earnings_list)


class TestInvitations(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.chat = create_chat()

    def test_invitation_options(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.start)
        msg = create_text_message(const.INVITATIONS, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()
        call_args = self.send_message_mock.call_args[0]
        markup = markup_to_list(call_args[5])
        self.assertIn(const.INVITATION_LINK, markup)
        self.assertIn(const.USER_INVITED_FRIENDS, markup)
        self.assertIn(const.BALANCE, markup)
        self.assertIn(const.INVITATION_DESCRIPTION, markup)
        self.assertEqual(get_step(self.chat.id), const.Steps.invitations_choice)

    def test_wrong_invitation_option_choosen(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.invitations_choice)
        msg = create_text_message('not exists', chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 2)
        call_args = self.send_message_mock.call_args_list[1][0]
        markup = markup_to_list(call_args[5])
        self.assertIn(const.INVITATION_LINK, markup)
        self.assertIn(const.USER_INVITED_FRIENDS, markup)
        self.assertIn(const.BALANCE, markup)
        self.assertIn(const.INVITATION_DESCRIPTION, markup)
        self.assertEqual(get_step(self.chat.id), const.Steps.invitations_choice)

    def test_invitation_link_is_generated(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.invitations_choice)
        user = create_user()
        msg = create_text_message(const.INVITATION_LINK, from_user=user, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called()
        call_args = self.send_message_mock.call_args_list[0][0]
        user_obj = self.db.session.query(models.TmUser).filter_by(id=user.id).one_or_none()
        self.assertIsNotNone(user_obj)
        self.assertIsNotNone(user_obj.token)
        self.assertIn(user_obj.token, call_args[2])
        self.assertEqual(get_step(self.chat.id), const.Steps.start)

    def test_invited_friends_shown(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.invitations_choice)
        user = create_user(id=1)
        self.db.session.add(models.TmUser(id=user.id, first_name=user.first_name, token='token'))
        user_friend_1st = create_user(id=2)
        user_friend_1st_obj = models.TmUser(id=user_friend_1st.id,
                                            first_name=user_friend_1st.first_name,
                                            invited_by_id=user.id)
        self.db.session.add(user_friend_1st_obj)
        user_friend_2nd = create_user(id=3)
        user_friend_2nd_obj = models.TmUser(id=user_friend_2nd.id,
                                            first_name=user_friend_2nd.first_name,
                                            invited_by_id=user_friend_1st.id)
        self.db.session.add(user_friend_2nd_obj)
        user_friend_3rd = create_user(id=4)
        user_friend_3rd_obj = models.TmUser(id=user_friend_3rd.id,
                                            first_name=user_friend_3rd.first_name,
                                            invited_by_id=user_friend_2nd.id)
        self.db.session.add(user_friend_3rd_obj)
        self.db.session.commit()
        msg = create_text_message(const.USER_INVITED_FRIENDS, from_user=user, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 4)
        calls = self.send_message_mock.call_args_list
        self.assertIn(user_friend_1st_obj.name, calls[0][0][2])
        self.assertIn(user_friend_2nd_obj.name, calls[1][0][2])
        self.assertIn(user_friend_3rd_obj.name, calls[2][0][2])
        self.assertEqual(get_step(self.chat.id), const.Steps.start)

    def test_balance_shown(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.invitations_choice)
        user = create_user(id=1)
        self.db.session.add(models.TmUser(id=user.id, first_name=user.first_name, token='token'))
        user_friend_1st = create_user(id=2)
        user_friend_1st_obj = models.TmUser(id=user_friend_1st.id,
                                            first_name=user_friend_1st.first_name,
                                            invited_by_id=user.id)
        self.db.session.add(user_friend_1st_obj)
        user_friend_2nd = create_user(id=3)
        user_friend_2nd_obj = models.TmUser(id=user_friend_2nd.id,
                                            first_name=user_friend_2nd.first_name,
                                            invited_by_id=user_friend_1st.id)
        self.db.session.add(user_friend_2nd_obj)
        user_friend_3rd = create_user(id=4)
        user_friend_3rd_obj = models.TmUser(id=user_friend_3rd.id,
                                            first_name=user_friend_3rd.first_name,
                                            invited_by_id=user_friend_2nd.id)
        self.db.session.add(user_friend_3rd_obj)
        self.db.session.commit()
        msg = create_text_message(const.BALANCE, from_user=user, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 2)
        call_args = self.send_message_mock.call_args_list[0][0]
        self.assertIn(str(const.REWARD_1ST_LEVEL_INVITE +
                          const.REWARD_2ND_LEVEL_INVITE +
                          const.REWARD_3RD_LEVEL_INVITE), call_args[2])
        self.assertEqual(get_step(self.chat.id), const.Steps.start)

    def test_invitation_description_shown(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.invitations_choice)
        msg = create_text_message(const.INVITATION_DESCRIPTION, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.assertEqual(self.send_message_mock.call_count, 2)
        call_args = self.send_message_mock.call_args_list[0][0]
        self.assertIn(self.site_settings.invitation_description, call_args[2])
        self.assertEqual(get_step(self.chat.id), const.Steps.start)


class TestOrder(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.chat = create_chat()

    def test_order_description(self):
        models.Steps.set_chat_step(self.chat.id, const.Steps.start)
        msg = create_text_message(const.ORDER, chat=self.chat)
        self.bot.process_new_messages([msg])
        self.send_message_mock.assert_called_once()
        call_args = self.send_message_mock.call_args[0]
        markup = markup_to_list(call_args[5])
        self.assertIn(const.ORDER_BUTTON_TEXT, markup)
        self.assertEqual(call_args[2], self.site_settings.order_description)
        self.assertEqual(get_step(self.chat.id), const.Steps.order)

    @patch('bot.send_email')
    def test_order_input(self, email_mock):
        admin_contact = models.AdminContact(chat_id=create_chat().id, tm_username=self.site_settings.admin_tm)
        self.db.session.add(admin_contact)
        self.db.session.commit()

        user = create_user()
        models.Steps.set_chat_step(self.chat.id, const.Steps.order)
        msg = create_text_message(const.ORDER_BUTTON_TEXT, chat=self.chat, from_user=user)
        self.bot.process_new_messages([msg])
        self.assertEqual(get_step(self.chat.id), const.Steps.order_input_name)

        name = 'user name'
        msg = create_text_message(name, chat=self.chat, from_user=user)
        self.bot.process_new_messages([msg])
        self.assertEqual(get_step(self.chat.id), const.Steps.order_input_phone)

        phone = '123456'
        msg = create_text_message(phone, chat=self.chat, from_user=user)
        self.bot.process_new_messages([msg])
        self.assertEqual(get_step(self.chat.id), const.Steps.order_input_tm)

        tm = 'tm'
        msg = create_text_message(tm, chat=self.chat, from_user=user)
        self.bot.process_new_messages([msg])
        self.assertEqual(get_step(self.chat.id), const.Steps.order_input_email)

        email = 'email@email.mail'
        msg = create_text_message(email, chat=self.chat, from_user=user)
        self.send_message_mock.reset_mock()
        self.bot.process_new_messages([msg])

        user_details_obj = self.db.session.query(models.UserDetails).filter_by(user_id=user.id).one_or_none()
        self.assertIsNotNone(user_details_obj)
        self.assertEqual(user_details_obj.name, name)
        self.assertEqual(user_details_obj.phone, phone)
        self.assertEqual(user_details_obj.tm_name, tm)
        self.assertEqual(user_details_obj.email, email)

        calls = self.send_message_mock.call_args_list
        admin_call = calls[1][0]
        self.assertEqual(admin_call[1], admin_contact.chat_id)
        self.assertEqual(admin_call[2], str(user_details_obj))

        email_mock.assert_called_once()
        email_args = email_mock.call_args[0]
        self.assertEqual(email_args[0], self.site_settings.admin_email)
        self.assertEqual(email_args[1], str(user_details_obj))

        self.assertEqual(get_step(self.chat.id), const.Steps.start)


if __name__ == '__main__':
    unittest.main()
