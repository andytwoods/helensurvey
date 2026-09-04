"""Backfill depth pathways for responses submitted before the field existed.

Depth is fully derivable from each response's existing answers, so
responses recorded before 0005_response_depth don't need to stay blank.
"""
from django.db import migrations

from helensurvey.quiz.pathways import PATHWAY_ORDER
from helensurvey.quiz.pathways import Rating
from helensurvey.quiz.pathways import encode_pathway_list

_KEYS = [str(p) for p in PATHWAY_ORDER]


def backfill_depth(apps, schema_editor):
    Response = apps.get_model("quiz", "Response")
    Answer = apps.get_model("quiz", "Answer")
    for response in Response.objects.filter(depth=""):
        confident = dict.fromkeys(_KEYS, 0)
        growing = dict.fromkeys(_KEYS, 0)
        for answer in Answer.objects.filter(
            response=response,
        ).select_related("statement"):
            pathway = answer.statement.pathway
            if answer.rating == Rating.CONFIDENT.value:
                confident[pathway] += 1
            elif answer.rating == Rating.GROWING.value:
                growing[pathway] += 1
        depth = [p for p in _KEYS if confident[p] >= 1 and growing[p] >= 1]
        if depth:
            response.depth = encode_pathway_list(depth)
            response.save(update_fields=["depth"])


def noop_reverse(apps, schema_editor):
    """Depth is derived data; nothing to restore going backward."""


class Migration(migrations.Migration):
    dependencies = [("quiz", "0005_response_depth")]
    operations = [migrations.RunPython(backfill_depth, noop_reverse)]
