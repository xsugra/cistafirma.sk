# Small helpers for consistent number formatting across backend

NBSP = "\u00A0"

def format_int_space(value):
    """Format integer with non-breaking spaces as thousands separator.
    Returns empty string for None or empty.
    """
    if value is None:
        return ""
    try:
        iv = int(round(value))
    except Exception:
        try:
            return str(value)
        except Exception:
            return ""
    # Use regular formatting then replace commas with NBSP
    return f"{iv:,}".replace(",", NBSP)


def format_currency_eur(value):
    """Format numeric value as euro with space thousands separator and no decimals.
    Example: 1234567 -> '1 234 567€'
    """
    if value is None:
        return ""
    try:
        iv = int(round(value))
    except Exception:
        try:
            iv = int(value)
        except Exception:
            return str(value)
    return f"{iv:,}".replace(",", NBSP) + "€"

