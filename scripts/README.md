# CistaFirma — `scripts/`

Pomocné skripty pre vývoj, deployment a **prevádzku dát** (zálohy, off-site
replikácia, restore drilly, ops gate).

> **Oprava 2026-09-18** (konsolidácia dokumentácie, #169): tento README bol
> neúplný a čiastočne zastaraný. Dokumentoval **6** zo **39** trackovaných
> súborov a adresár `scripts/local/` (24 súborov) nespomínal vôbec, hoci práve
> v ňom žije celá zálohovacia a prevádzková logika. Zároveň odkazoval na K8s
> cestu bez upozornenia, že nie je nasadená. Prepísané nižšie.

## Štruktúra

| Adresár | Súborov | Čo tam je |
|---|---|---|
| `scripts/` | 6 | pre-push cleanup + generovanie favicon |
| `scripts/docs/` | 1 | audit interných odkazov v markdown |
| `scripts/k8s/` | 8 | K8s/Helm deploy — **nenasadené**, viď nižšie |
| `scripts/local/` | 15 | zálohy, off-site, restore drilly, ops gate |
| `scripts/local/lib/` | 6 | knižnica, ktorú `scripts/local/` zdiela |
| `scripts/local/systemd/` | 2 | `.service` + `.timer` šablóny (Linux) |
| `scripts/local/launchd/` | 1 | `.plist` šablóna (macOS) |

**Väčšinu z toho nemusíš volať priamo** — `Makefile` a `CLAUDE.md` na ne majú
cielené príkazy (`make db-backup`, `make db-restore-drill`, `make ops-check`, …).
Tie sú primárny spôsob; skripty sú implementácia pod nimi.

---

## `scripts/local/` — prevádzka dát

Toto je najdôležitejšia časť adresára a do 2026-09-18 nebola zdokumentovaná.

| Skript | Účel |
|---|---|
| `scheduled_backup.sh` | Beh naplánovanej zálohy (volá ho launchd/systemd) |
| `backup_postgres.sh` | Vlastný `pg_dump` |
| `verify_postgres_backup.sh` | Overenie dumpu — kontrola archívu a checksumu |
| `restore_postgres_drill.sh` | **Izolovaný** restore do dočasného kontajnera; zapisuje rekord do `restore_drills.log` |
| `replicate_postgres_backup.sh` | Kópia dumpu na off-site |
| `prune_postgres_backups.sh` | Retencia (drží najnovších 7) |
| `offsite_status.sh` | Read-only stav off-site pripravenosti vrátane veku drillu |
| `offsite_key_drill.sh` | Overenie, že off-site kľúč sa dá naozaj použiť |
| `configure_offsite.sh` | Zapíše off-site cestu do `~/.config/cistafirma/backup.env` |
| `gpg_backup_key.sh` | Práca s GPG kľúčom záloh |
| `install_backup_schedule.sh` / `uninstall_backup_schedule.sh` | Inštalácia/odstránenie plánovača |
| `backup_schedule_status.sh` | Či plánovač naozaj beží |
| `ops_check.sh` | **Jediný read-only gate** cez celý ochranný príbeh (`make ops-check`) |
| `cleanup_mac_docker.sh` | Čistenie Dockeru na Macu (nie je súčasť záloh) |

`lib/` (`backup_env.sh`, `backup_gpg.sh`, `backup_log.sh`, `backup_os.sh`,
`backup_time.sh`, `offsite_crypto.sh`) je zdieľaná knižnica — `backup_env.sh`
je ten, vďaka ktorému funguje aj **launchd job**, ktorý štartuje takmer bez
prostredia.

`systemd/` a `launchd/` sú dve implementácie toho istého plánovača pre dva
systémy: Mac používa launchd, `dell` (Ubuntu) systemd.

> ⚠️ **Pred čímkoľvek nad dátami si prečítaj
> [`docs/DATA_PROTECTION.md`](../docs/DATA_PROTECTION.md).** Nikdy
> `docker compose down -v`, `docker volume rm/prune`, `make docker-reset` ani
> restore nad bežiacou databázou `cistafirma`. Restore patrí do izolovaného
> cieľa — `make db-restore-drill`.

---

## `scripts/` — pre-push cleanup

Čistenie pracovného stromu pred push-om.

- **`pre-push-cleanup.sh`** — hlavný skript
  - vyčistí lokálne artefakty,
  - nájde súbory trackované napriek `.gitignore`,
  - spraví `git rm --cached` pre nechcené súbory,
  - zobrazí `git status` pred push-om.
- **`PRE_PUSH_CLEANUP_GUIDE.md`** — podrobný guide (možnosti, troubleshooting).
- **`PRE_PUSH_CLEANUP_CHEATSHEET.md`** — rýchla referencia.
- **`QUICK_START.sh`** — interaktívne menu nad tými istými `make` cieľmi.
- **`generate-favicons.py`** — generovanie favicon sád pre frontend.

> ⚠️ **`pre-push-cleanup.sh` maže `.env`.** V `cleanup_patterns` sú `".env"`,
> `".env.*"`, `"venv"` aj `"env"` a telo skriptu na ne púšťa
> `rm -rf "$pattern"` **bez potvrdenia** (`scripts/pre-push-cleanup.sh:71-99`).
> Jediná poistka je `--dry-run`. Keďže `.env` v tomto projekte drží `SECRET_KEY`,
> `DATABASE_URL` a ďalšie tajomstvá, **vždy najprv**
> `make clean-pre-push-dry` a prečítaj si výpis. Poistku proti `.env` skript nemá.

### Spustenie

```bash
# z koreňa repa
make clean-pre-push-dry     # náhľad, nič nemení
make clean-pre-push         # aplikuj
make clean-pre-push-commit  # aplikuj + commit
```

Skript má shebang `#!/usr/bin/env zsh` (používa zsh arrays). Overenie syntaxe:
`bash -n scripts/pre-push-cleanup.sh`.

---

## `scripts/docs/` — audit dokumentácie

- **`check_markdown_links.py`** — overí interné markdown odkazy a kotvy.
  Spúšťa ho `make docs-audit` aj CI job `docs_audit`.

```bash
make docs-audit   # EXIT 0 = všetky odkazy sedia
```

---

## `scripts/k8s/` — nenasadené

> ⚠️ **Táto cesta nebeží.** Neexistuje klaster. Produkcia na `dell` beží cez
> `docker compose` z koreňa repa. `deploy/helm/cistafirma/` (chart) aj tieto
> skripty sú **kontrakt pre budúcnosť**, nie dnešný deploy flow —
> viď [`docs/DEPLOYMENT_CONTRACT.md`](../docs/DEPLOYMENT_CONTRACT.md).

| Skript | Účel |
|---|---|
| `deploy.sh` | Migračný job → overlay → rollout status |
| `migrate.sh` | Iba migračný job (+ namespace) |
| `rollback.sh` | Rollback deploymentu |
| `helm-deploy.sh` | Helm `upgrade --install` s `--set` pre image repozitáre |
| `backup_postgres.sh` | Backup cez `pg_dump` |
| `restore_postgres.sh` | ⚠️ **`pg_restore --clean --if-exists` — deštruktívny, bez poistky** |
| `local_registry.sh` | Lokálny registry pre kind |
| `validate_helm_runtime.py` | Kontrola oboch renderov (beží v CI) |

Dve veci, ktoré pri `deploy.sh` treba vedieť:

- **`BACKEND_RESOLVER` je povinný** — adresa clusterového DNS pre nginx
  (kubeadm/kind `10.96.0.10`, k3s `10.43.0.10`). Bez neho skript skončí
  `exit 1` (`scripts/k8s/deploy.sh:23-28`).
- **`migrate.sh` neaplikuje `configmap.yaml`**, hoci `deploy.sh` áno
  (`scripts/k8s/migrate.sh:23,25` vs `deploy.sh:64`).

> `restore_postgres.sh` spúšťa `--clean` proti databáze, ktorú mu dáš cez `DB_*`,
> nemá `--dry-run` a neoveruje cieľ. V tomto repozitári plati „nikdy restore nad
> bežiacou `cistafirma`" — použi `make db-restore-drill`.

---

## Pridanie nového skriptu

1. Vytvor skript v `scripts/` (alebo v podadresári, ak patrí k téme).
2. Pridaj `#!/usr/bin/env sh` (POSIX, najkompatibilnejšie), `bash` alebo `zsh`
   podľa potreby. `sh` preferuj, ak nepotrebuješ bash/zsh rozšírenia.
3. `chmod +x scripts/novy_skript.sh`
4. Ak je to operácia, ktorú má človek volať → pridaj `make` cieľ do `Makefile`
   a riadok do `CLAUDE.md`.
5. Ak pracuje s dátami → zapíš ho aj do `docs/DATA_PROTECTION.md`.

---

## Related

- [`../CLAUDE.md`](../CLAUDE.md) — príkazy a dátové pravidlá (začni tu)
- [`../docs/DATA_PROTECTION.md`](../docs/DATA_PROTECTION.md) — zálohy, RPO/RTO, incident response
- [`../docs/DEVOPS_CICD.md`](../docs/DEVOPS_CICD.md) — dnešný deploy flow
- [`../docs/DEVELOPER_GUIDE.md`](../docs/DEVELOPER_GUIDE.md) — lokálny setup
- [`../docs/GITFLOW.md`](../docs/GITFLOW.md) — contributing
- [`k8s/`](./k8s/) — nenasadená K8s cesta

## Git remoty

Kanonický remote je **`gitlab-home`** (self-hosted, SSH). `origin` je GitHub.
Po pushi over oba; `gitlab-home/main` a `origin/main` sa majú držať na tom
istom commite.

```bash
git log --oneline gitlab-home/main..HEAD   # čo je pred nami
git diff gitlab-home/main...HEAD           # čo je v nich
```

> Pozor: `git log origin/main..HEAD` je v tomto repe zavádzajúce — live vetva
> a pracovný strom bývajú pred `main`. Produkcia (`dell`) ale **beží z `main`**;
> do 2026-09-18 mala vycheckoutovanú `feat/ai-ready-baseline`, tá je však len
> *predkom* `main` (0 vlastných commitov), takže obe mená ukazujú na tú istú
> líniu.

---

**Naposledy aktualizované:** 2026-09-18
