# 🎯 SAFE PUSH STRATÉGIA - MASTER GUIDE

**Status:** ✅ **HOTOVO K PRODUKCII**  
**Verzia:** 1.0  
**Dátum:** 2026-04-18  
**Projekt:** CistaFirma.sk

---

## 📌 RÝCHLY START (Bez Čítania)

```bash
# Spusť interactive menu
bash QUICK_START.sh

# Vyber "Prehliadka" → "Cleanup" → "git push"
# HOTOVO! ✅
```

**Alebo priamo:**
```bash
make clean-pre-push-dry    # Prehliadka
make clean-pre-push        # Cleanup
git push                   # Push!
```

---

## 🗂️ SÚBORY VYTVORENÉ (nový setup)

### Dokumentácia (4 nové/aktualizované súbory)

| # | Súbor | Veľkosť | Účel | Čas Čítania |
|---|-------|---------|------|-------------|
| 1 | `SAFE_PUSH_ACTION_PLAN.md` | 300+ riadkov | ⭐ **Praktický action plan** | 3-5 min |
| 2 | `INTEGRATION_CHECKLIST.md` | 350+ riadkov | **Kompletný checklist + guide** | 10 min |
| 3 | `PRE_PUSH_CLEANUP_SETUP.md` | 228 riadkov | Setup info a overview | 5 min |
| 4 | `scripts/PRE_PUSH_CLEANUP_GUIDE.md` | 250+ riadkov | Podrobný technický guide | 15 min |
| 5 | `scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md` | 100+ riadkov | Rýchla referencie | 1-2 min |
| 6 | `scripts/README.md` | 50+ riadkov | Scripts directory index | 2 min |

### Skripty (2 súbory)

| # | Súbor | Veľkosť | Typ | Status |
|---|-------|---------|-----|--------|
| 1 | `scripts/pre-push-cleanup.sh` | 212 riadkov | Bash/Zsh | ✅ Executable |
| 2 | `QUICK_START.sh` | ~120 riadkov | Interactive Menu | ✅ Executable |

### Konfigurácia (2 aktualizované súbory)

| # | Súbor | Zmeny | Status |
|---|-------|-------|--------|
| 1 | `Makefile` | +3 targety (clean-pre-push-*) | ✅ Integrovaný |
| 2 | `.gitignore` | Audítovaný (97 riadkov) | ✅ Aktuálny |

---

## 🎯 AKO POUŽÍVAŤ

### Možnosť 1: Interaktívne Menu (NAJJEDNODUCHŠIE)
```bash
bash QUICK_START.sh

# Vyberieš z menu:
# 1. Prehliadka (dry-run)
# 2. Cleanup
# 3. Cleanup + Commit
# 4. Git Status
# 5. Dokumentácia
# 6. Ukončiť
```

### Možnosť 2: Makefile (ODPORÚČANÉ)
```bash
# Prehliadka bez zmien
make clean-pre-push-dry

# Vykonaj cleanup
make clean-pre-push

# Alebo cleanup + auto-commit
make clean-pre-push-commit

# Potom
git push
```

### Možnosť 3: Priame Skripty
```bash
# Prehliadka
./scripts/pre-push-cleanup.sh --dry-run

# Cleanup
./scripts/pre-push-cleanup.sh

# Cleanup + Commit
./scripts/pre-push-cleanup.sh --commit
```

### Možnosť 4: Manuálne (bez skriptu)
```bash
# Cleanup
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -rf .cache .pytest_cache node_modules dump.rdb

# Identifikuj a odstráň tracked files z .gitignore
git ls-files -i --exclude-standard -z | xargs -0 git rm --cached

# Commit a push
git add -A
git commit -m "chore: cleanup tracked files from .gitignore"
git push
```

---

## 📚 DOKUMENTÁCIA - KTORÚ ČÍTAŤ

### Podľa Situácie:

**Keď chceš hneď začať (1 minúta):**
```bash
bash QUICK_START.sh
```

**Keď potrebuješ praktické info (3-5 minút):**
```bash
# Najlepšia referencie!
cat SAFE_PUSH_ACTION_PLAN.md | less
```

**Keď chceš kompletný checklist (10 minút):**
```bash
cat INTEGRATION_CHECKLIST.md | less
```

**Keď chceš podrobný technický guide (15 minút):**
```bash
cat scripts/PRE_PUSH_CLEANUP_GUIDE.md | less
```

**Keď potrebuješ iba rýchlu referenciu (1-2 minúty):**
```bash
cat scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md | less
```

**Keď chceš vedieť čo sa vytvorilo:**
```bash
cat PRE_PUSH_CLEANUP_SETUP.md | less
```

---

## 🔑 KĽÚČOVÉ POJMY

### Čo Je "Safe Push"?

