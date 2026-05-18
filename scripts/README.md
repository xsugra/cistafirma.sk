# CistaFirma Scripts Directory

> Kolekcia pomocných skriptov pre vývoj a deployment.

## 📁 Obsah

### Pre-Push Cleanup
Čistenie git repozitára pred push-om.

- **`pre-push-cleanup.sh`** - Hlavný skript na cleanup
  - Vymaže lokálne artefakty
  - Identifikuje trackované súbory v .gitignore
  - Urobí `git rm --cached` pre nechtené súbory
  - Zobrazí git status pred push-om

- **`PRE_PUSH_CLEANUP_GUIDE.md`** - Podrobný guide
  - Všetky možnosti a príkazy
  - Troubleshooting
  - Best practices

- **`PRE_PUSH_CLEANUP_CHEATSHEET.md`** - Rýchla referencie
  - Stručný cheat sheet
  - Najčastejšie príkazy
  - Quick start

### Deployment & Kubernetes (`k8s/`)
- `deploy.sh` - Deploy do Kubernetes
- `migrate.sh` - Spustenie migráciám
- `backup_postgres.sh` - Backup databázy
- `restore_postgres.sh` - Restore databázy
- `rollback.sh` - Rollback deploymentu

### Dokumentácia (`docs/`)
- `check_markdown_links.py` - Validácia markdown linkům

---

## 🚀 Rýchly Start

### Pre-Push Cleanup

```bash
# Náhľad zmien (bez aplikácie)
./scripts/pre-push-cleanup.sh --dry-run
make clean-pre-push-dry

# Aplikuj cleanup
./scripts/pre-push-cleanup.sh
make clean-pre-push

# Cleanup + auto-commit
./scripts/pre-push-cleanup.sh --commit
make clean-pre-push-commit
```

**Pozri:** `PRE_PUSH_CLEANUP_CHEATSHEET.md` na rýchlu referenciu

---

## 📖 Dokumentácia

| Skript | Guide | Cheatsheet |
|--------|-------|-----------|
| `pre-push-cleanup.sh` | [PRE_PUSH_CLEANUP_GUIDE.md](PRE_PUSH_CLEANUP_GUIDE.md) | [PRE_PUSH_CLEANUP_CHEATSHEET.md](PRE_PUSH_CLEANUP_CHEATSHEET.md) |

---

## 🔧 Spúšťanie Skriptov

### Z koreňového adresára projektu
```bash
# Cez skript priamo
./scripts/pre-push-cleanup.sh

# Cez Makefile
make clean-pre-push
make clean-pre-push-dry
make clean-pre-push-commit
```

### Z `scripts/` adresára
```bash
cd scripts/
./pre-push-cleanup.sh
bash pre-push-cleanup.sh --dry-run
```

---

## 📝 Makefile Integrácia

V koreňovom `Makefile` sú pridané tieto ciele:

```makefile
make clean-pre-push        # Cleanup bez commit-u
make clean-pre-push-dry    # Dry-run (bez zmien)
make clean-pre-push-commit # Cleanup + auto-commit
```

```bash
make help  # Zobrazí všetky dostupné príkazy
```

---

## 🛠️ Vývoj Skriptov

### Testovanie Skriptu
```bash
# Dry-run
./scripts/pre-push-cleanup.sh --dry-run

# Spustenie s debugom
bash -x ./scripts/pre-push-cleanup.sh

# Kontrola syntax
bash -n ./scripts/pre-push-cleanup.sh
```

### Pridanie Nového Skriptu
1. Vytvor skript v `scripts/`
2. Daj mu `.sh` extension
3. Pridaj `#!/usr/bin/env bash` alebo `#!/usr/bin/env zsh` na začiatok
4. Daj mu execute permissions: `chmod +x scripts/new_script.sh`
5. Fakultatívne: Pridaj do `Makefile` pre ľahší prístup
6. Vytvor dokumentáciu (README alebo GUIDE)

### Shell Version
```bash
# Bash (kompilabilný)
#!/usr/bin/env bash

# ZSH (macOS default, podpouje zsh arrays)
#!/usr/bin/env zsh

# POSIX compatible (maximum compatibility)
#!/bin/sh
```

---

## 📊 Užitočné Príkazy

### Git pre-push kontroly
```bash
# Čo sa zmilo
git status
git diff --cached

# Pred push
git log --oneline origin/main..HEAD
git diff origin/main...HEAD
```

### Cleanup príkazy bez skriptu
```bash
# Python cache
find . -type d -name "__pycache__" -delete
find . -type f -name "*.pyc" -delete

# Git cache
git ls-files -i --exclude-standard -z | xargs -0 git rm --cached
```

---

## 🔗 Related Documentation

- **Projekt README:** [`../README.md`](../README.md)
- **Contributing Guide:** [`../docs/GITFLOW.md`](../docs/GITFLOW.md)
- **Developer Guide:** [`../docs/DEVELOPER_GUIDE.md`](../docs/DEVELOPER_GUIDE.md)
- **Architecture:** [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
- **Kubernetes:** [`./k8s/`](./k8s/)

---

## 💬 Support

- **Otázky o pre-push cleanup?** Pozri [PRE_PUSH_CLEANUP_GUIDE.md](PRE_PUSH_CLEANUP_GUIDE.md)
- **Rýchly reference?** Pozri [PRE_PUSH_CLEANUP_CHEATSHEET.md](PRE_PUSH_CLEANUP_CHEATSHEET.md)
- **Contributing?** Pozri [`../docs/GITFLOW.md`](../docs/GITFLOW.md)
- **Development setup?** Pozri [`../docs/DEVELOPER_GUIDE.md`](../docs/DEVELOPER_GUIDE.md)

---

**Naposledy aktualizované:** 2026-04-18

