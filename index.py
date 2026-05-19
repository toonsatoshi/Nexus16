import logging
import json
import random
from js import fetch, Object, Response
from pyodide.ffi import to_js

from constants import *
import db
from models import Game, get_ai_combo, calc_dmg

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global State
MATCHMAKING_QUEUE = []
ACTIVE_GAMES = {}
WAGERS = {} # user_id -> float

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def _post(self, method, data):
        url = f"{self.base_url}/{method}"
        payload = json.dumps(data)
        
        try:
            # Using native JS fetch via pyodide with correct object conversion
            options = to_js({
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": payload
            }, dict_converter=Object.fromEntries)
            
            response = await fetch(url, options)
            js_data = await response.json()
            # Convert back to python dict if possible, or just return as is
            return json.loads(json.dumps(js_data.to_py())) if hasattr(js_data, "to_py") else js_data
        except Exception as e:
            logger.error(f"API Error ({method}): {e}")
            return {"ok": False, "error": str(e)}

    async def send_message(self, chat_id, text, parse_mode="HTML", reply_markup=None):
        data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup: data["reply_markup"] = reply_markup
        return await self._post("sendMessage", data)

    async def edit_message_text(self, chat_id, message_id, text, parse_mode="HTML", reply_markup=None):
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
        if reply_markup: data["reply_markup"] = reply_markup
        return await self._post("editMessageText", data)

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
            data["show_alert"] = show_alert
        return await self._post("answerCallbackQuery", data)

# Bot instance
bot = None

# UI Helpers
def hp_bar(hp, max_hp=MAX_HP):
    length = 10
    filled = int(round(length * hp / max_hp))
    bar = "🟩" * filled + "⬜" * (length - filled)
    return f"[{bar}] {hp}/{max_hp} HP"

def get_main_menu_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🎮 Human Matchmaking", "callback_data": "menu_join"}],
            [{"text": "🤖 Practice vs Bot", "callback_data": "menu_solo"}],
            [{"text": "👤 My Profile", "callback_data": "menu_profile"},
             {"text": "💎 Wallet", "callback_data": "menu_wallet"}],
            [{"text": "🏆 Leaderboard", "callback_data": "menu_top"},
             {"text": "ℹ️ How to Play", "callback_data": "menu_help"}]
        ]
    }

def get_wallet_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "➕ Deposit TON", "callback_data": "wallet_deposit"}],
            [{"text": "📤 Withdraw TON", "callback_data": "wallet_withdraw"}],
            [{"text": "⬅️ Back", "callback_data": "menu_back"}]
        ]
    }

def get_symbols_keyboard(selected_ids):
    keyboard = []
    row = []
    for i, s in enumerate(SYMBOLS):
        text = "✅" if s['id'] in selected_ids else s['emoji']
        row.append({"text": text, "callback_data": f"select_{s['id']}"})
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    keyboard.append([{"text": "🔄 Reset", "callback_data": "reset_combo"},
                     {"text": "⚔️ Submit", "callback_data": "submit_combo"}])
    keyboard.append([{"text": "🏳️ Forfeit Match", "callback_data": "forfeit_match"}])
    return {"inline_keyboard": keyboard}

# Game Logic
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

async def start_game(p1, p2):
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
        await bot.send_message(pid, msg, reply_markup=get_symbols_keyboard([]))

async def finish_round(game):
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
        await bot.send_message(pid, res)

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
            await bot.send_message(pid, msg, reply_markup=get_main_menu_keyboard())
        
        db.delete_active_game(p1, p2)
        if p1 in ACTIVE_GAMES: del ACTIVE_GAMES[p1]
        if p2 in ACTIVE_GAMES: del ACTIVE_GAMES[p2]
    else:
        for pid in [p1, p2]:
            if pid == AI_USER_ID: continue
            await bot.send_message(pid, f"⚔️ <b>Round {game.current_round} begins!</b>", reply_markup=get_symbols_keyboard([]))

