"""
Chef Bot v0.4 — Dissident Labs
Telegram bot that cooks like Nosfe. Bilingual (ES/EN) with command aliases,
tap-buttons (reply keyboard), and one-tap taste rating (inline buttons).
Palate memory in SQLite. Brain = Claude.
"""

import os
import re
import time
import secrets
import traceback

import requests
import anthropic

import db
import levels

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = anthropic.Anthropic()
MODEL = os.environ.get("MODEL", "claude-opus-4-8")
OWNER_ID = os.environ.get("OWNER_ID", "").strip()
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "25"))  # recipes/user/day (owner exempt)


def is_owner(chat_id: int) -> bool:
    return OWNER_ID != "" and str(chat_id) == OWNER_ID


def new_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "CHEF-" + "".join(secrets.choice(alphabet) for _ in range(4))


# ---------------------------------------------------------------------------
# Doctrine — the chef's soul. Replies in the user's language.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the chef of Dissident Labs: a real cook with a decade in professional \
kitchens (including high-end kitchens in NYC) and a gastronomy degree. You are \
NOT a generic recipe site. You cook flavor-first: flavor bases, balancing \
acid/fat/salt/heat, texture, and technique that actually matters. You know the \
world's cuisines broadly — draw on any regional style that fits, not a fixed list.

LANGUAGE: Reply in the SAME language the user writes in — Spanish or English. \
Warm but direct.

FORMAT (Telegram plain text):
- NO markdown. Never use **asterisks**, __underscores__, or #headers — Telegram \
shows them literally. Use plain lines and a few emoji.
- Shape:
    Nombre del plato
    🥘 Ingredientes: item (cantidad), ...
    👣 Pasos: 1) ...  2) ...
    💡 Tip: una técnica que mejora el resultado
- Concise. Lead with the dish. No preamble, no filler, no "¡Qué buena elección!".

RULES:
- Cook with what's in the PANTRY. Missing a key item -> give the most realistic \
substitution, not a shopping list.
- ALLERGIES and dietary restrictions in the profile are absolute. Never break them.
- Only propose techniques the EQUIPMENT and methods allow. No oven -> no roasting.
- PREFERENCES ARE AN ANCHOR, NOT A CAGE: lean on what they like, but regularly \
offer one adjacent option that stretches their palate. Never trap them in a loop \
of the same flavors.
- INGREDIENTS ARE VERSATILE: never treat a product as single-use. When useful, \
show that something in their pantry can become more than the obvious dish.
- Calibrate complexity to SKILL and RANK. When you use a real cooking term \
(sauté, emulsify, temper, braise...), briefly teach it the first time so the user \
learns the vocabulary instead of being gatekept by it. Occasionally teach ONE \
technique slightly above their level.
- Fit the GOALS (macros, calories) without killing flavor.
- Use the TASTE HISTORY: lean into what they liked, avoid what they disliked.
- Ground everything in real gastronomy: name the technique and WHY it works; \
use regional/seasonal produce for their region; season in layers.
- Don't repeat recently served dishes.

