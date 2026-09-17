"""Make the 0018 note mean what it says: a marker, not a stale reason.

Migration 0018 wrote a Slovak note into `last_detail` on the 147 ORSR rows it
seeded, and its reverse deletes by that note. The note was meant to explain
where the row came from, and its docstring argued it "stays true after a
re-ask, so a row that has since been classified keeps a note that is history
rather than a claim about its last attempt".

That argument does not survive the screen it lands on. `frontend/admin/pages/
SyncStatus.tsx` renders `last_detail` in a `ReasonCell` next to `last_error` as
"the reason a company is where it is", and ORSR's own writer never wrote the
column -- so the note kept the slot a reason should occupy. Measured on dell
2026-09-15: of the 147 marked rows, **125** had since been classified
`not_in_register` by a real attempt, and every one of them still carried
"zaradené do fronty migráciou 0018…" as the sentence under its verdict.

The code now clears the column on every ORSR attempt (`record_orsr_outcome`
passes `detail=""`), which stops the class recurring. This repairs the rows that
were already classified before that, and it clears them by a predicate worth
stating exactly: the complement of the reverse's own.

    0018's reverse deletes where  last_error_type="" AND last_succeeded_at IS NULL
                                  AND consecutive_failures=1

Those three are the shape the seed wrote, and any attempt since moves at least
one of them -- a failure classifies `last_error_type` and increments
`consecutive_failures`, a success sets `last_succeeded_at` and zeroes the count.
So `NOT (those three)` is precisely "something has happened to this row since
0018 seeded it", and clearing the note on exactly those rows leaves the marker
on precisely the rows 0018 added and nothing has touched.

That is the point rather than a side effect: afterwards the note is no longer a
claim about a last attempt anywhere, it is a marker, and 0018's reverse becomes
exact -- it can only see the rows it actually created. Before this, 125 rows
that a rollback would have deleted were being spared by those same three
conditions; the two readings of one predicate now agree instead of being relied
on separately.

There is no reverse, and that is deliberate. Undoing this would mean re-writing
a false reason onto rows that have a real one -- and no predicate can tell a row
this migration cleared from a row a later attempt legitimately left without a
sentence, because after this migration both are `last_detail=""`. A reverse that
guesses would put the lie back; `noop` is the honest half of the pair.
"""

from django.db import migrations

# Byte-for-byte the constant from 0018. Duplicated rather than imported: a
# migration that reads another migration's module would change meaning the day
# that file is edited, and the whole value of this one is that it matches the
# `last_detail` strings already in the database.
SEED_DETAIL = (
    "zaradené do fronty migráciou 0018: profil fetch_ok=False vznikol skôr, "
    "než mal ORSR stavový riadok, takže firma nebola v žiadnej fronte na "
    "opakovanie (#126)"
)


def clear_stale_seed_detail(apps, schema_editor):
    CompanySyncStatus = apps.get_model("registers", "CompanySyncStatus")
    cleared = (
        CompanySyncStatus.objects.filter(source="orsr", last_detail=SEED_DETAIL)
        .exclude(
            last_error_type="",
            last_succeeded_at__isnull=True,
            consecutive_failures=1,
        )
        .update(last_detail="")
    )
    if cleared:
        print(f"    0019: cleared a stale seed note from {cleared} ORSR row(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("registers", "0018_seed_orsr_status_for_failed_profiles"),
    ]

    operations = [
        migrations.RunPython(clear_stale_seed_detail, migrations.RunPython.noop),
    ]
