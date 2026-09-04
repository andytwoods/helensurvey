"""Scoring rules, exercised without touching the database."""

import pytest

from helensurvey.quiz.pathways import Pathway
from helensurvey.quiz.pathways import Rating
from helensurvey.quiz.scoring import describe
from helensurvey.quiz.scoring import score_answers

CONFIDENT = Rating.CONFIDENT.value
GROWING = Rating.GROWING.value
SKIP = Rating.SKIP.value


def test_primary_is_the_most_confident_pathway():
    score = score_answers(
        [
            (Pathway.TECHNICAL.value, CONFIDENT),
            (Pathway.TECHNICAL.value, CONFIDENT),
            (Pathway.CREATIVE.value, CONFIDENT),
            (Pathway.CREATIVE.value, SKIP),
        ],
    )
    assert score.primary == Pathway.TECHNICAL.value


def test_ascending_is_the_strongest_non_primary_growth_area():
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.ETHICS.value, GROWING),
            (Pathway.ETHICS.value, GROWING),
            (Pathway.CREATIVE.value, GROWING),
        ],
    )
    assert score.primary == Pathway.MANAGEMENT.value
    assert score.ascending == Pathway.ETHICS.value
    assert score.is_pure is False


def test_no_growth_anywhere_else_gives_a_pure_result():
    score = score_answers(
        [
            (Pathway.AUDIENCE.value, CONFIDENT),
            (Pathway.TECHNICAL.value, SKIP),
        ],
    )
    assert score.primary == Pathway.AUDIENCE.value
    assert score.is_pure is True
    assert score.ascending == ""


def test_growth_on_the_primary_alone_still_counts_as_pure():
    """The ascending role must differ from the primary one."""
    score = score_answers(
        [
            (Pathway.CREATIVE.value, CONFIDENT),
            (Pathway.CREATIVE.value, GROWING),
        ],
    )
    assert score.primary == Pathway.CREATIVE.value
    assert score.is_pure is True


def test_no_confidence_anywhere_falls_back_to_growth():
    score = score_answers(
        [
            (Pathway.ETHICS.value, GROWING),
            (Pathway.ETHICS.value, GROWING),
            (Pathway.AUDIENCE.value, GROWING),
            (Pathway.MANAGEMENT.value, SKIP),
        ],
    )
    assert score.primary == Pathway.ETHICS.value
    assert score.ascending == Pathway.AUDIENCE.value


def test_all_skip_is_flagged_and_scores_nothing():
    score = score_answers(
        [(Pathway.TECHNICAL.value, SKIP), (Pathway.ETHICS.value, SKIP)],
    )
    assert score.all_skip is True
    assert score.primary == ""
    assert score.ascending == ""


def test_ties_break_on_canonical_pathway_order():
    """Management precedes Creative in display order, so it wins a tie."""
    score = score_answers(
        [
            (Pathway.CREATIVE.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, CONFIDENT),
        ],
    )
    assert score.primary == Pathway.MANAGEMENT.value


def test_tallies_cover_every_pathway():
    score = score_answers([(Pathway.TECHNICAL.value, CONFIDENT)])
    assert set(score.confident) == {p.value for p in Pathway}
    assert score.confident[Pathway.TECHNICAL.value] == 1
    assert score.growing[Pathway.TECHNICAL.value] == 0


@pytest.mark.parametrize("name", ["", "Ada"])
def test_describe_personalises_only_when_named(name):
    score = score_answers([(Pathway.ETHICS.value, CONFIDENT)])
    copy = describe(score, name)
    assert copy["title"] == "The Anchor"
    assert copy["subtitle"] == "Pure Ethics"
    assert copy["description"].startswith("Ada, " if name else "You ask")


def test_describe_all_skip_offers_a_human_route():
    score = score_answers([(Pathway.ETHICS.value, SKIP)])
    copy = describe(score, "Ada")
    assert copy["title"] == "Thanks for being honest."
    assert "challenge producer" in copy["description"]


# ---------- depth pathway ----------
# A pathway is "depth" when the respondent gave both a confident and an
# actively-trying answer to that pathway's two statements. score.depth is a
# fully independent signal, never filtered for overlap with primary or
# ascending — but describe()'s participant-facing note drops whichever
# overlaps, so nothing reads as "Technical... also building depth in
# Technical."


