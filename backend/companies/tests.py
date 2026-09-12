from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from backend.settings import _default_cache_redis_url
from companies.models import (
	Company,
	normalize_legal_form_code,
	LEGAL_FORMS,
	LEGAL_FORMS_SHORT,
)
from registers.models import OrsrCompanyProfile
from companies.serializers import CompanyDetailSerializer
from companies.services.pdf_report import _report_cache_key, get_company_report


class CompanyReportCacheConfigurationTests(SimpleTestCase):
	def test_default_cache_uses_a_separate_redis_database(self):
		self.assertEqual(
			_default_cache_redis_url('redis://redis.example:6379/0'),
			'redis://redis.example:6379/1',
		)
		self.assertEqual(
			_default_cache_redis_url('rediss://redis.example:6380/4?ssl_cert_reqs=required'),
			'rediss://redis.example:6380/5?ssl_cert_reqs=required',
		)


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
		self.assertContains(response, 'cf-hero')
		self.assertContains(response, 'cf-metric__accent--violet')
		self.assertContains(response, 'cf-btn cf-btn--secondary')

	def test_company_change_form_renders_sync_now_button(self):
		response = self.client.get(reverse('admin:companies_company_change', args=[self.company.id]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'cf-btn cf-btn--secondary')
		self.assertContains(response, 'Sync now')

	def test_add_from_ruz_page_renders_consistent_dark_panel(self):
		response = self.client.get(reverse('admin:companies_company_add_from_ruz'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'cf-hero')
		self.assertContains(response, 'cf-form')
		self.assertContains(response, 'cf-btn cf-btn--primary')


@override_settings(
	CACHES={
		'default': {
			'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
			'LOCATION': 'company-report-tests',
		},
	},
)
class CompanyReportCacheTests(TestCase):
	def setUp(self):
		self.company = Company.objects.create(
			ruz_id=999004,
			ico='12345680',
			nazov_UJ='Cached Report Company',
		)

	@patch('companies.services.pdf_report.generate_company_report')
	def test_report_endpoint_reuses_cached_pdf(self, generate_report_mock):
		generate_report_mock.return_value = b'%PDF-cached-report'
		url = reverse('company-report', args=[self.company.ico])

		first_response = self.client.get(url)
		second_response = self.client.get(url)

		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(second_response.status_code, 200)
		self.assertEqual(first_response.content, b'%PDF-cached-report')
		self.assertEqual(second_response.content, b'%PDF-cached-report')
		self.assertEqual(first_response['Content-Type'], 'application/pdf')
		generate_report_mock.assert_called_once()

	def test_report_cache_key_is_opaque_and_data_versioned(self):
		original_key = _report_cache_key(self.company)
		self.company.datum_poslednej_upravy = timezone.now().date()
		self.company.save(update_fields=['datum_poslednej_upravy'])

		updated_key = _report_cache_key(self.company)

		self.assertTrue(original_key.startswith('company-report:v1:'))
		self.assertNotIn(self.company.ico, original_key)
		self.assertNotEqual(original_key, updated_key)

	@patch('companies.services.pdf_report.time.sleep')
	@patch('companies.services.pdf_report.cache')
	def test_waits_for_locked_report_instead_of_generating_duplicate(
		self, cache_mock, sleep_mock
	):
		cache_mock.get.side_effect = [None, b'%PDF-from-other-worker']
		cache_mock.add.return_value = False

		report = get_company_report(self.company)

		self.assertEqual(report, b'%PDF-from-other-worker')
		cache_mock.add.assert_called_once()
		sleep_mock.assert_called_once()

	@patch('companies.services.pdf_report.generate_company_report')
	@patch('companies.services.pdf_report.cache')
	def test_cache_error_logs_and_falls_back_to_report_generation(
		self, cache_mock, generate_report_mock
	):
		cache_mock.get.side_effect = ConnectionError('cache unavailable')
		generate_report_mock.return_value = b'%PDF-direct-report'

		with self.assertLogs('companies.services.pdf_report', level='WARNING'):
			report = get_company_report(self.company)

		self.assertEqual(report, b'%PDF-direct-report')
		generate_report_mock.assert_called_once_with(self.company)


class CompanyViewErrorDisclosureTests(TestCase):
	"""A 500 must not hand the caller the exception's own text.

	Both endpoints are AllowAny, so an unauthenticated caller reaches them and
	an exception's message names tables, columns and file paths. The response
	carries a sentence instead; the traceback goes to the log.
	"""

	def setUp(self):
		self.company = Company.objects.create(
			ruz_id=999005,
			ico='12345681',
			nazov_UJ='Error Disclosure Company',
		)

	@patch('companies.views.CompanyDetailSerializer')
	def test_retrieve_keeps_the_exception_text_out_of_the_response(self, serializer_mock):
		serializer_mock.side_effect = RuntimeError(
			'relation "companies_secret_table" does not exist'
		)

		with self.assertLogs('companies.views', level='ERROR') as captured:
			response = self.client.get(reverse('company-detail', args=[self.company.ico]))

		self.assertEqual(response.status_code, 500)
		body = response.content.decode()
		self.assertNotIn('companies_secret_table', body)
		self.assertNotIn('RuntimeError', body)
		# Not discarded -- moved to the log, which is where it belongs.
		self.assertIn('companies_secret_table', '\n'.join(captured.output))

	@patch('companies.views.CompanyListSerializer')
	def test_search_keeps_the_exception_text_out_of_the_response(self, serializer_mock):
		serializer_mock.side_effect = RuntimeError(
			'column companies_company.internal_note does not exist'
		)

		with self.assertLogs('companies.views', level='ERROR') as captured:
			response = self.client.get(reverse('company-search'), {'q': 'Error Disclosure'})

		self.assertEqual(response.status_code, 500)
		body = response.content.decode()
		self.assertNotIn('internal_note', body)
		self.assertNotIn('RuntimeError', body)
		self.assertIn('internal_note', '\n'.join(captured.output))

	@patch('companies.views.get_company_report')
	def test_report_keeps_the_exception_text_out_of_the_response(self, report_mock):
		# The renderer wraps its own failure in a RuntimeError whose text *is*
		# the underlying exception, so this endpoint used to answer an anonymous
		# caller with the module path of a missing import, or with whatever
		# weasyprint said.
		report_mock.side_effect = RuntimeError(
			'PDF generation failed: No module named weasyprint (secrets.py line 41)'
		)

		with self.assertLogs('companies.views', level='ERROR') as captured:
			response = self.client.get(
				reverse('company-report', args=[self.company.ico])
			)

		self.assertEqual(response.status_code, 500)
		body = response.content.decode()
		self.assertNotIn('weasyprint', body)
		self.assertNotIn('secrets.py', body)
		self.assertIn('secrets.py', '\n'.join(captured.output))


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


class NormalizeLegalFormCodeTests(TestCase):
	"""Test the normalize_legal_form_code function for various input types."""

	def test_valid_code_string(self):
		"""Test valid code as string is returned unchanged."""
		self.assertEqual(normalize_legal_form_code('112'), '112')
		self.assertEqual(normalize_legal_form_code('101'), '101')
		self.assertEqual(normalize_legal_form_code('995'), '995')

	def test_valid_code_integer(self):
		"""Test valid code as integer is normalized to string."""
		self.assertEqual(normalize_legal_form_code(112), '112')
		self.assertEqual(normalize_legal_form_code(101), '101')

	def test_leading_zeros_stripped(self):
		"""Test codes with leading zeros are normalized correctly."""
		# '0112' should become '112'
		self.assertEqual(normalize_legal_form_code('0112'), '112')

	def test_whitespace_stripped(self):
		"""Test whitespace is trimmed from codes."""
		self.assertEqual(normalize_legal_form_code('  112  '), '112')
		self.assertEqual(normalize_legal_form_code('\t101\n'), '101')

	def test_none_returns_fallback(self):
		"""Test None value returns '995' (Nešpecifikovaná)."""
		self.assertEqual(normalize_legal_form_code(None), '995')

	def test_empty_string_returns_fallback(self):
		"""Test empty string returns '995'."""
		self.assertEqual(normalize_legal_form_code(''), '995')
		self.assertEqual(normalize_legal_form_code('  '), '995')

	def test_unknown_code_returns_fallback(self):
		"""Test unknown code returns '995' and logs once."""
		# Clear the logged set to ensure we capture the log
		from companies.models import _logged_unknown_legal_form_codes
		_logged_unknown_legal_form_codes.clear()

		with self.assertLogs('companies.models', level='INFO') as cm:
			result = normalize_legal_form_code('999')
			self.assertEqual(result, '995')
			# Check that log message was produced
			self.assertTrue(
				any('Unknown legal form code' in msg for msg in cm.output),
				f"Expected 'Unknown legal form code' in logs, got: {cm.output}",
			)

	def test_unknown_code_logged_only_once(self):
		"""Test that unknown code is logged only once per code value."""
		from companies.models import _logged_unknown_legal_form_codes
		_logged_unknown_legal_form_codes.clear()

		with self.assertLogs('companies.models', level='INFO') as cm:
			# First call should log
			result1 = normalize_legal_form_code('888')
			# Second call should NOT log (code already in set)
			result2 = normalize_legal_form_code('888')

			self.assertEqual(result1, '995')
			self.assertEqual(result2, '995')

			# Count how many times '888' was logged
			log_count = sum(1 for msg in cm.output if '888' in msg)
			self.assertEqual(log_count, 1, f"Expected '888' logged once, got {log_count} times")

	def test_invalid_type_returns_fallback(self):
		"""Test that invalid types (like dicts) are handled gracefully."""
		self.assertEqual(normalize_legal_form_code({'code': '112'}), '995')
		self.assertEqual(normalize_legal_form_code(['112']), '995')

	def test_all_valid_codes_in_legal_forms(self):
		"""Test that all codes in LEGAL_FORMS are recognized."""
		for code in LEGAL_FORMS.keys():
			self.assertEqual(normalize_legal_form_code(code), code)


class CompanyLegalFormDisplayTests(TestCase):
	"""Test Company model methods for displaying legal forms."""

	def setUp(self):
		self.company_sro = Company.objects.create(
			ruz_id=999010,
			ico='12345678',
			nazov_UJ='Test s. r. o.',
			pravna_forma='112',
		)
		self.company_as = Company.objects.create(
			ruz_id=999011,
			ico='12345679',
			nazov_UJ='Test a. s.',
			pravna_forma='121',
		)
		self.company_unknown = Company.objects.create(
			ruz_id=999012,
			ico='12345680',
			nazov_UJ='Test unknown',
			pravna_forma='995',
		)
		self.company_empty = Company.objects.create(
			ruz_id=999013,
			ico='12345681',
			nazov_UJ='Test empty',
			pravna_forma='',
		)

	def test_get_legal_form_display(self):
		"""Test full legal form name is returned."""
		self.assertEqual(
			self.company_sro.get_legal_form_display(),
			'Spoločnosť s ručením obmedzeným',
		)
		self.assertEqual(
			self.company_as.get_legal_form_display(),
			'Akciová spoločnosť',
		)

	def test_get_legal_form_display_unknown(self):
		"""Test that unspecified form returns correct text."""
		result = self.company_unknown.get_legal_form_display()
		self.assertIn('Nešpecifikovaná', result)

	def test_get_legal_form_display_empty(self):
		"""Test that empty pravna_forma returns empty string."""
		self.assertEqual(self.company_empty.get_legal_form_display(), '')

	def test_get_legal_form_short(self):
		"""Test short form abbreviation is returned."""
		self.assertEqual(self.company_sro.get_legal_form_short(), 's. r. o.')
		self.assertEqual(self.company_as.get_legal_form_short(), 'a. s.')

	def test_get_legal_form_short_unknown(self):
		"""Test that unspecified form returns short form."""
		result = self.company_unknown.get_legal_form_short()
		self.assertIn('nešpecifikovaná', result)

	def test_get_legal_form_short_empty(self):
		"""Test that empty pravna_forma returns empty string."""
		self.assertEqual(self.company_empty.get_legal_form_short(), '')

	def test_get_legal_form_with_code(self):
		"""Test that code + short form is formatted correctly."""
		result = self.company_sro.get_legal_form_with_code()
		self.assertIn('112', result)
		self.assertIn('s. r. o.', result)

	def test_get_legal_form_with_code_unknown(self):
		"""Test that unknown form is formatted correctly."""
		result = self.company_unknown.get_legal_form_with_code()
		self.assertIn('995', result)

	def test_get_legal_form_with_code_empty(self):
		"""Test that empty pravna_forma returns empty string."""
		self.assertEqual(self.company_empty.get_legal_form_with_code(), '')
