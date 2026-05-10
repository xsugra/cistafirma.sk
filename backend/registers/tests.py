from typing import Iterable, Optional
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from companies.models import Company
from registers.eligibility import is_orsr_eligible_company
from registers.models import SyncFocusModeState
from registers.scrapers.orsr_scraper import OrsrHtmlParser
from registers.services import focus_mode as focus_mode_service


def _entry(content: str, od: str = "") -> str:
	"""Wrap content in an ORSR entry <table> with optional "(od: DD.MM.YYYY)"."""
	od_html = f"(od: {od})" if od else ""
	return f'<table><tr><td>{content}</td><td>{od_html}</td></tr></table>'


def _person_html(
	name_tokens: Iterable[str],
	address_lines: Optional[Iterable[str]] = None,
	vznik: Optional[str] = None,
	trailing_notes: Optional[Iterable[str]] = None,
	role_suffix: str = "",
) -> str:
	"""Build a person block with <a class="lnm"> link, address and metadata."""
	spans = "".join(f'<span class="ra">{token}</span>' for token in name_tokens)
	link = f'<a class="lnm" href="#">{spans}</a>'
	if role_suffix:
		link += f" - {role_suffix}"
	parts = [link]
	for line in address_lines or []:
		parts.append(f'<span class="ra">{line}</span>')
	if vznik:
		parts.append(f"Vznik funkcie: {vznik}")
	for note in trailing_notes or []:
		parts.append(note)
	return "<br/>".join(parts)


def _build_orsr_html(
	*,
	oddiel: str = "",
	vlozka: str = "",
	sections: Optional[dict] = None,
	footer_dates: Optional[dict] = None,
) -> str:
	"""Build a minimal ORSR-like HTML document for parser tests."""
	oddiel_block = ""
	if oddiel or vlozka:
		oddiel_block = f"<p>Oddiel: {oddiel} Vložka číslo: {vlozka}</p>"

	rows = ""
	for title, entries_html in (sections or {}).items():
		rows += (
			f'<tr><td><span class="tl">{title}:</span></td>'
			f'<td>{entries_html}</td></tr>'
		)

	footer = ""
	if footer_dates:
		fragments = []
		if footer_dates.get("aktualizacia"):
			fragments.append(f"Dátum aktualizácie údajov: {footer_dates['aktualizacia']}")
		if footer_dates.get("vypis"):
			fragments.append(f"Dátum výpisu: {footer_dates['vypis']}")
		footer = "<p>" + " ".join(fragments) + "</p>"

	return f"<html><body>{oddiel_block}<table>{rows}</table>{footer}</body></html>"


