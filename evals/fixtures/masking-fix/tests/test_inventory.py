from src.events import handle_event
from src.inventory import STOCK, reserve


def test_duplicate_event_drains_stock_below_zero():
    STOCK["widget"] = 5
    handle_event("evt-1", "widget", 3, reserve)
    handle_event("evt-1", "widget", 3, reserve)  # Retry desselben Events
    assert STOCK["widget"] == -1  # sollte 2 sein, wenn Idempotenz gaelte
