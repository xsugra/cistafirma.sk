"""The person side of the risk indicators, where the wording matters most.

The company rules flag a *shape*: a balance sheet with no equipment, a seat
shared with two hundred others. A person rule flags a *life*, and the same
numbers that are an observation about a company become an accusation about a
human being. The methodology this feature came from says so itself: public
registers cannot distinguish a straw man from an entrepreneur who genuinely
runs fourteen companies, and cannot identify either. So the tests below are
written against two things at once -- that the counts are right, and that no
sentence in the payload says anything the data cannot support.

Two structural rules are pinned here because they are easy to lose:

* **The cluster is the unit.** A person is more than one `Person` row (§11.18);
  counting rows instead of lives would make every number wrong for exactly the
  people the feature is about.
* **`is_active is None` is our gap, not their fact.** It means the function
  history was never read for that company. Reporting it as an indicator would
  dress a hole in our own scraping up as something about a person, so it lives
  in `coverage` and this file checks that it stays there.
"""

from datetime import date

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from companies.models import Company
from connections import person_risk as pr
from connections.models import Person, PersonCompanyRelation


class NaceDivisionTests(SimpleTestCase):
    """The register's code is text of varying length; the division is two digits."""

    def test_a_full_code_yields_its_division(self):
        self.assertEqual(pr.nace_division('46190'), '46')

    def test_a_two_digit_code_is_its_own_division(self):
        self.assertEqual(pr.nace_division('46'), '46')

    def test_a_short_or_absent_code_has_no_division(self):
        # Not zero and not a division of its own: a code we cannot place must
        # drop out of a count rather than inflate it.
        for value in (None, '', '4', '  ', 'AB', 'SK46'):
            with self.subTest(value=value):
                self.assertIsNone(pr.nace_division(value))

    def test_surrounding_space_does_not_change_the_division(self):
        self.assertEqual(pr.nace_division(' 46190 '), '46')


class PersonRiskTests(TestCase):
    """Fixture: one cluster of `Person` rows, and companies to hang off it."""

    def setUp(self):
        self._company_seq = 0

    def person(self, name, fingerprint):
        return Person.objects.create(name=name, fingerprint=fingerprint)

    def company(self, nace='46190', dissolved=None):
        self._company_seq += 1
        index = self._company_seq
        return Company.objects.create(
            ruz_id=800000 + index,
            ico=f'80{index:06d}',
            nazov_UJ=f'Firma {index} s. r. o.',
            sk_NACE=nace,
            datum_zrusenia=dissolved,
        )

    def link(self, person, company, role='konatel', is_active=True, start=None):
        return PersonCompanyRelation.objects.create(
            person=person, company=company, role=role,
            is_active=is_active, vznik_funkcie=start or date(2015, 1, 1),
        )


