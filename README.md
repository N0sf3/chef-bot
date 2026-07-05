# Chef Bot — Dissident Labs

A Telegram bot that cooks like its owner: recipes fitted to your pantry, your
tastes, and your goals. Palate memory lives in SQLite; the brain is Claude.

## How it works

```
Telegram  ──(long polling)──▶  bot.py  ──▶  db.py / chef.db   (your memory, local)
                                  │
                                  └──(HTTPS)──▶  Claude API     (the brain, rented)
```

No inbound ports, no webhooks, no domain needed — the bot only ever calls out.

## Files

| File | Role |
|---|---|
| `bot.py` | Main loop: Telegram ⇄ Claude ⇄ memory |
| `db.py` | All memory operations (the only file that touches the database) |
| `schema.sql` | The 4 tables: users, pantry, taste_events, recipes_served |
| `Dockerfile` | How Coolify builds the container |
| `requirements.txt` | Python dependencies |
| `.env.example` | Shape of the 2 secrets (real values go in Coolify's vault) |

## Deploy (Coolify)

1. New Resource → Public Repository → this repo's URL
2. Build Pack: **Dockerfile**
3. Environment Variables: set `ANTHROPIC_API_KEY` and `TELEGRAM_TOKEN`
4. Persistent Storage: mount a volume at `/data` (keeps the palate memory across redeploys)
5. Deploy → message your bot on Telegram

## Commands

- `/perfil <texto>` — set goals, allergies, region
- `/despensa <items>` — set your pantry (comma-separated)
- `/gusto <texto>` — log a taste reaction
- `/historial` — recent recipes
- anything else — ask for food
