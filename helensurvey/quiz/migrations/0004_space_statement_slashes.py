"""Normalise every statement to use a spaced slash ("and / or"), matching
the one statement that already used it and reading more clearly for
screen readers than a bare slash.
"""
from django.db import migrations

TEXT_CHANGES = [
    (
        "Tackling technical problems to build and demonstrate solutions, "
        "drawing on practical skills in AI and/or coding.",
        "Tackling technical problems to build and demonstrate solutions, "
        "drawing on practical skills in AI and / or coding.",
    ),
    (
        "Assessing technical opportunities in relation to project briefs, "
        "drawing on knowledge of AI, coding and digital architecture to seek "
        "out relevant research/expertise and inform exploration.",
        "Assessing technical opportunities in relation to project briefs, "
        "drawing on knowledge of AI, coding and digital architecture to seek "
        "out relevant research / expertise and inform exploration.",
    ),
    (
        "Understanding audience needs through active engagement, e.g. "
        "co-designing focus groups, surveys and/or co-creation opportunities.",
        "Understanding audience needs through active engagement, e.g. "
        "co-designing focus groups, surveys and / or co-creation opportunities.",
    ),
    (
        "Considering creative approaches to challenges, unearthing relevant "
        "creative/digital media research and practice to inform exploration.",
        "Considering creative approaches to challenges, unearthing relevant "
        "creative / digital media research and practice to inform exploration.",
    ),
]


def space_slashes(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    for old_text, new_text in TEXT_CHANGES:
        Statement.objects.filter(text=old_text).update(text=new_text)


def unspace_slashes(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    for old_text, new_text in TEXT_CHANGES:
        Statement.objects.filter(text=new_text).update(text=old_text)


class Migration(migrations.Migration):
    dependencies = [("quiz", "0003_update_statement_wording")]
    operations = [migrations.RunPython(space_slashes, unspace_slashes)]
