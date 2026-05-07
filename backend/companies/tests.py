from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from companies.models import Company
from registers.models import OrsrCompanyProfile
from companies.serializers import CompanyDetailSerializer


class CompanyAdminSyncNowTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.admin_user = user_model.objects.create_superuser(
			username='admin',
			email='admin@example.com',
			password='adminpass123',
		)
		self.client.force_login(self.admin_user)
		self.company = Company.objects.create(
			ruz_id=999001,
			ico='12345678',
			nazov_UJ='Test Company, s. r. o.',
		)

	@patch('registers.tasks.sync_company_now.delay')
	def test_sync_now_admin_view_schedules_task_and_redirects(self, delay_mock):
		url = reverse('admin:companies_company_sync_now', args=[self.company.id])
		response = self.client.get(url, follow=True)

		self.assertRedirects(
			response,
			reverse('admin:companies_company_change', args=[self.company.id]),
		)
		delay_mock.assert_called_once_with(self.company.id)

		messages = [str(message) for message in get_messages(response.wsgi_request)]
		self.assertTrue(
			any('Full sync naplanovany' in message for message in messages),
			f'Expected success message not found. Messages: {messages}',
		)

	def test_company_changelist_renders_consistent_dark_dashboard(self):
		response = self.client.get(reverse('admin:companies_company_changelist'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'admin-theme-hero')
		self.assertContains(response, 'admin-theme-card--violet')
		self.assertContains(response, 'admin-theme-button--emerald')

	def test_company_change_form_renders_sync_now_button(self):
		response = self.client.get(reverse('admin:companies_company_change', args=[self.company.id]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'admin-theme-button--emerald')
		self.assertContains(response, 'Sync now')

	def test_add_from_ruz_page_renders_consistent_dark_panel(self):
		response = self.client.get(reverse('admin:companies_company_add_from_ruz'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'admin-theme-hero')
		self.assertContains(response, 'admin-theme-form-panel')
		self.assertContains(response, 'admin-theme-button--emerald')


class CompanyDetailSerializerProkuraTests(TestCase):
	def setUp(self):
		self.company = Company.objects.create(
			ruz_id=999002,
			ico='48097781',
			nazov_UJ='ECOKLIMA s.r.o.',
		)
		OrsrCompanyProfile.objects.create(
			company=self.company,
			ico='48097781',
			spolocnici=['Martin Močko'],
			statutarny_organ=['Martin Močko'],
			prokura=['Lukáš Jurica'],
		)

	def test_executives_include_prokura(self):
		data = CompanyDetailSerializer(self.company).data
		roles = {(item['name'], item['role']) for item in data['executives']}

		self.assertIn(('Martin Močko', 'Konateľ'), roles)
		self.assertIn(('Lukáš Jurica', 'Prokurista'), roles)

	def test_executives_skip_fragmented_single_token_names(self):
		self.company.orsr_profile.statutarny_organ = ['Ing.', 'Tomáš', 'Skřipský']
		self.company.orsr_profile.prokura = ['Petr Bartoníček']
		self.company.orsr_profile.spolocnici = ['Finance Services SK s. r. o.']
		self.company.orsr_profile.save()

		data = CompanyDetailSerializer(self.company).data
		names = {item['name'] for item in data['executives']}

		self.assertIn('Petr Bartoníček', names)
		self.assertIn('Finance Services SK s. r. o.', names)
		self.assertNotIn('Ing.', names)
		self.assertNotIn('Tomáš', names)


class CompanyDetailSerializerStructuredTests(TestCase):
	"""Exercises the structured-data path (new parser output in raw_payload)."""

	def setUp(self):
		self.company = Company.objects.create(
			ruz_id=999003,
			ico='00207306',
			nazov_UJ='Družstvo Test',
		)
		self.structured = {
			'statutarny_organ_typ': 'predstavenstvo',
			'statutarny_organ': [
				{
					'name': 'Ing. Martin Backo',
					'title': '',
					'role': 'predseda predstavenstva',
					'address': 'Dúbravská 672/23, Veľký Krtíš 990 01',
					'vznik_funkcie': '29.06.2022',
					'person_ico': '',
					'ine_id': '',
				},
			],
			'predstavenstvo': [
				{
					'name': 'Ing. Martin Backo',
					'role': 'predseda predstavenstva',
					'address': 'Dúbravská 672/23, Veľký Krtíš 990 01',
					'vznik_funkcie': '29.06.2022',
				},
			],
			'kontrolna_komisia': [
				{
					'name': 'Mária Kováčová',
					'role': 'člen kontrolnej komisie',
					'address': 'Vedľajšia 2, Nitra 949 01',
				},
			],
			'spolocnici': [],
			'prokura': [],
			'predmet_podnikania': [{'text': 'Kúpa tovaru', 'od': '29.06.2022'}],
		}
		OrsrCompanyProfile.objects.create(
			company=self.company,
			ico='00207306',
			oddiel='Dr',
			oddiel_type='dr',
			vlozka_cislo='66/R',
			obchodne_meno='Družstvo Test',
			pravna_forma='Družstvo',
			predstavenstvo=['Ing. Martin Backo'],
			kontrolna_komisia=['Mária Kováčová'],
			raw_payload={'structured': self.structured},
		)

	def test_orsr_profile_exposes_structured_payload(self):
		data = CompanyDetailSerializer(self.company).data

		self.assertIn('orsr_profile', data)
		orsr = data['orsr_profile']
		self.assertEqual(orsr['oddiel_type'], 'dr')

		structured = orsr['structured']
		self.assertEqual(len(structured['statutarny_organ']), 1)
		self.assertEqual(
			structured['statutarny_organ'][0]['address'],
			'Dúbravská 672/23, Veľký Krtíš 990 01',
		)
		self.assertEqual(
			structured['statutarny_organ'][0]['vznik_funkcie'], '29.06.2022'
		)
		self.assertEqual(len(structured['kontrolna_komisia']), 1)
		self.assertEqual(
			structured['kontrolna_komisia'][0]['name'], 'Mária Kováčová'
		)

	def test_executives_prefer_structured_over_flat_fields(self):
		data = CompanyDetailSerializer(self.company).data
		executives = {(item['name'], item['role']) for item in data['executives']}

		self.assertIn(('Ing. Martin Backo', 'predseda predstavenstva'), executives)


