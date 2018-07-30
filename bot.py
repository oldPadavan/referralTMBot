import os

import telebot
import sendgrid
from sendgrid.helpers.mail import Content, Email, Mail

import bot_constants as const
from config import current_config
from models import AdminContact, db, LinkProvider, SiteSettings, Steps as StepModel, TmUser, UserDetails


bot = telebot.TeleBot(current_config.API_TOKEN, threaded=False)


initial_choices_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, row_width=1)
initial_choices_keyboard.add(*const.INITIAL_CHOICES)

invitations_choices_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
invitations_choices_keyboard.add(*const.INVITATION_CHOICES)

order_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
order_keyboard.add(const.ORDER_BUTTON_TEXT)


def handle_earnings_list(message):
    link_provider = db.session.query(LinkProvider).filter_by(name=message.text).one_or_none()
    if link_provider:
        bot.send_message(message.chat.id, link_provider.description)
        bot.send_message(message.chat.id, link_provider.url)
        if link_provider.image:
            try:
                with open(os.path.join(os.path.dirname(__file__),
                                       current_config.IMAGE_DIR,
                                       link_provider.image), 'rb') as f:
                    bot.send_photo(message.chat.id, f)
            except OSError:
                pass
        show_start_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, 'Извините, не нашёл такого способа заработа. Пожалуйста, повторите')
        show_earnings_options(message)


def handle_invitation_choices(message):
    if message.text == const.INVITATION_LINK:
        handle_invitation_link_generation(message)
    elif message.text == const.USER_INVITED_FRIENDS:
        handle_invitated_users_list(message)
    elif message.text == const.BALANCE:
        handle_balance(message)
    elif message.text == const.INVITATION_DESCRIPTION:
        handle_invitation_description(message)
    else:
        bot.send_message(message.chat.id, 'Не понял введённой команды')
        show_invitations_options(message)


def handle_begin_order_input(message):
    if message.text == const.ORDER_BUTTON_TEXT:
        bot.send_message(message.chat.id, 'Введите ваше имя')
        StepModel.set_chat_step(message.chat.id, const.Steps.order_input_name)
    else:
        bot.send_message(message.chat.id, 'Подтвердите, что хотите оставить заявку')
        show_order_description(message)


def handle_order_input_name(message):
    if message.text:
        user_input = UserDetails.get_current_user_input(chat_id=message.chat.id, user=message.from_user)
        user_input.name = message.text
        user_input.save()
        StepModel.set_chat_step(message.chat.id, const.Steps.order_input_phone)
        bot.send_message(message.chat.id, 'Введите ваш телефон')
    else:
        bot.send_message(message.chat.id, 'Не понял. Введите ваше имя')


def handle_order_input_phone(message):
    if message.text:
        user_input = UserDetails.get_current_user_input(chat_id=message.chat.id, user=message.from_user)
        user_input.phone = message.text
        user_input.save()
        StepModel.set_chat_step(message.chat.id, const.Steps.order_input_tm)
        bot.send_message(message.chat.id, 'Введите ваш @TM')
    else:
        bot.send_message(message.chat.id, 'Не понял. Введите ваш телефон')


def handle_order_input_tm(message):
    if message.text:
        user_input = UserDetails.get_current_user_input(chat_id=message.chat.id, user=message.from_user)
        user_input.tm_name = message.text
        user_input.save()
        StepModel.set_chat_step(message.chat.id, const.Steps.order_input_email)
        bot.send_message(message.chat.id, 'Введите ваш email')
    else:
        bot.send_message(message.chat.id, 'Не понял. Введите ваш @TM')


def handle_order_input_email(message):
    if message.text:
        user_input = UserDetails.get_current_user_input(chat_id=message.chat.id, user=message.from_user)
        user_input.email = message.text
        user_input.save()
        bot.send_message(message.chat.id, 'Спасибо')
        send_user_details_to_admin(user_input)
        show_start_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, 'Не понял. Введите ваш email')


def send_email(to, content):
    sg = sendgrid.SendGridAPIClient(apikey=current_config.SENDGRID_API_KEY)
    from_email = Email("oldPadavanBot@example.com")
    to_email = Email(to)
    subject = "New order - user details"
    content = Content("text/plain", content)
    mail = Mail(from_email, subject, to_email, content)
    sg.client.mail.send.post(request_body=mail.get())


def send_user_details_to_admin(user_details):
    admin_chat_id = AdminContact.get_admin_chat_id(SiteSettings.get_settings().admin_tm)
    if admin_chat_id:
        bot.send_message(admin_chat_id, str(user_details))

    admin_email = SiteSettings.get_settings().admin_email
    if admin_email:
        send_email(admin_email, str(user_details))


