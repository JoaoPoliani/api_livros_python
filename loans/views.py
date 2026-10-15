import json
from datetime import date

from django.db import transaction
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from books.models import Book
from .models import Loan


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


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def loan_to_dict(loan):
    return {
        "id": loan.id,
        "book_id": loan.book_id,
        "person_name": loan.person_name,
        "loan_date": loan.loan_date.isoformat(),
        "return_date": loan.return_date.isoformat() if loan.return_date else None,
    }


def clean_loan(data):
    errors = {}
    book_id = data.get("book_id")
    person_name = data.get("person_name")
    loan_date = parse_date(data.get("loan_date"))
    return_raw = data.get("return_date")
    return_date = parse_date(return_raw) if return_raw is not None else None

    if not isinstance(book_id, int) or isinstance(book_id, bool):
        errors["book_id"] = "Deve ser um número inteiro."
    if not isinstance(person_name, str) or not person_name.strip():
        errors["person_name"] = "Campo obrigatório (texto)."
    if loan_date is None:
        errors["loan_date"] = "Use o formato AAAA-MM-DD."
    if return_raw is not None and return_date is None:
        errors["return_date"] = "Use o formato AAAA-MM-DD ou null."

    if errors:
        return None, errors
    return {
        "book_id": book_id,
        "person_name": person_name.strip(),
        "loan_date": loan_date,
        "return_date": return_date,
    }, None


@csrf_exempt
def loans_collection(request):
    if request.method == "GET":
        return JsonResponse([loan_to_dict(l) for l in Loan.objects.all()], safe=False)

    if request.method == "POST":
        data, err = parse_json(request)
        if err:
            return err
        cleaned, errors = clean_loan(data)
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        book = Book.objects.filter(pk=cleaned["book_id"]).first()
        if book is None:
            return error("Livro não encontrado.", 404)
        if not book.available:
            return error("Livro indisponível para empréstimo.", 400)

        with transaction.atomic():
            loan = Loan.objects.create(
                book=book,
                person_name=cleaned["person_name"],
                loan_date=cleaned["loan_date"],
            )
            book.available = False
            book.save(update_fields=["available"])

        return JsonResponse(loan_to_dict(loan), status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def loan_detail(request, pk):
    loan = Loan.objects.select_related("book").filter(pk=pk).first()
    if loan is None:
        return error("Empréstimo não encontrado.", 404)

    if request.method == "GET":
        return JsonResponse(loan_to_dict(loan))

    if request.method == "PUT":
        data, err = parse_json(request)
        if err:
            return err
        cleaned, errors = clean_loan(data)
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        new_book = Book.objects.filter(pk=cleaned["book_id"]).first()
        if new_book is None:
            return error("Livro não encontrado.", 404)

        old_book = loan.book
        was_active = loan.return_date is None
        is_active = cleaned["return_date"] is None
        changed = old_book.pk != new_book.pk

        if is_active and (not was_active or changed) and not new_book.available:
            return error("Livro indisponível para empréstimo.", 400)

        with transaction.atomic():
            if was_active and changed:
                old_book.available = True
                old_book.save(update_fields=["available"])

            new_book.available = not is_active
            new_book.save(update_fields=["available"])

            loan.book = new_book
            loan.person_name = cleaned["person_name"]
            loan.loan_date = cleaned["loan_date"]
            loan.return_date = cleaned["return_date"]
            loan.save()

        return JsonResponse(loan_to_dict(loan))

    if request.method == "DELETE":
        with transaction.atomic():
            if loan.return_date is None:
                book = loan.book
                book.available = True
                book.save(update_fields=["available"])
            loan.delete()
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "DELETE"])