from sqlalchemy import Column, Integer, String, Float
from app.database.sql_store import Base

class PlayerMatchStats(Base):
    __tablename__ = "player_match_stats"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String, index=True)          # Ex: "2025_01_22_psg_mancity"
    player_name = Column(String, index=True)       # Ex: "Ousmane Dembélé"
    minutes_played = Column(Integer)
    goals = Column(Integer, default=0)
    expected_goals = Column(Float, default=0.0)    # xG
    expected_assists = Column(Float, default=0.0)  # xA
    key_passes = Column(Integer, default=0)
    progressive_dribbles = Column(Integer, default=0)
    defensive_pressures = Column(Integer, default=0)
