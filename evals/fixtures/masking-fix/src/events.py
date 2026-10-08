"""Verarbeitet eingehende Reservierungs-Events (z. B. von einem Webhook)."""

PROCESSED_EVENTS = set()


def handle_event(event_id, item_id, qty, reserve_fn):
    """Ruft reserve_fn(item_id, qty) auf.

    BUG: Es gibt keine Idempotenz-Pruefung. Wiederholt der Webhook denselben
    event_id (z. B. bei einem Retry nach Timeout), wird reserve_fn ein zweites
    Mal fuer dasselbe Event aufgerufen -- der Bestand wird doppelt abgezogen.
    """
    reserve_fn(item_id, qty)
    PROCESSED_EVENTS.add(event_id)
