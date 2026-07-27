import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings, BASE_DIR

# On résout le chemin absolu de manière robuste
db_path = os.path.abspath(os.path.join(BASE_DIR, "data", "football_iq.db"))
DATABASE_URL = f"sqlite:///{db_path}"

# Le paramètre check_same_thread=False est VITAL pour que FastAPI puisse 
# faire des requêtes en parallèle sans bloquer Uvicorn
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Fonction "Générateur" pour ouvrir/fermer proprement les sessions SQL
def get_sql_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
