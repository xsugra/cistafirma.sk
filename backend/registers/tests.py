from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from registers.scrapers.orsr_scraper import OrsrHtmlParser


class OrsrHtmlParserTests(SimpleTestCase):
	def setUp(self):
		self.parser = OrsrHtmlParser()

	def test_parse_extracts_core_fields(self):
		html = """
		<html><body>
			<div>Oddiel: Sro Vložka číslo: 57997/T</div>
			<table>
				<tr><td>Obchodné meno:</td><td>ŠUPA s. r. o.<br>(od: 13.11.2024)</td></tr>
				<tr><td>Sídlo:</td><td>J.Hollého 164<br>Veľké Kostoľany 922 07<br>(od: 13.11.2024)</td></tr>
				<tr><td>IČO:</td><td>56 617 135<br>(od: 13.11.2024)</td></tr>
				<tr><td>Deň zápisu:</td><td>13.11.2024</td></tr>
				<tr><td>Právna forma:</td><td>Spoločnosť s ručením obmedzeným</td></tr>
				<tr><td>Predmet podnikania (činnosti):</td><td>Kúpa tovaru</td></tr>
				<tr><td></td><td>Vedenie účtovníctva</td></tr>
				<tr><td>Konanie menom spoločnosti:</td><td>Konatelia konajú samostatne.</td></tr>
				<tr><td>Výška základného imania:</td><td>6 000 EUR Rozsah splatenia: 6 000 EUR</td></tr>
				<tr><td>Dátum aktualizácie údajov:</td><td>16.04.2026</td></tr>
				<tr><td>Dátum výpisu:</td><td>17.04.2026</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "56617135")

		self.assertEqual(parsed["oddiel"], "Sro")
		self.assertEqual(parsed["vlozka_cislo"], "57997/T")
		self.assertEqual(parsed["obchodne_meno"], "ŠUPA s. r. o.")
		self.assertEqual(parsed["ico"], "56617135")
		self.assertEqual(parsed["den_zapisu"].isoformat(), "2024-11-13")
		self.assertEqual(len(parsed["predmet_podnikania"]), 2)
		self.assertIn("Vedenie účtovníctva", parsed["predmet_podnikania"])
		self.assertEqual(parsed["orsr_datum_vypisu"].isoformat(), "2026-04-17")

	def test_parse_handles_missing_optional_blocks(self):
		html = """
		<html><body>
			<table>
				<tr><td>Obchodné meno:</td><td>Test, s. r. o.</td></tr>
				<tr><td>IČO:</td><td>12345678</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "12345678")

		self.assertEqual(parsed["obchodne_meno"], "Test, s. r. o.")
		self.assertEqual(parsed["ico"], "12345678")
		self.assertEqual(parsed["oddiel"], "")
		self.assertEqual(parsed["predmet_podnikania"], [])

	def test_parse_cleans_spolocnici_and_statutary_people_blocks(self):
		html = """
		<html><body>
			<div>Oddiel: Sro Vložka číslo: 35637/T</div>
			<table>
				<tr><td>Spoločníci:</td><td>
					Martin<br>
					Močko<br>
					Nálepkova<br>
					7847/32A<br>
					Piešťany 921 01<br>
					(od: 28.09.2022)
				</td></tr>
				<tr><td>Spoločníci:</td><td>
					Martin<br>
					Močko<br>
					Nálepkova<br>
					7847/32A<br>
					Piešťany 921 01<br>
					(od: 28.09.2022)
				</td></tr>
				<tr><td>Štatutárny orgán:</td><td>
					konateľ<br>
					Martin<br>
					Močko<br>
					Nálepkova<br>
					7847/32A<br>
					Piešťany 921 01<br>
					Vznik funkcie: 23.04.2015<br>
					Osoba je stotožnená s referenčným registrom - RFO<br>
				</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "48097781")

		self.assertEqual(parsed["spolocnici"], ["Martin Močko"])
		self.assertEqual(parsed["statutarny_organ"], ["Martin Močko"])
		self.assertNotIn("Nálepkova", " ".join(parsed["spolocnici"]))
		self.assertNotIn("Nálepkova", " ".join(parsed["statutarny_organ"]))
		self.assertNotIn("konateľ", " ".join(parsed["statutarny_organ"]).lower())

	def test_parse_extracts_prokura_people(self):
		html = """
		<html><body>
			<div>Oddiel: Sro Vložka číslo: 35637/T</div>
			<table>
				<tr><td>Prokúra:</td><td>
					Lukáš Jurica<br>
					Poľná 5299/1<br>
					Banka 921 01<br>
					Vznik funkcie: 31.01.2025<br>
					Prokurista je oprávnený konať v mene spoločnosti samostatne.
				</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "48097781")

		self.assertEqual(parsed["prokura"], ["Lukáš Jurica"])
		self.assertNotIn("Poľná", " ".join(parsed["prokura"]))
		self.assertNotIn("Vznik funkcie", " ".join(parsed["prokura"]))

	def test_parse_keeps_surnames_for_titled_statutary_people(self):
		html = """
		<html><body>
			<div>Oddiel: Dr Vložka číslo: 66/R</div>
			<table>
				<tr><td>Štatutárny orgán:</td><td>
					predstavenstvo<br>
					Ing. Martin<br>
					Backo<br>
					Dúbravská 672/23<br>
					Veľký Krtíš 990 01<br>
					Vznik funkcie: 29.06.2022<br>
					Ing. Pavol<br>
					Výboch<br>
					P.O. Hviezdoslava 819/37<br>
					Veľký Krtíš 990 01<br>
					Vznik funkcie: 29.06.2022
				</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "00207306")

		self.assertIn("Ing. Martin Backo", parsed["statutarny_organ"])
		self.assertIn("Ing. Pavol Výboch", parsed["statutarny_organ"])

	def test_parse_trims_trailing_role_from_titled_name(self):
		html = """
		<html><body>
			<div>Oddiel: Dr Vložka číslo: 66/R</div>
			<table>
				<tr><td>Štatutárny orgán:</td><td>
					Ing. Milan Výboch - Člen predstavenstva<br>
					P.O. Hviezdoslava 819/37<br>
					Veľký Krtíš 990 01<br>
					Vznik funkcie: 29.06.2022
				</td></tr>
			</table>
		</body></html>
		"""

		parsed = self.parser.parse(html, "00207306")

		self.assertIn("Ing. Milan Výboch", parsed["statutarny_organ"])
		self.assertNotIn("Člen predstavenstva", " ".join(parsed["statutarny_organ"]))


class SyncProgressAdminDashboardTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.admin_user = user_model.objects.create_superuser(
			username='sync_admin',
			email='sync_admin@example.com',
			password='sync_admin_pass123',
		)
		self.client.force_login(self.admin_user)

	def test_sync_dashboard_changelist_renders_custom_kpis(self):
		url = reverse('admin:registers_syncprogress_changelist')
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'admin/registers/syncprogress/change_list.html')
		self.assertContains(response, 'RUZ Synchronizácia')
		self.assertContains(response, 'ORSR coverage')
		self.assertContains(response, 'Financial coverage')


class SyncGapAnalysisAdminDashboardTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.admin_user = user_model.objects.create_superuser(
			username='gap_admin',
			email='gap_admin@example.com',
			password='gap_admin_pass123',
		)
		self.client.force_login(self.admin_user)

	def test_gap_analysis_changelist_renders_custom_theme(self):
		url = reverse('admin:registers_syncgapanalysis_changelist')
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'admin-theme-hero')
		self.assertContains(response, 'admin-theme-card--amber')
		self.assertContains(response, 'admin-theme-button--blue')

