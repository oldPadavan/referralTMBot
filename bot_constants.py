import enum


@enum.unique
class Steps(enum.IntEnum):
    start = 0
    earnings_list = 1
    invitations_choice = 2
    order = 3
    make_order = 4
    order_input_name = 5
    order_input_phone = 6
    order_input_tm = 7
    order_input_email = 8


# site settings const
DEFAULT_INVITATION_DESCRIPTION = 'Реферральная система поможет вам заработать'
DEFAULT_ORDER_DESCRIPTION = 'Оставьте свою заявку и мы свяжемся с вами'


# there was nothing specified about rewards for different levels so I choices the same amount
REWARD_1ST_LEVEL_INVITE = 100
REWARD_2ND_LEVEL_INVITE = 100
REWARD_3RD_LEVEL_INVITE = 100


EARN_MONEY = 'Как зарабатывать в интернете'
INVITATIONS = 'Приглашённые друзья'
ORDER = 'Заказать'
INITIAL_CHOICES = [EARN_MONEY, INVITATIONS, ORDER]


INVITATION_LINK = 'Ссылка для приглашения'
USER_INVITED_FRIENDS = 'Список приглашённых'
BALANCE = 'Баланс'
INVITATION_DESCRIPTION = 'Описание системы приглашений'
INVITATION_CHOICES = [INVITATION_LINK, USER_INVITED_FRIENDS, BALANCE, INVITATION_DESCRIPTION]


ORDER_BUTTON_TEXT = 'Оставить заявку'
