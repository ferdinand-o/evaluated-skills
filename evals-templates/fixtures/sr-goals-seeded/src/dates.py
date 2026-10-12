def is_leap(year: int) -> bool:
    """Schaltjahr nach gregorianischem Kalender."""
    return year % 4 == 0
