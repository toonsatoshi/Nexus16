import json

# Global DB object to be set by the entry point
_DB = None

def set_db(db):
    global _DB
    _DB = db

async def get_player(user_id, username=None):
    if not _DB:
        raise Exception("Database not initialized")
    
    # D1 fetcher
    stmt = _DB.prepare("SELECT user_id, username, xp, level, wins, losses, ton_balance, wallet_address, wallet_mnemonic FROM players WHERE user_id = ?").bind(user_id)
    row = await stmt.first()
    
    if not row:
        await _DB.prepare("INSERT INTO players (user_id, username) VALUES (?, ?)").bind(user_id, username).run()
        return await get_player(user_id, username)
    
    return {
        "user_id": row.user_id,
        "username": row.username,
        "xp": row.xp,
        "level": row.level,
        "wins": row.wins,
        "losses": row.losses,
        "ton_balance": row.ton_balance,
        "wallet_address": row.wallet_address,
        "wallet_mnemonic": row.wallet_mnemonic
    }


async def update_player_wallet(user_id, address, mnemonic):
    await _DB.prepare("UPDATE players SET wallet_address = ?, wallet_mnemonic = ? WHERE user_id = ?").bind(address, mnemonic, user_id).run()

async def update_player(user_id, xp_gain, win=False, loss=False):
    player = await get_player(user_id)
    new_xp = player["xp"] + xp_gain
    new_level = player["level"]
    
    from constants import XP_PER_LEVEL
    while new_xp >= XP_PER_LEVEL:
        new_xp -= XP_PER_LEVEL
        new_level += 1
    
    new_wins = player["wins"] + (1 if win else 0)
    new_losses = player["losses"] + (1 if loss else 0)
    
    await _DB.prepare("""
        UPDATE players SET xp = ?, level = ?, wins = ?, losses = ? WHERE user_id = ?
    """).bind(new_xp, new_level, new_wins, new_losses, user_id).run()
    
    return new_level > player["level"]

async def save_active_game(p1_id, p2_id, game_data):
    await _DB.prepare("INSERT OR REPLACE INTO active_games (p1_id, p2_id, game_data) VALUES (?, ?, ?)").bind(p1_id, p2_id, json.dumps(game_data)).run()

async def delete_active_game(p1_id, p2_id):
    await _DB.prepare("DELETE FROM active_games WHERE p1_id = ? AND p2_id = ?").bind(p1_id, p2_id).run()

async def load_active_games():
    res = await _DB.prepare("SELECT game_data FROM active_games").all()
    return [json.loads(r.game_data) for r in res.results]

async def update_ton_balance(user_id, amount_change, tx_hash=None, tx_type=None):
    await _DB.prepare("UPDATE players SET ton_balance = ton_balance + ? WHERE user_id = ?").bind(amount_change, user_id).run()
    
    if tx_hash and tx_type:
        await _DB.prepare("INSERT OR IGNORE INTO transactions (tx_hash, user_id, amount, type) VALUES (?, ?, ?, ?)").bind(tx_hash, user_id, amount_change, tx_type).run()

async def get_leaderboard(limit=10):
    res = await _DB.prepare("""
        SELECT username, level, wins, user_id FROM players 
        ORDER BY level DESC, wins DESC 
        LIMIT ?
    """).bind(limit).all()
    return [(r.username, r.level, r.wins, r.user_id) for r in res.results]


def init_db():
    # In Workers, initialization is usually done via wrangler d1 execute
    pass
