# Prispievanie do CistaFirma

Tento dokument popisuje workflow, vetvy, commit konvencie a povinný štandard pre všetky merge requesty v projekte CistaFirma.

## 1. Vetvy a flow

- Feature práce rob na vetvách `feature/<scope>-<name>`.
- Urgentné opravy na `hotfix/<scope>-<name>`.
- **Integračná vetva je `main`.** Vetva `dev` existuje, ale je nečinná — jej
  posledný commit je z 20. 5. 2026 a `main` je odvtedy o ~457 commitov pred ňou.
  Za merge cieľ ju nepovažuj.
- **Release tagy sa nepoužívajú.** Repo nemá ani jeden tag a produkcia sa
  nasadzuje z `main` ručne, takže `vX.Y.Z` popisuje zámer, nie krok, ktorý
  niekto vykonáva.

## 2. Povinný štandard pre každý MR

1. Zmena má jasný cieľ a je popísaná v MR.
2. Lokálne prebehla aspoň minimálna validácia (build/test/lint podľa typu zmeny).
3. Dokumentácia je aktualizovaná, ak sa mení API, deploy alebo workflow.
4. Zmena neobsahuje heslá, tokeny ani citlivé údaje.
5. Pri schéma/deploy zmene je popísaný rollback plán.

## 3. Lokálna kontrola pred pushom

```bash
# z root adresára projektu
python3 scripts/docs/check_markdown_links.py
python3 scripts/docs/check_inline_citations.py
helm lint deploy/helm/cistafirma
```

Podľa povahy zmeny doplň:

```bash
cd frontend
npm run build
```

```bash
cd backend
python manage.py test --verbosity=1
```

## 4. Dokumentácia pri zmenách

Pri zmene API/deploy flow aktualizuj aj relevantné docs:

- `README.md`
- `docs/API_REFERENCE.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/DEVOPS_CICD.md`
- `docs/DEPLOYMENT_RUNBOOK.md`

## 5. Commit a review odporúčania

- Menšie, tematické commity sú lepšie ako jeden veľký dump.
- V MR popise uvádzaj **čo sa mení**, **prečo sa to mení**, **ako to overiť**.
- Pri rizikovej zmene pridaj aj **plán návratu (rollback)**.

## 6. Definícia „hotovo"

MR je pripravený na merge, keď:

- Quality gate v CI prejde.
- Reviewer rozumie dopadu zmeny.
- Dokumentácia a check-list sú kompletné.
