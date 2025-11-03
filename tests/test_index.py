import pytest
import json
from app.api.app import app
from unittest.mock import patch
from app.utils.graph import DiagState

# ---------------------------
# Fixtures Flask
# ---------------------------
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# ---------------------------
# Mock JWT valide
# ---------------------------
VALID_JWT = "Bearer faketoken123"

# ---------------------------
# Mock du graphe pour éviter de lancer LLM / BLIP
# ---------------------------
def mock_run(state):
    state.is_plant = True
    state.score = 4.5
    state.disease = "Aucune"
    state.advice = "Arroser régulièrement"
    return state

# ---------------------------
# Test /diag route
# ---------------------------
@patch("app.utils.graph.assistant_graph.run", side_effect=mock_run)
@patch("app.utils.verify_jwt.JWTVerifier.verify_token", return_value={"sub": "user123"})
def test_diag_endpoint(mock_jwt, mock_graph_run, client):
    payload = {
        "image_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_text": "Ma plante a des feuilles jaunes"
    }

    response = client.post(
        "/diag",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json", "Authorization": VALID_JWT}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["image_id"] == payload["image_id"]
    assert data["user_text"] == payload["user_text"]
    assert data["score"] == 4.5
    assert data["disease"] == "Aucune"
    assert data["advice"] == "Arroser régulièrement"

# ---------------------------
# Test sans JWT
# ---------------------------
def test_diag_no_jwt(client):
    payload = {
        "image_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_text": "Ma plante a des feuilles jaunes"
    }

    response = client.post(
        "/diag",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 401
    data = response.get_json()
    assert "JWT invalide" in data["message"]

# ---------------------------
# Test image non plante
# ---------------------------
@patch("app.utils.graph.assistant_graph.run")
@patch("app.utils.verify_jwt.JWTVerifier.verify_token", return_value={"sub": "user123"})
def test_diag_not_plant(mock_jwt, mock_graph_run, client):
    # Simuler un état où is_plant = False
    state = DiagState(
        image_id="123e4567-e89b-12d3-a456-426614174000",
        user_text="Ceci n'est pas une plante",
        is_plant=False
    )
    mock_graph_run.return_value = state

    payload = {
        "image_id": state.image_id,
        "user_text": state.user_text
    }

    response = client.post(
        "/diag",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json", "Authorization": VALID_JWT}
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "ne représente pas une plante" in data["error"]
