"""
Chef Bot v0.2 — Dissident Labs
Telegram bot that cooks like Nosfe: recipes fitted to pantry, tastes, goals,
equipment, and skill. Bilingual (ES/EN). Palate memory in SQLite. Brain = Claude.
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
# Config — secrets come from the environment, never from code.
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
MODEL = os.environ.get("MODEL", "claude-opus-4-8")

# Your own Telegram numeric ID. The owner can manage the allowlist and is always
# served. Set this in Coolify after you learn your ID via the /id command.
OWNER_ID = os.environ.get("OWNER_ID", "").strip()


def is_owner(chat_id: int) -> bool:
    return OWNER_ID != "" and str(chat_id) == OWNER_ID


def new_code() -> str:
    """A short, readable activation code like CHEF-7K3P."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusable 0/O/1/I
    return "CHEF-" + "".join(secrets.choice(alphabet) for _ in range(4))

# The cooking doctrine — the soul of the bot. Written in English for precision;
# the chef still replies in the USER's language (see the LANGUAGE rule).
SYSTEM_PROMPT = """\
You are the chef of Dissident Labs: a real cook with a decade in professional \
kitchens (including high-end kitchens in NYC) and a gastronomy degree. You are \
NOT a generic recipe site. You cook flavor-first: flavor bases, balancing \
acid/fat/salt/heat, texture, and technique that actually matters.

LANGUAGE: Reply in the SAME language the user writes in — Spanish or English. \
Match their register. Warm but direct.

FORMAT (this goes to Telegram as plain text):
- NO markdown. Never use **asterisks**, __underscores__, or #headers — Telegram \
shows them as literal characters. Use plain lines and a few emoji instead.
- Shape it like:
    Nombre del plato
    🥘 Ingredientes: item (cantidad), ...
    👣 Pasos: 1) ...  2) ...  3) ...
    💡 Tip: una técnica que mejora el resultado
- Be concise. Lead with the dish. No preamble, no "¡Qué buena elección!", no \
filler. One short framing line max.

RULES:
- Cook with what's in the PANTRY. If a key item is missing, give the most \
realistic substitution — not a shopping list.
- ALLERGIES and dietary restrictions in the profile are absolute. Never break them.
- Only propose techniques the user's EQUIPMENT and methods allow. No oven -> \
don't roast. No blender -> no purées.
- Calibrate to SKILL and RANK: lower level -> simpler steps, explain the \
technique; higher level -> assume competence, go deeper. Occasionally teach ONE \
technique slightly above their level to help them grow.
- Fit the GOALS (macros, calories) without killing flavor.
- Use the TASTE HISTORY: lean into what they liked, avoid what they disliked, \
and mention it briefly when relevant.
- Ground everything in real gastronomy: name the technique and WHY it works; use \
regional/seasonal produce for their region; season in layers; mise en place.
- Don't repeat recently served dishes.
"""

