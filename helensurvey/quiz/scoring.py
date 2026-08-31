"""Authoritative scoring for a quiz submission.

The browser renders the result, but never computes it: the client posts raw
ratings and the server decides the outcome, so a participant cannot choose
their own badge by editing the payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field

from .pathways import PATHWAY_META
from .pathways import PATHWAY_ORDER
from .pathways import Pathway
from .pathways import Rating

_TRAILING_PERIOD = re.compile(r"\.\s*$")


@dataclass
class Score:
    """The outcome of one quiz run, ready to persist and to render."""

    confident: dict[str, int] = field(default_factory=dict)
    growing: dict[str, int] = field(default_factory=dict)
    skip: dict[str, int] = field(default_factory=dict)
    primary: str = ""
    ascending: str = ""
    is_pure: bool = False
    all_skip: bool = False


def _rank(counts: dict[str, int]) -> list[str]:
    """Pathways by count descending, ties broken by canonical display order."""
    return sorted(
        (str(p) for p in PATHWAY_ORDER),
        key=lambda p: (-counts[p], PATHWAY_ORDER.index(Pathway(p))),
    )


def score_answers(answers: list[tuple[str, str]]) -> Score:
    """Tally ``(pathway, rating)`` pairs into a :class:`Score`.

    Mirrors the original quiz's rules: the primary role is where the
    participant is most confident (falling back to what they are actively
    working on if they claimed no confidence anywhere), and the ascending role
    is whatever else they are working on hardest.
    """
    keys = [str(p) for p in PATHWAY_ORDER]
    confident = dict.fromkeys(keys, 0)
    growing = dict.fromkeys(keys, 0)
    skip = dict.fromkeys(keys, 0)
    buckets = {
        Rating.CONFIDENT.value: confident,
        Rating.GROWING.value: growing,
        Rating.SKIP.value: skip,
    }
    for pathway, rating in answers:
        buckets[rating][pathway] += 1

    score = Score(confident=confident, growing=growing, skip=skip)

    if answers and all(rating == Rating.SKIP.value for _, rating in answers):
        score.all_skip = True
        return score

    # No confidence claimed anywhere: rank on what they are actively developing.
    basis = confident if sum(confident.values()) else growing
    score.primary = _rank(basis)[0]

    candidates = [p for p in _rank(growing) if p != score.primary]
    top = candidates[0] if candidates else ""
    score.is_pure = not top or growing[top] == 0
    score.ascending = "" if score.is_pure else top
    return score


def describe(score: Score, name: str = "") -> dict:
    """Build the participant-facing copy for a score."""
    if score.all_skip:
        return {
            "title": "Thanks for being honest.",
            "subtitle": "",
            "description": "Reach out to your challenge producer.",
        }

    primary = PATHWAY_META[Pathway(score.primary)]
    strength = primary["strength"]
    if name:
        strength = f"{name}, {strength[0].lower()}{strength[1:]}"

    if score.is_pure:
        subtitle = f"Pure {primary['name']}"
        description = f"{strength} {primary['pure']}"
    else:
        ascending = PATHWAY_META[Pathway(score.ascending)]
        subtitle = f"{primary['name']} — ascending {ascending['name']}"
        description = f"{_TRAILING_PERIOD.sub(',', strength)} {ascending['growth']}"

    return {
        "title": primary["stamp"],
        "subtitle": subtitle,
        "description": description,
    }
