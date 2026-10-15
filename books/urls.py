from django.urls import path
from . import views

urlpatterns = [
    path("books", views.books_collection),
    path("books/available", views.books_available),
    path("books/<int:pk>", views.book_detail),
]