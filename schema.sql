-- Players table
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ton_balance REAL DEFAULT 0.0,
    wallet_address TEXT,
    wallet_mnemonic TEXT
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    tx_hash TEXT PRIMARY KEY,
    user_id INTEGER,
    amount REAL,
    type TEXT, -- 'deposit', 'wager', 'payout', 'withdrawal'
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Active games table
CREATE TABLE IF NOT EXISTS active_games (
    p1_id INTEGER,
    p2_id INTEGER,
    game_data TEXT,
    PRIMARY KEY (p1_id, p2_id)
);
