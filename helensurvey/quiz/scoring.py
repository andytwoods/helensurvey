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
    depth: list[str] = field(default_factory=list)


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
    is whatever else they are working on hardest. A third, independent signal
    is "depth": any pathway where the participant answered "confident" on one
    of its statements and "actively trying" on the other. Depth is computed
    from the raw tallies alone and never suppressed for overlapping with the
    primary or ascending pathway.
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

    depth = [p for p in keys if confident[p] >= 1 and growing[p] >= 1]
    score = Score(confident=confident, growing=growing, skip=skip, depth=depth)

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


def _join_names(names: list[str]) -> str:
    """Join pathway names for prose: "A", "A and B", or "A, B, and C"."""
    *head, last = names
    if not head:
        return last
    return f"{', '.join(head)}{',' if len(head) > 1 else ''} and {last}"


def describe(score: Score, name: str = "") -> dict:
    """Build the participant-facing copy for a score.

    ``depth_note`` omits any pathway that's already named as the primary or
    ascending result — ``score.depth`` itself is untouched, so admin/CSV
    consumers still see the full, independent signal.
    """
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

    # score.depth itself stays the full, independent signal (used by the
    # admin column/filter and CSV export); the participant-facing note just
    # omits whatever's already named as the primary or ascending result, so
    # nothing reads as "Technical... also building depth in Technical."
    depth_names = [
        PATHWAY_META[Pathway(p)]["name"]
        for p in score.depth
        if p not in (score.primary, score.ascending)
    ]
    depth_note = (
        f"You're also building real depth in {_join_names(depth_names)}."
        if depth_names
        else ""
    )

    return {
        "title": primary["stamp"],
        "subtitle": subtitle,
        "description": description,
        "depth_note": depth_note,
    }