TECHNIQUE TREE: the user has a skill tree tied to their equipment. Prefer \
techniques they've already LEARNED; you may introduce ONE from their AVAILABLE \
list and teach it briefly. Never use a technique their equipment can't do.
At the VERY END of your reply, on its own final line, output exactly:
TECHNIQUES: name1, name2, name3
— the short lowercase cooking techniques this recipe uses. This line is parsed \
by the app and removed before the user sees it. Keep it to real technique names \
(sauté, braise, reduce, emulsify, roast, blanch, sear...), not ingredients.
"""

# Small helper-prompt: turn a list of kitchen tools into the techniques they enable.
EQUIP_PROMPT = (
    "List the cooking techniques the given kitchen equipment makes possible. "
    "Output ONLY a comma-separated list of short lowercase technique names "
    "(e.g. sauté, boil, roast, deep fry, emulsify). No other text."
)

# ---------------------------------------------------------------------------
# Command aliases — every action accepts BOTH languages.
# Maps a typed command word (no slash) to a canonical action name.
# ---------------------------------------------------------------------------
ALIASES = {
    "start": "help", "help": "help", "ayuda": "help", "menu": "help",
    "id": "id",
    "activar": "redeem", "redeem": "redeem",
    "idioma": "lang", "language": "lang", "lang": "lang",
    "perfil": "profile", "profile": "profile",
    "equipo": "equipment", "equipment": "equipment", "equip": "equipment",
    "skill": "skill", "habilidad": "skill",
    "despensa": "pantry", "pantry": "pantry",
    "gusto": "taste", "taste": "taste",
    "historial": "history", "history": "history",
    "nivel": "rank", "level": "rank", "rank": "rank",
    "tecnicas": "techniques", "techniques": "techniques", "arbol": "techniques", "tree": "techniques",
    # owner-only
    "gencode": "gencode", "codes": "codes", "codigos": "codes",
    "allow": "allow", "deny": "deny", "allowed": "allowed",
}

# ---------------------------------------------------------------------------
# Bilingual strings
# ---------------------------------------------------------------------------
UI = {
    "es": {
        "welcome": "🔪 Chef de Dissident Labs a la orden.",
        "profile_saved": "Perfil guardado. Eso no se me olvida.",
        "profile_show": "Tu perfil:\n{v}",
        "equip_saved": "Equipo guardado: {v}",
        "equip_show": "Tu equipo:\n{v}",
        "skill_saved": "Nivel declarado: {v}",
        "skill_ask": "Dime tu nivel: /skill principiante | intermedio | avanzado",
        "pantry_saved": "Despensa actualizada: {v}",
        "pantry_show": "Despensa: {v}",
        "pantry_empty_cook": "Primero dime qué tienes: /despensa pollo, arroz, ajo...",
        "taste_saved": "Anotado en tu paladar. 📝 (+{xp} XP)",
        "taste_ask": "Dime qué te gustó o no: /gusto me encantó el hogao",
        "history": "Últimas recetas:\n{v}",
        "history_empty": "Aún no te he cocinado nada.",
        "lang_set": "Idioma: Español 🇪🇸",
        "empty": "(vacío)",
        "levelup": "\n\n🎉 ¡Subiste de rango! Ahora eres {v}",
        "busy": "El chef está saturado, dame un minuto. 🔥",
        "brain": "Problema con el cerebro del chef ({v}). Intenta de nuevo.",
        "burned": "Algo se quemó en la cocina. Ya lo reviso.",
        "your_id": "Tu ID de Telegram es: {v}",
        "denied": "🔒 Necesitas un código de acceso.\nEnvía: /activar TU-CODIGO",
        "activated": "✅ ¡Acceso activado! Escribe /help.",
        "code_bad": "❌ Código inválido o ya usado.",
        "code_new": "Nuevo código: {v}",
        "allowed_list": "Con acceso:\n{v}",
        "codes_list": "Códigos:\n{v}",
        "user_allowed": "✅ Usuario {v} agregado.",
        "user_denied": "🚫 Usuario {v} removido.",
        "rate_thanks": "¡Anotado! 📝 (+{xp} XP)",
        "limit": "🍽️ Llegaste al límite de recetas de hoy. Vuelve mañana con hambre.",
        "tree": "🌳 Tu árbol de técnicas:\n{v}",
        "tree_empty": "Aún no tienes técnicas. Configura tu equipo con /equipo y cocina algo.",
        "tree_mastered": "✅ Practicadas:",
        "tree_available": "⬜ Disponibles (según tus herramientas):",
        "equip_analyzed": "🌳 Analicé tus herramientas — árbol de técnicas actualizado. Mira /tecnicas",
        # reply-keyboard button labels
        "btn_cook": "🍳 ¿Qué cocino?",
        "btn_pantry": "📋 Despensa",
        "btn_rank": "📊 Nivel",
        "btn_help": "❓ Ayuda",
        # inline rating labels
        "r_love": "👍 Me encantó",
        "r_no": "👎 No fue",
        "r_spicy": "🌶️ Muy picante",
        "r_again": "🔁 Otra",
    },
    "en": {
        "welcome": "🔪 Dissident Labs Chef at your service.",
        "profile_saved": "Profile saved. I won't forget that.",
        "profile_show": "Your profile:\n{v}",
        "equip_saved": "Equipment saved: {v}",
        "equip_show": "Your equipment:\n{v}",
        "skill_saved": "Skill level set: {v}",
        "skill_ask": "Tell me your level: /skill beginner | intermediate | advanced",
        "pantry_saved": "Pantry updated: {v}",
        "pantry_show": "Pantry: {v}",
        "pantry_empty_cook": "First tell me what you have: /pantry chicken, rice, garlic...",
        "taste_saved": "Logged to your palate. 📝 (+{xp} XP)",
        "taste_ask": "Tell me what you liked or not: /taste loved the garlic sauce",
        "history": "Recent dishes:\n{v}",
        "history_empty": "I haven't cooked for you yet.",
        "lang_set": "Language: English 🇬🇧",
        "empty": "(empty)",
        "levelup": "\n\n🎉 Rank up! You're now {v}",
        "busy": "The chef is slammed, give me a minute. 🔥",
        "brain": "Chef's brain hiccup ({v}). Try again.",
        "burned": "Something burned in the kitchen. Looking into it.",
        "your_id": "Your Telegram ID is: {v}",
        "denied": "🔒 You need an access code.\nSend: /activar YOUR-CODE",
        "activated": "✅ Access granted! Type /help.",
        "code_bad": "❌ Invalid or already-used code.",
        "code_new": "New code: {v}",
        "allowed_list": "With access:\n{v}",
        "codes_list": "Codes:\n{v}",
        "user_allowed": "✅ User {v} added.",
        "user_denied": "🚫 User {v} removed.",
        "rate_thanks": "Logged! 📝 (+{xp} XP)",
        "limit": "🍽️ You hit today's recipe limit. Come back hungry tomorrow.",
        "tree": "🌳 Your technique tree:\n{v}",
        "tree_empty": "No techniques yet. Set your equipment with /equipment and cook something.",
        "tree_mastered": "✅ Practiced:",
        "tree_available": "⬜ Available (from your tools):",
        "equip_analyzed": "🌳 Analyzed your tools — technique tree updated. See /techniques",
        "btn_cook": "🍳 What can I cook?",
        "btn_pantry": "📋 Pantry",
        "btn_rank": "📊 Level",
        "btn_help": "❓ Help",
        "r_love": "👍 Loved it",
        "r_no": "👎 Nope",
        "r_spicy": "🌶️ Too spicy",
        "r_again": "🔁 Another",
    },
}

HELP = {
    "es": (
        "Comandos (funcionan en español o inglés):\n"
        "/perfil <texto> — metas, alergias, región, dieta\n"
        "/equipo <texto> — herramientas y métodos (ej: estufa, sartén, sin horno)\n"
        "/skill principiante|intermedio|avanzado — tu nivel\n"
        "/despensa <items> — lo que tienes (comas)\n"
        "/gusto <texto> — registra una reacción\n"
        "/historial — últimas recetas\n"
        "/nivel — tu rango 🍳\n"
        "/tecnicas — tu árbol de técnicas 🌳\n"
        "/idioma es|en — idioma\n"
        "O usa los botones de abajo 👇, o pídeme de comer."
    ),
    "en": (
        "Commands (work in English or Spanish):\n"
        "/profile <text> — goals, allergies, region, diet\n"
        "/equipment <text> — tools & methods (e.g. stove, pan, no oven)\n"
        "/skill beginner|intermediate|advanced — your level\n"
        "/pantry <items> — what you have (commas)\n"
        "/taste <text> — log a reaction\n"
        "/history — recent dishes\n"
        "/rank — your rank 🍳\n"
        "/techniques — your technique tree 🌳\n"
        "/language es|en — language\n"
        "Or use the buttons below 👇, or just ask for food."
    ),
}


def t(lang: str, key: str, **kw) -> str:
    return UI.get(lang, UI["es"])[key].format(**kw)


# ---------------------------------------------------------------------------
# Telegram send helpers (now with optional keyboards)
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    return text.strip()


def reply_keyboard(lang: str) -> dict:
    """Persistent tap-buttons at the bottom, in the user's language."""
    return {
        "keyboard": [
            [{"text": t(lang, "btn_cook")}, {"text": t(lang, "btn_pantry")}],
            [{"text": t(lang, "btn_rank")}, {"text": t(lang, "btn_help")}],
        ],
        "resize_keyboard": True,
    }


