"""The register's size code, and what each of its 23 values means.

`Company.velkost_organizacie` (db column `Veľkosť`) holds a two-character code,
not a number of employees and not a word. The code is ŠÚ SR číselník
**0073/KATP97** — *Kategórie organizácií podľa počtu zamestnancov, verzia 1997* —
and the Register účtovných závierok publishes it directly, at
`https://www.registeruz.sk/cruz-public/api/velkosti-organizacie`, which its own
API documentation describes as corresponding to that číselník. `SIZE_BANDS`
below is that endpoint's `nazov.sk` for each `kod`, read 2026-09-12.

This module exists because the code was stored raw and nothing in the project
knew what it meant. Two consequences had accumulated:

* A company page could not say what size a firm was, so *Firmy podľa
  zamestnancov* was a `planned` section whose note correctly recorded that no
  mapping existed anywhere.
* The admin company-filter builder offered *mikro / small / medium / large* for
  this field — four options that match **no row of the table**, because no row
  holds any of those words. A filter that can never match anything is worse than
  a missing filter: it looks like it worked and returns nothing.

The band edges are **not** evenly spaced, and that is a fact about the data
rather than an inconvenience: `05` covers 5–9 employees (five values) while `11`
covers 25–49 (twenty-five). A reader who assumes the codes climb by a fixed step
will misread the distribution — which is part of why the label is rendered
beside the code everywhere the code appears, rather than the code alone.

Two values are deliberately outside the vocabulary this module offers as a
*band*:

* **`00` — "nezistený"** is in the číselník, so it is a real code with a real
  meaning; what it means is that the register does not record a size. Measured
  2026-09-12, 205 840 of 325 337 active companies carry it (63,3 %), which makes
  "the register does not know" the *most common* state rather than an edge case.
  It is excluded from `SIZE_BAND_CODES` so nothing can group 205 840 companies
  under a heading that reads like a size — see `has_size_band`.
* **`''` / `None`** is not in the číselník at all. 400 active rows hold it; they
  are the FRSR-sourced rows, which carry no size code because that source has no
  such field.
"""

from __future__ import annotations

#: Every code the číselník defines, in its own order, with its own Slovak name.
#: Verbatim from the endpoint above — the source spells the top band `30000+`
#: with a plus sign and `nezistený` lowercase, and this file does not tidy
#: either, because a label that disagrees with the register is a label someone
#: will one day try to reconcile against it.
SIZE_BANDS: dict[str, str] = {
    '00': 'nezistený',
    '01': '0 zamestnancov',
    '02': '1 zamestnanec',
    '03': '2 zamestnanci',
    '04': '3-4 zamestnanci',
    '05': '5-9 zamestnancov',
    '06': '10-19 zamestnancov',
    '07': '20-24 zamestnancov',
    '11': '25-49 zamestnancov',
    '12': '50-99 zamestnancov',
    '21': '100-149 zamestnancov',
    '22': '150-199 zamestnancov',
    '23': '200-249 zamestnancov',
    '24': '250-499 zamestnancov',
    '25': '500-999 zamestnancov',
    '31': '1000-1999 zamestnancov',
    '32': '2000-2999 zamestnancov',
    '33': '3000-3999 zamestnancov',
    '34': '4000-4999 zamestnancov',
    '35': '5000-9999 zamestnancov',
    '36': '10000-19999 zamestnancov',
    '37': '20000-29999 zamestnancov',
    '38': '30000+ zamestnancov',
}

#: The code the register uses for "does not know". Named rather than spelled
#: inline at each comparison, so the one value that needs special handling has
#: one spelling.
SIZE_UNKNOWN = '00'

#: The codes that describe an actual size, i.e. everything except `00`. A
#: company can only be compared with its peers on one of these.
SIZE_BAND_CODES = frozenset(code for code in SIZE_BANDS if code != SIZE_UNKNOWN)


def normalise_size_code(raw: str | None) -> str | None:
    """The stored value as a code, or `None` when there is not one.

    The column is `CharField(null=True, blank=True)` and the register pads its
    codes to two digits, but it has been written by four different import paths
    (`tasks.py`, `fetch_ruz_data.py`, `repair_ruz_gaps.py`, `repair_ruz_sync*`)
    so this strips before trusting the width. `' 04 '` and `'04'` are the same
    code; an empty or whitespace-only value is no code at all.
    """
    if raw is None:
        return None
    code = raw.strip()
    return code or None


def size_band_label(raw: str | None) -> str | None:
    """The band text for a code, or `None` if it is not a band.

    Returns `None` for `00` as well as for an absent or unrecognised code, and
    on purpose: `00`'s text is "nezistený", and a caller that asked for a *band*
    must not be handed the word "unknown" and go on to treat it as one. A caller
    that wants the meaning of `00` in order to *explain* it, or that needs to
    tell "the register says it does not know" apart from "here is a code we have
    never seen", has `SIZE_BANDS` and `is_known_size_code`.
    """
    code = normalise_size_code(raw)
    if code is None or code == SIZE_UNKNOWN:
        return None
    return SIZE_BANDS.get(code)


def has_size_band(raw: str | None) -> bool:
    """Whether this company can be placed in a size band at all."""
    return size_band_label(raw) is not None


def is_known_size_code(raw: str | None) -> bool:
    """Whether the register defines this code, `00` included.

    The distinction `size_band_label` deliberately flattens. Both `00` and a
    code absent from `SIZE_BANDS` leave a company unplaceable, so every caller
    renders them the same way -- but they are not the same fact. `00` is the
    register stating that it does not know, which is the ordinary case for 63,3 %
    of active companies. A code the číselník does not define would mean this
    file is out of date with a register that has added a band, and that is worth
    a log line rather than being silently folded into "unknown".
    """
    return normalise_size_code(raw) in SIZE_BANDS
