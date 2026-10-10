"""Suite-wide guard: tests use disposable storage and mocked HTTP only."""
import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import database
from app.main import app
from app.modules import ml_classifier


@pytest.fixture(autouse=True)
def isolated_default_database_and_network(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'suite.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def get_db():
        with sessions() as session:
            yield session
    previous = app.dependency_overrides.get(database.get_db)
    # Specialized test fixtures may replace this with their own isolated session.
    if previous is None:
        app.dependency_overrides[database.get_db] = get_db
    monkeypatch.setattr(database, "init_db", lambda: None)
    monkeypatch.setattr(ml_classifier, "MODEL_PATH", str(tmp_path / "model.joblib"))
    def deny_network(*args, **kwargs):
        raise AssertionError("Real HTTP is disabled in tests; supply a mock.")
    monkeypatch.setattr(requests.sessions.Session, "request", deny_network)
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(database.get_db, None)
        engine.dispose()
