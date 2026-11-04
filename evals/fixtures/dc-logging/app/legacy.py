"""Alter Import von Kundendaten."""


def import_customers(rows):
    print("import_customers: start")
    count = 0
    for _ in rows:
        count += 1
    print(f"import_customers: {count} Zeilen")
    return count