class OrsrHtmlParserTests(SimpleTestCase):
	def setUp(self):
		self.parser = OrsrHtmlParser()

	def test_parse_extracts_core_fields(self):
		html = _build_orsr_html(
			oddiel="Sro",
			vlozka="57997/T",
			sections={
				"Obchodné meno": _entry(
					'<span class="ra">ŠUPA s. r. o.</span>', od="13.11.2024"
				),
				"Sídlo": _entry(
					'<span class="ra">J.Hollého 164</span>'
					'<br/><span class="ra">Veľké Kostoľany 922 07</span>',
					od="13.11.2024",
				),
				"IČO": _entry('<span class="ra">56 617 135</span>', od="13.11.2024"),
				"Deň zápisu": _entry('<span class="ra">13.11.2024</span>'),
				"Právna forma": _entry(
					'<span class="ra">Spoločnosť s ručením obmedzeným</span>'
				),
				"Predmet podnikania (činnosti)": (
					_entry('<span class="ra">Kúpa tovaru</span>')
					+ _entry('<span class="ra">Vedenie účtovníctva</span>')
				),
				"Konanie menom spoločnosti": _entry(
					'<span class="ra">Konatelia konajú samostatne.</span>'
				),
				"Výška základného imania": _entry(
					'<span class="ra">6 000 EUR Rozsah splatenia: 6 000 EUR</span>'
				),
			},
			footer_dates={"aktualizacia": "16.04.2026", "vypis": "17.04.2026"},
		)

		parsed = self.parser.parse(html, "56617135")

		self.assertEqual(parsed["oddiel"], "Sro")
		self.assertEqual(parsed["oddiel_type"], "sro")
		self.assertEqual(parsed["vlozka_cislo"], "57997/T")
		self.assertEqual(parsed["obchodne_meno"], "ŠUPA s. r. o.")
		self.assertEqual(parsed["ico"], "56617135")
		self.assertEqual(parsed["den_zapisu"].isoformat(), "2024-11-13")
		self.assertEqual(parsed["pravna_forma"], "Spoločnosť s ručením obmedzeným")
		self.assertIn("Kúpa tovaru", parsed["predmet_podnikania"])
		self.assertIn("Vedenie účtovníctva", parsed["predmet_podnikania"])
		self.assertEqual(parsed["orsr_datum_vypisu"].isoformat(), "2026-04-17")
		self.assertEqual(
			parsed["konanie_menom_spolocnosti"], "Konatelia konajú samostatne."
		)

	def test_parse_handles_missing_optional_sections(self):
		html = _build_orsr_html(
			sections={
				"Obchodné meno": _entry('<span class="ra">Test, s. r. o.</span>'),
				"IČO": _entry('<span class="ra">12345678</span>'),
			}
		)

		parsed = self.parser.parse(html, "12345678")

		self.assertEqual(parsed["obchodne_meno"], "Test, s. r. o.")
		self.assertEqual(parsed["ico"], "12345678")
		self.assertEqual(parsed["oddiel"], "")
		self.assertEqual(parsed["predmet_podnikania"], [])
		self.assertEqual(parsed["statutarny_organ"], [])

	def test_parse_extracts_statutary_person_with_role_and_address(self):
		organ_header = _entry('<span class="ra">konateľ</span>')
		person = _person_html(
			name_tokens=["Martin", "Močko"],
			address_lines=["Nálepkova 7847/32A", "Piešťany 921 01"],
			vznik="23.04.2015",
			trailing_notes=["Osoba je stotožnená s referenčným registrom - RFO"],
		)
		html = _build_orsr_html(
			oddiel="Sro",
			vlozka="35637/T",
			sections={
				"Štatutárny orgán": organ_header + _entry(person, od="28.09.2022"),
			},
		)

		parsed = self.parser.parse(html, "48097781")

		self.assertEqual(parsed["statutarny_organ"], ["Martin Močko"])

		structured = parsed["structured"]
		self.assertEqual(structured["statutarny_organ_typ"], "konateľ")
		people = structured["statutarny_organ"]
		self.assertEqual(len(people), 1)
		self.assertEqual(people[0]["name"], "Martin Močko")
		self.assertEqual(people[0]["role"], "konateľ")
		self.assertEqual(people[0]["vznik_funkcie"], "23.04.2015")
		self.assertIn("Nálepkova", people[0]["address"])
		self.assertIn("Piešťany", people[0]["address"])
		self.assertEqual(people[0]["od"], "28.09.2022")
		self.assertTrue(
			any("stotožnená" in note for note in people[0]["notes"]),
			"Stotožnenie s registrom should be preserved in notes.",
		)

	def test_parse_separates_prokura_person_from_authorization_sentence(self):
		person = _person_html(
			name_tokens=["Lukáš", "Jurica"],
			address_lines=["Poľná 5299/1", "Banka 921 01"],
			vznik="31.01.2025",
		)
		authorization = _entry(
			'<span class="ra">Prokurista je oprávnený konať '
			'v mene spoločnosti samostatne.</span>'
		)
		html = _build_orsr_html(
			oddiel="Sro",
			vlozka="35637/T",
			sections={"Prokúra": _entry(person) + authorization},
		)

		parsed = self.parser.parse(html, "48097781")

		self.assertEqual(parsed["prokura"], ["Lukáš Jurica"])
		opravnenia = parsed["structured"].get("prokura_oprávnenie", [])
		self.assertTrue(
			any("je oprávnený" in line for line in opravnenia),
			f"Authorization sentence missing from {opravnenia!r}",
		)

	def test_parse_keeps_titled_names_and_extracts_role_suffix(self):
		html = _build_orsr_html(
			oddiel="Dr",
			vlozka="66/R",
			sections={
				"Štatutárny orgán": (
					_entry('<span class="ra">predstavenstvo</span>')
					+ _entry(_person_html(
						name_tokens=["Ing.", "Martin", "Backo"],
						address_lines=["Dúbravská 672/23", "Veľký Krtíš 990 01"],
						vznik="29.06.2022",
					))
					+ _entry(_person_html(
						name_tokens=["Ing.", "Pavol", "Výboch"],
						address_lines=["P.O. Hviezdoslava 819/37", "Veľký Krtíš 990 01"],
						vznik="29.06.2022",
						role_suffix="Člen predstavenstva",
					))
				),
			},
		)

		parsed = self.parser.parse(html, "00207306")

		self.assertIn("Ing. Martin Backo", parsed["statutarny_organ"])
		self.assertIn("Ing. Pavol Výboch", parsed["statutarny_organ"])

		# Pre družstvo/a.s. presmerujeme štatutárov aj do predstavenstvo
		self.assertEqual(len(parsed["structured"]["predstavenstvo"]), 2)

		people = parsed["structured"]["statutarny_organ"]
		vyboch = next(p for p in people if p["name"] == "Ing. Pavol Výboch")
		self.assertEqual(vyboch["role"], "Člen predstavenstva")

	def test_parse_spolocnici_supports_mixed_natural_and_legal_entities(self):
		entries = (
			_entry(_person_html(
				name_tokens=["TERRA", "Holding", "GmbH"],
				address_lines=["Fabianistraße 8", "Viedeň 1110"],
				trailing_notes=["Iné identifikačné číslo: FN 314385 g"],
			))
			+ _entry(_person_html(
				name_tokens=["Finance", "Services", "SK", "s.", "r.", "o."],
				address_lines=["Diaľničná cesta 22A", "Senec 903 01"],
				trailing_notes=["IČO: 45 588 678"],
			))
		)
		html = _build_orsr_html(
			oddiel="Sro",
			vlozka="12345/B",
			sections={"Spoločníci": entries},
		)

		parsed = self.parser.parse(html, "45588678")

		self.assertEqual(
			parsed["spolocnici"],
			["TERRA Holding GmbH", "Finance Services SK s. r. o."],
		)
		holding = parsed["structured"]["spolocnici"][0]
		self.assertEqual(holding["ine_id"], "FN 314385 g")

		finance = parsed["structured"]["spolocnici"][1]
		self.assertEqual(finance["person_ico"], "45588678")

	def test_parse_druzstvo_sections(self):
		board = (
			_entry('<span class="ra">predstavenstvo</span>')
			+ _entry(_person_html(
				name_tokens=["Ing.", "Ján", "Novák"],
				address_lines=["Hlavná 1", "Nitra 949 01"],
				vznik="01.01.2024",
			))
		)
		control = _entry(_person_html(
			name_tokens=["Mária", "Kováčová"],
			address_lines=["Vedľajšia 2", "Nitra 949 01"],
			vznik="01.01.2024",
		))
		html = _build_orsr_html(
			oddiel="Dr",
			vlozka="1/N",
			sections={
				"Štatutárny orgán": board,
				"Kontrolná komisia": control,
				"Zapisované základné imanie": _entry('<span class="ra">1 000 EUR</span>'),
				"Základný členský vklad": _entry('<span class="ra">50 EUR</span>'),
			},
		)

		parsed = self.parser.parse(html, "00207306")

		self.assertEqual(parsed["oddiel_type"], "dr")
		self.assertEqual(parsed["predstavenstvo"], ["Ing. Ján Novák"])
		self.assertEqual(parsed["kontrolna_komisia"], ["Mária Kováčová"])
		self.assertEqual(parsed["zapisovane_zakladne_imanie"], "1 000 EUR")
		self.assertIn("50 EUR", parsed["zakladny_clensky_vklad"])

	def test_parse_akciovka_sections(self):
		html = _build_orsr_html(
			oddiel="Sa",
			vlozka="100/B",
			sections={
				"Štatutárny orgán": (
					_entry('<span class="ra">predstavenstvo</span>')
					+ _entry(_person_html(
						name_tokens=["Peter", "Riaditeľ"],
						address_lines=["Adresa 1", "Bratislava 811 01"],
						vznik="01.01.2024",
					))
				),
				"Dozorná rada": _entry(_person_html(
					name_tokens=["Eva", "Dozorcová"],
					address_lines=["Adresa 2", "Bratislava 811 01"],
					vznik="01.01.2024",
				)),
				"Akcie": _entry(
					'<span class="ra">Počet: 100 Druh: kmeňové Forma: akcie na meno '
					'Podoba: listinné Menovitá hodnota: 10 EUR</span>'
				),
			},
		)

		parsed = self.parser.parse(html, "31322832")

		self.assertEqual(parsed["oddiel_type"], "sa")
		self.assertIn("Peter Riaditeľ", parsed["predstavenstvo"])
		self.assertIn("Eva Dozorcová", parsed["dozorna_rada"])
		self.assertEqual(len(parsed["structured"]["akcie"]), 1)
		self.assertIn("kmeňové", parsed["structured"]["akcie"][0]["text"])

	def test_parse_capital_and_contributions(self):
		html = _build_orsr_html(
			oddiel="Sro",
			vlozka="999/B",
			sections={
				"Výška základného imania": _entry(
					'<span class="ra">6 000 EUR Rozsah splatenia: 6 000 EUR</span>',
					od="01.01.2024",
				),
				"Výška vkladu každého spoločníka": _entry(
					'<span class="ra">Peter Novák</span>'
					'<br/><span class="ra">Vklad: 3 000 EUR '
					'( peňažný vklad ) Splatené: 3 000 EUR</span>'
				),
			},
		)

		parsed = self.parser.parse(html, "12345678")

		capital = parsed["structured"]["vyska_zakladneho_imania"]
		self.assertEqual(capital["imanie"], "6 000")
		self.assertEqual(capital["rozsah_splatenia"], "6 000")
		self.assertEqual(capital["currency"], "EUR")

		vklady = parsed["structured"]["vklady_spolocnikov"]
		self.assertEqual(len(vklady), 1)
		self.assertEqual(vklady[0]["name"], "Peter Novák")
		self.assertEqual(vklady[0]["vklad"], "3 000")
		self.assertEqual(vklady[0]["splatene"], "3 000")
		self.assertIn("peňažný", vklady[0]["typ"])


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
		self.assertContains(response, 'admin-theme-button--blue')