def test_one_depth_pathway():
    # Technical is the decoy primary (highest confident count) and Creative
    # the decoy ascending (highest growing count among the rest), so
    # Management is the sole depth pathway and doesn't overlap either.
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, GROWING),
            (Pathway.TECHNICAL.value, CONFIDENT),
            (Pathway.TECHNICAL.value, CONFIDENT),
            (Pathway.CREATIVE.value, GROWING),
            (Pathway.CREATIVE.value, GROWING),
        ],
    )
    assert score.primary == Pathway.TECHNICAL.value
    assert score.ascending == Pathway.CREATIVE.value
    assert score.depth == [Pathway.MANAGEMENT.value]
    copy = describe(score)
    assert copy["depth_note"] == "You're also building real depth in Management."


def test_multiple_depth_pathways_are_listed_in_canonical_order():
    # Audience is the decoy primary and Creative the decoy ascending, so all
    # three depth pathways (Management, Technical, Ethics) stay clear of both
    # and are listed in canonical order, not answer order.
    score = score_answers(
        [
            (Pathway.ETHICS.value, CONFIDENT),
            (Pathway.ETHICS.value, GROWING),
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, GROWING),
            (Pathway.TECHNICAL.value, CONFIDENT),
            (Pathway.TECHNICAL.value, GROWING),
            (Pathway.AUDIENCE.value, CONFIDENT),
            (Pathway.AUDIENCE.value, CONFIDENT),
            (Pathway.CREATIVE.value, GROWING),
            (Pathway.CREATIVE.value, GROWING),
        ],
    )
    assert score.primary == Pathway.AUDIENCE.value
    assert score.ascending == Pathway.CREATIVE.value
    assert score.depth == [
        Pathway.MANAGEMENT.value,
        Pathway.TECHNICAL.value,
        Pathway.ETHICS.value,
    ]
    copy = describe(score)
    assert copy["depth_note"] == (
        "You're also building real depth in Management, Technical, and Ethics."
    )


def test_no_depth_pathway_when_nothing_pairs_confident_with_growing():
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.CREATIVE.value, GROWING),
            (Pathway.CREATIVE.value, SKIP),
            (Pathway.TECHNICAL.value, SKIP),
            (Pathway.TECHNICAL.value, SKIP),
        ],
    )
    assert score.depth == []
    assert describe(score)["depth_note"] == ""


def test_depth_pathway_equal_to_primary_is_kept_in_score_but_dropped_from_the_note():
    """score.depth stays the full independent signal (for admin/CSV); the
    participant-facing note omits a pathway already named as the primary
    result, so nothing reads as "Management... also building depth in
    Management."
    """
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, GROWING),
            (Pathway.CREATIVE.value, SKIP),
            (Pathway.CREATIVE.value, SKIP),
        ],
    )
    assert score.primary == Pathway.MANAGEMENT.value
    assert score.depth == [Pathway.MANAGEMENT.value]
    copy = describe(score)
    assert copy["subtitle"] == "Pure Management"
    assert copy["depth_note"] == ""


def test_depth_pathway_equal_to_ascending_is_kept_in_score_but_dropped_from_the_note():
    """Same as above, for a depth pathway that matches the ascending result."""
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.ETHICS.value, CONFIDENT),
            (Pathway.ETHICS.value, GROWING),
        ],
    )
    assert score.primary == Pathway.MANAGEMENT.value
    assert score.ascending == Pathway.ETHICS.value
    assert score.is_pure is False
    assert score.depth == [Pathway.ETHICS.value]
    copy = describe(score)
    assert copy["subtitle"] == "Management — ascending Ethics"
    assert copy["depth_note"] == ""


def test_depth_note_still_shows_a_pathway_that_does_not_overlap():
    """Only the overlapping depth pathway is dropped from the note — a depth
    pathway distinct from both primary and ascending is still named.
    """
    score = score_answers(
        [
            (Pathway.MANAGEMENT.value, CONFIDENT),
            (Pathway.MANAGEMENT.value, GROWING),
            (Pathway.ETHICS.value, CONFIDENT),
            (Pathway.ETHICS.value, GROWING),
            (Pathway.TECHNICAL.value, GROWING),
            (Pathway.TECHNICAL.value, GROWING),
        ],
    )
    assert score.primary == Pathway.MANAGEMENT.value
    assert score.ascending == Pathway.TECHNICAL.value
    # The raw signal still includes both qualifying pathways...
    assert score.depth == [Pathway.MANAGEMENT.value, Pathway.ETHICS.value]
    # ...but the note only names the one that isn't already the primary
    # or ascending result.
    assert describe(score)["depth_note"] == "You're also building real depth in Ethics."
