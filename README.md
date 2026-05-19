# NEXUS-7 PvP Telegram Bot (v2.0)

A highly interactive Telegram PvP battle bot with progression, leveling, and a global leaderboard.

## New Features (v2.0)

*   **Modern UI:** Full transition to Inline Keyboards for seamless symbol selection and navigation.
*   **Persistent Profiles:** Your progress is saved in a SQLite database. Track your XP, Level, Wins, and Losses.
*   **Progression System:** Gain XP from battles. Leveling up increases your base damage, giving you an edge in the arena.
*   **Global Leaderboard:** Compete for the top spot on the Nexus Leaderboard (`/top`).
*   **Visual Combat:** Enhanced battle reports with HP bars and combat emojis.
*   **Practice Mode:** Instant battles against the Nexus Bot to test your combos.

## Setup Instructions (Cloudflare Workers)

1.  **Configure Secrets:**
    *   Set your Telegram Bot Token in Cloudflare:
        ```bash
        npx wrangler secret put BOT_TOKEN
        ```
2.  **Deploy:**
    ```bash
    npx wrangler deploy
    ```
3.  **Set Webhook:**
    *   After deployment, visit: `https://your-worker-url.workers.dev/set-webhook`

## Local Development

1.  **Run Dev Server:**
    ```bash
    npx wrangler dev
    ```
2.  **Environment Variables:**
    *   For local dev, you can use `.dev.vars` file (similar to `.env`) with:
        `BOT_TOKEN=your_token_here`

## Commands

*   `/start` - Open the main menu.
*   `/profile` - View your stats, level, and win rate.
*   `/top` - View the global leaderboard.
*   `/quit` - Forfeit your current match.

## Game Mechanics

Select 3 symbols to form a combat combo.

*   **Damage Calculation:**
    *   `Base Damage = 12 + (Level - 1) * 2`
    *   **Matchup Wins:** +5 damage for every symbol that beats an opponent's symbol.
    *   **Named Combos:** Specific combinations (e.g., Fire + Lightning + Storm) grant massive bonuses.
    *   **Multipliers:** Triples (3 of a kind) give 2.2x damage. Pairs give 1.5x damage.
    *   **Blind Spot:** The 'void' symbol grants a +32 damage bonus.

## Symbol Matchups

| Attacking Symbol | Beats (Defending Symbols) |
| :--------------- | :------------------------ |
| Fire             | Nature, Ice, Wind, Crystal |
| Water            | Fire, Lightning, Poison, Blood |
| Earth            | Lightning, Wind, Void, Storm |
| Wind             | Fire, Poison, Nature, Shadow |
| Lightning        | Water, Metal, Ice, Storm |
| Ice              | Wind, Nature, Shadow, Void |
| Shadow           | Light, Crystal, Time, Blood |
| Light            | Shadow, Void, Poison, Metal |
| Nature           | Earth, Water, Crystal, Time |
| Metal            | Earth, Ice, Crystal, Wind |
| Poison           | Nature, Water, Blood, Light |
| Time             | Lightning, Fire, Ice, Void |
| Void             | Time, Light, Metal, Crystal |
| Blood            | Nature, Earth, Crystal, Light |
| Crystal          | Fire, Shadow, Void, Poison |
| Storm            | Earth, Nature, Metal, Water |
