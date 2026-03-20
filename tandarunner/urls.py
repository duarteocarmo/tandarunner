from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("partials/graphs/", views.graphs_partial, name="graphs_partial"),
    path("partials/stats/", views.stats_partial, name="stats_partial"),
    path("partials/chat/", views.chat_partial, name="chat_partial"),
]
