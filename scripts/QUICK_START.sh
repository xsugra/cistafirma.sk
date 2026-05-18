#!/bin/bash
# 🎯 SAFE PUSH QUICK START
# Spustenie: bash QUICK_START.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  CISTAFIRMA - SAFE PUSH QUICK START                        ║"
echo "║  Verzia 1.0 | Production Ready                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Menu
PS3='Vyber akciu: '
options=(
    "Prehliadka (dry-run) - Len náhľad bez zmien"
    "Cleanup - Vyčisti a priprav na push"
    "Cleanup + Commit - Vyčisti a commit zmeny"
    "Git Status - Skontroluj aktuálny stav"
    "Dokumentácia - Otvor action plan"
    "Ukončiť"
)

select opt in "${options[@]}"
do
    case $opt in
        "Prehliadka (dry-run) - Len náhľad bez zmien")
            echo ""
            echo "🔍 Spúšťam dry-run (bez zmien)..."
            echo ""
            make clean-pre-push-dry
            break
            ;;
        "Cleanup - Vyčisti a priprav na push")
            echo ""
            echo "🧹 Spúšťam cleanup..."
            echo ""
            make clean-pre-push
            echo ""
            echo "✅ Cleanup hotový!"
            echo ""
            echo "Ďalšie kroky:"
            echo "  git status         # Skontroluj zmeny"
            echo "  git push           # Push!"
            break
            ;;
        "Cleanup + Commit - Vyčisti a commit zmeny")
            echo ""
            echo "🧹 Spúšťam cleanup s auto-commit..."
            echo ""
            make clean-pre-push-commit
            echo ""
            echo "✅ Cleanup + commit hotový!"
            echo ""
            echo "Ďalší krok:"
            echo "  git push           # Push!"
            break
            ;;
        "Git Status - Skontroluj aktuálny stav")
            echo ""
            echo "📊 Aktuálny git status:"
            echo ""
            git status
            break
            ;;
        "Dokumentácia - Otvor action plan")
            echo ""
            echo "📚 Otvára sa: SAFE_PUSH_ACTION_PLAN.md"
            echo ""
            less SAFE_PUSH_ACTION_PLAN.md || cat SAFE_PUSH_ACTION_PLAN.md
            break
            ;;
        "Ukončiť")
            echo "Zbohom! 👋"
            break
            ;;
        *) echo "Neplatná voľba";;
    esac
done

