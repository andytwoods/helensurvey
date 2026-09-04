"""End-to-end behaviour of the quiz page, submission endpoint and staff views."""

import csv
import json
import re

import pytest
from django.urls import reverse
from django.utils.html import escape

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


def _staff(django_user_model):
    return django_user_model.objects.create_user(
        username="staff2",
        email="staff2@example.com",
        password="pw",  # noqa: S106
        is_staff=True,
    )


def test_results_page_shows_each_participants_answers(client, django_user_model):
    """Helen needs per-participant detail, not just the aggregate."""
    statements = list(Statement.objects.filter(is_active=True))
    technical = [s.pk for s in statements if s.pathway == Pathway.TECHNICAL.value]
    overrides = dict.fromkeys(technical, Rating.CONFIDENT.value)
    _post(client, {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)})

    client.force_login(_staff(django_user_model))
    body = client.get(reverse("quiz:results")).content.decode()

    # Every statement is listed for the participant, with its rating.
    for statement in statements:
        assert escape(statement.text) in body
    assert "confident" in body
    assert "not interested" in body


def test_results_page_answer_data_is_per_response(client, django_user_model):
    _post(client, {"name": "Ada", "answers": _answers(Rating.CONFIDENT.value)})
    _post(client, {"name": "Grace", "answers": _answers(Rating.GROWING.value)})

    client.force_login(_staff(django_user_model))
    context = client.get(reverse("quiz:results")).context["responses"]

    by_name = {item["response"].name: item for item in context}
    ada_confident = sum(b["confident"] for b in by_name["Ada"]["bars"])
    grace_growing = sum(b["growing"] for b in by_name["Grace"]["bars"])
    assert ada_confident == len(by_name["Ada"]["answers"])
    assert grace_growing == len(by_name["Grace"]["answers"])
    assert sum(b["confident"] for b in by_name["Grace"]["bars"]) == 0


def test_results_page_does_not_query_per_response(
    client,
    django_user_model,
    django_assert_max_num_queries,
):
    """The per-participant detail must not reintroduce an N+1."""
    for name in ("A", "B", "C", "D", "E"):
        _post(client, {"name": name, "answers": _answers()})

    client.force_login(_staff(django_user_model))
    # Session/user lookups plus a fixed handful for the page itself; the point
    # is that this does not grow with the number of responses.
    with django_assert_max_num_queries(12):
        assert client.get(reverse("quiz:results")).status_code == 200


def test_submission_returns_and_persists_depth_pathways(client):
    """Ethics qualifies as depth without being primary or ascending, so the
    API and the persisted record both surface it, note text included.
    """
    statements = list(Statement.objects.filter(is_active=True))
    management = [s.pk for s in statements if s.pathway == Pathway.MANAGEMENT.value]
    ethics = [s.pk for s in statements if s.pathway == Pathway.ETHICS.value]
    technical = [s.pk for s in statements if s.pathway == Pathway.TECHNICAL.value]
    overrides = {
        management[0]: Rating.CONFIDENT.value,
        management[1]: Rating.CONFIDENT.value,
        ethics[0]: Rating.CONFIDENT.value,
        ethics[1]: Rating.GROWING.value,
        technical[0]: Rating.GROWING.value,
        technical[1]: Rating.GROWING.value,
    }
    http_response = _post(
        client,
        {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)},
    )
    body = http_response.json()
    assert body["primary"] == Pathway.MANAGEMENT.value
    assert body["ascending"] == Pathway.TECHNICAL.value
    assert body["depth"] == [Pathway.ETHICS.value]
    assert body["depth_note"] == "You're also building real depth in Ethics."

    saved = Response.objects.get()
    assert saved.depth_pathway_names == ["Ethics"]


def test_csv_includes_depth_pathways_column(client, django_user_model):
    statements = list(Statement.objects.filter(is_active=True))
    management = [s.pk for s in statements if s.pathway == Pathway.MANAGEMENT.value]
    overrides = {
        management[0]: Rating.CONFIDENT.value,
        management[1]: Rating.GROWING.value,
    }
    _post(client, {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)})

    client.force_login(_staff(django_user_model))
    rows = list(
        csv.reader(
            client.get(reverse("quiz:results_csv")).content.decode().splitlines(),
        ),
    )
    header, row = rows[0], rows[1]
    assert row[header.index("depth_pathways")] == Pathway.MANAGEMENT.value


def test_admin_shows_and_filters_by_depth_pathway(client, django_user_model):
    statements = list(Statement.objects.filter(is_active=True))
    management = [s.pk for s in statements if s.pathway == Pathway.MANAGEMENT.value]
    overrides = {
        management[0]: Rating.CONFIDENT.value,
        management[1]: Rating.GROWING.value,
    }
    _post(client, {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)})
    _post(client, {"name": "Grace", "answers": _answers(Rating.SKIP.value)})

    admin_user = django_user_model.objects.create_user(
        username="root",
        email="root@example.com",
        password="pw",  # noqa: S106
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(admin_user)

    changelist_url = reverse("admin:quiz_response_changelist")
    body = client.get(changelist_url).content.decode()
    assert "Ada" in body
    assert "Grace" in body
    assert "Management" in body

    filtered = client.get(changelist_url, {"depth_pathway": Pathway.MANAGEMENT.value})
    assert filtered.status_code == 200
    filtered_body = filtered.content.decode()
    assert "Ada" in filtered_body
    assert "Grace" not in filtered_body


def test_csv_includes_each_statement_answer(client, django_user_model):
    statements = list(Statement.objects.filter(is_active=True))
    ethics = [s.pk for s in statements if s.pathway == Pathway.ETHICS.value]
    overrides = dict.fromkeys(ethics, Rating.GROWING.value)
    _post(client, {"name": "Ada", "answers": _answers(Rating.SKIP.value, overrides)})

    client.force_login(_staff(django_user_model))
    rows = list(
        csv.reader(
            client.get(reverse("quiz:results_csv")).content.decode().splitlines(),
        ),
    )
    header, row = rows[0], rows[1]

    for statement in statements:
        column = f"[{statement.get_pathway_display()}] {statement.text}"
        assert column in header
        assert row[header.index(column)] == (
            Rating.GROWING.value if statement.pk in ethics else Rating.SKIP.value
        )