def rating_keyboard(lang: str) -> dict:
    """Inline buttons under a recipe — tapping logs a taste_event."""
    return {
        "inline_keyboard": [
            [
                {"text": t(lang, "r_love"), "callback_data": "rate:love"},
                {"text": t(lang, "r_no"), "callback_data": "rate:no"},
            ],
            [
                {"text": t(lang, "r_spicy"), "callback_data": "rate:spicy"},
                {"text": t(lang, "r_again"), "callback_data": "rate:again"},
            ],
        ]
    }


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    text = clean(text)
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)] or [""]
    for idx, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk}
        if reply_markup and idx == len(chunks) - 1:  # markup only on the last chunk
            payload["reply_markup"] = reply_markup
        requests.post(f"{TG_API}/sendMessage", json=payload, timeout=30)


def answer_callback(callback_id: str, text: str = "") -> None:
    """Stops the little spinner on the tapped button; optional toast text."""
    requests.post(
        f"{TG_API}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=30,
    )


def send_typing(chat_id: int) -> None:
    """Shows 'Chef is typing...' so the wait feels intentional, not broken."""
    try:
        requests.post(
            f"{TG_API}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=15,
        )
    except requests.RequestException:
        pass


# ---------------------------------------------------------------------------
# The brain call
# ---------------------------------------------------------------------------
def ask_chef(chat_id: int, user_message: str) -> str:
    u = db.get_user(chat_id)
    pantry = db.get_pantry(chat_id)
    tastes = db.recent_tastes(chat_id, limit=15)
    recipes = db.recent_recipe_titles(chat_id, limit=5)
    xp = db.get_xp(chat_id)
    techs = db.get_techniques(chat_id)
    learned = [f"{n}(x{c})" for n, c in techs if c > 0]
    available = [n for n, c in techs if c == 0]
    context = (
        f"PROFILE (goals/allergies/region/diet):\n{(u['profile'] if u else None) or '(none yet)'}\n\n"
        f"EQUIPMENT & METHODS:\n{(u['equipment'] if u else None) or '(unknown)'}\n\n"
        f"SELF-REPORTED SKILL: {(u['skill'] if u else None) or '(unspecified)'}\n"
        f"KITCHEN RANK: {levels.title_for(xp)} ({xp} XP)\n"
        f"LEARNED TECHNIQUES: {', '.join(learned) if learned else '(none yet)'}\n"
        f"AVAILABLE TECHNIQUES (from tools, not yet practiced): {', '.join(available) if available else '(none)'}\n\n"
        f"PANTRY:\n{', '.join(pantry) if pantry else '(empty)'}\n\n"
        f"TASTE HISTORY (recent reactions):\n{chr(10).join(tastes) if tastes else '(no data yet)'}\n\n"
        f"RECENTLY SERVED (do not repeat):\n{chr(10).join(recipes) if recipes else '(none)'}\n\n"
        f"USER MESSAGE:\n{user_message}"
    )
    # No extended thinking + capped output + medium effort = much faster.
    # Recipe generation doesn't need deep reasoning; speed matters more here.
    response = client.messages.create(
        model=MODEL, max_tokens=1500,
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT, messages=[{"role": "user", "content": context}],
    )
    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(parts).strip() or "(el chef se quedó sin palabras)"


