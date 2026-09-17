"""A company's účtovné závierky, served from this site rather than linked out.

The "Účtovné závierky" section could say how many statements RUZ holds and which
years we read, and then, for the document itself, it could only send the reader
to registeruz.sk. That link was also **wrong** -- it pointed at a route the
register's own front end rejects -- so the one thing the section offered did
not work. This module is the correction: the documents are fetched here.

**RUZ does publish them; the earlier note that no endpoint fetches a statement's
attachment was simply out of date.** Its API documentation names both routes,
and says why they sit outside `/api` ("Prílohy výkazov sú sprístupňované mimo
API cez URL zhodnú so samotnou web aplikáciou"):

* ``/domain/financialreport/pdf/<id-vykazu>`` -- the generated PDF of one
  `účtovný výkaz`, which the documentation says is the same data as the JSON
  detail, rendered.
* ``/domain/financialreport/attachment/<id-prilohy>`` -- one filed attachment:
  the auditor's report, the annual report, the signed PDF, an IFRS statement.

The anchor is the **statement** (`účtovná závierka`), not the výkaz, because one
statement holds a list of them (súvaha, výkaz ziskov a strát, poznámky) and
which one carried a given figure is a property of a parser run rather than of
the year. `CompanyFinancialResult.ruz_statement_id` records it, written for free
during the sync because the sync already had it in hand. Rows stored before that
field existed carry `NULL`, and `_resolve_statement_id` fills those in on the
first download and caches the answer, so an un-backfilled row costs one round of
requests **once** rather than on every view.

Deliberately synchronous and on demand rather than pre-fetched into the
database: a závierka is a document, not a datum, and 445 626 companies' worth of
them is a file store this project has not decided to run. Nothing here writes a
document to disk; the bytes go from RUZ to the reader's browser through this
process, and are never held.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from registers.integrations.ruz_api import RuzApi, RuzUnreachable
from registers.services.ruz_financials_sync import statement_year

logger = logging.getLogger(__name__)

#: A generated PDF of one `účtovný výkaz`.
KIND_VYKAZ = 'vykaz'
#: One filed attachment of a výkaz (auditor's report, annual report, …).
KIND_PRILOHA = 'priloha'

#: Documents were listed. The list may still be empty -- RUZ answered, and its
#: answer was that there is nothing to download for this year.
STATE_LISTED = 'listed'
#: RUZ could not be read. **Not** the same as an empty list, and never rendered
#: as "no documents": we do not know, and saying zero would be inventing it.
STATE_UNREACHABLE = 'unreachable'
#: We hold no statement for that year, so there is nothing to look up. This is
#: about *our* records, not about the register.
STATE_NO_STATEMENT = 'no_statement'

#: How many of a company's statements to walk when looking for one year.
#:
#: Only reached for rows written before `ruz_statement_id` existed. The walk is
#: one request per statement, so it is bounded rather than unbounded -- a company
#: with a pathological statement list must not turn one click into a minute of
#: requests. Statements past this many are not searched and the answer is
#: reported as unknown rather than as absent.
MAX_STATEMENT_PROBES = 15


@dataclass(frozen=True)
class RuzDocument:
    """One downloadable document, described well enough to render a row.

    `id` is this module's own handle (`'vykaz-7812758'`), not a RUZ URL. The
    download path is built by the view, which is the only layer that knows the
    company's IČO -- and keeping the register's addresses out of the payload is
    deliberate, because the point of the section is that the file arrives from
    this site.
    """

    id: str
    kind: str
    name: str
    mime_type: Optional[str] = None
    size: Optional[int] = None
    pages: Optional[int] = None


@dataclass(frozen=True)
class DocumentListing:
    """What can be downloaded for one company-year, and how sure we are."""

    year: int
    state: str
    documents: tuple[RuzDocument, ...] = ()
    detail: Optional[str] = None

    @property
    def is_listed(self) -> bool:
        return self.state == STATE_LISTED


def _client(api: Optional[RuzApi]) -> RuzApi:
    """A client that distinguishes an unreachable register from an empty one.

    Strict on purpose. The permissive default answers `None` for both "RUZ has
    no such document" and "RUZ could not be reached", and a download page that
    rendered the second as the first would be the same substitution this project
    keeps finding and removing elsewhere.
    """
    return api or RuzApi(raise_on_transport_error=True)


def _statement_ids(company) -> list[int]:
    """Every závierka id we hold for the company, as plain ints.

    `Company.id_uctovnych_zavierok` is a JSONField, so its elements have been
    through JSON round-trips and are not guaranteed to be `int` -- normalising
    here keeps a `"123"` from silently failing an `==` against an int id.
    """
    raw: Iterable = company.id_uctovnych_zavierok or []
    out = []
    for value in raw:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


def _resolve_statement_id(company, year: int, api: RuzApi) -> Optional[int]:
    """Which závierka this company's `year` came from.

    Read from the stored row when it is there -- which after the `PARSER_REVISION
    = 2` backfill is the ordinary case -- and otherwise found by asking RUZ which
    of the company's statements covers that year.

    The match uses `statement_year`, the same function the financials sync uses
    to decide which year a statement *is*. A second, similar rule here would be
    worse than no rule: it could send a reader to a different filing than the
    figures on the page were read from, and nothing on screen would show it.
    """
    from companies.models import CompanyFinancialResult

    row = company.financial_results.filter(year=year).first()
    if row is None:
        return None
    if row.ruz_statement_id:
        return row.ruz_statement_id

    for statement_id in _statement_ids(company)[:MAX_STATEMENT_PROBES]:
        statement = api.get_financial_statement_details(statement_id)
        if not statement:
            continue
        if statement_year(statement) != year:
            continue

        # Cached through `update()` rather than `save()`: `updated_at` is
        # `auto_now`, and it is the field this project reads as a row's vintage.
        # Bumping it to record a lookup would claim the figures had been re-read
        # when nothing about them changed.
        CompanyFinancialResult.objects.filter(pk=row.pk).update(
            ruz_statement_id=statement_id
        )
        return statement_id

    return None


def _documents_for_statement(statement_id: int, api: RuzApi) -> list[RuzDocument]:
    """Every downloadable document under one závierka.

    One `uctovna-zavierka` call for the výkaz ids, then one `uctovny-vykaz` call
    per výkaz for its attachments. Typically a single výkaz, so typically two
    requests -- and the second is what carries the attachment names, sizes and
    page counts, which is what makes the list worth showing rather than a row of
    anonymous links.
    """
    statement = api.get_financial_statement_details(statement_id)
    if not statement:
        return []

    year = statement_year(statement)
    documents: list[RuzDocument] = []

    for report_id in statement.get('idUctovnychVykazov') or []:
        try:
            report_id = int(report_id)
        except (TypeError, ValueError):
            continue

        documents.append(
            RuzDocument(
                id=f'{KIND_VYKAZ}-{report_id}',
                kind=KIND_VYKAZ,
                name=(
                    f'Účtovný výkaz {year}' if year else 'Účtovný výkaz'
                ),
                mime_type='application/pdf',
            )
        )

        report = api.get_financial_report_details(report_id)
        if not report:
            continue
        for attachment in report.get('prilohy') or []:
            try:
                attachment_id = int(attachment.get('id'))
            except (TypeError, ValueError):
                continue
            documents.append(
                RuzDocument(
                    id=f'{KIND_PRILOHA}-{attachment_id}',
                    kind=KIND_PRILOHA,
                    name=attachment.get('meno') or f'Príloha {attachment_id}',
                    mime_type=attachment.get('mimeType'),
                    size=attachment.get('velkostPrilohy'),
                    pages=attachment.get('pocetStran'),
                )
            )

    return documents


def list_documents(company, year: int, *, api: Optional[RuzApi] = None) -> DocumentListing:
    """What can be downloaded for one company and one year.

    Four outcomes, kept apart on purpose:

    * `listed` with documents -- there is something to download.
    * `listed` with none -- RUZ answered, and it holds no document we can fetch
      for that year. RUZ does have years whose výkaz carries neither a
      structured body nor an attachment.
    * `no_statement` -- we have no filing tied to that year in our own records,
      so there is nothing to look up. A statement about us, not about RUZ.
    * `unreachable` -- the register could not be read, so we do not know.

    Only the first is a promise that a download will work.
    """
    client = _client(api)
    try:
        statement_id = _resolve_statement_id(company, year, client)
        if statement_id is None:
            return DocumentListing(year=year, state=STATE_NO_STATEMENT)

        documents = _documents_for_statement(statement_id, client)
        return DocumentListing(year=year, state=STATE_LISTED, documents=tuple(documents))
    except RuzUnreachable as exc:
        logger.warning(
            'RUZ documents unreachable for company %s year %s: %s', company.ico, year, exc
        )
        return DocumentListing(year=year, state=STATE_UNREACHABLE, detail=str(exc))


def parse_document_id(document_id: str) -> Optional[tuple[str, int]]:
    """`'priloha-8736666'` -> `('priloha', 8736666)`, or `None` if malformed.

    The round trip through a string is what keeps the browser from naming a
    document kind or an arbitrary register path: a caller can only ask for an id
    this module produced.
    """
    kind, _, raw = document_id.partition('-')
    if kind not in (KIND_VYKAZ, KIND_PRILOHA) or not raw.isdigit():
        return None
    return kind, int(raw)


@dataclass(frozen=True)
class OpenedDocument:
    """A document opened for streaming, together with the row it was listed as.

    The listing row travels back with the response rather than being looked up
    again by the caller: the name to save the file under is a property of the
    listing, and re-deriving the listing to get it would double every download's
    requests against the register for a string we already had in hand.
    """

    response: object
    document: RuzDocument


def open_document(
    company, year: int, document_id: str, *, api: Optional[RuzApi] = None
) -> Optional[OpenedDocument]:
    """Open one document for streaming, or `None` if it is not one we may serve.

    **`None` is the security boundary, not an error path.** A download endpoint
    keyed by an id from the query string is an open proxy onto the register
    unless it checks that the id is one this company and year actually have, so
    that check is what this function is. The listing is re-derived here rather
    than trusted from the client, which costs the requests again and is the
    price of not being a proxy.

    The caller owns `response` and must close it; see `RuzApi.fetch_document`.
    """
    parsed = parse_document_id(document_id)
    if parsed is None:
        return None
    kind, ruz_id = parsed

    listing = list_documents(company, year, api=api)
    if listing.state == STATE_UNREACHABLE:
        # Raised rather than returned as `None`. `None` means "this company and
        # year do not have that document", and a register we could not read is
        # not that -- answering `None` here would have the view render a 404,
        # which tells the reader the filing does not exist when the truth is
        # that we do not know. The caller turns this into a 503.
        raise RuzUnreachable(listing.detail or 'RUZ unreachable')
    if not listing.is_listed:
        return None

    listed = next(
        (document for document in listing.documents if document.id == document_id),
        None,
    )
    if listed is None:
        return None

    path = 'pdf' if kind == KIND_VYKAZ else 'attachment'
    response = _client(api).fetch_document(path, ruz_id)
    if response is None:
        return None
    return OpenedDocument(response=response, document=listed)
