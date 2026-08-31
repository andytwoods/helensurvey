from django.db import models
from django.utils.translation import gettext_lazy as _

from .pathways import PATHWAY_META
from .pathways import Pathway
from .pathways import Rating


class Statement(models.Model):
    """One statement a participant rates, belonging to a single Pathway role."""

    text = models.TextField(_("Statement"))
    pathway = models.CharField(_("Pathway"), max_length=20, choices=Pathway.choices)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_("Inactive statements are not shown to new participants."),
    )

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self) -> str:
        return f"{self.get_pathway_display()}: {self.text[:60]}"


class Response(models.Model):
    """A completed run of the quiz by one participant."""

    # Blank remains permitted at the DB level for responses recorded before
    # the name became mandatory; the submit endpoint rejects empty names.
    name = models.CharField(_("Name"), max_length=120, blank=True)
    created = models.DateTimeField(_("Submitted"), auto_now_add=True, db_index=True)
    primary = models.CharField(
        _("Primary pathway"),
        max_length=20,
        choices=Pathway.choices,
        blank=True,
    )
    ascending = models.CharField(
        _("Ascending pathway"),
        max_length=20,
        choices=Pathway.choices,
        blank=True,
    )
    is_pure = models.BooleanField(_("Pure result"), default=False)
    all_skip = models.BooleanField(
        _("Flagged for outreach"),
        default=False,
        help_text=_("Participant answered “not interested” to every statement."),
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = _("response")
        verbose_name_plural = _("responses")

    def __str__(self) -> str:
        return f"{self.display_name} — {self.result_label}"

    @property
    def display_name(self) -> str:
        return self.name or "Anonymous"

    @property
    def result_label(self) -> str:
        """Human-readable summary used in the staff table and the admin."""
        if self.all_skip:
            return "All ‘not interested’ — flagged"
        if not self.primary:
            return "No result"
        primary = PATHWAY_META[Pathway(self.primary)]["name"]
        if self.is_pure or not self.ascending:
            return f"Pure {primary}"
        ascending = PATHWAY_META[Pathway(self.ascending)]["name"]
        return f"{primary} → {ascending}"


class Answer(models.Model):
    """One participant's rating of one statement."""

    response = models.ForeignKey(
        Response,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name=_("Response"),
    )
    statement = models.ForeignKey(
        Statement,
        on_delete=models.PROTECT,
        related_name="answers",
        verbose_name=_("Statement"),
    )
    rating = models.CharField(_("Rating"), max_length=20, choices=Rating.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["response", "statement"],
                name="unique_answer_per_statement",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.response_id}: {self.statement_id} = {self.rating}"
