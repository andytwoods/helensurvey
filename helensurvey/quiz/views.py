import csv
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models import Q
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import Answer
from .models import Response
from .models import Statement
from .pathways import PATHWAY_META
from .pathways import PATHWAY_ORDER
from .pathways import RATING_SHORT
from .pathways import Pathway
from .pathways import Rating
from .pathways import pathway_context
from .scoring import describe
from .scoring import score_answers

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = Response._meta.get_field("name").max_length  # noqa: SLF001

# Submission errors are deliberately terse: the client is our own JS, and a
# malformed payload means a bug or tampering, not something to explain.
ERR_MALFORMED = "Malformed request."
ERR_NO_ANSWERS = "No answers submitted."
ERR_BAD_ANSWER = "Malformed answer."
ERR_INCOMPLETE = "Please answer every statement."
ERR_NO_NAME = "Please enter your name."


def quiz(request: HttpRequest) -> HttpResponse:
    """The participant-facing quiz: intro, statements and result in one page."""
    statements = list(
        Statement.objects.filter(is_active=True).values("id", "text"),
    )
    pathways = pathway_context()
    return render(
        request,
        "quiz/quiz.html",
        {
            "pathways": pathways,
            "statements_count": len(statements),
            # Serialised with `json_script` in the template, so these must stay
            # plain Python objects. Pathway is deliberately omitted from the
            # statement payload: scoring happens server-side.
            "statements_data": statements,
            "pathways_data": [
                {
                    "value": p["value"],
                    "name": p["name"],
                    "hex": p["hex"],
                    "icon": str(p["icon"]),
                }
                for p in pathways
            ],
        },
    )


@require_POST
def submit(request: HttpRequest) -> JsonResponse:
    """Score and persist a completed quiz, returning the result for rendering.

    The client sends only raw ratings; the outcome is computed here so a
    participant cannot pick their own badge by editing the payload.
    """
    statements = Statement.objects.filter(is_active=True).in_bulk()
    try:
        name, cleaned = _parse_submission(request.body, statements)
    except ValidationError as exc:
        return JsonResponse({"error": exc.message}, status=400)

    score = score_answers(
        [(statements[sid].pathway, rating) for sid, rating in cleaned.items()],
    )

    with transaction.atomic():
        response = Response.objects.create(
            name=name,
            primary=score.primary,
            ascending=score.ascending,
            is_pure=score.is_pure,
            all_skip=score.all_skip,
        )
        Answer.objects.bulk_create(
            [
                Answer(response=response, statement_id=sid, rating=rating)
                for sid, rating in cleaned.items()
            ],
        )

    logger.info("Quiz response %s saved (%s)", response.pk, response.result_label)
    return JsonResponse(
        {
            "primary": score.primary,
            "ascending": score.ascending,
            "is_pure": score.is_pure,
            "all_skip": score.all_skip,
            "confident": score.confident,
            "growing": score.growing,
            "skip": score.skip,
            "statements_per_pathway": _statements_per_pathway(statements.values()),
            **describe(score, name),
        },
    )


