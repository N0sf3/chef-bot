"""
Chef Bot v0.1 — Dissident Labs
A Telegram bot that cooks like Nosfe: recipes fitted to your pantry,
your tastes, and your goals. Memory lives in SQLite. Brain is Claude.

Flow: Telegram (long polling) -> build context from DB -> Claude -> reply -> log.
"""

import os
import time
import traceback

import requests
import anthropic

import db

# ---------------------------------------------------------------------------
# Config — everything secret comes from environment variables, never from code
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

MODEL = os.environ.get("MODEL", "claude-opus-4-8")

# The cooking doctrine. This is the soul of the bot — and the first thing
# you should edit yourself. Make it sound like YOU.
SYSTEM_PROMPT = """\
Eres el Chef de Dissident Labs: un cocinero real con década de cocina \
profesional (incluida cocina de alto nivel en NYC), no un recetario genérico.

Reglas:
- Cocinas con lo que hay en la despensa del usuario. Si falta algo clave, \
propón el reemplazo más realista, no una lista de compras.
- El sabor manda: bases de sabor, ácido para balancear, textura. Nada de \
recetas planas de blog.
- Respeta SIEMPRE las alergias y restricciones del perfil. Eso no se negocia.
- Ajusta a las metas del perfil (macros, calorías) sin sacrificar gusto.
- Aprende del historial de gustos del usuario y menciónalo cuando sea relevante.
- Formato: nombre del plato, ingredientes con cantidades aproximadas, pasos \
numerados y cortos, y UN tip de técnica que mejore el resultado.
- Responde en el idioma del usuario. Directo y cálido, cero relleno.
"""


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------
def send_message(chat_id: int, text: str) -> None:
    """Telegram caps messages at 4096 chars, so long replies get split."""
    for i in range(0, len(text), 4000):
        requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text[i : i + 4000]},
            timeout=30,
        )


# ---------------------------------------------------------------------------
# The brain call
# ---------------------------------------------------------------------------
def ask_chef(chat_id: int, user_message: str) -> str:
    """Build the user's context from the DB and ask Claude for a reply."""
    profile = db.get_profile(chat_id)
    pantry = db.get_pantry(chat_id)
    tastes = db.recent_tastes(chat_id, limit=15)
    recipes = db.recent_recipe_titles(chat_id, limit=5)

    context = (
        f"PERFIL DEL USUARIO:\n{profile or '(sin perfil aún)'}\n\n"
        f"DESPENSA ACTUAL:\n{', '.join(pantry) if pantry else '(vacía)'}\n\n"
        f"HISTORIAL DE GUSTOS (reacciones recientes):\n"
        f"{chr(10).join(tastes) if tastes else '(sin datos aún)'}\n\n"
        f"RECETAS RECIENTES (no repetir):\n"
        f"{chr(10).join(recipes) if recipes else '(ninguna)'}\n\n"
        f"MENSAJE DEL USUARIO:\n{user_message}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )

    text_parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_parts).strip() or "(el chef se quedó sin palabras)"


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------
HELP = """\
Comandos del Chef:
/perfil <texto> — guarda tus metas, alergias, región (reemplaza el anterior)
/despensa — muestra tu despensa
/despensa <items separados por coma> — reemplaza tu despensa
/gusto <texto> — registra una reacción ("me encantó el curry", "menos picante")
/historial — últimas recetas
Todo lo demás: pídeme de comer. Ej: "tengo pollo, arroz y brócoli, algo rápido"
"""


def handle_message(chat_id: int, text: str) -> None:
    db.ensure_user(chat_id)
    text = text.strip()

    if text.startswith("/start") or text.startswith("/help"):
        send_message(chat_id, "🔪 Chef de Dissident Labs a la orden.\n\n" + HELP)

    elif text.startswith("/perfil"):
        body = text[len("/perfil"):].strip()
        if body:
            db.set_profile(chat_id, body)
            send_message(chat_id, "Perfil guardado. Eso no se me olvida.")
        else:
            send_message(chat_id, f"Tu perfil:\n{db.get_profile(chat_id) or '(vacío)'}")

    elif text.startswith("/despensa"):
        body = text[len("/despensa"):].strip()
        if body:
            items = [x.strip() for x in body.split(",") if x.strip()]
            db.set_pantry(chat_id, items)
            send_message(chat_id, f"Despensa actualizada: {', '.join(items)}")
        else:
            pantry = db.get_pantry(chat_id)
            send_message(chat_id, f"Despensa: {', '.join(pantry) if pantry else '(vacía)'}")

    elif text.startswith("/gusto"):
        body = text[len("/gusto"):].strip()
        if body:
            db.log_taste(chat_id, body)
            send_message(chat_id, "Anotado en tu paladar. 📝")
        else:
            send_message(chat_id, "Dime qué te gustó o no: /gusto me encantó el hogao")

    elif text.startswith("/historial"):
        titles = db.recent_recipe_titles(chat_id, limit=10)
        send_message(chat_id, "Últimas recetas:\n" + "\n".join(titles) if titles else "Aún no te he cocinado nada.")

    else:
        reply = ask_chef(chat_id, text)
        db.log_recipe(chat_id, reply)
        send_message(chat_id, reply)


# ---------------------------------------------------------------------------
# Main loop — long polling: we ask Telegram "anything new?" forever.
# No webhooks, no domain, no inbound ports. The bot only ever calls out.
# ---------------------------------------------------------------------------
def main() -> None:
    db.init()
    print("Chef bot corriendo. Ctrl+C para apagar.")
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
                    try:
                        handle_message(chat_id, text)
                    except anthropic.RateLimitError:
                        send_message(chat_id, "El chef está saturado, dame un minuto. 🔥")
                    except anthropic.APIStatusError as e:
                        send_message(chat_id, f"Problema con el cerebro del chef ({e.status_code}). Intenta de nuevo.")
                    except Exception:
                        traceback.print_exc()
                        send_message(chat_id, "Algo se quemó en la cocina. Ya lo reviso.")
        except requests.RequestException:
            time.sleep(5)  # network hiccup — breathe and retry


if __name__ == "__main__":
    main()
