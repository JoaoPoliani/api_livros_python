import json

from django.db.models import ProtectedError
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import Book


def error(message, status):
    return JsonResponse({"error": message}, status=status)


def parse_json(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return None, error("JSON inválido.", 400)
    if not isinstance(data, dict):
        return None, error("O corpo deve ser um objeto JSON.", 400)
    return data, None


def book_to_dict(book):
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "available": book.available,
        "created_at": book.created_at.isoformat(),
    }


def clean_book(data):
    errors = {}
    title = data.get("title")
    author = data.get("author")
    year = data.get("year")
    available = data.get("available", True)

    if not isinstance(title, str) or not title.strip():
        errors["title"] = "Campo obrigatório (texto)."
    if not isinstance(author, str) or not author.strip():
        errors["author"] = "Campo obrigatório (texto)."
    if not isinstance(year, int) or isinstance(year, bool):
        errors["year"] = "Deve ser um número inteiro."
    if not isinstance(available, bool):
        errors["available"] = "Deve ser true ou false."

    if errors:
        return None, errors
    return {
        "title": title.strip(),
        "author": author.strip(),
        "year": year,
        "available": available,
    }, None


@csrf_exempt
def books_collection(request):
    if request.method == "GET":
        return JsonResponse([book_to_dict(b) for b in Book.objects.all()], safe=False)

    if request.method == "POST":
        data, err = parse_json(request)
        if err:
            return err
        cleaned, errors = clean_book(data)
        if errors:
            return JsonResponse({"errors": errors}, status=400)
        book = Book.objects.create(**cleaned)
        return JsonResponse(book_to_dict(book), status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
@require_GET
def books_available(request):
    books = Book.objects.filter(available=True)
    return JsonResponse(
        [
            {"id": b.id, "title": b.title, "author": b.author, "available": b.available}
            for b in books
        ],
        safe=False,
    )


@csrf_exempt
def book_detail(request, pk):
    book = Book.objects.filter(pk=pk).first()
    if book is None:
        return error("Livro não encontrado.", 404)

    if request.method == "GET":
        return JsonResponse(book_to_dict(book))

    if request.method == "PUT":
        data, err = parse_json(request)
        if err:
            return err
        cleaned, errors = clean_book(data)
        if errors:
            return JsonResponse({"errors": errors}, status=400)
        for field, value in cleaned.items():
            setattr(book, field, value)
        book.save()
        return JsonResponse(book_to_dict(book))

    if request.method == "DELETE":
        try:
            book.delete()
        except ProtectedError:
            return error("Livro possui empréstimos vinculados.", 400)
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])