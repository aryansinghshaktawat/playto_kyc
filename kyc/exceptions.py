from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _first_error_message(detail):
    if isinstance(detail, list):
        return _first_error_message(detail[0]) if detail else "Invalid request."

    if isinstance(detail, dict):
        field, value = next(iter(detail.items()))
        message = _first_error_message(value)
        if field in {"detail", "non_field_errors", "error"}:
            return message
        return f"{field}: {message}"

    return str(detail)


def custom_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        return Response(
            {"error": _first_error_message(detail)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None

    response.data = {"error": _first_error_message(response.data)}
    return response