def handle_invitation_link_generation(message):
    token = TmUser.generate_invitation_token(message.from_user)
    invitation_url = '<a href="https://t.me/{bot_name}?start={token}">Ссылка для приглашения</a>'.format(
        bot_name=current_config.BOT_NAME,
        token=token)
    bot.send_message(message.chat.id, invitation_url, parse_mode='html')
    show_start_menu(message.chat.id)


def handle_invitated_users_list(message):
    invited_users = TmUser.get_invited_friends(message.from_user)
    if not invited_users:
        bot.send_message(message.chat.id, 'Вы ещё не запрашивали ссылку для приглашений')
        handle_invitation_link_generation(message)
        return
    bot.send_message(message.chat.id, 'Приглашённые вами: ' + ', '.join([user.name for user in invited_users[1]]))
    bot.send_message(message.chat.id, 'Приглашённые вами, приглашёнными вами: ' +
                     ', '.join([user.name for user in invited_users[2]]))
    bot.send_message(message.chat.id, 'Приглашённые вами, приглашёнными вами, приглашёнными вами: ' +
                     ', '.join([user.name for user in invited_users[3]]))
    show_start_menu(message.chat.id)


def handle_balance(message):
    balance = TmUser.get_balance(message.from_user)
    bot.send_message(message.chat.id, 'Ваш баланс: {}'.format(balance))
    show_start_menu(message.chat.id)


def handle_invitation_description(message):
    bot.send_message(message.chat.id, SiteSettings.get_invitation_description())
    show_start_menu(message.chat.id)


steps_handlers = {
    const.Steps.earnings_list: handle_earnings_list,
    const.Steps.invitations_choice: handle_invitation_choices,
    const.Steps.order: handle_begin_order_input,
    const.Steps.order_input_name: handle_order_input_name,
    const.Steps.order_input_phone: handle_order_input_phone,
    const.Steps.order_input_tm: handle_order_input_tm,
    const.Steps.order_input_email: handle_order_input_email
}


def init_bot():
    bot.remove_webhook()
    bot.set_webhook(url=current_config.WEB_HOOK_URL)


def get_step(chat_id):
    step = db.session.query(StepModel).filter_by(chat_id=chat_id).one_or_none()
    if step:
        return step.step


def generate_link_providers_keyboard():
    providers = [provider.name for provider in db.session.query(LinkProvider).all()]
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboard.add(*providers)
    return keyboard


@bot.message_handler(commands=['start'])
def start(message):
    args = telebot.util.extract_arguments(message.text)
    if args:
        token = args
        TmUser.parse_invitation_token(message.from_user, token)
    show_start_menu(message.chat.id)


@bot.message_handler(commands=['admin_save'])
def save_admin_contact(message):
    username = message.from_user.username
    if username:
        AdminContact.update_admin_contact(message.from_user.username, message.chat.id)
    show_start_menu(message.chat.id)


def show_start_menu(chat_id):
    StepModel.set_chat_step(chat_id, const.Steps.start)
    bot.send_message(chat_id, 'Что вы хотели бы сделать?', reply_markup=initial_choices_keyboard)


@bot.message_handler(func=lambda m: m.text.lower() == const.EARN_MONEY.lower())
def show_earnings_options(message):
    StepModel.set_chat_step(chat_id=message.chat.id, step=const.Steps.earnings_list)
    bot.send_message(message.chat.id, 'О каком способе заработка вы бы хотели узнать подробнее?',
                     reply_markup=generate_link_providers_keyboard())


@bot.message_handler(func=lambda m: m.text == const.INVITATIONS)
def show_invitations_options(message):
    StepModel.set_chat_step(chat_id=message.chat.id, step=const.Steps.invitations_choice)
    bot.send_message(message.chat.id, 'Выберите один из пунктов меню', reply_markup=invitations_choices_keyboard)


@bot.message_handler(func=lambda m: m.text == const.ORDER)
def show_order_description(message):
    StepModel.set_chat_step(chat_id=message.chat.id, step=const.Steps.order)
    bot.send_message(message.chat.id, SiteSettings.get_order_description(), reply_markup=order_keyboard)


@bot.message_handler(func=lambda m: True)
def handle_steps(message):
    step = get_step(message.chat.id)
    handler = steps_handlers.get(step)
    if handler:
        handler(message)
    else:
        bot.send_message(message.chat.id, 'Пожалуйста, повторите')
        show_start_menu(message.chat.id)
