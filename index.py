import logging
import os
import json
import random
import telebot
from telebot import types

from constants import *
import db
from models import Game, get_ai_combo, calc_dmg

# Toncenter API Helper (Alternative to tonutils for Worker compatibility)
class ToncenterClient:
    def __init__(self, api_key=None, is_testnet=True):
        self.api_key = api_key
        self.base_url = "https://testnet.toncenter.com/api/v2" if is_testnet else "https://toncenter.com/api/v2"

    def _request(self, method, params=None):
        import requests
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        resp = requests.get(f"{self.base_url}/{method}", params=params, headers=headers)
        return resp.json()

    def get_address_balance(self, address):
        res = self._request("getAddressInformation", {"address": address})
        if res.get("ok"):
            return int(res["result"]["balance"]) / 1e9
        return 0.0

    def send_boc(self, boc_base64):
        # This would require signing, which usually needs PyNaCl/cryptography.
        # For now, we'll keep transfers as placeholders or use an external signer service.
        pass

# Global State
MATCHMAKING_QUEUE = []
ACTIVE_GAMES = {}
WAGERS = {} # user_id -> float

# Bot Instance
bot = None

def init_bot(token):
    global bot
    if bot is None:
        bot = telebot.TeleBot(token, threaded=False)

# Helpers
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

# TON Integration Placeholder
class MockTonManager:
    async def transfer(self, *args, **kwargs):
        return "mock_tx_hash"
    async def create_user_wallet(self, user_id):
        return "EQMockAddress", "mock mnemonic"

ton_manager = MockTonManager()