def extract_techniques(text: str) -> tuple[list[str], str]:
    """Pull the 'TECHNIQUES: ...' trailer out; return (names, cleaned_text)."""
    m = re.search(r"(?im)^\s*TECHNIQUES:\s*(.+?)\s*$", text)
    if not m:
        return [], text
    names = [x.strip().lower() for x in m.group(1).split(",") if x.strip()]
    cleaned = (text[: m.start()] + text[m.end():]).strip()
    return names, cleaned


def derive_techniques(equipment_text: str) -> list[str]:
    """Ask the model which techniques a set of tools enables. One cheap call."""
    resp = client.messages.create(
        model=MODEL, max_tokens=200,
        output_config={"effort": "low"},
        system=EQUIP_PROMPT,
        messages=[{"role": "user", "content": equipment_text}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return [x.strip().lower() for x in text.split(",") if x.strip()][:40]


def render_tree(techs: list[tuple[str, int]], lang: str) -> str:
    practiced = [(n, c) for n, c in techs if c > 0]
    available = [n for n, c in techs if c == 0]
    lines = []
    if practiced:
        lines.append(t(lang, "tree_mastered"))
        lines += [f"  • {n} ×{c}" for n, c in practiced]
    if available:
        lines.append(t(lang, "tree_available"))
        lines += [f"  • {n}" for n in available]
    return "\n".join(lines)


def cook_and_send(chat_id: int, lang: str, request: str) -> None:
    """Ask the chef, log the recipe, award XP, send with rating buttons."""
    # Per-user daily cost cap (owner exempt) — protects your API bill.
    if not is_owner(chat_id) and db.recipes_today(chat_id) >= DAILY_LIMIT:
        send_message(chat_id, t(lang, "limit"))
        return
    send_typing(chat_id)  # 'Chef is typing...' while the model works
    reply = ask_chef(chat_id, request)
    techs_used, reply = extract_techniques(reply)  # pull + strip the trailer
    db.practice_techniques(chat_id, techs_used)     # level up the tree
    db.log_recipe(chat_id, reply)
    old, new = db.add_xp(chat_id, levels.XP_PER_RECIPE)
    up = levels.leveled_up(old, new)
    if up:
        reply += t(lang, "levelup", v=up)
    send_message(chat_id, reply, reply_markup=rating_keyboard(lang))


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------
def parse_command(text: str):
    """Return (action, arg) if it's a known command, else (None, text)."""
    if not text.startswith("/"):
        return None, text
    head, _, rest = text.partition(" ")
    word = head[1:].split("@")[0].lower()  # strip slash and any @botname
    return ALIASES.get(word), rest.strip()


def is_button(text: str, lang: str, key: str) -> bool:
    return text == t(lang, key)


# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------
def handle_message(chat_id: int, text: str) -> None:
    db.ensure_user(chat_id)
    lang = db.get_lang(chat_id)
    text = text.strip()
    action, arg = parse_command(text)

    # Map reply-keyboard taps (which arrive as plain text) to actions
    if action is None:
        if is_button(text, lang, "btn_cook"):
            action = "cook_pantry"
        elif is_button(text, lang, "btn_pantry"):
            action, arg = "pantry", ""
        elif is_button(text, lang, "btn_rank"):
            action = "rank"
        elif is_button(text, lang, "btn_help"):
            action = "help"

    # --- Always-open actions (work without access) ---------------------------
    if action == "id":
        send_message(chat_id, t(lang, "your_id", v=chat_id))
        return
    if action == "redeem":
        if db.redeem_code(arg.strip().upper(), chat_id):
            send_message(chat_id, t(lang, "activated"), reply_markup=reply_keyboard(lang))
        else:
            send_message(chat_id, t(lang, "code_bad"))
        return

    # --- Owner-only management ------------------------------------------------
    if is_owner(chat_id):
        if action == "gencode":
            code = new_code()
            db.create_code(code, arg)
            send_message(chat_id, t(lang, "code_new", v=code))
            return
        if action == "codes":
            rows = db.list_codes()
            body = "\n".join(f"{c} {'· USADO ' + str(u) if u else '· libre'} {n}" for c, n, u in rows) or "—"
            send_message(chat_id, t(lang, "codes_list", v=body))
            return
        if action == "allow":
            bits = arg.split(maxsplit=1)
            if bits and bits[0].lstrip("-").isdigit():
                db.allow_user(int(bits[0]), bits[1] if len(bits) > 1 else "")
                send_message(chat_id, t(lang, "user_allowed", v=bits[0]))
            return
        if action == "deny":
            if arg.strip().lstrip("-").isdigit():
                db.deny_user(int(arg.strip()))
                send_message(chat_id, t(lang, "user_denied", v=arg.strip()))
            return
        if action == "allowed":
            rows = db.list_allowed()
            body = "\n".join(f"{cid} {note}" for cid, note in rows) or "—"
            send_message(chat_id, t(lang, "allowed_list", v=body))
            return

    # --- THE GATE -------------------------------------------------------------
    if not (is_owner(chat_id) or db.is_allowed(chat_id)):
        if action == "help":
            send_message(chat_id, t(lang, "welcome") + "\n\n" + t(lang, "denied"))
        else:
            send_message(chat_id, t(lang, "denied"))
        return

    # --- Authorized actions ---------------------------------------------------
    if action == "help":
        send_message(chat_id, t(lang, "welcome") + "\n\n" + HELP[lang], reply_markup=reply_keyboard(lang))

    elif action == "lang":
        new = "en" if arg.lower().startswith("en") else "es"
        db.set_lang(chat_id, new)
        send_message(chat_id, t(new, "lang_set"), reply_markup=reply_keyboard(new))

    elif action == "profile":
        if arg:
            db.set_profile(chat_id, arg)
            send_message(chat_id, t(lang, "profile_saved"))
        else:
            u = db.get_user(chat_id)
            send_message(chat_id, t(lang, "profile_show", v=(u["profile"] if u else None) or t(lang, "empty")))

    elif action == "equipment":
        if arg:
            db.set_equipment(chat_id, arg)
            send_message(chat_id, t(lang, "equip_saved", v=arg))
            # Derive which techniques these tools enable -> grow the tree.
            send_typing(chat_id)
            try:
                names = derive_techniques(arg)
                if names:
                    db.add_available_techniques(chat_id, names)
                    send_message(chat_id, t(lang, "equip_analyzed"))
            except Exception:
                traceback.print_exc()  # tree derivation is best-effort, never fatal
        else:
            u = db.get_user(chat_id)
            send_message(chat_id, t(lang, "equip_show", v=(u["equipment"] if u else None) or t(lang, "empty")))

    elif action == "skill":
        if arg:
            db.set_skill(chat_id, arg)
            send_message(chat_id, t(lang, "skill_saved", v=arg))
        else:
            send_message(chat_id, t(lang, "skill_ask"))

    elif action == "pantry":
        if arg:
            items = [x.strip() for x in arg.split(",") if x.strip()]
            db.set_pantry(chat_id, items)
            send_message(chat_id, t(lang, "pantry_saved", v=", ".join(items)))
        else:
            pantry = db.get_pantry(chat_id)
            send_message(chat_id, t(lang, "pantry_show", v=", ".join(pantry) if pantry else t(lang, "empty")))

    elif action == "taste":
        if arg:
            db.log_taste(chat_id, arg)
            old, new = db.add_xp(chat_id, levels.XP_PER_TASTE)
            msg = t(lang, "taste_saved", xp=levels.XP_PER_TASTE)
            up = levels.leveled_up(old, new)
            if up:
                msg += t(lang, "levelup", v=up)
            send_message(chat_id, msg)
        else:
            send_message(chat_id, t(lang, "taste_ask"))

    elif action == "history":
        titles = db.recent_recipe_titles(chat_id, limit=10)
        send_message(chat_id, t(lang, "history", v="\n".join(titles)) if titles else t(lang, "history_empty"))

    elif action == "rank":
        send_message(chat_id, levels.status(db.get_xp(chat_id)), reply_markup=reply_keyboard(lang))

    elif action == "techniques":
        techs = db.get_techniques(chat_id)
        if techs:
            send_message(chat_id, t(lang, "tree", v=render_tree(techs, lang)))
        else:
            send_message(chat_id, t(lang, "tree_empty"))

    elif action == "cook_pantry":
        if db.get_pantry(chat_id):
            cook_and_send(chat_id, lang, "Cook something from my pantry.")
        else:
            send_message(chat_id, t(lang, "pantry_empty_cook"))

    else:
        # free text -> cook
        cook_and_send(chat_id, lang, text)


# ---------------------------------------------------------------------------
# Button-tap (callback) handling — the one-tap rating system
# ---------------------------------------------------------------------------
def handle_callback(chat_id: int, data: str, callback_id: str) -> None:
    lang = db.get_lang(chat_id)
    if not (is_owner(chat_id) or db.is_allowed(chat_id)):
        answer_callback(callback_id, t(lang, "denied"))
        return

    if data == "rate:again":
        answer_callback(callback_id)
        if db.get_pantry(chat_id):
            cook_and_send(chat_id, lang, "Give me a different option from my pantry.")
        else:
            send_message(chat_id, t(lang, "pantry_empty_cook"))
        return

    if data.startswith("rate:"):
        kind = data.split(":", 1)[1]
        last = db.recent_recipe_titles(chat_id, limit=1)
        dish = last[0] if last else "?"
        note = {
            "love": f"👍 le encantó: {dish}",
            "no": f"👎 no le gustó: {dish}",
            "spicy": f"🌶️ muy picante: {dish}",
        }.get(kind)
        if note:
            db.log_taste(chat_id, note)
            db.add_xp(chat_id, levels.XP_PER_TASTE)
            answer_callback(callback_id, t(lang, "rate_thanks", xp=levels.XP_PER_TASTE))
        else:
            answer_callback(callback_id)


# ---------------------------------------------------------------------------
# Register the "/" command menu (nice-to-have; shows the menu button)
# ---------------------------------------------------------------------------
def register_commands() -> None:
    cmds = [
        {"command": "help", "description": "Menu / Ayuda"},
        {"command": "perfil", "description": "Perfil: metas, alergias / Profile"},
        {"command": "despensa", "description": "Despensa / Pantry"},
        {"command": "equipo", "description": "Equipo / Equipment"},
        {"command": "nivel", "description": "Tu rango / Your rank"},
        {"command": "idioma", "description": "Idioma es|en / Language"},
    ]
    try:
        requests.post(f"{TG_API}/setMyCommands", json={"commands": cmds}, timeout=30)
    except requests.RequestException:
        pass


# ---------------------------------------------------------------------------
# Main loop — long polling. Handles both messages and button taps.
# ---------------------------------------------------------------------------
def main() -> None:
    db.init()
    register_commands()
    print("Chef bot v0.4 corriendo. Ctrl+C para apagar.")
    offset = None
    while True:
        try:
            resp = requests.get(
                f"{TG_API}/getUpdates",
                params={"timeout": 50, "offset": offset,
                        "allowed_updates": '["message","callback_query"]'},
                timeout=60,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1

                if "callback_query" in update:
                    cq = update["callback_query"]
                    chat_id = (cq.get("message", {}).get("chat") or {}).get("id")
                    data = cq.get("data", "")
                    if chat_id:
                        try:
                            handle_callback(chat_id, data, cq["id"])
                        except Exception:
                            traceback.print_exc()
                            answer_callback(cq["id"])
                    continue

                msg = update.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = msg.get("text")
                if chat_id and text:
                    lang = db.get_lang(chat_id)
                    try:
                        handle_message(chat_id, text)
                    except anthropic.RateLimitError:
                        send_message(chat_id, t(lang, "busy"))
                    except anthropic.APIStatusError as e:
                        send_message(chat_id, t(lang, "brain", v=e.status_code))
                    except Exception:
                        traceback.print_exc()
                        send_message(chat_id, t(lang, "burned"))
        except requests.RequestException:
            time.sleep(5)  # network blip — breathe and retry
        except Exception:
            # Any other error (e.g. a malformed Telegram response) must NOT
            # kill the bot. Log it and keep the loop alive.
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    main()