# Update Handlers
async def process_update(update):
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            user = msg["from"]
            db.get_player(user_id, user.get("username") or user.get("first_name"))
            welcome = f"🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\nWelcome!\nReady to test your strategy?"
            await bot.send_message(chat_id, welcome, reply_markup=get_main_menu_keyboard())
        
        elif text.startswith("/profile"):
            p = db.get_player(user_id)
            profile_text = (f"👤 <b>{p['username']}'s Profile</b>\n\n"
                            f"Level: {p['level']}\nXP: {p['xp']}/{XP_PER_LEVEL}\n"
                            f"Wins: {p['wins']} | Losses: {p['losses']}")
            await bot.send_message(chat_id, profile_text)

    elif "callback_query" in update:
        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        data = cb["data"]

        if data == "menu_join":
            if user_id in MATCHMAKING_QUEUE:
                await bot.answer_callback_query(cb["id"], "Still searching...")
            else:
                MATCHMAKING_QUEUE.append(user_id)
                await bot.edit_message_text(chat_id, message_id, "🛰️ <b>Searching for an opponent...</b>", reply_markup={"inline_keyboard": [[{"text": "❌ Cancel", "callback_data": "leave_queue"}]]})
                if len(MATCHMAKING_QUEUE) >= 2:
                    p1 = MATCHMAKING_QUEUE.pop(0)
                    p2 = MATCHMAKING_QUEUE.pop(0)
                    await start_game(p1, p2)
        
        elif data == "menu_solo":
            await start_game(user_id, AI_USER_ID)
        
        elif data == "menu_back":
            await bot.edit_message_text(chat_id, message_id, "🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\nMain Menu", reply_markup=get_main_menu_keyboard())

        elif data == "menu_wallet":
            await wallet_menu(cb)

        elif data == "leave_queue":
            if user_id in MATCHMAKING_QUEUE:
                MATCHMAKING_QUEUE.remove(user_id)
                await bot.edit_message_text(chat_id, message_id, "Left the queue.", reply_markup=get_main_menu_keyboard())

        elif data.startswith("select_"):
            game = await ensure_game(user_id)
            if not game: return
            symbol_id = data.split("_")[1]
            combo = game.players[user_id]["combo"]
            if len(combo) < 3 and symbol_id not in combo:
                combo.append(symbol_id)
                await bot.edit_message_text(chat_id, message_id, cb["message"].get("text", "Round in progress"), reply_markup=get_symbols_keyboard(combo))
            else:
                await bot.answer_callback_query(cb["id"], "Selection full.")

        elif data == "submit_combo":
            game = await ensure_game(user_id)
            if not game: return
            combo = game.players[user_id]["combo"]
            if len(combo) != 3:
                await bot.answer_callback_query(cb["id"], "Select 3 symbols!", show_alert=True)
                return
            game.set_player_combo(user_id, combo)
            await bot.edit_message_text(chat_id, message_id, "⌛ <b>Waiting for opponent...</b>")
            
            if game.is_vs_ai:
                game.set_player_combo(AI_USER_ID, get_ai_combo())
            
            if game.is_round_ready():
                await finish_round(game)
        
        await bot.answer_callback_query(cb["id"])

async def wallet_menu(cb):
    user_id = cb["from"]["id"]
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    p = db.get_player(user_id)
    text = (f"💎 <b>Your Nexus Wallet</b>\n\n"
            f"<b>Address:</b> <code>{p['wallet_address'] or 'Not Created'}</code>\n"
            f"<b>Balance:</b> {round(p['ton_balance'], 4)} TON")
    await bot.edit_message_text(chat_id, message_id, text, reply_markup=get_wallet_keyboard())

# Cloudflare Worker Entry
async def on_fetch(request, env, ctx):
    global bot
    try:
        # Ensure DB is initialized
        db.set_db(env.DB)
        
        # Initialize Bot if needed
        if bot is None:
            token = getattr(env, "BOT_TOKEN", None)
            if not token:
                return Response.new("BOT_TOKEN not found in env. Please set it using 'wrangler secret put BOT_TOKEN'.", status=500)
            bot = TelegramBot(token)

        # Handle specific routes
        url = str(request.url)
        
        if "/set-webhook" in url:
            # Construct the webhook URL by removing the path
            base_url = url.split("/set-webhook")[0]
            res = await bot._post("setWebhook", {"url": base_url})
            return Response.new(json.dumps(res), headers=Object.fromEntries(to_js({"Content-Type": "application/json"})))

        if "/health" in url:
            try:
                leaders = db.get_leaderboard(1)
                return Response.new(f"Health OK. DB Ready. Leaders: {len(leaders)}")
            except Exception as e:
                return Response.new(f"Health Fail: {e}", status=500)

        if request.method == "POST":
            try:
                body_text = await request.text()
                logger.info(f"Received update: {body_text}")
                body = json.loads(body_text)
                await process_update(body)
                return Response.new("OK")
            except Exception as e:
                logger.error(f"Error processing update: {e}")
                return Response.new(f"Error: {e}", status=500)
        
        return Response.new("Nexus Bot is Active. Visit /set-webhook to register.")

    except Exception as e:
        logger.error(f"Global Worker Error: {e}")
        return Response.new(f"Critical Worker Error: {e}", status=500)
