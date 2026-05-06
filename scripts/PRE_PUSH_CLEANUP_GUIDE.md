# Pre-Push Cleanup Guide

> Komplexný guide na prípravu git repozitára pred push-om do vzdialeného úložiska.

## Prečo je cleanup dôležitý?

1. **Zníženie veľkosti repozitára** - Bez cache súborov a build artefaktov
2. **Čistota história** - Bez náhodne trackovaných súborov (`.pyc`, `__pycache__`, `node_modules`)
3. **Bezpečnosť** - Bez `.env` alebo iných citlivých súborov
4. **Vzhl'ad** - Korektný git status pred push-om

## Stav problému

V projekte **cistafirma** môžu byť náhodne trackované súbory:

- Python cache: `__pycache__/`, `*.pyc`, `.mypy_cache/`
- Node cache: `node_modules/`, `dist/`, `build/`
- Systémové súbory: `.DS_Store`, `.idea/`
- Dočasné artefakty: `*.log`, `htmlcov/`, `.coverage`

Tieto súbory sú definované v `.gitignore`, ale keď boli už commitnuté pred pridaním do `.gitignore`, 
git ich naďalej trackuje. Musíme ich **explicitne odstrániť** z cache.

## Rýchly start

### Prehliadka bez zmien (DRY-RUN)

```bash
# Náhľad na to, čo sa zmení
make clean-pre-push-dry
```

Alebo priamo:
```bash
./scripts/pre-push-cleanup.sh --dry-run
```

### Spustenie cleanup

```bash
# Čistenie bez automatického commit-u
make clean-pre-push
```

Alebo:
```bash
./scripts/pre-push-cleanup.sh
```

### Cleanup + Automatický Commit

```bash
# Cleanup a hneď commit zmeny
make clean-pre-push-commit
```

Alebo:
```bash
./scripts/pre-push-cleanup.sh --commit
```

## Krok za krokom

### 1. Skontroluj čo sa zmení

```bash
make clean-pre-push-dry
```

Výstup:
```
═══════════════════════════════════════════════════════════════════════
  CistaFirma - Pre-Push Cleanup
═══════════════════════════════════════════════════════════════════════

[1/4] Vyčistenie lokálnych artefaktov...
  ✓ Žiadne lokálne artefakty na vymazanie

[2/4] Identifikácia trackovaných súborov na vymazanie z cache...
  ⚠ Nájdené trackované súbory, ktoré majú byť ignorované:
    - backend/__pycache__/models.cpython-39.pyc
    - frontend/node_modules/package.json
    - .DS_Store

[3/4] Odstránenie trackovaných súborov z cache (git rm --cached)...
  [DRY-RUN] git rm --cached: backend/__pycache__/models.cpython-39.pyc
  [DRY-RUN] git rm --cached: frontend/node_modules/package.json
  [DRY-RUN] git rm --cached: .DS_Store

[4/4] Git status pred push-om...

D  backend/__pycache__/models.cpython-39.pyc
D  frontend/node_modules/package.json
D  .DS_Store
```

### 2. Aplikuj zmeny

Ak výstup vyzerá OK:

```bash
make clean-pre-push
```

Alebo s automatickým commit-om:

```bash
make clean-pre-push-commit
```

### 3. Verifikácia

```bash
# Skontroluj čo sa zmenilo
git status

# Detailný pohľad na zmeny
git diff --cached

# Skontroluj commits
git log --oneline -5
```

### 4. Push

```bash
git push origin <branch-name>
```

## Manuálny prístup (bez skriptu)

Ak nechceš používať skript, tu je manuálny postup:

### 1. Vyčistenie lokálnych artefaktov

```bash
# Python cache
find . -type d -name "__pycache__" -delete
find . -type f -name "*.pyc" -delete
find . -type d -name ".pytest_cache" -delete
find . -type d -name ".mypy_cache" -delete

# Node cache
rm -rf frontend/node_modules
rm -rf frontend/dist
rm -rf frontend/dist-ssr

# Build artefakty
rm -rf build/ dist/ *.egg-info/

# Ostatné
rm -rf .cache .coverage htmlcov
rm -f dump.rdb celerybeat-schedule*
rm -f .DS_Store
```

### 2. Identifikácia trackovaných súborov v .gitignore

```bash
git ls-files -i --exclude-standard
```

