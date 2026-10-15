from django.urls import path
from . import views

urlpatterns = [
    path("loans", views.loans_collection),
    path("loans/<int:pk>", views.loan_detail),
]