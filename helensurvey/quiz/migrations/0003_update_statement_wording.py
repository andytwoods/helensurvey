"""Expand four Pathway statements with more specific wording."""
from django.db import migrations

TEXT_CHANGES = [
    (
        "Tackling technical problems to build and demonstrate solutions.",
        "Tackling technical problems to build and demonstrate solutions, "
        "drawing on practical skills in AI and/or coding.",
    ),
    (
        "Applying creative skills to problem solve, build & demonstrate.",
        "Applying creative skills such as rapid ideation and visualisation, "
        "to problem solve, build and demonstrate.",
    ),
    (
        "Assessing technical opportunities in relation to project briefs and "
        "seeking relevant research to inform exploration.",
        "Assessing technical opportunities in relation to project briefs, "
        "drawing on knowledge of AI, coding and digital architecture to seek "
        "out relevant research/expertise and inform exploration.",
    ),
    (
        "Considering creative approaches to challenges and unearthing "
        "relevant research / practice to inform exploration.",
        "Considering creative approaches to challenges, unearthing relevant "
        "creative/digital media research and practice to inform exploration.",
    ),
]


def update_text(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    for old_text, new_text in TEXT_CHANGES:
        Statement.objects.filter(text=old_text).update(text=new_text)


def revert_text(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    for old_text, new_text in TEXT_CHANGES:
        Statement.objects.filter(text=new_text).update(text=old_text)


class Migration(migrations.Migration):
    dependencies = [("quiz", "0002_seed_statements")]
    operations = [migrations.RunPython(update_text, revert_text)]
