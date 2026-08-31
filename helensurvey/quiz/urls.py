from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("", views.quiz, name="quiz"),
    path("submit/", views.submit, name="submit"),
    path("results/", views.results, name="results"),
    path("results/export.csv", views.results_csv, name="results_csv"),
]
