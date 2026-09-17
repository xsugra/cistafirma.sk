"""Put the failed ORSR profiles that predate the status writer back in the queue.

`OrsrCompanyProfile.fetch_ok=False` takes a company out of ORSR's "new ground"
(`orsr_profile__isnull=True`) for good, so the only way back to it is a
`CompanySyncStatus(source='orsr')` row with an elapsed `next_retry_at` -- the
retry lane `rotating_batch` reads. An attempt writes that row, which means the
lane cannot have a hole in it from now on.

It has one from before. Migration 0008 seeded a status row per profile that
existed at the time; profiles written *after* it, by attempts from the era when
nothing wrote a status row, have neither. Measured on dell 2026-09-15: of the
27 311 ORSR profiles, 249 carry `fetch_ok=False`, and 147 of those 249 have no
status row at all -- in no lane, unretryable, invisible to `source_health`, each
one holding a generic `OrsrScraperError: ... sa nepodarilo získať` from an
attempt between 2026-08-24 and 2026-09-11.

The 147 cannot be classified from the record, and that is the point of the
seed: their `last_error` is one generic sentence, so nothing stored can say
whether the register holds no such IČO (`not_in_register`, a month between
asks) or whether the attempt failed at the transport (`network`, backoff). The
only honest way to find out is to ask the register once more, so the row is
written unclassified with `next_retry_at = now` and the next attempt decides.

`last_error_type` is therefore `""` and not `"unknown"`. `unknown` is a verdict
-- this attempt failed and we could not say why -- and no attempt is being
claimed here. An empty type is what the column holds before anything has
answered, which is exactly the state of these companies.

The value written to `last_detail` explains where the row came from to whoever
reads the admin list later, and doubles as the marker the reverse deletes by.
It stays true after a re-ask, so a row that has since been classified keeps a
note that is history rather than a claim about its last attempt.

This is a one-off repair and not a third population in `rotating_batch`: the
current code always writes a status row, so the gap cannot recur, and adding a
permanent branch for a set that can only shrink would be paying for it every
batch for ever.

Cost of draining it is bounded by the lane it enters. `schedule_missing_orsr_sync`
dispatches `rotating_batch(limit=500)`, whose retry budget is `500 / RETRY_SHARE`
= 125 per batch, six batches a day -- so these 147 are re-asked inside the
queue's ordinary capacity, not as a spike.
"""

from django.db import migrations
from django.utils import timezone

# Written to `last_detail` on every row this migration creates, and the only
# thing the reverse deletes by. Slovak, because it is read in the admin UI.
SEED_DETAIL = (
    "zaradené do fronty migráciou 0018: profil fetch_ok=False vznikol skôr, "
    "než mal ORSR stavový riadok, takže firma nebola v žiadnej fronte na "
    "opakovanie (#126)"
)


def seed_status_for_failed_profiles(apps, schema_editor):
    CompanySyncStatus = apps.get_model("registers", "CompanySyncStatus")
    OrsrCompanyProfile = apps.get_model("registers", "OrsrCompanyProfile")

    now = timezone.now()
    already_recorded = set(
        CompanySyncStatus.objects.filter(source="orsr").values_list(
            "company_id", flat=True
        )
    )

    bulk = []
    for profile in (
        OrsrCompanyProfile.objects.filter(fetch_ok=False)
        .only("company_id", "last_error", "last_synced_at")
        .iterator(chunk_size=2000)
    ):
        if profile.company_id in already_recorded:
            continue
        bulk.append(
            CompanySyncStatus(
                company_id=profile.company_id,
                source="orsr",
                last_attempted_at=profile.last_synced_at,
                last_succeeded_at=None,
                last_error=(profile.last_error or "")[:4000],
                last_error_type="",
                last_detail=SEED_DETAIL,
                consecutive_failures=1,
                # Due immediately: the re-ask is the whole purpose of the row.
                next_retry_at=now,
                is_blocked=False,
            )
        )
        if len(bulk) >= 1000:
            CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)
            bulk = []
    if bulk:
        CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)


def unseed_status_for_failed_profiles(apps, schema_editor):
    """Delete only the rows this migration created and nothing has touched since.

    A row that has been re-asked no longer looks like a seed row: an attempt
    either increments `consecutive_failures` to 2 or resets it to 0 and sets
    `last_succeeded_at`. Anything an operator has edited since -- a block, a
    manual retry -- moves it out of that shape too. Those rows are left alone,
    which is the only safe reading of a reverse: this migration removes what it
    added, not what happened afterwards.
    """
    CompanySyncStatus = apps.get_model("registers", "CompanySyncStatus")
    CompanySyncStatus.objects.filter(
        source="orsr",
        last_detail=SEED_DETAIL,
        last_error_type="",
        last_succeeded_at__isnull=True,
        consecutive_failures=1,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("registers", "0017_alter_companysyncstatus_last_error_type"),
    ]

    operations = [
        migrations.RunPython(
            seed_status_for_failed_profiles,
            unseed_status_for_failed_profiles,
        ),
    ]
