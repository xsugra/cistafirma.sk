#!/usr/bin/env zsh
# ==============================================================================
# CistaFirma - Pre-Push Cleanup Script
# ==============================================================================
# Čistí git repozitár pred push-om:
# 1. Vymaže lokálne artefakty (Python cache, node_modules, build, atď.)
# 2. Identifikuje súbory trackované v git, ktoré sú v .gitignore
# 3. Urobí `git rm --cached` pre nechtené súbory
# 4. Zobrazí git status na finálnu kontrolu
#
# Použitie:
#   ./scripts/pre-push-cleanup.sh
#   ./scripts/pre-push-cleanup.sh --dry-run    # Len náhľad, bez zmien
#   ./scripts/pre-push-cleanup.sh --commit     # Automaticky commit zmeny
#
# ==============================================================================


# Farby pre output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Konfigurácia
PROJECT_ROOT="$(cd "$(dirname "$0")/../" && pwd)"
DRY_RUN=false
AUTO_COMMIT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --commit)
      AUTO_COMMIT=true
      shift
      ;;
    *)
      echo "${RED}Neznámy parameter: $1${NC}"
      exit 1
      ;;
  esac
done

cd "$PROJECT_ROOT"

echo "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo "${BLUE}  CistaFirma - Pre-Push Cleanup${NC}"
echo "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"

# ============================================================================
# KROK 1: Vyčistenie lokálnych artefaktov
# ============================================================================
echo ""
echo "${YELLOW}[1/4] Vyčistenie lokálnych artefaktov...${NC}"

cleanup_patterns=(
  ".cache"
  ".pytest_cache"
  ".mypy_cache"
  ".hypothesis"
  "build"
  "dist"
  "*.egg-info"
  "htmlcov"
  ".coverage"
  ".coverage.*"
  "*.log"
  "celerybeat-schedule*"
  "dump.rdb"
  "venv"
  "env"
  ".env"
  ".env.*"
  "node_modules"
  "__pycache__"
  "*.pyc"
  "*.pyo"
  "*.pyd"
  ".DS_Store"
  ".idea"
  ".vscode"
)

# Nájdenie a zmazanie
found_count=0
for pattern in "${cleanup_patterns[@]}"; do
  # Pre konkrétne cesty (napr. venv, .cache, atď.)
  if [ -e "$pattern" ] && [[ ! "$pattern" =~ ".git" ]]; then
    if $DRY_RUN; then
      echo "  [DRY-RUN] Vymazať: $pattern"
    else
      echo "  Vymazať: $pattern"
      rm -rf "$pattern"
    fi
    ((found_count++))
  fi

  # Pre globálne glob vzory (napr. __pycache__)
  if [[ "$pattern" == "__pycache__" ]] || [[ "$pattern" == "*.pyc" ]]; then
    while IFS= read -r dir; do
      if [[ -n "$dir" ]] && [[ ! "$dir" =~ ".git/" ]]; then
        if $DRY_RUN; then
          echo "  [DRY-RUN] Vymazať: $dir"
        else
          echo "  Vymazať: $dir"
          rm -rf "$dir"
        fi
        ((found_count++))
      fi
    done < <(find . -type d -name "$pattern" 2>/dev/null)
  fi
done

if [ $found_count -eq 0 ]; then
  echo "  ${GREEN}✓ Žiadne lokálne artefakty na vymazanie${NC}"
fi

# ============================================================================
# KROK 2: Identifikácia súborov trackovaných v git, ktoré sú v .gitignore
# ============================================================================
echo ""
echo "${YELLOW}[2/4] Identifikácia trackovaných súborov na vymazanie z cache...${NC}"

# Zoznam súborov v .gitignore (trackovaných v git)
tracked_ignored=$(git ls-files -i --exclude-standard 2>/dev/null)

if [ -z "$tracked_ignored" ]; then
  echo "  ${GREEN}✓ Žiadne trackované súbory v .gitignore nenájdené${NC}"
else
  echo "  ${RED}⚠ Nájdené trackované súbory, ktoré majú byť ignorované:${NC}"
  echo "$tracked_ignored" | while read -r file; do
    if [ -n "$file" ]; then
      echo "    - $file"
    fi
  done
fi

# ============================================================================
# KROK 3: Odstrániť trackované súbory, ktoré majú byť v .gitignore
# ============================================================================
echo ""
echo "${YELLOW}[3/4] Odstránenie trackovaných súborov z cache (git rm --cached)...${NC}"

if [ -z "$tracked_ignored" ]; then
  echo "  ${GREEN}✓ Žiadne súbory na odstránenie${NC}"
else
  echo "$tracked_ignored" | while read -r file; do
    if [ -n "$file" ]; then
      if $DRY_RUN; then
        echo "  [DRY-RUN] git rm --cached: $file"
      else
        echo "  git rm --cached: $file"
        git rm --cached "$file" 2>/dev/null || true
      fi
    fi
  done
fi

# ============================================================================
# KROK 4: Git status a návrhy
# ============================================================================
echo ""
echo "${YELLOW}[4/4] Git status pred push-om...${NC}"
echo ""

git status --short

# ============================================================================
# AUTOMATICKÝ COMMIT (ak je flag)
# ============================================================================
if $AUTO_COMMIT && [ -n "$tracked_ignored" ]; then
  echo ""
  echo "${BLUE}Automatický commit zmien...${NC}"
  if ! $DRY_RUN; then
    git add -A
    git commit -m "chore: cleanup tracked files from .gitignore" || true
    echo "${GREEN}✓ Commit vytvorený${NC}"
  fi
fi

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"

if $DRY_RUN; then
  echo "${YELLOW}DRY-RUN MODE - Žiadne zmeny sa nevykonal.${NC}"
  echo ""
  echo "Ak chceš aplikovať zmeny, spusti:"
  echo "  ${GREEN}./scripts/pre-push-cleanup.sh${NC}"
  echo ""
  echo "Alebo s automatickým commitom:"
  echo "  ${GREEN}./scripts/pre-push-cleanup.sh --commit${NC}"
else
  echo "${GREEN}✓ Cleanup hotový!${NC}"
  echo ""
  echo "Ďalšie kroky:"
  echo "  1. Prehliadni zmeny: ${YELLOW}git status${NC}"
  echo "  2. Skontroluj diff: ${YELLOW}git diff --cached${NC}"
  echo "  3. Commit (ak potrebné): ${YELLOW}git commit -m 'chore: cleanup'${NC}"
  echo "  4. Push: ${YELLOW}git push${NC}"
fi

echo "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"

