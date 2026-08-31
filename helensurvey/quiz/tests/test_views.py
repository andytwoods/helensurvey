"""End-to-end behaviour of the quiz page, submission endpoint and staff views."""

import json
import re

import pytest
from django.urls import reverse

from helensurvey.quiz.models import Answer
from helensurvey.quiz.models import Response
from helensurvey.quiz.models import Statement
from helensurvey.quiz.pathways import Pathway
from helensurvey.quiz.pathways import Rating

pytestmark = pytest.mark.django_db


def _post(client, payload):
    return client.post(
        reverse("quiz:submit"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def _answers(rating=Rating.CONFIDENT.value, overrides=None):
    overrides = overrides or {}
    return [
        {"statement": s.pk, "rating": overrides.get(s.pk, rating)}
        for s in Statement.objects.filter(is_active=True)
    ]


def test_seeded_statements_cover_every_pathway():
    counts = {p.value: 0 for p in Pathway}
    for statement in Statement.objects.all():
        counts[statement.pathway] += 1
    assert all(count == 2 for count in counts.values())


def test_quiz_page_renders_statements_without_leaking_pathways(client):
    response = client.get(reverse("quiz:quiz"))
    assert response.status_code == 200
    payload = json.loads(
        re.search(
            r'id="statements-data"[^>]*>(.*?)</script>',
            response.content.decode(),
            re.S,
        ).group(1),
    )
    assert len(payload) == Statement.objects.filter(is_active=True).count()
    # Pathways are omitted so the answer key isn't shipped to the browser.
    assert all("pathway" not in item for item in payload)


def test_submission_is_scored_and_persisted(client):
    statements = list(Statement.objects.filter(is_active=True))
    technical = [s.pk for s in statements if s.pathway == Pathway.TECHNICAL.value]
    ethics = [s.pk for s in statements if s.pathway == Pathway.ETHICS.value]
    overrides = dict.fromkeys(technical, Rating.CONFIDENT.value)
    overrides.update(dict.fromkeys(ethics, Rating.GROWING.value))

    http_response = _post(
        client,
        {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)},
    )
    assert http_response.status_code == 200
    body = http_response.json()
    assert body["primary"] == Pathway.TECHNICAL.value
    assert body["ascending"] == Pathway.ETHICS.value
    assert body["title"] == "The Builder"
    assert body["description"].startswith("Ada,")

    saved = Response.objects.get()
    assert saved.name == "Ada"
    assert saved.primary == Pathway.TECHNICAL.value
    assert saved.ascending == Pathway.ETHICS.value
    assert saved.answers.count() == len(statements)


def test_all_skip_submission_is_flagged(client):
    http_response = _post(
        client,
        {"name": "Ada", "answers": _answers(Rating.SKIP.value)},
    )
    body = http_response.json()
    assert body["all_skip"] is True
    saved = Response.objects.get()
    assert saved.all_skip is True
    assert saved.display_name == "Ada"
    assert saved.result_label == "All ‘not interested’ — flagged"


@pytest.mark.parametrize("name", ["", "   ", None])
def test_submission_requires_a_name(client, name):
    """The name is mandatory, and not only in the browser."""
    http_response = _post(client, {"name": name, "answers": _answers()})
    assert http_response.status_code == 400
    assert http_response.json()["error"] == "Please enter your name."
    assert not Response.objects.exists()


def test_name_is_stripped_of_surrounding_whitespace(client):
    _post(client, {"name": "  Ada  ", "answers": _answers()})
    assert Response.objects.get().name == "Ada"


def test_client_cannot_choose_its_own_result(client):
    """A forged outcome in the payload is ignored; the server rescores."""
    _post(
        client,
        {
            "name": "Mallory",
            "primary": Pathway.CREATIVE.value,
            "is_pure": True,
            "answers": _answers(Rating.SKIP.value),
        },
    )
    saved = Response.objects.get()
    assert saved.primary == ""
    assert saved.all_skip is True


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "x", "answers": []},
        {"name": "x", "answers": "nope"},
        {"name": "x"},
        {"name": "x", "answers": [{"statement": 999999, "rating": "confident"}]},
        {"name": "x", "answers": [{"statement": 1, "rating": "excellent"}]},
        {"name": "x", "answers": ["not-a-dict"]},
    ],
)
def test_malformed_submissions_are_rejected(client, payload):
    assert _post(client, payload).status_code == 400
    assert not Response.objects.exists()


def test_partial_submissions_are_rejected(client):
    payload = {"name": "x", "answers": _answers()[:3]}
    assert _post(client, payload).status_code == 400
    assert not Response.objects.exists()


def test_malformed_json_is_rejected(client):
    http_response = client.post(
        reverse("quiz:submit"),
        data="{not json",
        content_type="application/json",
    )
    assert http_response.status_code == 400


def test_submit_rejects_get(client):
    assert client.get(reverse("quiz:submit")).status_code == 405


def test_overlong_names_are_truncated_not_rejected(client):
    _post(client, {"name": "A" * 500, "answers": _answers()})
    assert len(Response.objects.get().name) == 120


@pytest.mark.parametrize("url_name", ["quiz:results", "quiz:results_csv"])
def test_staff_views_reject_anonymous_visitors(client, url_name):
    http_response = client.get(reverse(url_name))
    assert http_response.status_code == 302
    assert reverse(url_name) not in http_response.url.split("?")[0]


@pytest.mark.parametrize("url_name", ["quiz:results", "quiz:results_csv"])
def test_staff_views_reject_signed_in_non_staff(client, user, url_name):
    client.force_login(user)
    assert client.get(reverse(url_name)).status_code == 302


def test_results_page_shows_responses_to_staff(client, django_user_model):
    _post(client, {"name": "Ada", "answers": _answers()})
    staff = django_user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="pw",  # noqa: S106
        is_staff=True,
    )
    client.force_login(staff)
    http_response = client.get(reverse("quiz:results"))
    assert http_response.status_code == 200
    assert "Ada" in http_response.content.decode()
    assert http_response.context["total"] == 1


def test_csv_export_has_a_row_per_response(client, django_user_model):
    _post(client, {"name": "Ada", "answers": _answers()})
    staff = django_user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="pw",  # noqa: S106
        is_staff=True,
    )
    client.force_login(staff)
    http_response = client.get(reverse("quiz:results_csv"))
    assert http_response.status_code == 200
    assert http_response["Content-Type"] == "text/csv"
    rows = http_response.content.decode().strip().splitlines()
    assert len(rows) == 2
    assert rows[1].startswith("Ada,")


def test_inactive_statements_are_not_served_or_required(client):
    Statement.objects.filter(pathway=Pathway.CREATIVE.value).update(is_active=False)
    active = Statement.objects.filter(is_active=True).count()
    http_response = _post(client, {"name": "Ada", "answers": _answers()})
    assert http_response.status_code == 200
    assert Answer.objects.count() == active
