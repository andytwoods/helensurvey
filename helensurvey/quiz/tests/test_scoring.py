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