# ---------------------------------------------------------------------------
# Bilingual UI strings for command confirmations
# ---------------------------------------------------------------------------
UI = {
    "es": {
        "welcome": "🔪 Chef de Dissident Labs a la orden.",
        "profile_saved": "Perfil guardado. Eso no se me olvida.",
        "profile_show": "Tu perfil:\n{v}",
        "equip_saved": "Equipo de cocina guardado: {v}",
        "equip_show": "Tu equipo:\n{v}",
        "skill_saved": "Nivel declarado: {v}",
        "skill_ask": "Dime tu nivel: /skill principiante | intermedio | avanzado",
        "pantry_saved": "Despensa actualizada: {v}",
        "pantry_show": "Despensa: {v}",
        "taste_saved": "Anotado en tu paladar. 📝 (+{xp} XP)",
        "taste_ask": "Dime qué te gustó o no: /gusto me encantó el hogao",
        "history": "Últimas recetas:\n{v}",
        "history_empty": "Aún no te he cocinado nada.",
        "lang_set": "Idioma de comandos: Español 🇪🇸",
        "empty": "(vacío)",
        "levelup": "\n\n🎉 ¡Subiste de rango! Ahora eres {v}",
        "busy": "El chef está saturado, dame un minuto. 🔥",
        "brain": "Problema con el cerebro del chef ({v}). Intenta de nuevo.",
        "burned": "Algo se quemó en la cocina. Ya lo reviso.",
        "your_id": "Tu ID de Telegram es: {v}",
        "denied": "🔒 Necesitas un código de acceso para usar el chef.\nEnvía: /activar TU-CODIGO",
        "activated": "✅ ¡Acceso activado! Bienvenido a la cocina. Escribe /help.",
        "code_bad": "❌ Código inválido o ya usado.",
        "code_new": "Nuevo código: {v}",
        "allowed_list": "Usuarios con acceso:\n{v}",
        "codes_list": "Códigos:\n{v}",
        "user_allowed": "✅ Usuario {v} agregado.",
        "user_denied": "🚫 Usuario {v} removido.",
    },
    "en": {
        "welcome": "🔪 Dissident Labs Chef at your service.",
        "profile_saved": "Profile saved. I won't forget that.",
        "profile_show": "Your profile:\n{v}",
        "equip_saved": "Kitchen equipment saved: {v}",
        "equip_show": "Your equipment:\n{v}",
        "skill_saved": "Skill level set: {v}",
        "skill_ask": "Tell me your level: /skill beginner | intermediate | advanced",
        "pantry_saved": "Pantry updated: {v}",
        "pantry_show": "Pantry: {v}",
        "taste_saved": "Logged to your palate. 📝 (+{xp} XP)",
        "taste_ask": "Tell me what you liked or not: /taste loved the garlic sauce",
        "history": "Recent dishes:\n{v}",
        "history_empty": "I haven't cooked for you yet.",
        "lang_set": "Command language: English 🇬🇧",
        "empty": "(empty)",
        "levelup": "\n\n🎉 Rank up! You're now {v}",
        "busy": "The chef is slammed, give me a minute. 🔥",
        "brain": "Chef's brain hiccup ({v}). Try again.",
        "burned": "Something burned in the kitchen. Looking into it.",
        "your_id": "Your Telegram ID is: {v}",
        "denied": "🔒 You need an access code to use the chef.\nSend: /activar YOUR-CODE",
        "activated": "✅ Access granted! Welcome to the kitchen. Type /help.",
        "code_bad": "❌ Invalid or already-used code.",
        "code_new": "New code: {v}",
        "allowed_list": "Users with access:\n{v}",
        "codes_list": "Codes:\n{v}",
        "user_allowed": "✅ User {v} added.",
        "user_denied": "🚫 User {v} removed.",
    },
}

HELP = {
    "es": (
        "Comandos:\n"
        "/perfil <texto> — metas, alergias, región, dieta\n"
        "/equipo <texto> — herramientas y métodos disponibles (ej: estufa, sartén, sin horno)\n"
        "/skill principiante|intermedio|avanzado — tu nivel de cocina\n"
        "/despensa <items> — lo que tienes (separado por comas)\n"
        "/gusto <texto> — registra una reacción\n"
        "/historial — últimas recetas\n"
        "/nivel — tu rango de cocina 🍳\n"
        "/idioma es|en — idioma de comandos\n"
        "Todo lo demás: pídeme de comer. Ej: \"tengo pollo y arroz, algo rápido\""
    ),
    "en": (
        "Commands:\n"
        "/perfil <text> — goals, allergies, region, diet\n"
        "/equipo <text> — tools & methods you have (e.g. stove, pan, no oven)\n"
        "/skill beginner|intermediate|advanced — your cooking level\n"
        "/despensa <items> — what you have (comma-separated)\n"
        "/gusto <text> — log a taste reaction\n"
        "/historial — recent dishes\n"
        "/nivel — your kitchen rank 🍳\n"
        "/idioma es|en — command language\n"
        "Anything else: ask for food. e.g. \"I have chicken and rice, something quick\""
    ),
}


def t(lang: str, key: str, **kw) -> str:
    return UI.get(lang, UI["es"])[key].format(**kw)


