# Archív dokumentácie

Historické dokumenty. **Nie sú zdrojom pravdy** — sú tu preto, aby sa zachoval
kontext a aby sa dalo dohľadať, odkiaľ sa vzali rozhodnutia. Pri rozpore medzi
archívom a kódom platí **kód**.

Ako sa sem dostali: konsolidácia z 2026-09-18 (úloha #169) zlúčila jednorazové
pracovné záznamy z koreňa repa do kanonických dokumentov a zvyšok presunula sem.
Koreň repa tak drží len `README.md`, `CLAUDE.md` a `AGENTS.md`.

> **Pozor na tvrdenia v týchto dokumentoch.** Väčšina z nich končí vetou
> „production ready / complete / ✅", ktorú kód nepotvrdzuje. Čo presne je
> vyvrátené, je zmerané v [`docs/PLAN.md` → § 8 Nálezy z konsolidácie
> dokumentácie](../PLAN.md#8-nálezy-z-konsolidácie-dokumentácie-2026-09-18).
> Než z niektorého z nich niečo použiješ, prečítaj si tú sekciu.

## Firmy / SZCO

| Dokument | Čo v ňom je |
|---|---|
| [`FIRMY_SZCO_ARCHITECTURE.md`](FIRMY_SZCO_ARCHITECTURE.md) | PRO/CON odôvodnenie troch design decisions, ASCII diagramy toku |
| [`FIRMY_SZCO_IMPLEMENTATION.md`](FIRMY_SZCO_IMPLEMENTATION.md) | Implementačný záznam (duplikát, pozri dokument nižšie) |
| [`FIRMY_SZCO_QUICK_START.md`](FIRMY_SZCO_QUICK_START.md) | Payloady `ruz_full_firmy` / `ruz_full_szco`, pasca NULL/995 |
| [`README_FIRMY_SZCO_IMPLEMENTATION.md`](README_FIRMY_SZCO_IMPLEMENTATION.md) | Odkaz na `verify_implementation.sh`, troubleshooting |
| [`RUZ_SYNC_ENTITY_SEPARATION_COMPLETE.md`](RUZ_SYNC_ENTITY_SEPARATION_COMPLETE.md) | **Otvorená dátová diera**: chýbajúca migrácia SZCO riadkov z legacy tabuľky |
| [`ADMIN_PANEL_PROFESSIONAL_GUIDE.md`](ADMIN_PANEL_PROFESSIONAL_GUIDE.md) | Jednostranný záznam o admin triedach — zlúčené do [`DEVELOPER_GUIDE.md`](../DEVELOPER_GUIDE.md) § 9 |
| [`ADMIN_DEPLOYMENT_GUIDE.md`](ADMIN_DEPLOYMENT_GUIDE.md) | 16-bodová DO/DON'T politika syncu, troubleshooting „Running bez progresu" |
| [`ADMIN_IMPLEMENTATION_COMPLETE.md`](ADMIN_IMPLEMENTATION_COMPLETE.md) | Zdôvodnenie zrkadlových tabuliek a runtime klasifikácie |

**Vyvrátené v týchto dokumentoch:** „Can run both simultaneously" (sync je
serializovaný jedným globálnym kľúčom), „starting from 2000-01-01" (tlačidlo
FULL robí inkrementálny prechod), API `/api/sync/start/` a tlačidlá „Full
Companies / Full Individuals" (neexistujú), index `idx_sync_type_status`
(neexistuje). Podrobne `docs/PLAN.md` § 8.3–8.5.

## Výkon

