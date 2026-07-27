import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ajouter la racine du projet backend au PYTHONPATH pour s'assurer que les imports fonctionnent
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