def _parse_submission(body: bytes, statements: dict) -> tuple[str, dict[int, str]]:
    """Validate a raw submission body into a name and ``{statement_id: rating}``.

    Raises:
        ValidationError: if the payload is malformed or incomplete.

    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError(ERR_MALFORMED) from exc

    if not isinstance(payload, dict):
        raise ValidationError(ERR_MALFORMED)

    raw_answers = payload.get("answers")
    if not isinstance(raw_answers, list) or not raw_answers:
        raise ValidationError(ERR_NO_ANSWERS)

    valid_ratings = set(Rating.values)
    cleaned: dict[int, str] = {}
    for entry in raw_answers:
        if not isinstance(entry, dict):
            raise ValidationError(ERR_BAD_ANSWER)
        try:
            statement_id = int(entry.get("statement"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(ERR_BAD_ANSWER) from exc
        rating = entry.get("rating")
        if statement_id not in statements or rating not in valid_ratings:
            raise ValidationError(ERR_BAD_ANSWER)
        cleaned[statement_id] = rating

    if len(cleaned) != len(statements):
        raise ValidationError(ERR_INCOMPLETE)

    name = str(payload.get("name") or "").strip()[:MAX_NAME_LENGTH]
    if not name:
        raise ValidationError(ERR_NO_NAME)
    return name, cleaned


def _statements_per_pathway(statements) -> dict[str, int]:
    """How many statements each pathway has, so the client can scale the bars."""
    counts = dict.fromkeys((str(p) for p in PATHWAY_ORDER), 0)
    for statement in statements:
        counts[statement.pathway] += 1
    return counts


@staff_member_required
def results(request: HttpRequest) -> HttpResponse:
    """Staff-only dashboard: pathway distribution plus every response."""
    # One extra query for all answers rather than one per response; the per-
    # participant breakdown below needs every rating.
    responses = list(Response.objects.prefetch_related("answers__statement"))
    statements = list(Statement.objects.all())

    totals = Response.objects.aggregate(
        total=Count("id"),
        flagged=Count("id", filter=Q(all_skip=True)),
    )
    primary_counts = dict.fromkeys((str(p) for p in PATHWAY_ORDER), 0)
    ascending_counts = dict.fromkeys((str(p) for p in PATHWAY_ORDER), 0)
    for row in (
        Response.objects.filter(all_skip=False)
        .exclude(primary="")
        .values("primary")
        .annotate(n=Count("id"))
    ):
        primary_counts[row["primary"]] = row["n"]
    for row in (
        Response.objects.filter(all_skip=False, is_pure=False)
        .exclude(ascending="")
        .values("ascending")
        .annotate(n=Count("id"))
    ):
        ascending_counts[row["ascending"]] = row["n"]

    max_primary = max([1, *primary_counts.values()])
    max_ascending = max([1, *ascending_counts.values()])

    def bars(counts: dict[str, int], scale: int) -> list[dict]:
        return [
            {
                "meta": PATHWAY_META[pathway],
                "count": counts[str(pathway)],
                "percent": counts[str(pathway)] / scale * 100,
            }
            for pathway in PATHWAY_ORDER
        ]

    return render(
        request,
        "quiz/results.html",
        {
            "responses": [_response_detail(r, statements) for r in responses],
            "total": totals["total"],
            "flagged": totals["flagged"],
            "primary_bars": bars(primary_counts, max_primary),
            "ascending_bars": bars(ascending_counts, max_ascending),
        },
    )


def _response_detail(response: Response, statements: list[Statement]) -> dict:
    """One participant's full answers: pathway tallies plus every rating.

    Built from the prefetched answers rather than fresh queries, so adding this
    to the dashboard costs no extra query per participant.
    """
    per_pathway = _statements_per_pathway(statements)
    confident = dict.fromkeys((str(p) for p in PATHWAY_ORDER), 0)
    growing = dict.fromkeys((str(p) for p in PATHWAY_ORDER), 0)
    by_statement = {}
    for answer in response.answers.all():
        by_statement[answer.statement_id] = answer.rating
        if answer.rating == Rating.CONFIDENT:
            confident[answer.statement.pathway] += 1
        elif answer.rating == Rating.GROWING:
            growing[answer.statement.pathway] += 1

    def pct(count: int, pathway: str) -> float:
        total = per_pathway.get(pathway, 0)
        return count / total * 100 if total else 0

    return {
        "response": response,
        "bars": [
            {
                "meta": PATHWAY_META[pathway],
                "confident": confident[str(pathway)],
                "growing": growing[str(pathway)],
                "confident_percent": pct(confident[str(pathway)], str(pathway)),
                "growing_percent": pct(growing[str(pathway)], str(pathway)),
            }
            for pathway in PATHWAY_ORDER
        ],
        "answers": [
            {
                "text": statement.text,
                "meta": PATHWAY_META[Pathway(statement.pathway)],
                "rating": by_statement.get(statement.pk),
                "rating_label": RATING_SHORT[Rating(by_statement[statement.pk])]
                if statement.pk in by_statement
                else "—",
            }
            for statement in statements
        ],
    }


@staff_member_required
def results_csv(request: HttpRequest) -> HttpResponse:
    """Staff-only CSV export, one row per response with per-pathway tallies."""
    pathways = [str(p) for p in PATHWAY_ORDER]
    # Every statement, in a stable order, so each gets its own column and the
    # per-pathway totals can be checked against the individual answers.
    statements = list(Statement.objects.all())
    http_response = HttpResponse(content_type="text/csv")
    http_response["Content-Disposition"] = (
        'attachment; filename="pathway-quiz-results.csv"'
    )
    writer = csv.writer(http_response)
    writer.writerow(
        [
            "name",
            "primary",
            "ascending",
            "is_pure",
            "all_skip",
            *[f"confident_{p}" for p in pathways],
            *[f"growing_{p}" for p in pathways],
            *[f"skip_{p}" for p in pathways],
            # Headed by the statement itself rather than an opaque q1/q2, so the
            # file is readable without a separate key.
            *[f"[{s.get_pathway_display()}] {s.text}" for s in statements],
            "timestamp",
        ],
    )

    queryset = Response.objects.prefetch_related("answers__statement").order_by(
        "-created",
    )
    for response in queryset:
        tallies = {r: dict.fromkeys(pathways, 0) for r in Rating.values}
        by_statement = {}
        for answer in response.answers.all():
            tallies[answer.rating][answer.statement.pathway] += 1
            by_statement[answer.statement_id] = answer.rating
        writer.writerow(
            [
                response.display_name,
                response.primary,
                response.ascending,
                response.is_pure,
                response.all_skip,
                *[tallies[Rating.CONFIDENT][p] for p in pathways],
                *[tallies[Rating.GROWING][p] for p in pathways],
                *[tallies[Rating.SKIP][p] for p in pathways],
                *[by_statement.get(s.pk, "") for s in statements],
                response.created.isoformat(),
            ],
        )
    return http_response
