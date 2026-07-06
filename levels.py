"""
levels.py — the light RPG layer.

You earn XP by cooking and rating. XP maps to a kitchen rank, shown to you and
fed to the chef so recipes grow with you. Rank titles are localized (ES/EN).
"""

# Shared thresholds + emoji; titles are per-language.
THRESHOLDS = [0, 50, 120, 220, 350, 520, 750, 1100, 1600]
EMOJIS = ["🥄", "🔪", "🥗", "🔥", "🍳", "🎩", "👨‍🍳", "⭐", "🌟"]
TITLES = {
    "es": ["Aprendiz", "Pinche", "Ayudante de cocina", "Cocinero de línea",
           "Cocinero de partida", "Subchef", "Jefe de cocina", "Chef Ejecutivo", "Maestro"],
    "en": ["Apprentice", "Prep Cook", "Pantry Cook", "Line Cook",
           "Station Chef", "Sous Chef", "Head Chef", "Executive Chef", "Master"],
}

XP_PER_RECIPE = 10
XP_PER_TASTE = 5


def _index_for(xp: int) -> int:
    """Which rank index this XP total falls into."""
    idx = 0
    for i, thr in enumerate(THRESHOLDS):
        if xp >= thr:
            idx = i
        else:
            break
    return idx


def _titles(lang: str) -> list[str]:
    return TITLES.get(lang, TITLES["es"])


def title_for(xp: int, lang: str = "es") -> str:
    """Just the '🍳 Cocinero de línea' string — for display and chef context."""
    i = _index_for(xp)
    return f"{EMOJIS[i]} {_titles(lang)[i]}"


def _bar(into: int, span: int, width: int = 10) -> str:
    filled = int(width * into / span) if span else width
    return "▰" * filled + "▱" * (width - filled)


def status(xp: int, lang: str = "es") -> str:
    """The full RPG status card shown on /nivel."""
    i = _index_for(xp)
    emoji, title, thr = EMOJIS[i], _titles(lang)[i], THRESHOLDS[i]
    if i + 1 < len(THRESHOLDS):
        nxt_thr, nxt_title, nxt_emoji = THRESHOLDS[i + 1], _titles(lang)[i + 1], EMOJIS[i + 1]
        into, span = xp - thr, nxt_thr - thr
        return (
            f"{emoji} {title} · {xp} XP\n"
            f"{_bar(into, span)}  {into}/{span} → {nxt_emoji} {nxt_title}"
        )
    max_label = {"es": "(nivel máximo)", "en": "(max level)"}.get(lang, "(nivel máximo)")
    return f"{emoji} {title} {max_label} · {xp} XP 🏆"


def leveled_up(old_xp: int, new_xp: int, lang: str = "es"):
    """If a rank threshold was crossed, return the new rank string, else None."""
    if _index_for(old_xp) != _index_for(new_xp):
        return title_for(new_xp, lang)
    return None
