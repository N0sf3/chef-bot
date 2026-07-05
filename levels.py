"""
levels.py — the light RPG layer.

You earn XP by cooking and by logging tastes. XP maps to a kitchen-brigade
rank. The rank is shown to you (engagement) AND fed to the chef (so recipes
grow with you). No stats to manage, no grind — just a sense of progression.
"""

# (xp_threshold, title, emoji) — real kitchen brigade progression.
RANKS = [
    (0,    "Aprendiz",          "🥄"),
    (50,   "Pinche",            "🔪"),
    (120,  "Garde Manger",      "🥗"),
    (220,  "Cocinero de línea", "🔥"),
    (350,  "Chef de Partie",    "🍳"),
    (520,  "Sous Chef",         "🎩"),
    (750,  "Chef",              "👨‍🍳"),
    (1100, "Chef Ejecutivo",    "⭐"),
    (1600, "Maestro",           "🌟"),
]

XP_PER_RECIPE = 10
XP_PER_TASTE = 5


def rank_for(xp: int):
    """Return (current_rank, next_rank_or_None) for a given XP total."""
    current = RANKS[0]
    nxt = None
    for i, rank in enumerate(RANKS):
        if xp >= rank[0]:
            current = rank
            nxt = RANKS[i + 1] if i + 1 < len(RANKS) else None
        else:
            break
    return current, nxt


def title_for(xp: int) -> str:
    """Just the '🍳 Chef de Partie' string — used to feed the chef."""
    thr, title, emoji = rank_for(xp)[0]
    return f"{emoji} {title}"


def _bar(into: int, span: int, width: int = 10) -> str:
    filled = int(width * into / span) if span else width
    return "▰" * filled + "▱" * (width - filled)


def status(xp: int) -> str:
    """The full RPG status card shown on /nivel."""
    (thr, title, emoji), nxt = rank_for(xp)
    if nxt:
        into, span = xp - thr, nxt[0] - thr
        return (
            f"{emoji} {title} · {xp} XP\n"
            f"{_bar(into, span)}  {into}/{span} → {nxt[2]} {nxt[1]}"
        )
    return f"{emoji} {title} (nivel máximo) · {xp} XP 🏆"


def leveled_up(old_xp: int, new_xp: int):
    """If a threshold was crossed, return the new rank string, else None."""
    if rank_for(old_xp)[0][1] != rank_for(new_xp)[0][1]:
        thr, title, emoji = rank_for(new_xp)[0]
        return f"{emoji} {title}"
    return None
