from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QuizConfig(AppConfig):
    name = "helensurvey.quiz"
    verbose_name = _("Pathway Quiz")
