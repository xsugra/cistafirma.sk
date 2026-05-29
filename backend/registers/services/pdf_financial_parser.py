"""
Parser for IFRS financial statements submitted as PDF attachments in RUZ.

Handles two formats:
1. VÚ POD (Výkaz Vybraných Údajov) — standardized MF SR form with row numbers
2. Free-form IFRS — financial statements with labels and two value columns

Uses pdfplumber for word-level extraction with x-coordinate awareness
to correctly reconstruct numbers that use spaces as thousand separators.
"""

import io
import logging
import re
import tempfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

import pdfplumber
import requests

from registers.http_client import build_retry_session

logger = logging.getLogger(__name__)

ATTACHMENT_URL = "https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/{id}"


# --- Keyword maps for extracting financial line items ---

PL_KEYWORDS = {
    "revenue": [
        "tržby celkom",
        "tržby z predaja tovaru, vlastných výrobkov a služieb",
        "výnosy z prevádzkovej činnosti celkom",
    ],
    "total_revenue": [
        "výnosy celkom",
    ],
    "costs": [
        "náklady na prevádzkovú činnosť celkom",
        "náklady celkom",
    ],
    "profit": [
        "zisk / (strata) za obdobie",
        "zisk za obdobie",
        "zisk/(strata) za obdobie",
        "výsledok hospodárenia za účtovné obdobie po zdanení",
        "výsledok hospodárenia za účtovné obdobie",
    ],
    "added_value": [
        "pridaná hodnota",
    ],
    "income_tax": [
        "daň z príjmov celkom",
        "daň z príjmu",
        "daň z príjmov",
    ],
    "income_tax_paid": [
        "splatná daň z príjmu",
        "splatná daň z príjmov",
        "daň z príjmov splatná celkom",
    ],
}

# Special: "Výnosy" as a standalone top-level line is used as revenue in IFRS P&L
# where there's no "Tržby celkom" line
STANDALONE_REVENUE_LABEL = "výnosy"

BS_KEYWORDS = {
    # Specific sub-categories MUST come before general totals
    # to prevent "dlhodobé záväzky celkom" matching as "záväzky celkom"
    "liabilities_long": [
        "dlhodobé záväzky celkom",
        "dlhodobé záväzky",
    ],
    "liabilities_short": [
        "krátkodobé záväzky celkom",
        "krátkodobé záväzky",
    ],
    "assets_tangible": [
        "pozemky, budovy a zariadenia",
        "pozemky, budovy a zariadenie",
        "dlhodobý hmotný majetok",
    ],
    "assets_intangible": [
        "nehmotný majetok",
        "dlhodobý nehmotný majetok",
        "goodwill a nehmotný majetok",
    ],
    "assets_inventory": [
        "zásoby",
    ],
    "equity_basic": [
        "základné imanie",
    ],
    # General totals come last
    "assets_total": [
        "aktíva celkom",
        "majetok celkom",
        "spolu majetok",
    ],
    "equity": [
        "vlastné imanie celkom",
        "vlastné imanie spolu",
    ],
    "liabilities_total": [
        "záväzky celkom",
        "cudzie zdroje celkom",
    ],
}

# Lines that look like totals — these are preferred when multiple matches exist
TOTAL_SUFFIXES = ("celkom", "spolu", "súčet")

# VÚ POD format detection keywords
VU_POD_MARKERS = (
    "výkaz vybraných údajov",
    "vú pod",
    "príloha k opatreniu",
)

IFRS_MARKERS = (
    "medzinárodnými štandardmi",
    "ifrs",
    "international financial reporting",
    "ias",
)


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().lower())


def _is_numeric_token(text: str) -> bool:
    cleaned = text.replace('-', '').replace('(', '').replace(')', '').replace(',', '').replace('.', '')
    return cleaned.isdigit() if cleaned else False