| Dokument | Čo v ňom je |
|---|---|
| [`PERFORMANCE_OPTIMIZATION.md`](PERFORMANCE_OPTIMIZATION.md) | 4 indexy ↔ migrácia `companies/0015`; `pg_indexes` overovací dotaz |
| [`PERFORMANCE_FIX_ACTION_PLAN.md`](PERFORMANCE_FIX_ACTION_PLAN.md) | Akčný plán; **obsahuje dnes zakázaný `make docker-reset`** |
| [`PERFORMANCE_FIX_SUMMARY.md`](PERFORMANCE_FIX_SUMMARY.md) | Súhrn |
| [`PERFORMANCE_FIX_EXPLANATION.md`](PERFORMANCE_FIX_EXPLANATION.md) | Vysvetlenie + `diagnostic.py` a očakávaný podpis výstupu |
| [`COMBINED_FILTER_FIX_COMPLETE.md`](COMBINED_FILTER_FIX_COMPLETE.md) | Kombinovaný filter — zlúčené do [`PLAN.md`](../PLAN.md) § 8.1 |
| [`COMPLETION_REPORT.md`](COMPLETION_REPORT.md) | Záverečný report |
| [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) | Tahák |
| [`DEPLOYMENT_PLAN.md`](DEPLOYMENT_PLAN.md) | Rollback so zoznamom dotknutých súborov, `git check-ignore -v` recept |

**Vyvrátené:** čísla `30,000x`, `1500%`, `100-1000x`, `~100-200 companies/second`
a `> 90% coverage` sú odhady alebo tvrdenia bez merania — test na reálnych
1,2 mil. firmách sa nikdy nestal (vlastné checklisty týchto dokumentov majú
kroky nezaškrtnuté). `migrate companies 0014` ako „rollback bez zmeny dát" je
nepravda — reverz 0016–0019 zahodí dátové stĺpce. Podrobne § 8.6 a § 8.1.

## Lead scoring a právne formy

| Dokument | Čo v ňom je |
|---|---|
| [`LEAD_SCORING_IMPLEMENTATION.md`](LEAD_SCORING_IMPLEMENTATION.md) | „Performance Characteristics" (~100–200 firiem/s, ~50 MB) — nepodložené |
| [`LEAD_SCORING_CHECKLIST.md`](LEAD_SCORING_CHECKLIST.md) | Checklist s nezaškrtnutými krokmi; tvrdenie „> 90% coverage" je nepodložené |
| [`LEGAL_FORMS_IMPLEMENTATION_COMPLETE.md`](LEGAL_FORMS_IMPLEMENTATION_COMPLETE.md) | Právne formy: testy, metriky, i18n — stav i18n je v ňom už opravený (2026-09-18) |

## Pre-push cleanup

Zjednodušené do [`scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md`](../../scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md).

- [`MASTER_GUIDE.md`](MASTER_GUIDE.md) — jediné miesto v repe s pravidlom „NIE `git add -A`", blokom `git stash` a prácou s `ORIG_HEAD`
- [`SAFE_PUSH_ACTION_PLAN.md`](SAFE_PUSH_ACTION_PLAN.md)
- [`SAFE_PUSH_COMPLETE.md`](SAFE_PUSH_COMPLETE.md)
- [`PRE_PUSH_CLEANUP_SETUP.md`](PRE_PUSH_CLEANUP_SETUP.md)
- [`ORIENTATION.md`](ORIENTATION.md) — rozcestník; jeho zmienky o `scripts/QUICK_START.sh` sú opravené

## Setup dokumenty

- [`setup/quickstart.md`](setup/quickstart.md)
- [`setup/config.md`](setup/config.md)
- [`setup/development-setup.md`](setup/development-setup.md)
- [`setup/setup-verification.md`](setup/setup-verification.md)
- [`setup/start-here.md`](setup/start-here.md)
- [`setup/env-architecture.md`](setup/env-architecture.md)
- [`setup/env-refactoring-summary.md`](setup/env-refactoring-summary.md)

## Poznámky

- [`notes/backend-fix-summary.md`](notes/backend-fix-summary.md)

## Kam namiesto toho

- [`docs/README.md`](../README.md) — rozcestník živej dokumentácie
- [`docs/PLAN.md`](../PLAN.md) — plán prác, nálezy a nemenné pravidlá
- [`docs/DATA_PROTECTION.md`](../DATA_PROTECTION.md) — dátová bezpečnosť
- [`docs/SOURCE_DATA_INTEGRITY.md`](../SOURCE_DATA_INTEGRITY.md) — integrita zdrojových dát
