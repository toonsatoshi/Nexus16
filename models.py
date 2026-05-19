from constants import *
import random

def combo_key(ids):
    return ",".join(sorted(ids))

def find_named_combo(ids):
    k = combo_key(ids)
    for combo in NAMED_COMBOS:
        if combo_key(combo["ids"]) == k:
            return combo
    return None

def combo_type(ids):
    cnt = {}
    for id_val in ids:
        cnt[id_val] = cnt.get(id_val, 0) + 1
    v = list(cnt.values())
    if 3 in v: return "TRIPLE"
    if 2 in v: return "PAIR"
    return "SPREAD"

def matchup_wins(mine, theirs):
    w = 0
    for m in mine:
        for t in theirs:
            if m in BEATS and t in BEATS[m]:
                w += 1
    return w

def calc_dmg(atk_combo, def_combo, atk_level=1):
    dmg = BASE_DMG + (atk_level - 1) * 2
    named = find_named_combo(atk_combo)
    combo_t = combo_type(atk_combo)

    if named: dmg += named.get("atkBonus", 0)
    
    wins = matchup_wins(atk_combo, def_combo)
    dmg += wins * 5

    if BLIND_SPOT in atk_combo: dmg += 32

    # Multipliers at the end
    if combo_t == "TRIPLE": dmg = round(dmg * 2.2)
    elif combo_t == "PAIR": dmg = round(dmg * 1.5)

    return max(5, round(dmg))

class Game:
    def __init__(self, p1_id, p2_id, p1_hp=MAX_HP, p2_hp=MAX_HP, p1_combo=None, p2_combo=None, round_num=1, p1_level=1, p2_level=1, wager=0.0):
        self.p1_id = p1_id
        self.p2_id = p2_id
        self.wager = wager
        self.players = {
            p1_id: {"hp": p1_hp, "combo": p1_combo or [], "level": p1_level, "ready": bool(p1_combo), "history": []},
            p2_id: {"hp": p2_hp, "combo": p2_combo or [], "level": p2_level, "ready": bool(p2_combo), "history": []}
        }
        self.current_round = round_num

    @property
    def is_vs_ai(self):
        return self.p1_id == AI_USER_ID or self.p2_id == AI_USER_ID

    def get_opponent_id(self, player_id):
        return self.p2_id if player_id == self.p1_id else self.p1_id

    def set_player_combo(self, player_id, combo):
        self.players[player_id]["combo"] = combo
        self.players[player_id]["ready"] = True

    def is_round_ready(self):
        return self.players[self.p1_id]["ready"] and self.players[self.p2_id]["ready"]

    def process_round(self):
        p1, p2 = self.p1_id, self.p2_id
        c1, c2 = self.players[p1]["combo"], self.players[p2]["combo"]
        l1, l2 = self.players[p1]["level"], self.players[p2]["level"]

        p1_dmg_to_p2 = calc_dmg(c1, c2, l1)
        p2_dmg_to_p1 = calc_dmg(c2, c1, l2)

        self.players[p1]["hp"] = max(0, self.players[p1]["hp"] - p2_dmg_to_p1)
        self.players[p2]["hp"] = max(0, self.players[p2]["hp"] - p1_dmg_to_p2)

        self.players[p1]["history"].append(c1)
        self.players[p2]["history"].append(c2)

        self.current_round += 1
        self.players[p1]["ready"] = False
        self.players[p2]["ready"] = False
        self.players[p1]["combo"] = []
        self.players[p2]["combo"] = []

        return p1_dmg_to_p2, p2_dmg_to_p1

    def is_game_over(self):
        return self.players[self.p1_id]["hp"] <= 0 or self.players[self.p2_id]["hp"] <= 0

    def get_winner(self):
        if self.players[self.p1_id]["hp"] <= 0 and self.players[self.p2_id]["hp"] <= 0:
            return "Draw"
        if self.players[self.p1_id]["hp"] <= 0: return self.p2_id
        if self.players[self.p2_id]["hp"] <= 0: return self.p1_id
        return None

    def to_dict(self):
        return {
            "p1": self.p1_id,
            "p2": self.p2_id,
            "p1_hp": self.players[self.p1_id]["hp"],
            "p2_hp": self.players[self.p2_id]["hp"],
            "p1_combo": self.players[self.p1_id]["combo"],
            "p2_combo": self.players[self.p2_id]["combo"],
            "p1_level": self.players[self.p1_id]["level"],
            "p2_level": self.players[self.p2_id]["level"],
            "round": self.current_round,
            "wager": self.wager
        }

def get_ai_combo():
    if random.random() < 0.4:
        return random.choice(NAMED_COMBOS)["ids"]
    return [random.choice(SYMBOLS)["id"] for _ in range(3)]
