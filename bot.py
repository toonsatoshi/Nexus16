import logging
import os
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from constants import *
import db
from models import Game, get_ai_combo, calc_dmg
# from ton_manager import ton_manager

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Global State (Persistent in memory for the life of the worker instance, but should be backed by DB)
MATCHMAKING_QUEUE = []
ACTIVE_GAMES = {}
WAGERS = {} # user_id -> float

# Helper to ensure game is in memory
async def ensure_game(user_id):
    if user_id in ACTIVE_GAMES:
        return ACTIVE_GAMES[user_id]
    
    # Load from DB
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
    keyboard = [
        [InlineKeyboardButton("🎮 Human Matchmaking", callback_data="menu_join")],
        [InlineKeyboardButton("🤖 Practice vs Bot", callback_data="menu_solo")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
         InlineKeyboardButton("💎 Wallet", callback_data="menu_wallet")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_top"),
         InlineKeyboardButton("ℹ️ How to Play", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_wallet_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Deposit TON", callback_data="wallet_deposit")],
        [InlineKeyboardButton("📤 Withdraw TON", callback_data="wallet_withdraw")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    p = db.get_player(user.id, user.username or user.first_name)
    
    if not p["wallet_address"]:
        # await ton_manager.create_user_wallet(user.id)
        pass
        p = db.get_player(user.id)
    
    text = (f"💎 <b>Your Nexus Wallet</b> 💎\n\n"
            f"<b>Address:</b>\n<code>{p['wallet_address']}</code>\n\n"
            f"<b>Balance:</b> {round(p['ton_balance'], 4)} TON\n\n"
            f"<i>You can fund this wallet to wager in PvP matches.</i>\n"
            f"<i>Keep your mnemonic safe (available in /profile).</i>")
    
    if update.message:
        await update.message.reply_html(text, reply_markup=get_wallet_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_wallet_keyboard(), parse_mode="HTML")

def get_symbols_keyboard(selected_ids):
    keyboard = []
    row = []
    for i, s in enumerate(SYMBOLS):
        text = f"{s['emoji']}"
        if s['id'] in selected_ids:
            text = "✅"
        row.append(InlineKeyboardButton(text, callback_data=f"select_{s['id']}"))
        if (i + 1) % 4 == 0:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("🔄 Reset", callback_data="reset_combo"),
                     InlineKeyboardButton("⚔️ Submit", callback_data="submit_combo")])
    keyboard.append([InlineKeyboardButton("🏳️ Forfeit Match", callback_data="forfeit_match")])
    return InlineKeyboardMarkup(keyboard)

async def set_wager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        amount = float(context.args[0])
        if amount < 0: raise ValueError
        
        p = db.get_player(user_id)
        if p["ton_balance"] < amount:
            await update.message.reply_text(f"❌ Insufficient balance. Your balance: {p['ton_balance']} TON")
            return
            
        WAGERS[user_id] = amount
        await update.message.reply_text(f"✅ Wager set to {amount} TON for your next match.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /wager <amount>")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.get_player(user.id, user.username or user.first_name)
    
    text = (f"🛡️ <b>NEXUS-7 PvP</b> 🛡️\n\n"
            f"Welcome, {user.mention_html()}!\n"
            "Ready to test your strategic combinations in the Nexus arena?")
    
    if update.message:
        await update.message.reply_html(text, reply_markup=get_main_menu_keyboard())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    p = db.get_player(user.id, user.username or user.first_name)
    
    text = (f"👤 <b>{p['username']}'s Profile</b>\n\n"
            f"Level: {p['level']}\n"
            f"XP: {p['xp']}/{XP_PER_LEVEL}\n"
            f"Wins: {p['wins']}\n"
            f"Losses: {p['losses']}\n"
            f"Win Rate: {round(p['wins']/(p['wins']+p['losses'])*100 if (p['wins']+p['losses']) > 0 else 0, 1)}%\n\n"
            f"🔐 <b>Recovery Mnemonic:</b>\n<pre>{p['wallet_mnemonic']}</pre>\n"
            f"<i>Do not share this with anyone!</i>")
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    
    if update.message:
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    leaders = db.get_leaderboard()
    text = "🏆 <b>Nexus Leaderboard</b> 🏆\n\n"
    for i, (name, lvl, wins, uid) in enumerate(leaders):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
        text += f"{medal} <b>{name}</b> (Lvl {lvl}) - {wins} wins\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    
    if update.message:
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def join_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    
    await ensure_game(user_id)
    if user_id in ACTIVE_GAMES:
        await query.answer("You are already in a game!")
        return
    if user_id in MATCHMAKING_QUEUE:
        await query.answer("Still searching...")
        return

    MATCHMAKING_QUEUE.append(user_id)
    await query.answer("Entering queue...")
    
    caption = "🛰️ <b>Searching for an opponent...</b>\n\nTip: Leveling up increases your base damage!"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Search", callback_data="leave_queue")]])
    await query.edit_message_text(caption, parse_mode="HTML", reply_markup=keyboard)

    if len(MATCHMAKING_QUEUE) >= 2:
        p1 = MATCHMAKING_QUEUE.pop(0)
        p2 = MATCHMAKING_QUEUE.pop(0)
        await start_game(p1, p2, context)

async def solo_battle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await ensure_game(user_id)
    if user_id in ACTIVE_GAMES:
        await query.answer("You are already in a game!")
        return
    if user_id in MATCHMAKING_QUEUE:
        MATCHMAKING_QUEUE.remove(user_id)
    
    await start_game(user_id, AI_USER_ID, context)

ARENA_ADDRESS = os.getenv("TON_WALLET_ADDRESS")
ARENA_MNEMONIC = os.getenv("TON_MNEMONIC")

async def start_game(p1, p2, context):
    p1_data = db.get_player(p1)
    p2_data = db.get_player(p2, "Nexus Bot") if p2 != AI_USER_ID else {"level": 1, "ton_balance": 0}
    
    # Calculate wager
    w1 = WAGERS.get(p1, 0)
    w2 = WAGERS.get(p2, 0) if p2 != AI_USER_ID else 0
    match_wager = min(w1, w2)
    
    if match_wager > 0:
        # Check balances
        if p1_data["ton_balance"] < match_wager or (p2 != AI_USER_ID and p2_data["ton_balance"] < match_wager):
            for pid in [p1, p2]:
                if pid == AI_USER_ID: continue
                await context.bot.send_message(chat_id=pid, text="❌ Match cancelled: Insufficient balance for wager.")
            return

        # Start escrow transfers
        await context.bot.send_message(chat_id=p1, text=f"⏳ Locking {match_wager} TON wager...")
        # tx1 = await ton_manager.transfer(p1_data["wallet_mnemonic"], ARENA_ADDRESS, match_wager, f"Game Escrow: {p1}")
        tx1 = "mock_tx"
        
        if p2 != AI_USER_ID:
            await context.bot.send_message(chat_id=p2, text=f"⏳ Locking {match_wager} TON wager...")
            # tx2 = await ton_manager.transfer(p2_data["wallet_mnemonic"], ARENA_ADDRESS, match_wager, f"Game Escrow: {p2}")
            tx2 = "mock_tx"
            if not tx2:
                # if tx1: await ton_manager.transfer(ARENA_MNEMONIC, p1_data["wallet_address"], match_wager, "Refund: Opponent Error")
                await context.bot.send_message(chat_id=p1, text="❌ Match cancelled: Opponent wallet error.")
                return
        
        if not tx1:
            await context.bot.send_message(chat_id=p1, text="❌ Match cancelled: Your wallet error.")
            return

    game = Game(p1, p2, p1_level=p1_data["level"], p2_level=p2_data["level"])
    game.wager = match_wager
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
        
        await context.bot.send_message(chat_id=pid, text=msg, parse_mode="HTML", reply_markup=get_symbols_keyboard([]))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith("menu_"):
        if data == "menu_join": await join_queue(update, context)
        elif data == "menu_solo": await solo_battle(update, context)
        elif data == "menu_profile": await profile(update, context)
        elif data == "menu_wallet": await wallet_menu(update, context)
        elif data == "menu_top": await top(update, context)
        elif data == "menu_back": await start(update, context)
        elif data == "menu_help": await query.answer("Pick 3 symbols to battle!", show_alert=True)
        return

    if data.startswith("wallet_"):
        if data == "wallet_deposit":
            await query.answer("Send Testnet TON to your wallet address listed in the menu.", show_alert=True)
        elif data == "wallet_withdraw":
            await query.answer("Withdrawals coming soon! Use your mnemonic to withdraw manually for now.", show_alert=True)
        return

    if data == "leave_queue":
        if user_id in MATCHMAKING_QUEUE:
            MATCHMAKING_QUEUE.remove(user_id)
            await query.answer("Left the queue.")
            await start(update, context)
        return

    await ensure_game(user_id)
    if data == "forfeit_match":
        if user_id in ACTIVE_GAMES:
            game = ACTIVE_GAMES[user_id]
            opp_id = game.get_opponent_id(user_id)
            wager = game.wager
            
            db.delete_active_game(game.p1_id, game.p2_id)
            if game.p1_id in ACTIVE_GAMES: del ACTIVE_GAMES[game.p1_id]
            if game.p2_id in ACTIVE_GAMES: del ACTIVE_GAMES[game.p2_id]
            
            await query.message.reply_text("🏳️ You forfeited the game.", reply_markup=get_main_menu_keyboard())
            if opp_id != AI_USER_ID:
                db.update_player(opp_id, XP_PER_WIN, win=True)
                msg = "🏳️ Opponent forfeited. You win!"
                if wager > 0:
                    payout = wager * 2 * 0.95
                    msg += f"\n💰 <b>Payout: {round(payout, 4)} TON</b>"
                    # await ton_manager.transfer(ARENA_MNEMONIC, db.get_player(opp_id)["wallet_address"], payout, "Opponent Forfeit")
                await context.bot.send_message(chat_id=opp_id, text=msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
            await query.message.delete()
        return

    if user_id not in ACTIVE_GAMES:
        await query.answer("No active game found.")
        return

    game = ACTIVE_GAMES[user_id]
    combo = game.players[user_id]["combo"]

    if data.startswith("select_"):
        symbol_id = data.split("_")[1]
        if len(combo) < 3 and symbol_id not in combo:
            combo.append(symbol_id)
            await query.edit_message_reply_markup(reply_markup=get_symbols_keyboard(combo))
        else:
            await query.answer("Max 3 symbols or already selected.")
            
    elif data == "reset_combo":
        game.players[user_id]["combo"] = []
        await query.edit_message_reply_markup(reply_markup=get_symbols_keyboard([]))
        
    elif data == "submit_combo":
        if len(combo) != 3:
            await query.answer("Select 3 symbols first!", show_alert=True)
            return
        
        game.set_player_combo(user_id, combo)
        
        text = "⌛ <b>Waiting for opponent...</b>"
        if query.message.caption:
            await query.edit_message_caption(caption=text, parse_mode="HTML")
        else:
            await query.edit_message_text(text=text, parse_mode="HTML")
        
        if game.is_vs_ai:
            game.set_player_combo(AI_USER_ID, get_ai_combo())
        
        if game.is_round_ready():
            await finish_round(game, context)

async def finish_round(game, context):
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
        
        await context.bot.send_message(chat_id=pid, text=res, parse_mode="HTML")

    if game.is_game_over():
        winner_id = game.get_winner()
        wager = game.wager
        
        for pid in [p1, p2]:
            if pid == AI_USER_ID: continue
            
            if winner_id == "Draw":
                msg = "🤝 <b>It's a Draw!</b>\nBoth players fought to a standstill."
                if wager > 0:
                    msg += f"\nYour {wager} TON wager has been refunded."
                    # await ton_manager.transfer(ARENA_MNEMONIC, db.get_player(pid)["wallet_address"], wager, "Refund: Draw")
                db.update_player(pid, XP_PER_LOSS)
            elif winner_id == pid:
                payout = wager * 2 * 0.95 # 5% arena fee
                msg = "🏆 <b>Victory!</b>\nYou have defeated your opponent and gained XP!"
                if wager > 0:
                    msg += f"\n💰 <b>Payout: {round(payout, 4)} TON</b> (95% of total pot)"
                    # await ton_manager.transfer(ARENA_MNEMONIC, db.get_player(pid)["wallet_address"], payout, "Match Payout")
                leveled_up = db.update_player(pid, XP_PER_WIN, win=True)
                if leveled_up: msg += "\n\n✨ <b>Level Up!</b> You are now stronger."
            else:
                msg = "💀 <b>Defeat!</b>\nYou were bested this time. Keep practicing!"
                if wager > 0: msg += f"\nYou lost your {wager} TON wager."
                db.update_player(pid, XP_PER_LOSS, loss=True)
            
            await context.bot.send_message(chat_id=pid, text=msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        
        db.delete_active_game(p1, p2)
        if p1 in ACTIVE_GAMES: del ACTIVE_GAMES[p1]
        if p2 in ACTIVE_GAMES: del ACTIVE_GAMES[p2]
    else:
        for pid in [p1, p2]:
            if pid == AI_USER_ID: continue
            await context.bot.send_message(chat_id=pid, text=f"⚔️ <b>Round {game.current_round} begins!</b>", parse_mode="HTML", reply_markup=get_symbols_keyboard([]))

async def quit_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await ensure_game(user_id)
    if user_id not in ACTIVE_GAMES:
        await update.message.reply_text("You aren't in a game.")
        return
    
    game = ACTIVE_GAMES[user_id]
    opp_id = game.get_opponent_id(user_id)
    wager = game.wager
    
    db.delete_active_game(game.p1_id, game.p2_id)
    if game.p1_id in ACTIVE_GAMES: del ACTIVE_GAMES[game.p1_id]
    if game.p2_id in ACTIVE_GAMES: del ACTIVE_GAMES[game.p2_id]
    
    await update.message.reply_text("🏳️ You forfeited the game.", reply_markup=get_main_menu_keyboard())
    if opp_id != AI_USER_ID:
        db.update_player(opp_id, XP_PER_WIN, win=True)
        msg = "🏳️ Opponent forfeited. You win!"
        if wager > 0:
            payout = wager * 2 * 0.95
            msg += f"\n💰 <b>Payout: {round(payout, 4)} TON</b>"
            # await ton_manager.transfer(ARENA_MNEMONIC, db.get_player(opp_id)["wallet_address"], payout, "Opponent Forfeit")
        await context.bot.send_message(chat_id=opp_id, text=msg, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

# Cloudflare Worker Entry Point
app = None

try:
    from js import Response
except ImportError:
    # Fallback for local testing
    class Response:
        @staticmethod
        def new(text, **kwargs):
            return text

async def on_fetch(request, env, ctx):
    global app
    
    # Initialize DB
    db.set_db(env.DB)
    
    # Check for TON deposits (optional: on every request or use Cron)
    # ctx.waitUntil(ton_manager.check_deposits(app.bot))
    
    if request.method == "POST":
        if app is None:
            token = env.TELEGRAM_BOT_TOKEN
            app = Application.builder().token(token).updater(None).build()
            
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("profile", profile))
            app.add_handler(CommandHandler("top", top))
            app.add_handler(CommandHandler("wager", set_wager))
            app.add_handler(CommandHandler("quit", quit_game))
            app.add_handler(CallbackQueryHandler(handle_callback))
            
            await app.initialize()

        try:
            body = await request.json()
            update = Update.de_json(body, app.bot)
            await app.process_update(update)
        except Exception as e:
            logger.error(f"Error processing update: {e}")
        
        return Response.new("OK")
    
    return Response.new("Nexus Bot is running!")

# For local testing/non-worker environments
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Mock behavior or run polling if needed
    pass
