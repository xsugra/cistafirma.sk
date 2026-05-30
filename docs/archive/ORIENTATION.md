# 🗺️ ORIENTÁCIA - Kde Čítať a Ako Začať

**Verzia:** 1.0 | **Dátum:** 2026-04-18 | **Status:** ✅ Ready

---

## 🚀 HNEĎ! (2 MINÚTY)

```bash
# Spusť interaktívne menu a vyber akciu
# Použi Makefile namiesto QUICK_START.sh (súbor už neexistuje):
make clean-pre-push

# Hotovo! 🎉
```

---

## 📌 BEZ DLHÉHO ČÍTANIA (5 MINÚT)

**Otvoriť v editore/termináli:**
```bash
# Praktický action plan - ZAČNI SEM! ⭐
cat SAFE_PUSH_ACTION_PLAN.md

# Alebo v editore:
open SAFE_PUSH_ACTION_PLAN.md
```

**Alebo spustiť priamo:**
```bash
make clean-pre-push-dry      # Prehliadka
make clean-pre-push          # Cleanup
git push                      # Push
```

---

## 📚 PODĽA SITUÁCIE

### "Chcem hneď Začať"
👉 **`MASTER_GUIDE.md`** (5 min)

### "Chcem Praktické Info"
👉 **`SAFE_PUSH_ACTION_PLAN.md`** (3-5 min) ⭐

### "Chcem Kompletný Checklist"
👉 **`INTEGRATION_CHECKLIST.md`** (10 min)

### "Chcem Detailný Guide"
👉 **`scripts/PRE_PUSH_CLEANUP_GUIDE.md`** (15 min)

### "Chcem Rýchlu Referenciu"
👉 **`scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md`** (1-2 min)

### "Chcem Vedieť Čo Sa Vytvorilo"
👉 **`PRE_PUSH_CLEANUP_SETUP.md`** (5 min)

---

## 🎯 SPUSTENIE

### Spôsob 1: Menu (Najjednoduchšie)
```bash
# Použi Makefile namiesto QUICK_START.sh (súbor už neexistuje):
make clean-pre-push
```

### Spôsob 2: Makefile (Odporúčané)
```bash
make clean-pre-push-dry
make clean-pre-push
git push
```

### Spôsob 3: Skript (Priame)
```bash
./scripts/pre-push-cleanup.sh --dry-run
./scripts/pre-push-cleanup.sh
git push
```

---

## 🗂️ KOMPLETNÝ ZOZNAM SÚBOROV

### Dokumentácia (Root Adresár)
```
├── MASTER_GUIDE.md                    ⭐ START SEM (5 min)
├── SAFE_PUSH_ACTION_PLAN.md          ⭐ PRAKTICKÝ NÁHĽAD (3-5 min)
├── INTEGRATION_CHECKLIST.md          ✓ Kompletný checklist (10 min)
├── PRE_PUSH_CLEANUP_SETUP.md         ✓ Setup info (5 min)
└── scripts/pre-push-cleanup.sh          ✓ Cleanup skript
```

### Dokumentácia (Scripts)
```
scripts/
├── pre-push-cleanup.sh                ✓ Main cleanup skript
├── PRE_PUSH_CLEANUP_GUIDE.md         ✓ Podrobný guide (15 min)
├── PRE_PUSH_CLEANUP_CHEATSHEET.md    ✓ Rýchla ref (1-2 min)
└── README.md                          ✓ Scripts index
```

### Konfigurácia
```
├── Makefile                           ✓ +3 targety
└── .gitignore                         ✓ Audítovaný
```

---

## 🎓 VZDELÁVACIA CESTA

### Level 1: Absolútny Začiatočník
1. Čítaj: `MASTER_GUIDE.md` (5 min)
2. Spusti: `make clean-pre-push`
3. Vyber: "Prehliadka"
4. ✅ Hotovo

### Level 2: Chceš Vedieť Detaily
1. Čítaj: `SAFE_PUSH_ACTION_PLAN.md` (3-5 min)
2. Spusti: `make clean-pre-push-dry`
3. Čítaj: Output a skontroluj zmeny
4. Spusti: `make clean-pre-push`
5. ✅ Hotovo

### Level 3: Power User
1. Čítaj: `INTEGRATION_CHECKLIST.md` (10 min)
2. Čítaj: `scripts/PRE_PUSH_CLEANUP_GUIDE.md` (15 min)
3. Spusti: `./scripts/pre-push-cleanup.sh --dry-run`
4. Spusti: `./scripts/pre-push-cleanup.sh --commit`
5. ✅ Hotovo

