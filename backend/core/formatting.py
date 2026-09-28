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


def plural_sk(count, one, few, many):
    """A counted noun in Slovak: `1 firma`, `3 firmy`, `5 firiem`.

    The same rule the frontend already applies to points
    (`RiskScoreSection.pointsLabel`): singular for one, the plural form for two
    to four, the genitive plural above that.

    It lives here rather than being inlined at each call site because these
    strings appear in text a reader takes as the product's own statement --
    beside a company's name, beside a person's name. `1 firiem` is the kind of
    text that makes a reader trust the numbers next to it less.
    """
    if count == 1:
        return f'{count} {one}'
    if 2 <= count <= 4:
        return f'{count} {few}'
    return f'{count} {many}'


def plural_oblique_sk(count, one, many):
    """The same count where only two forms exist: `1 firme`, `5 firmách`.

    After a preposition -- `v 1 firme`, `v 5 firmách`, `z 1 osoby`, `z 5 osôb`
    -- Slovak uses a case form that is the same for two as for five, so the
    three-way rule above does not apply. Keeping it a separate function means
    no caller has to remember which of the two shapes it needs.
    """
    return f'{count} {one}' if count == 1 else f'{count} {many}'

