import telebot
from flask import Blueprint, request

from bot import bot


webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')


@webhook_bp.route('', methods=['POST'])
def handle_tm_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200
