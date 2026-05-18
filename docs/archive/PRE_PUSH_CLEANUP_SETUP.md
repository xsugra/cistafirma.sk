# ✅ Pre-Push Cleanup Setup - HOTOVO

## 📦 Čo Bolo Vytvorené

### Hlavné Súbory
1. **`scripts/pre-push-cleanup.sh`** 
   - Vykonateľný bash skript (~200 riadkov)
   - Čistenie lokálnych artefaktov
   - Identifikácia a odstránenie trackovaných súborov z cache
   - Podpora `--dry-run` a `--commit` flags

2. **`scripts/PRE_PUSH_CLEANUP_GUIDE.md`**
   - Podrobný guide (10+ sekcií)
   - Všetky príkazy a príklady
   - Troubleshooting sekcia
   - Best practices

3. **`scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md`**
   - Rýchly reference (1 minúta čítania)
   - Stručný príkaz pre príkaz guide
   - Pro tips

4. **`scripts/README.md`**
   - Orientácia v `scripts/` adresári
   - Index všetkých skriptov

### Makefile Update
- `make clean-pre-push` - Cleanup bez commit-u
- `make clean-pre-push-dry` - Dry-run náhľad (bezpečné)
- `make clean-pre-push-commit` - Cleanup + auto-commit

---

## 🚀 Rýchly Start

```bash
# 1. Náhľad (bez zmien)
make clean-pre-push-dry

# 2. Aplikuj cleanup
make clean-pre-push

# 3. Push
git push
```

---

## 🛠️ Skript Robí 4 Veci

```
[1/4] Vyčistenie lokálnych artefaktov
     (__pycache__, *.pyc, node_modules, .env, .cache, atď.)

[2/4] Identifikácia trackovaných súborov v .gitignore
     (git ls-files -i --exclude-standard)

[3/4] Odstránenie z git cache
     (git rm --cached <file>)

[4/4] Zobrazenie git status
     (čo sa zmilo pred push-om)
```

---

## 📖 Dokumentácia

| Súbor | Použitie |
|-------|---------|
| `PRE_PUSH_CLEANUP_CHEATSHEET.md` | Rýchla referencie (1 min) |
| `PRE_PUSH_CLEANUP_GUIDE.md` | Podrobný guide (10+ min) |
| `README.md` | Orientácia v scripts/ |
| `pre-push-cleanup.sh` | Samotný skript |

---

## ✨ Tri Spôsoby Použitia

### Spôsob 1: S Makefile (Odporúčané)
```bash
make clean-pre-push-dry    # Prehliadka
make clean-pre-push        # Cleanup
git push
```

### Spôsob 2: Priamo Skript
```bash
./scripts/pre-push-cleanup.sh --dry-run
./scripts/pre-push-cleanup.sh
./scripts/pre-push-cleanup.sh --commit
```

### Spôsob 3: Manuálne (bez skriptu)
```bash
# Cleanup lokálnych súborov
find . -type d -name "__pycache__" -delete
find . -type f -name "*.pyc" -delete

# Identifikácia trackovaných súborov
git ls-files -i --exclude-standard

# Odstránenie z cache
git ls-files -i --exclude-standard -z | xargs -0 git rm --cached

# Commit
git add -A && git commit -m "chore: cleanup"
```

---

## 🔍 Overenie

```bash
# Skontroluj zmeny pred push-om
git status
git diff --cached

# Vyrieš conflicts
git diff --cached --name-status

# Push
git push
```

---

## ⚠️ Čo Sa Vyčistí

- Python: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`
- Node: `node_modules/`, `dist/`, `dist-ssr/`, `coverage/`
- Build: `build/`, `dist/`, `*.egg-info/`
- Ostatné: `.cache/`, `.coverage`, `*.log`, `.DS_Store`, `.idea/`, `.vscode/`, `venv/`, `.env`

---

## 💡 Pro Tips

### 1. Git Alias
```bash
git config --global alias.cleanup '!bash scripts/pre-push-cleanup.sh'
git cleanup
```

### 2. Makefile Alias
```bash
alias gitclean='make clean-pre-push'
gitclean
```

### 3. Pre-Push Hook (budúcnosť)
```bash
# .git/hooks/pre-push
#!/bin/bash
bash scripts/pre-push-cleanup.sh --dry-run
```

---

## 🎯 Best Practices

✅ **Správne**
- Vždy spusti `--dry-run` pred aplikáciou
- Skontroluj `git diff --cached`
- Commit cleanup do vlastného commitu
- Udržuj `.gitignore` aktualizovaný

❌ **Nesprávne**
- Nepush-uj bez cleanup
- Netrackovaj `__pycache__`, `node_modules`, `.env`
- Neignoruj chybovky

---

## 📝 Ďalšie Informácie

```bash
# Podrobný guide
cat scripts/PRE_PUSH_CLEANUP_GUIDE.md

# Rýchly reference
cat scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md

# Všetky make targety
make help
```

---

## 🔗 Súvisiace Dokumenty

- `CONTRIBUTING.md` - Contributing pravidlá
- `docs/DEVELOPER_GUIDE.md` - Development setup
- `docs/ARCHITECTURE.md` - Projekt architektúra

---

## ✅ Status

- ✓ Skript vytvorený a testovaný
- ✓ Makefile integrovaný (3 nové targety)
- ✓ Dokumentácia kompletná (3 dokumenty + README)
- ✓ Dry-run test na reálnom projekte - ÚSPEŠNÝ
- ✓ Best practices zdokumentované
- ✓ Troubleshooting príklady
- ✓ Pro tips na optimalizáciu

---

## 🎉 Hotovo!

Teraz môžeš:
```bash
make clean-pre-push-dry    # Prehliadka
make clean-pre-push        # Cleanup
git push                    # Push
```

Alebo skrátene:
```bash
make clean-pre-push-commit && git push
```

---

**Naposledy aktualizované:** 2026-04-18

