"""Verify worker isolation, responsive health and no persistence after deadline."""
import importlib
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import database
from app.modules import ml_classifier

main = importlib.import_module("app.main")
INPUT = {"benchmark_identity": "AI Engineer", "visibility_level": "Privacy Focused", "linkedin_text": "Python developer"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def get_db():
        with sessions() as session:
            yield session
    main.app.dependency_overrides[database.get_db] = get_db
    monkeypatch.setattr(ml_classifier, "predict_role", lambda *args, **kwargs: {"model_available": False})
    try:
        with TestClient(main.app) as client:
            yield client, sessions
    finally:
        main.app.dependency_overrides.pop(database.get_db, None)
        engine.dispose()


def test_health_responds_while_analysis_worker_is_blocked(api, monkeypatch):
    client, _ = api
    original = main._build_report
    started, release = threading.Event(), threading.Event()
    def blocked(*args):
        started.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(main, "_build_report", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        analysis = pool.submit(client.post, "/api/analyze", data=INPUT)
        try:
            assert started.wait(2)
            health = pool.submit(client.get, "/api/health")
            assert health.result(timeout=2).status_code == 200
        finally:
            release.set()
        assert analysis.result(timeout=5).status_code == 200


def test_deadline_returns_without_saving_late_worker_result(api, monkeypatch):
    client, sessions = api
    original = main._build_report
    release, finished = threading.Event(), threading.Event()
    def blocked(*args):
        assert release.wait(5)
        try:
            return original(*args)
        finally:
            finished.set()
    monkeypatch.setattr(main, "ANALYSIS_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(main, "_build_report", blocked)
    try:
        response = client.post("/api/analyze", data=INPUT)
        assert response.status_code == 504
        with sessions() as db:
            assert db.query(database.Report).count() == 0
    finally:
        release.set()
        assert finished.wait(5)
    with sessions() as db:
        assert db.query(database.Report).count() == 0


def test_model_exception_keeps_rule_report_and_avoids_logging_source(api, monkeypatch, caplog):
    client, _ = api
    def failed(*args, **kwargs):
        raise RuntimeError("private-profile-value")
    monkeypatch.setattr(ml_classifier, "predict_role", failed)
    response = client.post("/api/analyze", data=INPUT)
    assert response.status_code == 200
    report = response.json()
    assert report["ml_prediction"]["model_available"] is False
    assert "python" in report["benchmark_comparison"]["matched_skills"]
    assert report["recommendations"]
    assert "private-profile-value" not in response.text + caplog.text


def test_worker_never_receives_a_database_session(api, monkeypatch):
    client, _ = api
    original = main._build_report
    def inspected(*args):
        assert len(args) == 7
        assert not any(isinstance(item, database.SessionLocal.class_) for item in args)
        return original(*args)
    monkeypatch.setattr(main, "_build_report", inspected)
    assert client.post("/api/analyze", data=INPUT).status_code == 200
