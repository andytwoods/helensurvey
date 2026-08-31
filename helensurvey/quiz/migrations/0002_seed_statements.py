"""Seed the ten Pathway statements the quiz ships with."""
from django.db import migrations

STATEMENTS = [
    ("Leading a team and being goal-oriented.", "management"),
    (
        "Co-designing and structuring projects, working with peers and stakeholders alike.",
        "management",
    ),
    ("Identifying, describing and / or mitigating ethical risks.", "ethics"),
    (
        "Being methodical with paperwork and managing team in following ethical frameworks.",
        "ethics",
    ),
    ("Tackling technical problems to build and demonstrate solutions.", "technical"),
    (
        "Assessing technical opportunities in relation to project briefs and seeking "
        "relevant research to inform exploration.",
        "technical",
    ),
    (
        "Leading on inclusion, ensuring users are appropriately involved & represented.",
        "audience",
    ),
    (
        "Understanding audience needs through active engagement, e.g. co-designing "
        "focus groups, surveys and/or co-creation opportunities.",
        "audience",
    ),
    ("Applying creative skills to problem solve, build & demonstrate.", "creative"),
    (
        "Considering creative approaches to challenges and unearthing relevant "
        "research / practice to inform exploration.",
        "creative",
    ),
]


def seed(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    Statement.objects.bulk_create(
        [
            Statement(text=text, pathway=pathway, order=index)
            for index, (text, pathway) in enumerate(STATEMENTS)
        ],
    )


def unseed(apps, schema_editor):
    Statement = apps.get_model("quiz", "Statement")
    Statement.objects.filter(text__in=[text for text, _ in STATEMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("quiz", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
