import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from app.modules import ml_classifier as ml


@pytest.fixture
def model(monkeypatch):
    pipeline = Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
                         ('clf', LogisticRegression(random_state=42))])
    pipeline.fit(['python software testing', 'software code python',
                  'research scientific papers', 'scientific research methods'],
                 ['Software Engineer', 'Software Engineer', 'Researcher', 'Researcher'])
    monkeypatch.setattr(ml, 'get_model', lambda: pipeline)
    return pipeline


@pytest.mark.parametrize('text', ['', '   ', 'zxqv unmatchedword'])
def test_insufficient_text_has_no_prior_role(model, text):
    result = ml.predict_role(text, 'Researcher')
    assert result['prediction_status'] == 'insufficient_evidence'
    assert result['probabilities'] == {}
    assert result['predicted_role'] == 'Undetermined'
    assert not result['matches_target']


@pytest.mark.parametrize('text', ['python software testing', 'python research scientific software'])
def test_distribution_and_deterministic_vocabulary(model, text):
    result = ml.predict_role(text, 'software engineer')
    assert result == ml.predict_role(text, 'software engineer')
    assert result['confidence'] == result['probabilities'][result['predicted_role']]
    assert result['target_benchmark_probability'] == result['probabilities']['Software Engineer']
    assert result['feature_explanation_method'] == 'matching_vocabulary'
    assert 'calibrated' in result['note']
    assert result['top_features']


def test_load_or_training_failure_is_unavailable(monkeypatch):
    def fail():
        raise FileNotFoundError('synthetic missing dataset')
    monkeypatch.setattr(ml, 'get_model', fail)
    assert ml.predict_role('python')['prediction_status'] == 'unavailable'


def test_corrupt_model_inference_is_unavailable(monkeypatch):
    monkeypatch.setattr(ml, 'get_model', lambda: object())
    assert ml.predict_role('python')['model_available'] is False
