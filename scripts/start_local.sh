#!/usr/bin/env bash
# ==============================================================================
# VISION-BALLING Local Startup & Tooling Script (RC1)
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Select Python binary
if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ]; then
    PY="$PYTHON_BIN"
elif [ -d "$PROJECT_ROOT/.venv-training" ]; then
    PY="$PROJECT_ROOT/.venv-training/bin/python"
elif [ -d "$PROJECT_ROOT/backend/.venv" ]; then
    PY="$PROJECT_ROOT/backend/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    PY="$PROJECT_ROOT/.venv/bin/python"
else
    PY="python3"
fi

COMMAND="${1:-help}"

case "$COMMAND" in
    api|backend)
        echo "==> Démarrage de l'API FastAPI VISION-BALLING sur http://127.0.0.1:8000..."
        exec "$PY" -m uvicorn app.main:app --app-dir backend --reload --port 8000
        ;;

    ui|frontend)
        echo "==> Démarrage du frontend React/Vite sur http://localhost:5173..."
        cd frontend
        exec npm run dev
        ;;

    all|dev)
        echo "==> Démarrage simultané API + Frontend..."
        "$PY" -m uvicorn app.main:app --app-dir backend --reload --port 8000 &
        BACKEND_PID=$!
        cd frontend
        npm run dev &
        FRONTEND_PID=$!
        trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
        wait
        ;;

    test)
        echo "==> Exécution de la suite de tests et des vérifications de qualité..."
        "$PY" -m ruff check backend
        "$PY" -m pytest backend/tests -q
        (cd frontend && npm run lint && npm run build)
        echo "==> Tous les contrôles de qualité sont validés avec succès."
        ;;

    analyze)
        VIDEO_PATH="$2"
        MODE="${3:-QUALITY}"
        if [ -z "$VIDEO_PATH" ]; then
            echo "Erreur: spécifiez le chemin de la vidéo. Exemple:"
            echo "  $0 analyze path/to/match.mp4 [QUALITY|LOW_LATENCY]"
            exit 1
        fi
        echo "==> Lancement de l'analyse vidéo complète en mode $MODE..."
        exec "$PY" scripts/run_full_video_analysis.py --input "$VIDEO_PATH" --mode "$MODE"
        ;;

    benchmark)
        echo "==> Exécution du benchmark formel RAG et ancrage de preuves..."
        exec "$PY" scripts/tactics/run_exp26_benchmark.py
        ;;

    *)
        echo "=================================================================="
        echo " VISION-BALLING (v0.9.0-rc1) — Commande d'Exécution Locale"
        echo "=================================================================="
        echo "Usage: $0 [COMMANDE] [OPTIONS]"
        echo ""
        echo "Commandes disponibles :"
        echo "  api                  Démarrer l'API FastAPI (port 8000)"
        echo "  ui                   Démarrer l'interface React/Vite (port 5173)"
        echo "  all                  Démarrer API et UI conjointement"
        echo "  test                 Exécuter les tests backend, ruff, lint frontend et build"
        echo "  analyze <video> [m]  Lancer l'analyse complète d'une vidéo (QUALITY ou LOW_LATENCY)"
        echo "  benchmark            Exécuter le benchmark de grounding RAG EXP-26"
        echo "=================================================================="
        ;;
esac
