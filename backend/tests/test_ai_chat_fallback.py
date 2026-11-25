from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_engine


class UnauthorizedResponse:
    status_code = 401

    @staticmethod
    def json():
        return {"error": {"message": "User not found.", "code": 401}}


class UnauthorizedProvider:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        return UnauthorizedResponse()


def test_ai_chat_returns_catalog_matches_when_provider_rejects_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "' test-key '")
    monkeypatch.setattr(ai_engine, "_cached_catalog", lambda: [
        {
            "id": "brake-1",
            "name": "Front Brake Pads",
            "category": "Brake Parts",
            "price": 4200,
            "stock_quantity": 4,
        },
        {
            "id": "brake-2",
            "name": "Rear Brake Pads",
            "category": "Brake Parts",
            "price": 6200,
            "stock_quantity": 3,
        },
        {
            "id": "oil-1",
            "name": "Engine Oil",
            "category": "Lubricants",
            "price": 1800,
            "stock_quantity": 8,
        },
        {
            "id": "brake-out",
            "name": "Brake Disc",
            "category": "Brake Parts",
            "price": 1500,
            "stock_quantity": 0,
        },
    ])
    monkeypatch.setattr(ai_engine.httpx, "AsyncClient", UnauthorizedProvider)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={"messages": [{"role": "user", "content": "Brake pads under KES 5000"}]},
        )

    assert response.status_code == 200
    result = response.json()
    assert "Front Brake Pads (KES 4,200)" in result["reply"]
    assert [product["id"] for product in result["products"]] == ["brake-1"]
    assert "User not found" not in response.text
    assert "401" not in response.text


def test_secret_reader_removes_surrounding_whitespace_and_quotes(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", '  "sample-key"  ')

    assert ai_engine.clean_env_secret("GROQ_API_KEY") == "sample-key"