```
Bezpečný push bez:
  ❌ nechcených trackovaných súborov
  ❌ lokálnych artefaktov (__pycache__, node_modules, atď.)
  ❌ chyby alebo nekonzistencie v histórii

S:
  ✅ Prehliadkou zmien pred push-om
  ✅ Automatizovaným cleanup-om
  ✅ Reversible zmenami (git history)
```

### Čo Skript Robí?

```
[1/4] Lokálne Cleanup
      Mazáva: __pycache__, *.pyc, node_modules, .env, atď.

[2/4] Identifikácia Tracked Files
      Hľadá: Súbory v git cache ale v .gitignore

[3/4] Removal z Cache
      Vykonáva: git rm --cached

[4/4] Git Status
      Zobrazuje: Čo sa zmení
```

---

## ✨ NAJDÔLEŽITEJŠIE BODY

### ✅ Správne Spustenie

1. **Vždy spusť `--dry-run` najprv**
   ```bash
   make clean-pre-push-dry
   ```
   → Vidíš čo sa bude meniť bez zmien

2. **Čítaj Output Pozorne**
   → Skontroluj či sa nemažú dôležité súbory

3. **Spusť Cleanup**
   ```bash
   make clean-pre-push
   ```

4. **Verifikuj Zmeny**
   ```bash
   git status --short
   git diff --cached
   ```

5. **Push**
   ```bash
   git push
   ```

### ❌ Čoho Sa Vyhnúť

- Nepush-uj bez cleanup
- Netrackovaj `__pycache__`, `node_modules`, `.env`
- Neignoruj output skriptu
- Nepreskakovaj dry-run krok

---

## 🎓 EDUKAČNÁ SEKCIA

### Typy Nechcených Súborov

```
Python Cache & Build:
  __pycache__/
  *.pyc, *.pyo, *.pyd
  .pytest_cache/
  .mypy_cache/
  build/
  dist/
  *.egg-info/

Node.js & Frontend:
  node_modules/
  frontend/dist/
  frontend/dist-ssr/
  coverage/

Build Artifacts:
  build/
  dist/
  htmlcov/
  .coverage*

Sekretné Súbory:
  .env
  .env.*

Runtime Artifacts:
  .cache/
  *.log
  dump.rdb
  celerybeat-schedule*

IDE & Editor:
  .idea/
  .vscode/
  .DS_Store

Virtual Environments:
  venv/
  env/
  .venv/
```

### Prečo Je To Dôležité?

```
Problem:
  • Trackované súbory sú väčšie na push
  • Môžu obsahovať lokálne paths
  • Braniť merge-om na iných dev machines

Solution:
  • Cleanup pred push-om
  • Skript automatizuje proces
  • .gitignore zabezpečuje aby sa neopakoval
```

---

## 🛠️ POKROČILÉ FUNKCIE

### Git Alias Setup (Voliteľne)

```bash
# Globálne aliasy
git config --global alias.cleanup '!bash scripts/pre-push-cleanup.sh'
git config --global alias.cleanup-dry '!bash scripts/pre-push-cleanup.sh --dry-run'
git config --global alias.cleanup-commit '!bash scripts/pre-push-cleanup.sh --commit'

# Potom môžeš používať:
git cleanup-dry
git cleanup
git cleanup-commit
```

### Shell Alias Setup (Voliteľne)

```bash
# Pridaj do ~/.zshrc
echo 'alias gitclean="make clean-pre-push"' >> ~/.zshrc
source ~/.zshrc

# Potom:
gitclean
```

### Git Hook Setup (Budúcnosť)

```bash
# .git/hooks/pre-push (budúcnosť)
#!/bin/bash
bash scripts/pre-push-cleanup.sh --dry-run
```

---

## 📊 WORKFLOW DIAGRAM

```
┌──────────────────────────────────────────────────────┐
│ Začáť Development                                    │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Pracuj na code  │
        │ (features)      │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────────────────┐
        │ Chceš Push-núť?             │
        └────────┬────────────────────┘
                 │
                 ▼
        ┌──────────────────────────────────┐
        │ bash QUICK_START.sh              │
        │ ALEBO                            │
        │ make clean-pre-push-dry          │
        └────────┬───────────────────────┘
                 │
                 ▼
        ┌──────────────────────────┐
        │ Čítaj Output             │
        │ (Skontroluj zmeny)       │
        └────────┬─────────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ make clean-pre-push    │
        │ ALEBO                  │
        │ ./scripts/...sh        │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ git status             │
        │ git diff --cached      │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ git push               │
        │ ✅ HOTOVO!             │
        └────────────────────────┘
```

---

## 🐛 TROUBLESHOOTING

### Q: "Chyba: Skript nenašiel git"
```bash
# Skontroluj či je git nainštalovaný
which git
git --version

# Ak nie, nainštaluj:
brew install git  # na macOS
apt install git   # na Ubuntu/Debian
```

### Q: "Permission denied na QUICK_START.sh"
```bash
# Urob skript executable
chmod +x QUICK_START.sh
chmod +x scripts/pre-push-cleanup.sh

# Potom spusti
bash QUICK_START.sh
```

