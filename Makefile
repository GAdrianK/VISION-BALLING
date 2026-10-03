.PHONY: help api ui all test lint analyze benchmark clean

help:
	@echo "VISION-BALLING (v0.9.0-rc1) - Commandes Make"
	@echo "  make api         - Démarrer l'API FastAPI"
	@echo "  make ui          - Démarrer le frontend React"
	@echo "  make all         - Démarrer API et Frontend simultanément"
	@echo "  make test        - Exécuter la suite complète de tests (backend + frontend)"
	@echo "  make lint        - Contrôler la qualité statique (Ruff + ESLint)"
	@echo "  make benchmark   - Exécuter le benchmark RAG EXP-26"
	@echo "  make clean       - Nettoyer les caches et artefacts temporaires"

api:
	./scripts/start_local.sh api

ui:
	./scripts/start_local.sh ui

all:
	./scripts/start_local.sh all

test:
	./scripts/start_local.sh test

lint:
	./scripts/start_local.sh test

benchmark:
	./scripts/start_local.sh benchmark

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf frontend/dist