class OrsrEligibilityTests(TestCase):
	def test_orsr_eligibility_allows_target_legal_entity(self):
		company = Company.objects.create(
			ruz_id=990001,
			ico='11111111',
			nazov_UJ='Test ORSR s. r. o.',
			pravna_forma='112',
		)

		self.assertTrue(is_orsr_eligible_company(company))

	def test_orsr_eligibility_blocks_sole_trader(self):
		company = Company.objects.create(
			ruz_id=990002,
			ico='22222222',
			nazov_UJ='Test zivnostnik',
			pravna_forma='101',
		)

		self.assertFalse(is_orsr_eligible_company(company))


class FocusModeTests(TestCase):
	"""Ensures enter/exit focus mode disables non-keep PeriodicTasks and revokes running tasks."""

	def setUp(self):
		from django_celery_beat.models import IntervalSchedule, PeriodicTask

		user_model = get_user_model()
		self.user = user_model.objects.create_superuser(
			username='focus_admin',
			email='focus@example.com',
			password='focus_pass123',
		)
		self.schedule = IntervalSchedule.objects.create(
			every=1,
			period=IntervalSchedule.HOURS,
		)
		# 2× keep tasks — should stay enabled.
		self.keep_a = PeriodicTask.objects.create(
			name='orsr-schedule',
			task='registers.tasks.schedule_missing_orsr_sync',
			interval=self.schedule,
			enabled=True,
		)
		self.keep_b = PeriodicTask.objects.create(
			name='financials-schedule',
			task='registers.tasks.schedule_ruz_financials_sync',
			interval=self.schedule,
			enabled=True,
		)
		# 2× non-keep tasks — should get disabled.
		self.drop_a = PeriodicTask.objects.create(
			name='insurance-debts',
			task='registers.tasks.schedule_insurance_debt_checks',
			interval=self.schedule,
			enabled=True,
		)
		self.drop_b = PeriodicTask.objects.create(
			name='ruz-fetch',
			task='registers.tasks.fetch_ruz_data_task',
			interval=self.schedule,
			enabled=True,
		)

	def _patch_inspect(self, active_tasks=None, reserved_tasks=None):
		"""Helper that patches celery inspect/revoke to return deterministic data."""
		active_tasks = active_tasks or {}
		reserved_tasks = reserved_tasks or {}

		fake_inspect = mock.MagicMock()
		fake_inspect.active.return_value = active_tasks
		fake_inspect.reserved.return_value = reserved_tasks
		fake_inspect.scheduled.return_value = {}

		return fake_inspect

	def _patch_celery_control(self, active_tasks=None, reserved_tasks=None):
		"""Combined context manager patching inspect, revoke, and purge calls."""
		fake_inspect = self._patch_inspect(active_tasks, reserved_tasks)
		return (
			mock.patch(
				'registers.services.focus_mode.celery_app.control.inspect',
				return_value=fake_inspect,
			),
			mock.patch(
				'registers.services.focus_mode.celery_app.control.revoke',
			),
			mock.patch(
				'registers.services.focus_mode.celery_app.control.purge',
				return_value=0,
			),
		)

	def test_enter_focus_mode_disables_non_keep_periodic_tasks(self):
		inspect_patch, revoke_patch, purge_patch = self._patch_celery_control()
		with inspect_patch, revoke_patch, purge_patch:
			state = focus_mode_service.enter_focus_mode(self.user)

		self.assertTrue(state.active)
		self.assertEqual(state.activated_by_id, self.user.id)
		self.assertIsNotNone(state.activated_at)

		self.keep_a.refresh_from_db()
		self.keep_b.refresh_from_db()
		self.drop_a.refresh_from_db()
		self.drop_b.refresh_from_db()

		self.assertTrue(self.keep_a.enabled)
		self.assertTrue(self.keep_b.enabled)
		self.assertFalse(self.drop_a.enabled)
		self.assertFalse(self.drop_b.enabled)

		# Snapshot should include both dropped tasks (and only them).
		snapshot_ids = {entry['id'] for entry in state.snapshot}
		self.assertEqual(snapshot_ids, {self.drop_a.id, self.drop_b.id})

	def test_exit_focus_mode_restores_previous_enabled_state(self):
		inspect_patch, revoke_patch, purge_patch = self._patch_celery_control()
		with inspect_patch, revoke_patch, purge_patch:
			focus_mode_service.enter_focus_mode(self.user)
			focus_mode_service.exit_focus_mode(self.user)

		state = SyncFocusModeState.load()
		self.assertFalse(state.active)
		self.assertIsNotNone(state.deactivated_at)

		self.drop_a.refresh_from_db()
		self.drop_b.refresh_from_db()
		self.assertTrue(self.drop_a.enabled)
		self.assertTrue(self.drop_b.enabled)

	def test_enter_focus_mode_is_idempotent(self):
		inspect_patch, revoke_patch, purge_patch = self._patch_celery_control()
		with inspect_patch, revoke_patch, purge_patch:
			first = focus_mode_service.enter_focus_mode(self.user)
			first_activated_at = first.activated_at
			second = focus_mode_service.enter_focus_mode(self.user)

		self.assertEqual(first.pk, second.pk)
		self.assertEqual(second.activated_at, first_activated_at)
		self.assertEqual(SyncFocusModeState.objects.count(), 1)

	def test_revoke_skips_keep_list_tasks(self):
		active_tasks = {
			'worker@host': [
				{'id': 'task-keep-1', 'name': 'registers.tasks.sync_company_orsr_data'},
				{'id': 'task-drop-1', 'name': 'registers.tasks.update_insurance_debt'},
				{'id': 'task-drop-2', 'name': 'registers.tasks.fetch_ruz_data_task'},
			],
		}
		fake_inspect = self._patch_inspect(active_tasks=active_tasks)
		revoke_mock = mock.MagicMock()
		with mock.patch(
			'registers.services.focus_mode.celery_app.control.inspect',
			return_value=fake_inspect,
		), mock.patch(
			'registers.services.focus_mode.celery_app.control.revoke',
			revoke_mock,
		):
			revoked = focus_mode_service.revoke_non_focus_tasks()

		revoked_ids = {item['id'] for item in revoked}
		self.assertEqual(revoked_ids, {'task-drop-1', 'task-drop-2'})
		# revoke called with terminate=True on both non-keep tasks (and only them).
		call_ids = {call.args[0] for call in revoke_mock.call_args_list}
		self.assertEqual(call_ids, {'task-drop-1', 'task-drop-2'})


