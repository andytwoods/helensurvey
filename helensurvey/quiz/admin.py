from django.contrib import admin

from .models import Answer
from .models import Response
from .models import Statement
from .pathways import PATHWAY_META
from .pathways import PATHWAY_ORDER


class DepthPathwayFilter(admin.SimpleListFilter):
    """Filter responses by a single depth pathway across the cohort."""

    title = "depth pathway"
    parameter_name = "depth_pathway"

    def lookups(self, request, model_admin):
        return [(str(p), PATHWAY_META[p]["name"]) for p in PATHWAY_ORDER]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(depth__contains=f",{self.value()},")


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    list_display = ["text", "pathway", "order", "is_active"]
    list_filter = ["pathway", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["text"]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    readonly_fields = ["statement", "rating"]

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["display_name", "result_label", "depth_pathways", "created"]
    list_filter = [
        "primary",
        "ascending",
        DepthPathwayFilter,
        "is_pure",
        "all_skip",
        "created",
    ]
    search_fields = ["name"]
    date_hierarchy = "created"
    readonly_fields = [
        "name",
        "created",
        "primary",
        "ascending",
        "is_pure",
        "all_skip",
        "depth",
    ]
    inlines = [AnswerInline]

    @admin.display(description="Name", ordering="name")
    def display_name(self, obj: Response) -> str:
        return obj.display_name

    @admin.display(description="Result")
    def result_label(self, obj: Response) -> str:
        return obj.result_label

    @admin.display(description="Depth pathway(s)", ordering="depth")
    def depth_pathways(self, obj: Response) -> str:
        return ", ".join(obj.depth_pathway_names)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("answers__statement")

    def has_add_permission(self, request) -> bool:
        # Responses are only ever created by participants taking the quiz.
        return False
