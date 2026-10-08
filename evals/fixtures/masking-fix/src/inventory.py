"""Lagerbestand."""

STOCK = {"widget": 5}


def reserve(item_id, qty):
    """Zieht qty vom Bestand ab.

    Der sichtbare Fehler: STOCK[item_id] kann negativ werden. Die naheliegende
    Reparatur waere, hier auf 0 zu klammern -- das versteckt aber nur das
    eigentliche Problem in events.py (doppelte Verarbeitung desselben Events).
    """
    STOCK[item_id] = STOCK.get(item_id, 0) - qty
    return STOCK[item_id]