def _parse_number(tokens: List[str]) -> Optional[Decimal]:
    """Reconstruct a number from word tokens like ['-23', '959', '963'] → -23959963."""
    if not tokens:
        return None

    combined = ''.join(tokens)
    combined = combined.replace(' ', '')

    negative = False
    if combined.startswith('(') and combined.endswith(')'):
        negative = True
        combined = combined[1:-1]
    elif combined.startswith('-'):
        negative = True
        combined = combined.lstrip('-')
    elif combined.endswith('-'):
        negative = True
        combined = combined.rstrip('-')

    combined = combined.replace(',', '.').replace(' ', '')

    if not combined or combined in ('-', '.'):
        return None

    try:
        value = Decimal(combined)
        return -value if negative else value
    except (InvalidOperation, ValueError):
        return None


class PageLines:
    """Extract words from a page and group them into positioned lines."""

    def __init__(self, page):
        self.page_width = page.width
        words = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
        raw_lines = defaultdict(list)
        for w in words:
            y_key = round(w['top'])
            raw_lines[y_key].append(w)

        # Merge lines that are very close vertically (within 3px)
        self.lines: List[Tuple[float, List[dict]]] = []
        sorted_ys = sorted(raw_lines.keys())
        i = 0
        while i < len(sorted_ys):
            y = sorted_ys[i]
            merged = list(raw_lines[y])
            while i + 1 < len(sorted_ys) and sorted_ys[i + 1] - y <= 3:
                i += 1
                merged.extend(raw_lines[sorted_ys[i]])
            merged.sort(key=lambda w: w['x0'])
            self.lines.append((y, merged))
            i += 1

    def get_text(self) -> str:
        parts = []
        for _, words in self.lines:
            parts.append(' '.join(w['text'] for w in words))
        return '\n'.join(parts)


class ColumnDetector:
    """Detect column boundaries from header rows on financial pages."""

    def __init__(self, page_lines: PageLines):
        self.col1_start: Optional[float] = None
        self.col2_start: Optional[float] = None
        self.col_boundary: Optional[float] = None
        self._detect(page_lines)

    def _detect(self, page_lines: PageLines):
        for _, words in page_lines.lines:
            text = ' '.join(w['text'] for w in words).lower()
            # Look for period headers like "31.10.2024 31.10.2023" or "3/2021-2/2022 3/2020-2/2021"
            date_words = [w for w in words if re.search(r'\d{2}\.\d{2}\.\d{4}|\d{4}|\d/\d{4}', w['text'])]
            if len(date_words) >= 2:
                xs = sorted(set(round(w['x0']) for w in date_words))
                if len(xs) >= 2:
                    self.col1_start = xs[-2]
                    self.col2_start = xs[-1]
                    self.col_boundary = (self.col1_start + self.col2_start) / 2
                    return

            # Also look for column headers like "Bežné účtovné obdobie" and "predchádzajúce"
            if 'bežné' in text and 'predchádzajúce' in text:
                header_words = [w for w in words if any(
                    k in w['text'].lower() for k in ('bežné', 'predchádzajúce', 'obdobie')
                )]
                if len(header_words) >= 2:
                    xs = sorted(set(round(w['x0']) for w in header_words))
                    if len(xs) >= 2:
                        self.col1_start = xs[-2]
                        self.col2_start = xs[-1]
                        self.col_boundary = (self.col1_start + self.col2_start) / 2
                        return

    @property
    def detected(self) -> bool:
        return self.col_boundary is not None

    def assign_column(self, x: float) -> Optional[int]:
        """Returns 0 for current period, 1 for previous period, None if before both columns."""
        if self.col_boundary is None:
            return None
        if x >= self.col2_start - 10:
            return 1
        if x >= self.col1_start - 10:
            return 0
        return None


