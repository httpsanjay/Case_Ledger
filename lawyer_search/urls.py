from django.urls import path
from . import views


urlpatterns = [
   path("search/", views.lawyer_search, name="lawyer_search"),
]