Príklad výstupu:
```
backend/__pycache__/models.cpython-39.pyc
backend/__pycache__/admin.cpython-39.pyc
frontend/node_modules/package.json
.DS_Store
```

### 3. Odstránenie z cache

```bash
# Všetky naraz
git ls-files -i --exclude-standard -z | xargs -0 git rm --cached

# Alebo individuálne
git rm --cached backend/__pycache__/models.cpython-39.pyc
git rm --cached frontend/node_modules/package.json
git rm --cached .DS_Store
```

### 4. Commit

```bash
git add -A
git commit -m "chore: cleanup tracked files from .gitignore"
```

### 5. Push

```bash
git push origin <branch-name>
```

## Užitočné príkazy

### Git status pred push-om

```bash
git status
git status --short

# Len súbory na delete
git status | grep "deleted"
```

### Detailný diff

```bash
# Čo sa zmení
git diff --cached

# Len zoznam súborov
git diff --cached --name-status

# Len stat (počet zmien)
git diff --cached --stat
```

### Undo zmien pred push-om

```bash
# Ak si sa pomýlil a nechceš zmenách
git reset HEAD <file>
git restore --staged <file>

# Alebo všetko
git reset HEAD
```

### Verifikácia pred push-om

```bash
# Skontroluj co sa pushne
git log --oneline origin/main..HEAD

# Porovnaj s remote
git diff origin/main...HEAD

# Počet commitov
git rev-list --count HEAD origin/main..HEAD
```

## Best Practices

### ✅ Pred Push-om

1. **Spusti dry-run cleanup**
   ```bash
   make clean-pre-push-dry
   ```

2. **Prehliadni git status**
   ```bash
   git status
   git diff --cached
   ```

3. **Spusti testy** (ak máš)
   ```bash
   make test
   ```

4. **Spustenie cleanup**
   ```bash
   make clean-pre-push
   ```

5. **Finálna kontrola**
   ```bash
   git status
   git log --oneline -3
   ```

6. **Push**
   ```bash
   git push
   ```

### ❌ Čo sa vyhnúť

- ❌ Trackovanie `.env`, `.env.local` alebo iných sekrét súborov
- ❌ Trackovanie `node_modules/`, `venv/`, `build/`
- ❌ Trackovanie `.pyc`, `__pycache__`, `.DS_Store`
- ❌ Push bez cleanup - veľký repository = pomalý clone

## Troubleshooting

### Problém: `git rm --cached` hovori "did not match any files"

Súbor už bol zmazaný lokálne ale nie z cache.

```bash
# Skúsiť s force
git rm --force --cached <file>

# Alebo resetovať stage
git reset HEAD <file>
```

### Problém: Cleanup zmrazil viacero súborov

To je v poriadku! Git to identifikoval ako delete. Commit zmeny:

```bash
git status

# Vidíš "deleted: file1, deleted: file2, ..."
git add -A
git commit -m "chore: cleanup tracked files from gitignore"
```

### Problém: Nechceš zmazať nejaký súbor z cache

```bash
# Undo zmeny na jednom súbore
git restore --staged <file>

# Alebo pred push-om resetuj konkrétny commit
git reset HEAD~1
```

### Problém: Chceš vidieť celú históriu čo sa zmení

```bash
# Všetky deleted súbory v cache
git diff --cached --name-status | grep "^D"

# Počet deleted súborov
git diff --cached --name-status | grep "^D" | wc -l

# Velkosť cleanup
git diff --cached --stat
```

## Automatizácia (GitHub/GitLab Actions - budúcnosť)

Neskôr by sme mohli pridať pre-push hook alebo CI/CD check:

```bash
# .git/hooks/pre-push (lokálny hook)
#!/bin/bash
bash scripts/pre-push-cleanup.sh --dry-run
```

## Zdroje

- [Git .gitignore dokumentácia](https://git-scm.com/docs/gitignore)
- [Git rm dokumentácia](https://git-scm.com/docs/git-rm)
- [Projekt CONTRIBUTING.md](../CONTRIBUTING.md)
- [Git workflow guide](https://git-scm.com/docs/gittutorial)

---

**Viac otázok?** Pozri [DEVELOPER_GUIDE.md](../docs/DEVELOPER_GUIDE.md) alebo [CONTRIBUTING.md](../CONTRIBUTING.md).