class FinancialPageExtractor:
    """Extract financial values from a single page with known column layout."""

    def __init__(self, page_lines: PageLines, columns: ColumnDetector, unit_multiplier: Decimal = Decimal(1)):
        self.page_lines = page_lines
        self.columns = columns
        self.unit_multiplier = unit_multiplier

    def extract_line_values(self, words: List[dict]) -> Tuple[str, Optional[Decimal], Optional[Decimal]]:
        """Split a line into label text and two column values."""
        if not self.columns.detected:
            return ' '.join(w['text'] for w in words), None, None

        label_parts = []
        col_tokens: Dict[int, List[str]] = {0: [], 1: []}

        for w in words:
            col = self.columns.assign_column(w['x0'])
            if col is not None and _is_numeric_token(w['text']):
                col_tokens[col].append(w['text'])
            elif col is None:
                label_parts.append(w['text'])

        label = ' '.join(label_parts).strip()
        # Remove note references (single numbers 1-99 at end of label)
        label = re.sub(r'\s+\d{1,2}(,\d{1,2})*\s*$', '', label)
        label = re.sub(r'\s+\d{1,2}[a-zA-Z]?\)?\s*$', '', label)

        val_current = _parse_number(col_tokens[0])
        val_previous = _parse_number(col_tokens[1])

        if val_current is not None:
            val_current *= self.unit_multiplier
        if val_previous is not None:
            val_previous *= self.unit_multiplier

        return label, val_current, val_previous

    def extract_all(self) -> List[Tuple[str, Optional[Decimal], Optional[Decimal]]]:
        results = []
        for _, words in self.page_lines.lines:
            label, val_cur, val_prev = self.extract_line_values(words)
            if label and (val_cur is not None or val_prev is not None):
                results.append((label, val_cur, val_prev))
        return results


def _detect_unit_multiplier(text: str) -> Decimal:
    """Detect if values are in thousands or millions from page text."""
    lower = text.lower()
    if 'v tis.' in lower or 'tisícoch eur' in lower or 'tis. eur' in lower:
        return Decimal(1000)
    if 'miliónoch eur' in lower or 'v miliónoch' in lower:
        return Decimal(1000000)
    return Decimal(1)


def _match_keyword(label: str, keywords: List[str]) -> bool:
    """Check if a label matches any of the keywords (case-insensitive substring match)."""
    label_lower = _normalize(label)
    for kw in keywords:
        kw_lower = _normalize(kw)
        if kw_lower in label_lower:
            return True
    return False


def _is_total_line(label: str) -> bool:
    label_lower = _normalize(label)
    return any(label_lower.endswith(s) for s in TOTAL_SUFFIXES) or any(s in label_lower for s in TOTAL_SUFFIXES)


def _pick_better(current: Optional[Decimal], candidate: Optional[Decimal]) -> Optional[Decimal]:
    if candidate is None:
        return current
    if current is None:
        return candidate
    if abs(candidate) > abs(current):
        return candidate
    return current


def _detect_format(full_text: str) -> str:
    lower = full_text.lower()
    for marker in VU_POD_MARKERS:
        if marker in lower:
            return 'vu_pod'
    for marker in IFRS_MARKERS:
        if marker in lower:
            return 'ifrs'
    return 'unknown'


def _find_financial_pages(pdf) -> Tuple[List[int], List[int]]:
    """Find pages containing P&L and balance sheet data."""
    pl_pages = []
    bs_pages = []

    pl_markers = [
        'výkaz ziskov a strát',
        'výkaz komplexného výsledku',
        'výkaz o finančnej situácii',  # Some use this for P&L section header
        'prehľad o vybraných nákladoch a výnosoch',
        'výnosy z prevádzkovej činnosti',
        'tržby celkom',
    ]
    bs_markers = [
        'výkaz finančnej pozície',
        'finančná pozícia',
        'prehľad o štruktúre majetku',
        'aktíva celkom',
        'majetok celkom',
        'strana aktív',
    ]

    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ''
        lower = text.lower()

        is_pl = any(m in lower for m in pl_markers) and any(
            k in lower for k in ('tržby', 'výnosy', 'zisk', 'strata', 'náklady')
        )
        is_bs = any(m in lower for m in bs_markers) and any(
            k in lower for k in ('majetok', 'aktíva', 'vlastné imanie', 'záväzky')
        )

        if is_pl:
            pl_pages.append(i)
        if is_bs:
            bs_pages.append(i)

    return pl_pages, bs_pages