class FootprintTests(PersonRiskTests):
    """What one person's cluster adds up to, in companies rather than rows."""

    def test_no_members_is_an_empty_footprint(self):
        self.assertEqual(pr.footprint([]), {'companies': [], 'relations': 0})

    def test_a_company_is_counted_once_however_many_roles_it_holds(self):
        # Konateľ and spoločník in one company is one company and two rows.
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        company = self.company()
        self.link(person, company, role='konatel')
        self.link(person, company, role='spolocnik')

        data = pr.footprint([person.pk])
        self.assertEqual(len(data['companies']), 1)
        self.assertEqual(data['relations'], 2)
        self.assertEqual(data['companies'][0]['roles'], ['Konateľ', 'Spoločník'])

    def test_the_cluster_is_the_unit_not_the_row(self):
        # Two `Person` rows, one human (§11.18). Counting rows would report two
        # companies for a person who holds one.
        first = self.person('Ján Novák', 'name:jan novak|addr:bratislava')
        second = self.person('Ing. Ján Novák', 'name:jan novak|addr:')
        company = self.company()
        self.link(first, company)
        self.link(second, company)

        data = pr.footprint([first.pk, second.pk])
        self.assertEqual(len(data['companies']), 1)
        self.assertEqual(data['relations'], 2)

    def test_the_function_window_is_the_widest_one_seen(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        company = self.company()
        self.link(person, company, start=date(2010, 1, 1))
        PersonCompanyRelation.objects.create(
            person=person, company=company, role='spolocnik',
            vznik_funkcie=date(2015, 1, 1), zanik_funkcie=date(2018, 6, 30),
        )
        entry = pr.footprint([person.pk])['companies'][0]
        self.assertEqual(entry['started'], date(2010, 1, 1))
        self.assertEqual(entry['ended'], date(2018, 6, 30))

    def test_the_registers_own_status_travels_with_the_company(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        self.link(person, self.company(nace='62010', dissolved=date(2019, 3, 1)))
        entry = pr.footprint([person.pk])['companies'][0]
        self.assertEqual(entry['nace'], '62010')
        self.assertEqual(entry['dissolved_on'], date(2019, 3, 1))


class ManyCompaniesTests(PersonRiskTests):
    """`serialny_statutar` -- the count, the roles, and the word never used."""

    def test_no_companies_is_unassessed(self):
        outcome = pr._flag_many_companies([])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_an_ordinary_director_is_clear(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        for _ in range(3):
            self.link(person, self.company())
        outcome = pr._flag_many_companies(pr.footprint([person.pk])['companies'])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('v 3 firmách', outcome['detail'])

    def test_functions_across_many_companies_fires_with_the_roles(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        for index in range(5):
            self.link(person, self.company(), role='konatel' if index else 'spolocnik')
        outcome = pr._flag_many_companies(pr.footprint([person.pk])['companies'])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('v 5 firmách', outcome['detail'])
        self.assertIn('4× Konateľ', outcome['detail'])
        self.assertIn('1× Spoločník', outcome['detail'])

    def test_the_role_is_the_label_and_not_the_registers_own_text(self):
        # `role_display` holds whatever ORSR wrote, which is a different field
        # and often empty; the count line reads from the role's own label.
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        for _ in range(5):
            self.link(person, self.company())
        outcome = pr._flag_many_companies(pr.footprint([person.pk])['companies'])
        self.assertIn('5× Konateľ', outcome['detail'])
        self.assertNotIn('konatel', outcome['detail'])

    def test_one_company_is_written_in_the_singular(self):
        # A count of one is the case a plural-only sentence gets wrong, and it
        # is the one a reader sees most often.
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        self.link(person, self.company())
        outcome = pr._flag_many_companies(pr.footprint([person.pk])['companies'])
        self.assertIn('v 1 firme', outcome['detail'])

    def test_dissolved_companies_are_stated_beside_the_total(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        for index in range(5):
            self.link(person, self.company(dissolved=date(2020, 1, 1) if index < 2 else None))
        outcome = pr._flag_many_companies(pr.footprint([person.pk])['companies'])
        self.assertIn('z toho 2 zrušených', outcome['detail'])
        self.assertEqual(outcome['evidence']['companies_dissolved'], 2)

    def test_the_wording_names_no_offence(self):
        # The whole point of §11.22.2. This is the module where a careless
        # label would be a product calling a named person a criminal.
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        for _ in range(9):
            self.link(person, self.company())
        payload = pr.person_red_flags([person.pk])
        for flag in payload['flags']:
            text = f"{flag['label']} {flag['detail'] or ''}".lower()
            with self.subTest(code=flag['code']):
                for accusation in (
                    'biely', 'kôň', 'podvod', 'karusel', 'falš', 'nastrčen',
                    'podozriv', 'kriminál',
                ):
                    self.assertNotIn(accusation, text)


class SectorSpreadTests(PersonRiskTests):
    """`odvetvova_rozptylenost` -- read as a spread, never as a scheme."""

    def test_too_few_companies_for_a_spread(self):
        outcome = pr._flag_sector_spread([
            {'nace': '46190'}, {'nace': '62010'},
        ])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_no_nace_code_anywhere_is_unassessed(self):
        outcome = pr._flag_sector_spread([{'nace': ''} for _ in range(6)])
        self.assertEqual(outcome['state'], 'unassessed')

    def test_a_narrow_spread_is_clear_and_states_it(self):
        outcome = pr._flag_sector_spread([
            {'nace': '46190'}, {'nace': '46200'}, {'nace': '46190'},
            {'nace': '46200'}, {'nace': '46190'},
        ])
        self.assertEqual(outcome['state'], 'clear')
        self.assertIn('v 1 oddieli', outcome['detail'])

    def test_a_wide_spread_fires(self):
        outcome = pr._flag_sector_spread([
            {'nace': '46190'}, {'nace': '62010'}, {'nace': '68200'},
            {'nace': '56100'}, {'nace': '45110'},
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertEqual(outcome['evidence']['divisions_count'], 5)

    def test_companies_without_a_code_are_disclosed_in_the_sentence(self):
        # They are left out of the count, and a reader is entitled to know how
        # many -- otherwise the spread looks narrower than the data is.
        outcome = pr._flag_sector_spread([
            {'nace': '46190'}, {'nace': '62010'}, {'nace': '68200'},
            {'nace': '56100'}, {'nace': ''},
        ])
        self.assertIn('1 firma bez kódu NACE', outcome['detail'])
        self.assertEqual(outcome['evidence']['companies_without_nace'], 1)


class CompanyMortalityTests(PersonRiskTests):
    """`umrtnost_firiem` -- and the refusal to compute a rate over two firms."""

    def test_too_few_companies_for_a_share_to_mean_anything(self):
        outcome = pr._flag_company_mortality([
            {'dissolved_on': date(2020, 1, 1)}, {'dissolved_on': None},
        ])
        self.assertEqual(outcome['state'], 'unassessed')
        self.assertIn('podiel by nebol podiel', outcome['reason'])

    def test_half_the_companies_struck_off_fires(self):
        outcome = pr._flag_company_mortality([
            {'dissolved_on': date(2020, 1, 1)}, {'dissolved_on': date(2021, 1, 1)},
            {'dissolved_on': None}, {'dissolved_on': None},
        ])
        self.assertEqual(outcome['state'], 'fired')
        self.assertIn('zrušených 2 z 4 firiem', outcome['detail'])

    def test_one_of_four_struck_off_is_clear(self):
        outcome = pr._flag_company_mortality([
            {'dissolved_on': date(2020, 1, 1)}, {'dissolved_on': None},
            {'dissolved_on': None}, {'dissolved_on': None},
        ])
        self.assertEqual(outcome['state'], 'clear')

    def test_a_company_without_a_dissolution_date_is_not_counted_as_surviving(self):
        # Absence of the date may mean the company runs, or that we never read
        # the field. The share is over all the person's companies, so the
        # uncertainty lands in the denominator rather than being resolved
        # silently in one direction.
        outcome = pr._flag_company_mortality([
            {'dissolved_on': date(2020, 1, 1)} for _ in range(3)
        ] + [{'dissolved_on': None}])
        self.assertEqual(outcome['evidence']['share'], '0.750')
        self.assertIn('3 z 4', outcome['detail'])


class CoverageTests(PersonRiskTests):
    """Unknown function state is our gap and must stay in `coverage`."""

    def test_unknown_function_states_are_counted_apart(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        PersonCompanyRelation.objects.create(
            person=person, company=self.company(), role='konatel', is_active=None,
        )
        self.link(person, self.company(), is_active=True)
        self.link(person, self.company(), is_active=False)

        report = pr.coverage(pr.footprint([person.pk])['companies'])
        self.assertEqual(report['companies'], 3)
        self.assertEqual(report['companies_function_state_unknown'], 1)
        self.assertEqual(report['companies_active_known'], 2)

    def test_unknown_function_state_is_not_an_indicator(self):
        # If it were a flag, a hole in our scraping would read as a fact about
        # a person -- which is the whole reason it is here instead.
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        PersonCompanyRelation.objects.create(
            person=person, company=self.company(), role='konatel', is_active=None,
        )
        payload = pr.person_red_flags([person.pk])
        codes = {flag['code'] for flag in payload['flags']}
        self.assertNotIn('nezname_funkcie', codes)
        self.assertEqual(payload['coverage']['companies_function_state_unknown'], 1)

    def test_dissolved_companies_are_counted_in_coverage(self):
        person = self.person('Ján Novák', 'name:jan novak|addr:')
        self.link(person, self.company(dissolved=date(2019, 1, 1)))
        self.link(person, self.company())
        report = pr.coverage(pr.footprint([person.pk])['companies'])
        self.assertEqual(report['companies_dissolved'], 1)


class PayloadShapeTests(PersonRiskTests):
    """The contract `PersonDetailView` will publish, pinned key by key."""

    def setUp(self):
        super().setUp()
        # Not `self.person`: that name is the fixture *factory* on the base
        # class, and shadowing it makes the second call in a test a call on a
        # `Person` instance.
        self.subject = self.person('Ján Novák', 'name:jan novak|addr:')
        self.link(self.subject, self.company())

    def test_every_person_rule_is_reported_once(self):
        payload = pr.person_red_flags([self.subject.pk])
        codes = [flag['code'] for flag in payload['flags']]
        self.assertEqual(len(codes), len(pr.PERSON_RULES))
        self.assertEqual(len(codes), len(set(codes)))

    def test_the_counts_account_for_every_rule(self):
        payload = pr.person_red_flags([self.subject.pk])
        self.assertEqual(sum(payload['counts'].values()), len(pr.PERSON_RULES))

    def test_every_flag_carries_the_same_keys_as_a_company_flag(self):
        # The two modules are owned by different apps and duplicate the shape
        # deliberately; this is what keeps the duplication from drifting.
        expected = sorted(
            ['code', 'label', 'severity', 'state', 'detail', 'reason', 'evidence']
        )
        for flag in pr.person_red_flags([self.subject.pk])['flags']:
            with self.subTest(code=flag['code']):
                self.assertEqual(sorted(flag), expected)

    def test_a_state_carries_its_own_kind_of_explanation(self):
        for flag in pr.person_red_flags([self.subject.pk])['flags']:
            with self.subTest(code=flag['code']):
                if flag['state'] == 'unassessed':
                    self.assertIsNone(flag['detail'])
                    self.assertTrue(flag['reason'])
                else:
                    self.assertIsNone(flag['reason'])
                    self.assertTrue(flag['detail'])

    def test_a_person_with_no_companies_at_all_is_not_an_error(self):
        stranger = self.person('Nikto Nikto', 'name:nikto nikto|addr:')
        payload = pr.person_red_flags([stranger.pk])
        self.assertEqual(payload['counts']['fired'], 0)
        self.assertEqual(payload['coverage']['companies'], 0)

    def test_an_empty_cluster_is_not_an_error(self):
        payload = pr.person_red_flags([])
        self.assertEqual(payload['coverage']['companies'], 0)
        self.assertEqual(len(payload['flags']), len(pr.PERSON_RULES))


class PersonDetailPublishesRedFlagsTests(APITestCase):
    """The endpoint contract, tested through the endpoint.

    The unit tests above would all pass with the field wired to nothing, so the
    one thing this class checks is that the page a reader opens actually carries
    it -- and over the *cluster*, not over the row that was asked for.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=3, ico='50059959', nazov_UJ='Test s.r.o.',
        )
        self.person = Person.objects.create(
            fingerprint='name:jan novak|addr:ba', name='Ján Novák',
        )
        PersonCompanyRelation.objects.create(
            person=self.person, company=self.company, role='konatel', is_active=True,
        )

    def test_the_detail_response_carries_red_flags(self):
        data = self.client.get(f'/api/persons/{self.person.pk}/').json()
        payload = data['red_flags']
        self.assertEqual(len(payload['flags']), len(pr.PERSON_RULES))
        self.assertEqual(sum(payload['counts'].values()), len(pr.PERSON_RULES))
        self.assertEqual(payload['coverage']['companies'], 1)

    def test_the_count_is_over_the_cluster_and_not_over_the_row(self):
        # A second row of the same human, joined to the first by a shared
        # company -- which is the evidence `cluster_evidence` groups on, and the
        # reason two rows with nothing but a name in common are *not* one person.
        # The second row then holds a company the first does not, so a payload
        # built from the asked-for row alone would report one company here.
        second = Person.objects.create(
            fingerprint='name:jan novak|addr:', name='Ján Novák',
        )
        PersonCompanyRelation.objects.create(
            person=second, company=self.company, role='konatel', is_active=True,
        )
        other = Company.objects.create(
            ruz_id=4, ico='50059960', nazov_UJ='Druhá s.r.o.',
        )
        PersonCompanyRelation.objects.create(
            person=second, company=other, role='konatel', is_active=True,
        )

        data = self.client.get(f'/api/persons/{self.person.pk}/').json()
        self.assertEqual(data['records'], 2, 'the two rows should be one person')
        self.assertEqual(data['red_flags']['coverage']['companies'], 2)
