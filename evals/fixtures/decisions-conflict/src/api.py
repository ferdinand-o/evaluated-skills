"""Kleine REST-API. Bestehende Endpunkte nutzen ausschließlich `ApiError`
aus `src/errors.py` für Fehlerantworten."""

from src.errors import ApiError


def get_order(order_id: str, db) -> dict:
    order = db.get(order_id)
    if order is None:
        raise ApiError(code="ORDER_NOT_FOUND", message=f"Bestellung {order_id} nicht gefunden")
    return order