def _extract_pl_from_page(page, unit_multiplier: Decimal) -> Dict[str, Optional[Decimal]]:
    """Extract P&L fields from a single page. Returns dict of field→value."""
    page_text = page.extract_text() or ''
    page_unit = _detect_unit_multiplier(page_text)
    if page_unit == Decimal(1):
        page_unit = unit_multiplier

    page_lines = PageLines(page)
    columns = ColumnDetector(page_lines)
    if not columns.detected:
        return {}

    extractor = FinancialPageExtractor(page_lines, columns, page_unit)
    lines = extractor.extract_all()

    result: Dict[str, Optional[Decimal]] = {}
    last_profit: Optional[Decimal] = None

    for label, val_cur, val_prev in lines:
        label_lower = _normalize(label)

        # Handle standalone "Výnosy" line (top-level revenue in IFRS P&L)
        if label_lower.strip() == _normalize(STANDALONE_REVENUE_LABEL) and val_cur is not None:
            if result.get('revenue') is None:
                result['revenue'] = val_cur
            result['total_revenue'] = _pick_better(result.get('total_revenue'), val_cur)
            continue

        for field, keywords in PL_KEYWORDS.items():
            if not _match_keyword(label, keywords):
                continue

            if field == 'profit':
                # For profit, always take the LAST matching line on the page
                # (bottom-line figure appears after sub-totals)
                if val_cur is not None:
                    last_profit = val_cur
            else:
                result[field] = _pick_better(result.get(field), val_cur)
            break

    if last_profit is not None:
        result['profit'] = last_profit

    return result


def _extract_bs_from_page(page, unit_multiplier: Decimal) -> Dict[str, Optional[Decimal]]:
    """Extract balance sheet fields from a single page."""
    page_text = page.extract_text() or ''
    page_unit = _detect_unit_multiplier(page_text)
    if page_unit == Decimal(1):
        page_unit = unit_multiplier

    page_lines = PageLines(page)
    columns = ColumnDetector(page_lines)
    if not columns.detected:
        return {}

    extractor = FinancialPageExtractor(page_lines, columns, page_unit)
    lines = extractor.extract_all()

    result: Dict[str, Optional[Decimal]] = {}

    for label, val_cur, val_prev in lines:
        label_lower = _normalize(label)

        # "Vlastné imanie a záväzky celkom" is a check figure, not liabilities
        if 'imanie' in label_lower and 'záväzky' in label_lower:
            continue

        for field, keywords in BS_KEYWORDS.items():
            if not _match_keyword(label, keywords):
                continue
            is_total = _is_total_line(label)
            existing = result.get(field)
            if existing is not None and not is_total:
                continue
            result[field] = _pick_better(existing, val_cur)
            break

    return result


def _is_valid_bs_extraction(data: Dict[str, Optional[Decimal]]) -> bool:
    """Check if a BS extraction looks valid (has main totals, values are consistent)."""
    at = data.get('assets_total')
    eq = data.get('equity')
    lt = data.get('liabilities_total')
    if at is None:
        return False
    # Must have at least equity or liabilities
    if eq is None and lt is None:
        return False
    # Sanity: assets should roughly equal equity + liabilities (within 5%)
    if eq is not None and lt is not None:
        expected = eq + lt
        if expected != Decimal(0) and abs((at - expected) / expected) > Decimal('0.05'):
            return False
    return True


