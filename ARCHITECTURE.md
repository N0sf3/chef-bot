# Chef Bot — The Map (plain language)

A guide to your own product, in kitchen terms. No jargon. Open this anytime you
want to know "where does X live" or "what happens when Y."

---

## The restaurant metaphor

Your bot is a tiny restaurant with three staff:

- **The waiter** (`bot.py`) — takes orders from Telegram, carries them to the
  kitchen, brings food back. Never cooks. Just runs back and forth.
- **The notebook** (`db.py` + the database file) — everything the restaurant
  remembers: who each guest is, what's in their pantry, what they've liked, their
  skill tree. The waiter reads and writes this.
- **The chef** (Claude, reached over the internet) — the only one with cooking
  brains. The waiter phones the chef with all the guest's details and gets back a
  recipe. The chef lives in Anthropic's building, not yours. You pay per phone call.

Nothing on your server is "smart." Your server is the waiter + the notebook. The
intelligence is rented, one call at a time.

---

## The files (what each one is for)

| File | Role | Open it when you want to change… |
|---|---|---|
| `bot.py` | The waiter. All the logic: reading messages, buttons, routing, phoning the chef. | how it talks, buttons, commands, the chef's instructions |
| `db.py` | The notebook's hands. Every "remember this / recall that" lives here. | how memory is saved or read |
| `schema.sql` | The shape of the notebook — its pages (tables) and columns. | adding a new *kind* of thing to remember |
| `levels.py` | The RPG ranks (Aprendiz → Maestro) and the XP math. | rank names, XP amounts, thresholds |
| `Dockerfile` | The recipe Coolify uses to build the container. | rarely — only the runtime setup |
| `requirements.txt` | The two libraries the bot needs. | adding a new library |
| `.env.example` | The *shape* of the two secrets (real ones live in Coolify). | documenting a new secret |

**Why this split matters:** each file has ONE job. If recipes are wrong, it's the
chef's instructions in `bot.py`. If memory is broken, it's `db.py`. If a rank is
wrong, it's `levels.py`. You always know which drawer to open.

---

## The journey of one "tengo pollo y arroz"

This is the whole thing, start to finish:

```
1. You type it in Telegram.
2. The waiter (bot.py) is constantly asking Telegram "anything new?"
   (this is the "polling loop" at the bottom of bot.py).
3. It sees your message and figures out: is this a command (/despensa),
   a button tap, or free text? (that's parse_command + handle_message)
4. Free text = a food request. The waiter opens your notebook page:
   profile, pantry, tastes, recent recipes, your technique tree. (ask_chef)
5. It phones the chef (Claude) with ALL of that + your cooking-doctrine rules.
6. The chef sends back a recipe (with a hidden TECHNIQUES: line at the end).
7. The waiter strips that hidden line, records which techniques you used
   (levels up your tree), logs the recipe, gives you XP.
8. It sends you the clean recipe + the 👍👎 rating buttons.
9. You tap a rating → that logs a taste_event → next recipe is smarter.
```

Every feature you've built is a step in this loop.

---

## The notebook's pages (the database tables)

These are defined in `schema.sql`. Each guest is identified by their Telegram
number (`chat_id`) — that's how everyone's data stays separate.

| Page (table) | What it holds |
|---|---|
| `users` | one row per guest: profile, equipment, skill, language, XP |
| `pantry` | what's in their kitchen right now |
| `taste_events` | every 👍/👎 reaction, forever — **this is the crown jewel** (the palate) |
| `recipes_served` | every dish cooked, so it never repeats + powers the daily cap |
| `allowed_users` | who's allowed to use the bot (the gate) |
| `access_codes` | the activation codes you hand out (the selling mechanism) |
| `user_techniques` | the skill tree: which techniques each guest has (available vs practiced) |

---

## "I want to change X" → where to look

- **Make the chef cook differently** → `SYSTEM_PROMPT` near the top of `bot.py`.
  This is the chef's soul. The single highest-leverage thing you can edit.
- **Change a button** → the `reply_keyboard` function + the `btn_*` labels in the
  `UI` dictionary (both `es` and `en`).
- **Add/rename a command** → the `ALIASES` map in `bot.py` (add both languages).
- **Change what's remembered** → add a column in `schema.sql`, a get/set in
  `db.py`, and feed it into `ask_chef`'s context.
- **Change rank names or XP** → `levels.py`.
- **Change the daily recipe limit** → nothing in code — set `DAILY_LIMIT` in
  Coolify's environment variables.
- **Switch the chef's brain (speed/cost)** → nothing in code — set `MODEL` in
  Coolify (e.g. `claude-sonnet-5` for faster/cheaper).

---

## The two secrets

The bot needs exactly two passwords, and they never live in the code:
- `ANTHROPIC_API_KEY` — lets the waiter phone the chef.
- `TELEGRAM_TOKEN` — lets the waiter talk to Telegram.

They live in **Coolify's Environment Variables** (the vault). The code just reads
them by name. That's why the code is safe to keep on public GitHub.

Also there: `OWNER_ID` (you, the manager) and optional `DAILY_LIMIT` / `MODEL`.

---

## How a change reaches the live bot

1. The code changes (edit the files).
2. Push to GitHub (`git push`).
3. In Coolify, hit **Deploy** — it pulls the new code, rebuilds, restarts.
4. The database survives (it's on the `/data` volume, and `db.py`'s migration
   step adds any new columns without wiping anything).

---

## What you own here

You don't write the syntax — an AI does that. But you own:
- **the shape** (this map)
- **the decisions** (what to build, what to refuse)
- **the verification** (testing, noticing when it's slow or wrong)

That's real ownership. Any developer or AI can pick this codebase up from this map
and be useful in an hour. You are never trapped, never hostage to one person.

Keep it lean: before every new feature, ask "is this worth the weight it adds?"
That question is what keeps this a kitchen you can walk through — not a maze.
