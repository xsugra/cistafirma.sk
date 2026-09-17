"""The IČO shapes the register uses and our pipeline could not hold.

Two failure modes, one cause -- treating IČO as a fixed eight-character digit
string. Both are repairs against a database that cannot be recreated, so the
tests here are as much about what the command refuses to do as about what it
does.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from companies.models import Company
from registers.models import IndividualEntity, OrsrCompanyProfile


class RepairIcoStripTests(TestCase):
    """`'177474  '` is a company we hold and cannot find by its own IČO.

    Every lookup path does `.strip().zfill(8)`, so a stored padded value never
    matches: the register answers the IČO, the database holds the row, and the
    reader is told the company does not exist.
    """

    def _run(self, *args):
        out = StringIO()
        call_command("repair_ico_shape", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_a_padded_ico_is_stripped(self):
        company = Company.objects.create(
            ruz_id=1825863, ico="177474  ", nazov_UJ="DHZ Sološnica"
        )

        out = self._run()

        company.refresh_from_db()
        self.assertEqual(company.ico, "177474")
        self.assertIn("177474", out)

    def test_a_dry_run_reports_and_writes_nothing(self):
        """The only honest way to repair a database that cannot be recreated is
        to be able to see what it would do first."""
        company = Company.objects.create(
            ruz_id=1825863, ico="177474  ", nazov_UJ="DHZ Sološnica"
        )

        out = self._run("--dry-run")

        company.refresh_from_db()
        self.assertEqual(company.ico, "177474  ")
        self.assertIn("would be stripped", out)

    def test_a_conflict_is_reported_and_skipped_rather_than_crashing(self):
        """`Company.ico` is `unique`, so stripping only succeeds while no other
        row holds the stripped value. Checked *before* writing rather than
        caught afterwards: a conflict has to be a named row, not a traceback
        halfway through a repair.

        The other row is left alone. `'177474'` and `'177474  '` may well be two
        different organisational units -- the register does answer one IČO with
        more than one entity -- so silently merging them would destroy one.
        """
        holder = Company.objects.create(
            ruz_id=1677, ico="177474", nazov_UJ="DHZ Nová Kelča"
        )
        padded = Company.objects.create(
            ruz_id=1825863, ico="177474  ", nazov_UJ="DHZ Sološnica"
        )

        out = self._run()

        holder.refresh_from_db()
        padded.refresh_from_db()
        self.assertEqual(holder.ico, "177474")
        self.assertEqual(padded.ico, "177474  ")
        self.assertIn("skipped", out)

    def test_a_conflict_does_not_stop_the_other_rows(self):
        """One unrepairable row must not cost the rest of the pass -- the same
        rule the walk follows for an unstorable record."""
        Company.objects.create(ruz_id=1677, ico="177474", nazov_UJ="DHZ Nová Kelča")
        Company.objects.create(ruz_id=1825863, ico="177474  ", nazov_UJ="DHZ Sološnica")
        clean = Company.objects.create(
            ruz_id=1680728, ico="9155139 ", nazov_UJ="Fecenková Miroslava"
        )

        self._run()

        clean.refresh_from_db()
        self.assertEqual(clean.ico, "9155139")

    def test_a_value_with_no_whitespace_is_left_alone(self):
        company = Company.objects.create(
            ruz_id=48097781, ico="48097781", nazov_UJ="ECKLIMA"
        )

        out = self._run()

        company.refresh_from_db()
        self.assertEqual(company.ico, "48097781")
        self.assertIn("No stored IČO carries whitespace.", out)

    def test_it_covers_all_three_ico_columns(self):
        """The widening was applied to three columns because a width that
        differs between two tables holding the same field is the asymmetry that
        surfaces as a `DataError` on the rarer one. The repair has to match.
        """
        company = Company.objects.create(ruz_id=1, ico="90000001", nazov_UJ="A")
        individual = IndividualEntity.objects.create(
            ruz_id=2, ico="90000002 ", nazov_UJ="B"
        )
        profile = OrsrCompanyProfile.objects.create(
            company=company, ico="90000003 ", obchodne_meno="C"
        )

        self._run()

        individual.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(individual.ico, "90000002")
        self.assertEqual(profile.ico, "90000003")

    def test_a_profile_ico_is_stripped_even_when_the_value_is_taken(self):
        """`OrsrCompanyProfile.ico` is not unique -- the row is keyed by its
        `company` OneToOne, and the column is a search aid rather than an
        identity. A duplicate there is normal and must not be reported as a
        conflict.
        """
        first = Company.objects.create(ruz_id=1, ico="90000001", nazov_UJ="A")
        second = Company.objects.create(ruz_id=2, ico="90000002", nazov_UJ="B")
        OrsrCompanyProfile.objects.create(company=first, ico="90000001")
        profile = OrsrCompanyProfile.objects.create(company=second, ico="90000001 ")

        self._run()

        profile.refresh_from_db()
        self.assertEqual(profile.ico, "90000001")


class _StubRuzApi:
    """A register that answers one id, and knows nothing about the network."""

    def __init__(self, details):
        self._details = details
        self.asked = []

    def get_company_details(self, ruz_id):
        self.asked.append(ruz_id)
        return self._details.get(ruz_id)


class RepairIcoReimportTests(TestCase):
    """The half that no query can find: a record the walk could not store.

    Those ids are not enumerable from the database -- the run that skipped them
    predates the code that records them in `SyncProgress.notes` -- so the only
    way to name one is from the worker log: `--ruz-id 1520199`.
    """

    def _run(self, api, *args):
        out = StringIO()
        with patch(
            "registers.management.commands.repair_ico_shape.RuzApi",
            return_value=api,
        ):
            call_command("repair_ico_shape", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_a_named_ruz_id_is_read_and_stored(self):
        """The twelve-character organisational-unit IČO, which is the record
        `varchar(8)` refused. Stored through the walk's own mapping rather than
        a second copy of it, so the row is what the walk would have written.
        """
        api = _StubRuzApi({
            1520199: {
                "ico": "001781521576",
                "id": 1520199,
                "nazovUJ": "SZZ Základná organizácia 43-1",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        })

        out = self._run(api, "--ruz-id", "1520199")

        company = Company.objects.get(ruz_id=1520199)
        self.assertEqual(company.ico, "001781521576")
        self.assertEqual(api.asked, [1520199])
        self.assertIn("created", out)

    def test_a_reimport_is_idempotent(self):
        """Re-running it must update the same row, not create a second one under
        the same `ruz_id` -- the repair is meant to be safe to repeat while
        someone works out which ids were skipped."""
        api = _StubRuzApi({
            1520199: {
                "ico": "001781521576",
                "id": 1520199,
                "nazovUJ": "SZZ Základná organizácia 43-1",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        })

        self._run(api, "--ruz-id", "1520199")
        self._run(api, "--ruz-id", "1520199")

        self.assertEqual(Company.objects.filter(ruz_id=1520199).count(), 1)

    def test_a_dry_run_does_not_call_the_register(self):
        """A dry run that reaches the network is not a dry run: it would be the
        one operation nobody can undo by not repeating it."""
        api = _StubRuzApi({})

        out = self._run(api, "--ruz-id", "1520199", "--dry-run")

        self.assertEqual(api.asked, [])
        self.assertFalse(Company.objects.filter(ruz_id=1520199).exists())
        self.assertIn("Would re-read", out)

    def test_an_id_the_register_does_not_know_fails_loudly(self):
        """Silence here would read as a successful repair -- the record would
        simply not be there, and nothing would say why."""
        api = _StubRuzApi({})

        with self.assertRaises(CommandError):
            self._run(api, "--ruz-id", "999999999")

    def test_a_collision_on_reimport_is_reported_not_forced(self):
        """Re-reading a skipped record can land on an IČO another row now holds.
        That is exactly the collision the walk files as `unstorable`, and the
        repair must not resolve it by overwriting the incumbent -- the two rows
        may be two different entities the register answers one IČO with.
        """
        holder = Company.objects.create(
            ruz_id=1677, ico="001781521576", nazov_UJ="Iný subjekt"
        )
        api = _StubRuzApi({
            1520199: {
                "ico": "001781521576",
                "id": 1520199,
                "nazovUJ": "SZZ Základná organizácia 43-1",
                "pravnaForma": "112",
                "datumZalozenia": "2020-01-01",
            }
        })

        out = self._run(api, "--ruz-id", "1520199")

        holder.refresh_from_db()
        self.assertEqual(holder.ruz_id, 1677)
        self.assertFalse(Company.objects.filter(ruz_id=1520199).exists())
        self.assertIn("not stored", out)
