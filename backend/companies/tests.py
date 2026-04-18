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
			any('Full sync bol naplánovaný' in message for message in messages),
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