### Level 4: Expert (Inžinier)
1. Čítaj: `scripts/PRE_PUSH_CLEANUP_GUIDE.md` (15 min)
2. Čítaj: Bash skript (212 riadkov)
3. Počítaj git aliasy
4. Nastavuj git hooks
5. ✅ Master

---

## ⏱️ ČAS ČÍTANIA PODĽA SITUÁCIE

```
Keď Sa Ponáhľaš:         ⏱️ 2-3 min
  └─ # Použi Makefile namiesto QUICK_START.sh (súbor už neexistuje):
make clean-pre-push

Keď Máš 5 Minút:         ⏱️ 5 min
  └─ cat SAFE_PUSH_ACTION_PLAN.md

Keď Máš 10 Minút:        ⏱️ 10 min
  └─ cat INTEGRATION_CHECKLIST.md

Keď Máš 20 Minút:        ⏱️ 20 min
  └─ cat scripts/PRE_PUSH_CLEANUP_GUIDE.md

Keď Máš Čas:             ⏱️ 30 min
  └─ Prečítaj Všetko
```

---

## 🎯 NAJDÔLEŽITEJŠIE PRÍKAZY

```bash
# Spustiť interactive menu
# Použi Makefile namiesto QUICK_START.sh (súbor už neexistuje):
make clean-pre-push

# Prehliadka bez zmien
make clean-pre-push-dry

# Cleanup
make clean-pre-push

# Cleanup + Commit
make clean-pre-push-commit

# Push
git push
```

---

## ✨ ČOMU VERIŤ

- ✅ Všetko je automatizované
- ✅ Dry-run je 100% bezpečný
- ✅ Všetky zmeny sú reversible (v git)
- ✅ Dokumentácia je kompletná
- ✅ Testované a overené

---

## 🆘 PROBLÉM?

**"Neviem ako začať"**
→ Čítaj: `MASTER_GUIDE.md`

**"Neviem čo skript robí"**
→ Čítaj: `SAFE_PUSH_ACTION_PLAN.md`

**"Chcem vedieť detaily"**
→ Čítaj: `INTEGRATION_CHECKLIST.md`

**"Potrebujem rýchlu referenciu"**
→ Čítaj: `scripts/PRE_PUSH_CLEANUP_CHEATSHEET.md`

**"Chcem všetko vedieť"**
→ Čítaj: `scripts/PRE_PUSH_CLEANUP_GUIDE.md`

---

## 📝 NAJČASTEJŠIE OTÁZKY

### Q: Koľko času to trvá?
A: Spustenie <1 min, čítanie 5-15 min

### Q: Je to bezpečné?
A: Áno! Dry-run test bez zmien. Všetko reversible.

### Q: Čím začať?
A: `make clean-pre-push` alebo `cat SAFE_PUSH_ACTION_PLAN.md`

### Q: Čo keď niečo pôjde zle?
A: `git reflog` a `git reset --hard`

### Q: Kde je dokumentácia?
A: V tomto súbore + v `scripts/` + v root adresári

---

## 🚀 POSLEDNÝ KROK

```bash
# Vyber Jeden:

# Najrýchlejšie
# Použi Makefile namiesto QUICK_START.sh (súbor už neexistuje):
make clean-pre-push

# Alebo Priamo
make clean-pre-push-dry && make clean-pre-push && git push

# Alebo Skript
./scripts/pre-push-cleanup.sh --dry-run
./scripts/pre-push-cleanup.sh
git push
```

---

## 📊 SUMMARY

```
Súborov:        9 (4 nové v root, 3 v scripts, 2 skripty)
Riadkov:        1500+
Čas Čítania:    5-30 min (podľa úrovne)
Čas Spustenia:  <1 minúta
Komplexnosť:    LOW (bezpečný)
Status:         ✅ Production Ready
```

---

## 🎉 HOTOVO!

Teraz si pripravený! Vyber svoj spôsob a začni:

1. **Interaktívne:** `make clean-pre-push`
2. **Makefile:** `make clean-pre-push-dry`
3. **Čítanie:** `cat SAFE_PUSH_ACTION_PLAN.md`

Veľa úspechov pri push-ovaní! 🚀

---

**Status:** ✅ Production Ready  
**Verzia:** 1.0  
**Dátum:** 2026-04-18