class FocusModeDashboardTests(TestCase):
	"""Ensures sync_dashboard POST endpoints activate/deactivate focus mode."""

	def setUp(self):
		user_model = get_user_model()
		self.admin_user = user_model.objects.create_superuser(
			username='dashboard_admin',
			email='dashboard@example.com',
			password='dashboard_pass123',
		)
		self.client.force_login(self.admin_user)

	def _patched_service(self):
		"""Patch inspect, revoke, purge + schedule task .delay for any service calls triggered by the view."""
		fake_inspect = mock.MagicMock()
		fake_inspect.active.return_value = {}
		fake_inspect.reserved.return_value = {}
		fake_inspect.scheduled.return_value = {}
		return (
			mock.patch(
				'registers.services.focus_mode.celery_app.control.inspect',
				return_value=fake_inspect,
			),
			mock.patch(
				'registers.services.focus_mode.celery_app.control.revoke',
			),
			mock.patch(
				'registers.services.focus_mode.celery_app.control.purge',
				return_value=0,
			),
			mock.patch('registers.views.schedule_missing_orsr_sync.delay'),
			mock.patch('registers.views.schedule_ruz_financials_sync.delay'),
		)

	def test_enter_focus_mode_via_dashboard(self):
		patches = self._patched_service()
		with patches[0], patches[1], patches[2], patches[3], patches[4]:
			response = self.client.post(
				reverse('registers_sync_dashboard'),
				data={'action': 'enter_focus_mode', 'limit': '100'},
			)
		self.assertEqual(response.status_code, 302)
		self.assertTrue(SyncFocusModeState.load().active)

	def test_exit_focus_mode_via_dashboard(self):
		patches = self._patched_service()
		with patches[0], patches[1], patches[2], patches[3], patches[4]:
			focus_mode_service.enter_focus_mode(self.admin_user)
			response = self.client.post(
				reverse('registers_sync_dashboard'),
				data={'action': 'exit_focus_mode'},
			)
		self.assertEqual(response.status_code, 302)
		self.assertFalse(SyncFocusModeState.load().active)
