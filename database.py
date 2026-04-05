from sqlalchemy import create_engine, Column, String, Integer, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# This creates a file called interview.db in your project folder
DATABASE_URL = "sqlite:///./interview.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


# Table 1: Sessions
class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    role = Column(String)


# Table 2: Evaluations
class EvaluationModel(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String)
    question = Column(String)
    score = Column(Integer)
    feedback = Column(String)
    weakness = Column(String)


# Create all tables
Base.metadata.create_all(bind=engine)