### Q: "Nechcel som mazať ten súbor!"
```bash
# Neboj sa, git drží všetko
git reflog
git checkout HEAD@{x}
git reset --hard ORIG_HEAD
```

### Q: "Skript je pomalý"
```bash
# Je to normálne, čistí všetky artefakty
# Normálne treba <1 minútu

# Ak je príliš pomalý:
# - Skontroluj disk space
# - Skontroluj disk speed
# - Spusti make clean-pre-push-dry len na prehliadku
```

---

## 🎯 QUICK REFERENCE

| Čo Chceš | Príkaz | Čas |
|----------|--------|-----|
| **Prehliadka** | `make clean-pre-push-dry` | <10s |
| **Cleanup** | `make clean-pre-push` | <1min |
| **Cleanup+Commit** | `make clean-pre-push-commit` | <1min |
| **Menu** | `bash QUICK_START.sh` | 30s |
| **Git Status** | `git status` | <1s |
| **Push** | `git push` | 1-10s |

---

## 📈 STATISTICS

```
Dokumentácia:     1000+ riadkov
Skripty:          350+ riadkov
Makefile:         3 nové targety
Gitignore:        97 riadkov
Čas na Learn:     5-10 minút
Čas na Run:       <1 minúta
Files Created:    6 nové súbory
Complexity:       Low (bezpečný)
```

---

## ✅ FINAL CHECKLIST

- [x] Skript vytvorený (212 riadkov)
- [x] Makefile integrovaný (3 targety)
- [x] Dokumentácia kompletná (6 súborov)
- [x] Dry-run test úspešný
- [x] Interactive menu hotový
- [x] Best practices zdokumentované
- [x] Troubleshooting príklady
- [x] Pro tips na optimalizáciu
- [x] Integration checklist
- [x] Ready for production! 🚀

---

## 🚀 POSLEDNÝ KROK

### Teraz Môžeš Spustiť:

```bash
# Najjednoduchšie - Interactive Menu
bash QUICK_START.sh

# Alebo - Makefile
make clean-pre-push-dry
make clean-pre-push
git push

# Alebo - Priamo
./scripts/pre-push-cleanup.sh --dry-run
./scripts/pre-push-cleanup.sh
git push
```

---

## 📞 SUPPORT & ĎALŠIE INFO

**Potrebuješ čítať:**
- `SAFE_PUSH_ACTION_PLAN.md` - Praktický náhľad ⭐
- `INTEGRATION_CHECKLIST.md` - Kompletný checklist
- `scripts/PRE_PUSH_CLEANUP_GUIDE.md` - Podrobný guide
- `scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md` - Rýchla ref.

**Potrebuješ spustiť:**
- `bash QUICK_START.sh` - Interactive menu
- `make clean-pre-push-dry` - Prehliadka
- `make clean-pre-push` - Cleanup
- `git push` - Push

**Potrebuješ sa učiť:**
- Čítaj `scripts/PRE_PUSH_CLEANUP_GUIDE.md`
- Skúšaj `make clean-pre-push-dry`

---

## 🎉 HOTOVO!

**Congratulations!** 🎊

Máš kompletný "safe push" setup:
- ✅ Automatizovaný skript
- ✅ Jednoduchý Makefile interface
- ✅ Interactive menu
- ✅ Kompletná dokumentácia
- ✅ Best practices guide
- ✅ Troubleshooting help

**Teraz môžeš bezpečne push-núť! 🚀**

```bash
bash QUICK_START.sh
# alebo
make clean-pre-push-dry && make clean-pre-push && git push
```

---

**Status:** ✅ Production Ready  
**Verzia:** 1.0  
**Dátum:** 2026-04-18  
**Projekt:** CistaFirma.sk

Viac otázok? Čítaj dokumentáciu v `scripts/` alebo `SAFE_PUSH_ACTION_PLAN.md` 📖



## Príkazy na zapamätanie (do budúcna)

  ### 1. Vytvorenie novej branch
  git checkout -b feature/nazov main        # nová branch z main
  git checkout -b feature/B feature/A       # nová branch z inej branch (závislosť)

  ### 2. Pridanie konkrétnych súborov (NIE git add -A)
  git add subor1.py subor2.py dir/

  ### 3. Commit
  git commit -m "feat(app): popis zmeny"

  ### 4. Prvý push (nastaví tracking na remote)
  git push -u gitlab feature/nazov

  ### 5. Ďalšie pushe na tej istej branch
  git push

  ### 6. Prepnutie medzi branches
  git checkout main                          # späť na main
  git checkout feature/nazov                 # na existujúcu branch

  ### 7. Stash — dočasné uloženie rozpracovaných zmien
  git stash push -u -m "popis"              # ulož všetko (aj untracked)
  git stash apply                            # obnov (stash zostane)
  git stash pop                              # obnov a vymaž stash


