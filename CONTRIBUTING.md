# Prispievanie do `cistafirma`

Dakujeme, ze chces prispiet. Tento dokument definuje standard pre zmeny kodu, dokumentacie a release pripravy.

## 1. Vetvy a flow

- feature prace rob na vetvach `feature/<scope>-<name>`
- urgentne opravy na `hotfix/<scope>-<name>`
- integracia prebieha do `dev`
- produkcne releasy idu cez tagy `vX.Y.Z`

## 2. Povinny standard pre kazdy MR

1. zmena ma jasny ciel a je popisana v MR
2. lokalne prebehla aspon minimalna validacia (build/test/lint podla typu zmeny)
3. dokumentacia je aktualizovana, ak sa meni API, deploy alebo workflow
4. zmena neobsahuje hesla, tokeny ani citlive udaje
5. pri schema/deploy zmene je popisany rollback plan

## 3. Lokalna kontrola pred pushom

```bash
cd /Users/samuelsugra/Code/cistafirma
python3 scripts/docs/check_markdown_links.py
helm lint deploy/helm/cistafirma
```

Podla povahy zmeny dopln:

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm run build
```

```bash
cd /Users/samuelsugra/Code/cistafirma/backend
python manage.py test --verbosity=1
```

## 4. Dokumentacia pri zmenach

Pri zmene API/deploy flow aktualizuj aj relevantne docs:

- `README.md`
- `docs/API_REFERENCE.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/DEVOPS_CICD.md`
- `docs/DEPLOYMENT_RUNBOOK.md`

## 5. Commit a review odporucania

- mensie, tematicke commity su lepsie ako jeden velky dump
- v MR popise uvadzaj **co sa meni**, **preco sa to meni**, **ako to overit**
- pri rizikovej zmene pridaj aj **plan navratu (rollback)**

## 6. Definicia hotovo

MR je pripraveny na merge, ked:

- quality gate v CI prejde,
- reviewer rozumie dopadu zmeny,
- dokumentacia a check-list su kompletne.
