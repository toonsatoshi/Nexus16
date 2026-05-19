SYMBOLS = [
    {"id": "fire", "name": "Fire", "emoji": "🔥", "color": "#ff6b35", "type": "ATK"},
    {"id": "water", "name": "Water", "emoji": "💧", "color": "#00aaff", "type": "DEF"},
    {"id": "earth", "name": "Earth", "emoji": "🪨", "color": "#c4953a", "type": "DEF"},
    {"id": "wind", "name": "Wind", "emoji": "🌪️", "color": "#89d4cf", "type": "AGI"},
    {"id": "lightning", "name": "Lightning", "emoji": "⚡", "color": "#ffd700", "type": "ATK"},
    {"id": "ice", "name": "Ice", "emoji": "❄️", "color": "#a8e6f0", "type": "CTR"},
    {"id": "shadow", "name": "Shadow", "emoji": "🌑", "color": "#bb86fc", "type": "AGI"},
    {"id": "light", "name": "Light", "emoji": "✨", "color": "#fffacd", "type": "SUP"},
    {"id": "nature", "name": "Nature", "emoji": "🌿", "color": "#00c853", "type": "SUP"},
    {"id": "metal", "name": "Metal", "emoji": "⚙️", "color": "#95a5a6", "type": "DEF"},
    {"id": "poison", "name": "Poison", "emoji": "☠️", "color": "#a855f7", "type": "CTR"},
    {"id": "time", "name": "Time", "emoji": "⏳", "color": "#f39c12", "type": "CTR"},
    {"id": "void", "name": "Void", "emoji": "🕳️", "color": "#9b59b6", "type": "???", "isBlindSpot": True},
    {"id": "blood", "name": "Blood", "emoji": "🩸", "color": "#e74c3c", "type": "ATK"},
    {"id": "crystal", "name": "Crystal", "emoji": "💎", "color": "#1abc9c", "type": "SUP"},
    {"id": "storm", "name": "Storm", "emoji": "🌩️", "color": "#7f8c8d", "type": "ATK"},
]

BEATS = {
    "fire": ["nature", "ice", "wind", "crystal"],
    "water": ["fire", "lightning", "poison", "blood"],
    "earth": ["lightning", "wind", "void", "storm"],
    "wind": ["fire", "poison", "nature", "shadow"],
    "lightning": ["water", "metal", "ice", "storm"],
    "ice": ["wind", "nature", "shadow", "void"],
    "shadow": ["light", "crystal", "time", "blood"],
    "light": ["shadow", "void", "poison", "metal"],
    "nature": ["earth", "water", "crystal", "time"],
    "metal": ["earth", "ice", "crystal", "wind"],
    "poison": ["nature", "water", "blood", "light"],
    "time": ["lightning", "fire", "ice", "void"],
    "void": ["time", "light", "metal", "crystal"],
    "blood": ["nature", "earth", "crystal", "light"],
    "crystal": ["fire", "shadow", "void", "poison"],
    "storm": ["earth", "nature", "metal", "water"],
}

NAMED_COMBOS = [
    {"ids": ["fire", "lightning", "storm"], "name": "Apocalypse Storm", "atkBonus": 38},
    {"ids": ["water", "ice", "crystal"], "name": "Glacial Fortress", "atkBonus": 8, "defBonus": 40},
    {"ids": ["shadow", "void", "time"], "name": "Eternal Dark", "atkBonus": 32, "defBonus": 15},
    {"ids": ["fire", "blood", "storm"], "name": "Crimson Fury", "atkBonus": 48},
    {"ids": ["light", "crystal", "nature"], "name": "Sacred Bloom", "atkBonus": 10, "defBonus": 38},
    {"ids": ["poison", "shadow", "blood"], "name": "Death Plague", "atkBonus": 42},
    {"ids": ["earth", "metal", "crystal"], "name": "Iron Citadel", "atkBonus": 0, "defBonus": 50},
    {"ids": ["lightning", "wind", "storm"], "name": "Thunder Surge", "atkBonus": 40},
    {"ids": ["void", "shadow", "poison"], "name": "Void Corruption", "atkBonus": 44, "defBonus": 5},
    {"ids": ["fire", "light", "lightning"], "name": "Solar Flare", "atkBonus": 32, "defBonus": 10},
    {"ids": ["ice", "crystal", "wind"], "name": "Blizzard Veil", "atkBonus": 14, "defBonus": 32},
    {"ids": ["time", "void", "shadow"], "name": "Temporal Rift", "atkBonus": 36, "defBonus": 18},
    {"ids": ["blood", "fire", "shadow"], "name": "Infernal Hunger", "atkBonus": 44},
    {"ids": ["nature", "earth", "water"], "name": "World's Heart", "atkBonus": 5, "defBonus": 44},
    {"ids": ["lightning", "blood", "storm"], "name": "Red Thunder", "atkBonus": 50},
]

BLIND_SPOT = "void"
MAX_HP = 100
BASE_DMG = 12
AI_USER_ID = 0
XP_PER_WIN = 25
XP_PER_LOSS = 5
XP_PER_LEVEL = 100