def register_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        user = message.from_user
        db.get_player(user.id, user.username or user.first_name)
        text = (f"🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\n"
                f"Welcome, {user.first_name}!\n"
                "Ready to test your strategic combinations in the Nexus arena?")
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

    @bot.message_handler(commands=['profile'])
    def profile_cmd(message):
        user = message.from_user
        p = db.get_player(user.id, user.username or user.first_name)
        text = (f"👤 <b>{p['username']}'s Profile</b>\n\n"
                f"Level: {p['level']}\n"
                f"XP: {p['xp']}/{XP_PER_LEVEL}\n"
                f"Wins: {p['wins']} | Losses: {p['losses']}\n"
                f"Win Rate: {round(p['wins']/(p['wins']+p['losses'])*100 if (p['wins']+p['losses']) > 0 else 0, 1)}%")
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(commands=['top'])
    def top_cmd(message):
        leaders = db.get_leaderboard()
        text = "🏆 <b>Nexus Leaderboard</b> 🏆\n\n"
        for i, (name, lvl, wins, uid) in enumerate(leaders):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
            text += f"{medal} <b>{name}</b> (Lvl {lvl}) - {wins} wins\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call):
        user_id = call.from_user.id
        data = call.data

        if data.startswith("menu_"):
            if data == "menu_join":
                if user_id in MATCHMAKING_QUEUE:
                    bot.answer_callback_query(call.id, "Still searching...")
                else:
                    MATCHMAKING_QUEUE.append(user_id)
                    bot.edit_message_text("🛰️ <b>Searching for an opponent...</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=types.InlineKeyboardMarkup().row(types.InlineKeyboardButton("❌ Cancel", callback_data="leave_queue")))
                    if len(MATCHMAKING_QUEUE) >= 2:
                        p1 = MATCHMAKING_QUEUE.pop(0)
                        p2 = MATCHMAKING_QUEUE.pop(0)
                        start_game(p1, p2)
            elif data == "menu_solo":
                start_game(user_id, AI_USER_ID)
            elif data == "menu_profile":
                bot.answer_callback_query(call.id)
                profile_cmd(call.message)
            elif data == "menu_wallet":
                wallet_menu(call)
            elif data == "menu_back":
                bot.edit_message_text(f"🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\nMain Menu", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
            return

        if data == "leave_queue":
            if user_id in MATCHMAKING_QUEUE:
                MATCHMAKING_QUEUE.remove(user_id)
                bot.edit_message_text("Left the queue.", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_keyboard())
            return

        if data.startswith("select_"):
            # Game logic for symbol selection
            game = ACTIVE_GAMES.get(user_id)
            if not game: return
            symbol_id = data.split("_")[1]
            combo = game.players[user_id]["combo"]
            if len(combo) < 3 and symbol_id not in combo:
                combo.append(symbol_id)
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_symbols_keyboard(combo))
            else:
                bot.answer_callback_query(call.id, "Selection full or symbol already chosen.")
            return

        if data == "submit_combo":
            game = ACTIVE_GAMES.get(user_id)
            if not game: return
            combo = game.players[user_id]["combo"]
            if len(combo) != 3:
                bot.answer_callback_query(call.id, "Select 3 symbols!", show_alert=True)
                return
            game.set_player_combo(user_id, combo)
            bot.edit_message_text("⌛ <b>Waiting for opponent...</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            
            if game.is_vs_ai:
                game.set_player_combo(AI_USER_ID, get_ai_combo())
            
            if game.is_round_ready():
                finish_round(game)
            return

        if data == "forfeit_match":
            # Forfeit logic
            pass

def start_game(p1, p2):
    p1_data = db.get_player(p1)
    p2_data = db.get_player(p2, "Nexus Bot") if p2 != AI_USER_ID else {"level": 1}
    
    game = Game(p1, p2, p1_level=p1_data["level"], p2_level=p2_data["level"])
    ACTIVE_GAMES[p1] = game
    ACTIVE_GAMES[p2] = game
    db.save_active_game(p1, p2, game.to_dict())

    for pid in [p1, p2]:
        if pid == AI_USER_ID: continue
        opp_id = game.get_opponent_id(pid)
        opp_p = db.get_player(opp_id, "Nexus Bot") if opp_id != AI_USER_ID else {"username": "Nexus Bot", "level": 1}
        msg = (f"⚔️ <b>Match Found!</b> ⚔️\n\n"
               f"You vs <b>{opp_p['username']}</b> (Lvl {opp_p['level']})\n"
               f"Round 1 begins. Select 3 symbols.")
        bot.send_message(pid, msg, parse_mode="HTML", reply_markup=get_symbols_keyboard([]))

def finish_round(game):
    p1, p2 = game.p1_id, game.p2_id
    p1_dmg, p2_dmg = game.process_round()
    db.save_active_game(p1, p2, game.to_dict())

    for pid in [p1, p2]:
        if pid == AI_USER_ID: continue
        opp_id = game.get_opponent_id(pid)
        opp_name = "Nexus Bot" if opp_id == AI_USER_ID else "Opponent"
        
        my_c = " ".join([next(s['emoji'] for s in SYMBOLS if s['id'] == cid) for cid in game.players[pid]["history"][-1]])
        opp_c = " ".join([next(s['emoji'] for s in SYMBOLS if s['id'] == cid) for cid in game.players[opp_id]["history"][-1]])
        
        res = (f"💥 <b>Round {game.current_round - 1} Results</b> 💥\n\n"
               f"You: {my_c} (-{p2_dmg} HP)\n"
               f"{opp_name}: {opp_c} (-{p1_dmg} HP)\n\n"
               f"<b>Your HP:</b>\n{hp_bar(game.players[pid]['hp'])}\n"
               f"<b>{opp_name} HP:</b>\n{hp_bar(game.players[opp_id]['hp'])}\n")
        bot.send_message(pid, res, parse_mode="HTML")

    if game.is_game_over():
        winner_id = game.get_winner()
        for pid in [p1, p2]:
            if pid == AI_USER_ID: continue
            if winner_id == "Draw":
                msg = "🤝 <b>It's a Draw!</b>"
                db.update_player(pid, XP_PER_LOSS)
            elif winner_id == pid:
                msg = "🏆 <b>Victory!</b>"
                leveled_up = db.update_player(pid, XP_PER_WIN, win=True)
                if leveled_up: msg += "\n\n✨ <b>Level Up!</b>"
            else:
                msg = "💀 <b>Defeat!</b>"
                db.update_player(pid, XP_PER_LOSS, loss=True)
            bot.send_message(pid, msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        
        db.delete_active_game(p1, p2)
        if p1 in ACTIVE_GAMES: del ACTIVE_GAMES[p1]
        if p2 in ACTIVE_GAMES: del ACTIVE_GAMES[p2]
    else:
        for pid in [p1, p2]:
            if pid == AI_USER_ID: continue
            bot.send_message(pid, f"⚔️ <b>Round {game.current_round} begins!</b>", parse_mode="HTML", reply_markup=get_symbols_keyboard([]))

def wallet_menu(call):
    user = call.from_user
    p = db.get_player(user.id)
    text = (f"💎 <b>Your Nexus Wallet</b>\n\n"
            f"<b>Address:</b> <code>{p['wallet_address'] or 'Not Created'}</code>\n"
            f"<b>Balance:</b> {round(p['ton_balance'], 4)} TON")
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_wallet_keyboard())

# Cloudflare Worker Entry
async def on_fetch(request, env, ctx):
    db.set_db(env.DB)
    init_bot(env.TELEGRAM_BOT_TOKEN)
    register_handlers(bot)

    if request.method == "POST":
        try:
            body = await request.json()
            update = types.Update.de_json(body)
            bot.process_new_updates([update])
        except Exception as e:
            logging.error(f"Error: {e}")
        return Response.new("OK")
    
    return Response.new("Nexus Bot is Active.")

try:
    from js import Response
except ImportError:
    class Response:
        @staticmethod
        def new(text, **kwargs): return text
