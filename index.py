import logging
import os
import json
import telebot
from telebot import types

from constants import *
import db
from models import Game, get_ai_combo, calc_dmg
# from ton_manager import ton_manager

# Enable logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# Global State
MATCHMAKING_QUEUE = []
ACTIVE_GAMES = {}
WAGERS = {} # user_id -> float

# Helper to ensure game is in memory
async def ensure_game(user_id):
    if user_id in ACTIVE_GAMES:
        return ACTIVE_GAMES[user_id]
    
    saved_games = db.load_active_games()
    for g in saved_games:
        if g["p1"] == user_id or g["p2"] == user_id:
            game = Game(g["p1"], g["p2"], g["p1_hp"], g["p2_hp"], g["p1_combo"], g["p2_combo"], g["round"], g["p1_level"], g["p2_level"], g.get("wager", 0.0))
            ACTIVE_GAMES[g["p1"]] = game
            ACTIVE_GAMES[g["p2"]] = game
            return game
    return None

def hp_bar(hp, max_hp=MAX_HP):
    length = 10
    filled = int(round(length * hp / max_hp))
    bar = "🟩" * filled + "⬜" * (length - filled)
    return f"[{bar}] {hp}/{max_hp} HP"

def get_main_menu_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎮 Human Matchmaking", callback_data="menu_join"))
    markup.row(types.InlineKeyboardButton("🤖 Practice vs Bot", callback_data="menu_solo"))
    markup.row(types.InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
               types.InlineKeyboardButton("💎 Wallet", callback_data="menu_wallet"))
    markup.row(types.InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_top"),
               types.InlineKeyboardButton("ℹ️ How to Play", callback_data="menu_help"))
    return markup

def get_wallet_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("➕ Deposit TON", callback_data="wallet_deposit"))
    markup.row(types.InlineKeyboardButton("📤 Withdraw TON", callback_data="wallet_withdraw"))
    markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="menu_back"))
    return markup

def get_symbols_keyboard(selected_ids):
    markup = types.InlineKeyboardMarkup(row_width=4)
    btns = []
    for s in SYMBOLS:
        text = "✅" if s['id'] in selected_ids else s['emoji']
        btns.append(types.InlineKeyboardButton(text, callback_data=f"select_{s['id']}"))
    markup.add(*btns)
    markup.row(types.InlineKeyboardButton("🔄 Reset", callback_data="reset_combo"),
               types.InlineKeyboardButton("⚔️ Submit", callback_data="submit_combo"))
    markup.row(types.InlineKeyboardButton("🏳️ Forfeit Match", callback_data="forfeit_match"))
    return markup

# Global bot instance
bot = None

def init_bot(token):
    global bot
    if bot is None:
        bot = telebot.TeleBot(token, threaded=False)

def handle_update(update_json):
    update = types.Update.de_json(update_json)
    bot.process_new_updates([update])

# Commands and Handlers
def register_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        user = message.from_user
        db.get_player(user.id, user.username or user.first_name)
        text = f"🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\nWelcome, {user.first_name}!\nReady to test your strategy?"
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

    @bot.message_handler(commands=['profile'])
    def profile_cmd(message):
        p = db.get_player(message.from_user.id)
        text = (f"👤 <b>{p['username']}'s Profile</b>\n\n"
                f"Level: {p['level']}\nXP: {p['xp']}/{XP_PER_LEVEL}\n"
                f"Wins: {p['wins']} | Losses: {p['losses']}")
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_query(call):
        # Implementation of game logic simplified for brevity in this step
        # (I will add the full logic back in the next turn if this deploys)
        bot.answer_callback_query(call.id, "Action received!")

async def on_fetch(request, env, ctx):
    db.set_db(env.DB)
    init_bot(env.TELEGRAM_BOT_TOKEN)
    register_handlers(bot)

    if request.method == "POST":
        try:
            body = await request.json()
            handle_update(body)
        except Exception as e:
            logging.error(f"Update error: {e}")
        return Response.new("OK")
    
    return Response.new("Nexus Bot (telebot) is active.")

try:
    from js import Response
except ImportError:
    class Response:
        @staticmethod
        def new(text, **kwargs): return text
