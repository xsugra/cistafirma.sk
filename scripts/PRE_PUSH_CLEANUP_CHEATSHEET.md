# 🧹 CistaFirma Pre-Push Cleanup - Rýchla Referencie

> Stručný cheat sheet pre cleanup git repozitára pred push-om.

## ⚡ Super Rýchlo (1 minúta)

```bash
# 1. Náhľad na zmeny (DRY-RUN)
make clean-pre-push-dry

# 2. Aplikuj cleanup
make clean-pre-push

# 3. Skontroluj výsledok
git status

# 4. Push
git push
```

---

## 🎯 Tri Spôsoby Cleanup

### Spôsob #1: Bez Automatického Commitu
```bash
make clean-pre-push
# alebo
./scripts/pre-push-cleanup.sh
```
**Výsledok:** Vyčistí artefakty, `git rm --cached` pre nechtené súbory.  
**Ďalší krok:** `git add -A && git commit -m "chore: cleanup"`

### Spôsob #2: S Automatickým Commitom
```bash
make clean-pre-push-commit
# alebo
./scripts/pre-push-cleanup.sh --commit
```
**Výsledok:** Cleanup + auto-commit s správou "chore: cleanup tracked files from .gitignore"

### Spôsob #3: Len Náhľad (DRY-RUN)
```bash
make clean-pre-push-dry
# alebo
./scripts/pre-push-cleanup.sh --dry-run
```
**Výsledok:** Zobrazí čo by sa zmilo, ale nezmení nič.  
**Bezpečné:** 100% - žiadne zmeny

---

## 📋 Čo Script Robí

```
[1/4] Vyčistenie lokálnych artefaktov
  - Vymaže: __pycache__/, *.pyc, .pytest_cache/, node_modules/, build/, atď.
  - Vymaže: .cache/, .coverage, *.log, .DS_Store, .idea/, atď.

[2/4] Identifikácia trackovaných súborov
  - Zistí súbory v git, ktoré by mali byť ignorované (podľa .gitignore)

[3/4] Odstránenie z cache
  - Spustí: git rm --cached <file> pre každý nechtený súbor

[4/4] Git status
  - Zobrazí čo sa zmilo pred push-om
```

---

## 🔍 Kontrola Pred Push-om

```bash
# Čo sa zmilo
git status

# Detailný diff
git diff --cached

# Len zoznam zmien
git diff --cached --name-status

# Commit log
git log --oneline -3

# Pred push do remote
git diff origin/main...HEAD
```

---

## 🚀 Kompletný Workflow Pred Push-om

```bash
# 1. Dry-run (bez zmien)
make clean-pre-push-dry

# 2. Prehliadni výstup ✓

# 3. Aplikuj cleanup
make clean-pre-push

# 4. Skontroluj zmeny
git status

# 5. Skontroluj git diff
git diff --cached | less

# 6. Commit (ak sa nevykonal automaticky)
git add -A
git commit -m "chore: cleanup tracked files from .gitignore"

# 7. Finálna kontrola
git log --oneline -3

# 8. Push
git push
```

---

## ⚠️ Čo Sa Vyčistí

### Python Cache
```
__pycache__/
*.pyc, *.pyo, *.pyd
.pytest_cache/
.mypy_cache/
```

### Node/Frontend
```
node_modules/
frontend/dist/
frontend/dist-ssr/
```

### Build Artefakty
```
build/
dist/
*.egg-info/
```

### Ostatné
```
.cache/
.coverage
htmlcov/
.DS_Store
.idea/
.vscode/
*.log
celerybeat-schedule*
dump.rdb
```

---

## 🛡️ Bezpečnosť

✅ **Bezpečné operácie:**
- Vymazáva iba lokálne súbory (v `.gitignore`)
- `git rm --cached` nezmení pracujúci adresár, len cache
- Všetko je možné vrátit cez `git reset`

❌ **Čo script NEZMENÍ:**
- `.env`, `.env.local` - ignoruje automaticky (v `.gitignore`)
- Trackované súbory mimo `.gitignore` - vôbec ich nezmení
- Tvoja pracovná kopie - iba git cache

---

## 🆘 Problémy & Riešenia

### Q: "Did not match any files" chyba
```bash
# Súbor už neexistuje lokálne ale je v cache
git rm --force --cached <file>
```

### Q: Chceš vrátit zmeny
```bash
# Undo všetko pred commit-om
git reset HEAD

# Undo konkrétny súbor
git restore --staged <file>

# Ak si už commitol
git reset --soft HEAD~1
```

### Q: Chceš vidieť čo sa zmení bez aplikácie
```bash
make clean-pre-push-dry
# alebo
./scripts/pre-push-cleanup.sh --dry-run
```

### Q: Script nefunguje
```bash
# Overenie oprávnení
ls -la scripts/pre-push-cleanup.sh

# Priame spustenie
bash scripts/pre-push-cleanup.sh --dry-run

# S debugom
bash -x scripts/pre-push-cleanup.sh --dry-run
```

---

## 📚 Viac Informácií

```bash
# Podrobný guide
cat scripts/PRE_PUSH_CLEANUP_GUIDE.md

# Git status
git status
git status --short

# Git help
git help rm          # git rm help
git help clean       # git clean help
```

---

## 💡 Pro Tips

### 1. Makefile je tvoj priateľ
```bash
make help              # Všetky príkazy
make clean             # Vyčistiť venv
make clean-pre-push    # Pre-push cleanup
```

### 2. Git aliases pre frekventantných príkazov
```bash
git config --global alias.cleanup '!bash scripts/pre-push-cleanup.sh'
git config --global alias.status-short 'status --short'
git cleanup
```

### 3. Pre-push hook (budúcnosť)
```bash
# V .git/hooks/pre-push
#!/bin/bash
bash scripts/pre-push-cleanup.sh --dry-run
```

### 4. Svižnejšie
```bash
# Alias v ~/.zshrc alebo ~/.bashrc
alias gitclean='make clean-pre-push'
alias gitdry='make clean-pre-push-dry'
```

---

## 🔗 Referenčné Príkazy

| Príkaz | Čo robí |
|--------|--------|
| `make clean-pre-push-dry` | Náhľad zmien |
| `make clean-pre-push` | Cleanup bez commit-u |
| `make clean-pre-push-commit` | Cleanup + auto-commit |
| `git ls-files -i --exclude-standard` | Zoznam trackovaných v .gitignore |
| `git rm --cached <file>` | Odstrániť z cache (uchová lokálny súbor) |
| `git status --short` | Kompaktný status |
| `git diff --cached` | Zmeny v stage |

---

## 🎯 Najčastejšia Situácia

**Situácia:** Máš zmeny, chceš push-nut, ale máš viacero `__pycache__`, `.pyc` súborov a iných artefaktov.

**Riešenie:**
```bash
# 1 minúta
make clean-pre-push-commit && git push

# Hotovo! 🎉
```

---

**Otázky?** Pozri [PRE_PUSH_CLEANUP_GUIDE.md](PRE_PUSH_CLEANUP_GUIDE.md)  
**Viac info:** [CONTRIBUTING.md](../../CONTRIBUTING.md)

