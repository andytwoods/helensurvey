"""Static copy and presentation metadata for the five Pathway roles.

This is authored content rather than data users edit, so it lives in code:
no migrations churn when the wording is tweaked, and the values are available
to templates, the scoring code and the staff dashboard alike.
"""

from django.db import models
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


class Pathway(models.TextChoices):
    MANAGEMENT = "management", _("Management")
    CREATIVE = "creative", _("Creative")
    TECHNICAL = "technical", _("Technical")
    AUDIENCE = "audience", _("Audience")
    ETHICS = "ethics", _("Ethics")


class Rating(models.TextChoices):
    CONFIDENT = "confident", _("I can do this with some confidence")
    GROWING = "growing", _("I am actively trying to get better at this")
    SKIP = "skip", _("I am not interested in this")


# Display order for chips, breakdown rows and tie-breaking.
PATHWAY_ORDER = [
    Pathway.MANAGEMENT,
    Pathway.CREATIVE,
    Pathway.TECHNICAL,
    Pathway.AUDIENCE,
    Pathway.ETHICS,
]

# SVG path fragments, drawn on a 24x24 viewBox. Authored constants, so they are
# marked safe for direct inclusion in templates and inline JSON.
_ICONS = {
    Pathway.MANAGEMENT: (
        '<path d="M7 3V21"/>'
        '<path d="M7 4.5 L18 7.5 L7 10.5 Z" fill="currentColor" stroke="none"/>'
        '<circle cx="7" cy="20.5" r="1.3" fill="currentColor" '
        'stroke="none"/>'
    ),
    Pathway.CREATIVE: (
        '<path d="M12 2.5 L14 9.8 L21.5 12 L14 14.2 L12 21.5 L10 14.2 '
        'L2.5 12 L10 9.8 Z"/>'
    ),
    Pathway.TECHNICAL: (
        '<circle cx="12" cy="12" r="3.2"/>'
        '<path d="M12 2.5V5.5M12 18.5V21.5M21.5 12H18.5M5.5 12H2.5'
        'M18.6 5.4L16.5 7.5M7.5 16.5L5.4 18.6M18.6 18.6L16.5 16.5M7.5 7.5L5.4 5.4"/>'
    ),
    Pathway.AUDIENCE: (
        '<path d="M2.5 12C5 6.5 19 6.5 21.5 12C19 17.5 5 17.5 2.5 12Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    Pathway.ETHICS: (
        '<path d="M12 2.5L20 6V11.2C20 17 16.3 20.3 12 21.8C7.7 20.3 4 17 4 11.2V6Z"/>'
        '<path d="M8.5 12L11 14.5L16 9.5"/>'
    ),
}

PATHWAY_META = {
    Pathway.MANAGEMENT: {
        "name": "Management",
        "hex": "#C1521F",
        "stamp": "The Orchestrator",
        "strength": (
            "You turn scattered moving parts into a plan people can actually follow, "
            "timelines, priorities, and the calm in the room when things wobble."
        ),
        "growth": (
            "and you're sharpening how you organise and lead — turning instinct "
            "into a repeatable rhythm."
        ),
        "pure": (
            "Structure is your native language, and everyone around you moves "
            "faster because of it."
        ),
    },
    Pathway.CREATIVE: {
        "name": "Creative",
        "hex": "#3B3486",
        "stamp": "The Originator",
        "strength": (
            "You reach for the idea nobody else pitched, original, a little bold, "
            "and usually the one people remember."
        ),
        "growth": (
            "and you're stretching your creative range, pushing past the first idea "
            "to find the better one."
        ),
        "pure": (
            "Ideas are where you live, and you're rarely short of one worth chasing."
        ),
    },
    Pathway.TECHNICAL: {
        "name": "Technical",
        "hex": "#8C1F28",
        "stamp": "The Builder",
        "strength": (
            "You care about how things actually work, the mechanics, the tools, the "
            "details that make something function instead of just look good."
        ),
        "growth": (
            "and you're building sharper technical instincts, getting more fluent in "
            "the systems behind the work."
        ),
        "pure": "If it needs to actually work, you're the one who makes sure it does.",
    },
    Pathway.AUDIENCE: {
        "name": "Audience",
        "hex": "#0F6E6E",
        "stamp": "The Translator",
        "strength": (
            "You think in terms of the people on the other end of the work, what "
            "they'll feel, notice, and remember."
        ),
        "growth": (
            "and you're deepening how well you read a room and translate for it."
        ),
        "pure": (
            "Everything you make is built with someone specific in mind, and it shows."
        ),
    },
    Pathway.ETHICS: {
        "name": "Ethics",
        "hex": "#1F5B3A",
        "stamp": "The Anchor",
        "strength": (
            "You ask the harder question before anyone else does, is this fair, "
            "honest, and worth doing the way we're doing it."
        ),
        "growth": (
            "and you're strengthening your instinct for when to pump the brakes "
            "and ask why."
        ),
        "pure": (
            "Integrity isn't an afterthought for you — it's the first filter "
            "everything passes through."
        ),
    },
}

for _key, _meta in PATHWAY_META.items():
    _meta["value"] = str(_key)
    _meta["icon"] = mark_safe(_ICONS[_key])  # noqa: S308 - authored constant, not user input


def pathway_context() -> list[dict]:
    """Pathway metadata in display order, for templates and the client bundle."""
    return [PATHWAY_META[p] for p in PATHWAY_ORDER]