# ---------------------------------------------------------------------------
# Telegram + output helpers
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    """Belt-and-suspenders: strip stray markdown the model might still emit."""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)  # drop leading # headers
    return text.strip()


def send_message(chat_id: int, text: str) -> None:
    text = clean(text)
    for i in range(0, len(text), 4000):  # Telegram caps at 4096 chars
        requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text[i : i + 4000]},
            timeout=30,
        )


# ---------------------------------------------------------------------------
# The brain call
# ---------------------------------------------------------------------------
def ask_chef(chat_id: int, user_message: str) -> str:
    u = db.get_user(chat_id)
    pantry = db.get_pantry(chat_id)
    tastes = db.recent_tastes(chat_id, limit=15)
    recipes = db.recent_recipe_titles(chat_id, limit=5)
    xp = db.get_xp(chat_id)

    context = (
        f"PROFILE (goals/allergies/region/diet):\n{(u['profile'] if u else None) or '(none yet)'}\n\n"
        f"EQUIPMENT & METHODS:\n{(u['equipment'] if u else None) or '(unknown)'}\n\n"
        f"SELF-REPORTED SKILL: {(u['skill'] if u else None) or '(unspecified)'}\n"
        f"KITCHEN RANK: {levels.title_for(xp)} ({xp} XP)\n\n"
        f"PANTRY:\n{', '.join(pantry) if pantry else '(empty)'}\n\n"
        f"TASTE HISTORY (recent reactions):\n{chr(10).join(tastes) if tastes else '(no data yet)'}\n\n"
        f"RECENTLY SERVED (do not repeat):\n{chr(10).join(recipes) if recipes else '(none)'}\n\n"
        f"USER MESSAGE:\n{user_message}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(parts).strip() or "(el chef se quedó sin palabras)"


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------
def _arg(text: str, cmd: str) -> str:
    return text[len(cmd):].strip()


def handle_message(chat_id: int, text: str) -> None:
    db.ensure_user(chat_id)
    lang = db.get_lang(chat_id)
    text = text.strip()

    # --- Always-open commands (work even without access) ---------------------
    if text.startswith("/id"):
        send_message(chat_id, t(lang, "your_id", v=chat_id))
        return

    if text.startswith("/activar") or text.startswith("/redeem"):
        cmd = "/activar" if text.startswith("/activar") else "/redeem"
        code = _arg(text, cmd).strip().upper()
        if db.redeem_code(code, chat_id):
            send_message(chat_id, t(lang, "activated"))
        else:
            send_message(chat_id, t(lang, "code_bad"))
        return

    # --- Owner-only management commands ---------------------------------------
    if is_owner(chat_id):
        if text.startswith("/gencode"):
            code = new_code()
            db.create_code(code, _arg(text, "/gencode"))
            send_message(chat_id, t(lang, "code_new", v=code))
            return
        if text.startswith("/codes"):
            rows = db.list_codes()
            body = "\n".join(f"{c} {'· USADO por '+str(u) if u else '· libre'} {n}" for c, n, u in rows) or "—"
            send_message(chat_id, t(lang, "codes_list", v=body))
            return
        if text.startswith("/allow"):
            arg = _arg(text, "/allow").split(maxsplit=1)
            if arg and arg[0].lstrip("-").isdigit():
                target = int(arg[0])
                db.allow_user(target, arg[1] if len(arg) > 1 else "")
                send_message(chat_id, t(lang, "user_allowed", v=target))
            return
        if text.startswith("/deny"):
            arg = _arg(text, "/deny").strip()
            if arg.lstrip("-").isdigit():
                db.deny_user(int(arg))
                send_message(chat_id, t(lang, "user_denied", v=arg))
            return
        if text.startswith("/allowed"):
            rows = db.list_allowed()
            body = "\n".join(f"{cid} {note}" for cid, note in rows) or "—"
            send_message(chat_id, t(lang, "allowed_list", v=body))
            return

    # --- THE GATE: everything below costs API money, so check access first ----
    if not (is_owner(chat_id) or db.is_allowed(chat_id)):
        if text.startswith("/start") or text.startswith("/help"):
            send_message(chat_id, t(lang, "welcome") + "\n\n" + t(lang, "denied"))
        else:
            send_message(chat_id, t(lang, "denied"))
        return

    # --- From here on, the user is authorized --------------------------------
    if text.startswith("/start") or text.startswith("/help"):
        send_message(chat_id, t(lang, "welcome") + "\n\n" + HELP[lang])

    elif text.startswith("/idioma"):
        choice = _arg(text, "/idioma").lower()
        new = "en" if choice.startswith("en") else "es"
        db.set_lang(chat_id, new)
        send_message(chat_id, t(new, "lang_set"))

    elif text.startswith("/perfil"):
        body = _arg(text, "/perfil")
        if body:
            db.set_profile(chat_id, body)
            send_message(chat_id, t(lang, "profile_saved"))
        else:
            u = db.get_user(chat_id)
            send_message(chat_id, t(lang, "profile_show", v=(u["profile"] if u else None) or t(lang, "empty")))

    elif text.startswith("/equipo"):
        body = _arg(text, "/equipo")
        if body:
            db.set_equipment(chat_id, body)
            send_message(chat_id, t(lang, "equip_saved", v=body))
        else:
            u = db.get_user(chat_id)
            send_message(chat_id, t(lang, "equip_show", v=(u["equipment"] if u else None) or t(lang, "empty")))

    elif text.startswith("/skill"):
        body = _arg(text, "/skill")
        if body:
            db.set_skill(chat_id, body)
            send_message(chat_id, t(lang, "skill_saved", v=body))
        else:
            send_message(chat_id, t(lang, "skill_ask"))

    elif text.startswith("/despensa"):
        body = _arg(text, "/despensa")
        if body:
            items = [x.strip() for x in body.split(",") if x.strip()]
            db.set_pantry(chat_id, items)
            send_message(chat_id, t(lang, "pantry_saved", v=", ".join(items)))
        else:
            pantry = db.get_pantry(chat_id)
            send_message(chat_id, t(lang, "pantry_show", v=", ".join(pantry) if pantry else t(lang, "empty")))

    elif text.startswith("/gusto") or text.startswith("/taste"):
        cmd = "/gusto" if text.startswith("/gusto") else "/taste"
        body = _arg(text, cmd)
        if body:
            db.log_taste(chat_id, body)
            old, new = db.add_xp(chat_id, levels.XP_PER_TASTE)
            msg = t(lang, "taste_saved", xp=levels.XP_PER_TASTE)
            up = levels.leveled_up(old, new)
            if up:
                msg += t(lang, "levelup", v=up)
            send_message(chat_id, msg)
        else:
            send_message(chat_id, t(lang, "taste_ask"))

    elif text.startswith("/historial") or text.startswith("/history"):
        titles = db.recent_recipe_titles(chat_id, limit=10)
        send_message(chat_id, t(lang, "history", v="\n".join(titles)) if titles else t(lang, "history_empty"))

    elif text.startswith("/nivel") or text.startswith("/level"):
        send_message(chat_id, levels.status(db.get_xp(chat_id)))

    else:
        reply = ask_chef(chat_id, text)
        db.log_recipe(chat_id, reply)
        old, new = db.add_xp(chat_id, levels.XP_PER_RECIPE)
        up = levels.leveled_up(old, new)
        if up:
            reply += t(lang, "levelup", v=up)
        send_message(chat_id, reply)


# ---------------------------------------------------------------------------
# Main loop — long polling. Bot only ever calls out; no inbound ports.
# ---------------------------------------------------------------------------
def main() -> None:
    db.init()
    print("Chef bot v0.2 corriendo. Ctrl+C para apagar.")
    offset = None
    while True:
        try:
            resp = requests.get(
                f"{TG_API}/getUpdates",
                params={"timeout": 50, "offset": offset},
                timeout=60,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
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
            time.sleep(5)


if __name__ == "__main__":
    main()