def parse_ifrs_pdf(pdf_bytes: bytes) -> Dict[str, Optional[Decimal]]:
    """Parse an IFRS PDF and extract financial data."""
    result: Dict[str, Optional[Decimal]] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            return result

        header_text = '\n'.join(
            (pdf.pages[i].extract_text() or '') for i in range(min(3, len(pdf.pages)))
        )
        fmt = _detect_format(header_text)
        unit_multiplier = _detect_unit_multiplier(header_text)

        logger.info("PDF format detected: %s, unit multiplier: %s", fmt, unit_multiplier)

        pl_pages, bs_pages = _find_financial_pages(pdf)
        if not pl_pages and not bs_pages:
            logger.warning("No financial pages found in PDF (%d pages total)", len(pdf.pages))
            return result

        # P&L: try pages in order, stop after first successful extraction
        for pg_idx in pl_pages:
            extracted = _extract_pl_from_page(pdf.pages[pg_idx], unit_multiplier)
            if extracted.get('revenue') is not None or extracted.get('profit') is not None:
                for k, v in extracted.items():
                    if v is not None:
                        result[k] = v
                logger.info("P&L extracted from page %d: revenue=%s, profit=%s",
                            pg_idx + 1, result.get('revenue'), result.get('profit'))
                break

        # Balance sheet: try pages in order, stop after first valid extraction
        for pg_idx in bs_pages:
            extracted = _extract_bs_from_page(pdf.pages[pg_idx], unit_multiplier)
            if _is_valid_bs_extraction(extracted):
                for k, v in extracted.items():
                    if v is not None:
                        result[k] = v
                logger.info("BS extracted from page %d: assets=%s, equity=%s, liabilities=%s",
                            pg_idx + 1, result.get('assets_total'), result.get('equity'), result.get('liabilities_total'))
                break

    if result.get('profit') is None and result.get('revenue') is not None and result.get('costs') is not None:
        result['profit'] = result['revenue'] - result['costs']

    return result


def download_attachment(attachment_id: int, session=None) -> Optional[bytes]:
    """Download a PDF attachment from RUZ."""
    url = ATTACHMENT_URL.format(id=attachment_id)
    sess = session or build_retry_session(
        headers={"User-Agent": "CistaFirma SK App / 1.0"},
        total_retries=3,
        backoff_factor=0.5,
    )
    try:
        resp = sess.get(url, timeout=60)
        resp.raise_for_status()
        if resp.headers.get('content-type', '').startswith('application/pdf') or len(resp.content) > 1000:
            return resp.content
        logger.warning("Attachment %d: unexpected content type %s", attachment_id, resp.headers.get('content-type'))
        return None
    except requests.exceptions.RequestException as e:
        logger.error("Failed to download attachment %d: %s", attachment_id, e)
        return None


def extract_financials_from_attachments(
    report_attachments: List[Dict],
    session=None,
) -> Dict[str, Optional[Decimal]]:
    """
    Try to extract financials from PDF attachments of a report.

    Prefers IFRS/accounting statement PDFs over VÚ POD summary forms.
    Returns a dict of financial field values.
    """
    result: Dict[str, Optional[Decimal]] = {}

    # Sort attachments: prefer IFRS statements, then VÚ POD, skip non-PDFs
    pdfs = [a for a in report_attachments if (a.get('mimeType') or '').startswith('application/pdf')]
    if not pdfs:
        return result

    # Prioritize by filename — IFRS statements tend to have more data
    def sort_key(a):
        name = (a.get('meno') or '').lower()
        if 'ifrs' in name or 'účtovná závierka' in name:
            return 0
        if 'vú' in name or 'vybrané údaje' in name or 'pod' in name:
            return 1
        return 2

    pdfs.sort(key=sort_key)

    for attachment in pdfs:
        att_id = attachment.get('id')
        if not att_id:
            continue

        logger.info("Downloading attachment %d (%s, %.0f KB)",
                     att_id, attachment.get('meno', '?'), (attachment.get('velkostPrilohy', 0) or 0) / 1024)

        # Skip very large files (>20MB) to avoid memory issues
        if (attachment.get('velkostPrilohy') or 0) > 20 * 1024 * 1024:
            logger.warning("Attachment %d too large (%d bytes), skipping", att_id, attachment.get('velkostPrilohy'))
            continue

        pdf_bytes = download_attachment(att_id, session)
        if not pdf_bytes:
            continue

        try:
            parsed = parse_ifrs_pdf(pdf_bytes)
            if parsed:
                for field, value in parsed.items():
                    if value is not None:
                        result[field] = _pick_better(result.get(field), value)

                # If we got the main fields, no need to process more attachments
                if result.get('revenue') is not None and result.get('assets_total') is not None:
                    break
        except Exception as e:
            logger.error("Error parsing PDF attachment %d: %s", att_id, e, exc_info=True)

    return result
