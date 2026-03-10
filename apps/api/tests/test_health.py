import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get('/health')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['service'] == 'api'
    assert 'environment' in body


def test_livez_endpoint() -> None:
    response = client.get('/livez')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_readyz_endpoint() -> None:
    response = client.get('/readyz')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] in {'ok', 'degraded'}
    assert body['checks']['api'] == 'ok'
    assert body['checks']['database'] in {'sqlite-ok', 'down'}


def test_request_id_header_is_returned() -> None:
    response = client.get('/health')

    assert response.status_code == 200
    assert 'x-request-id' in response.headers


def test_ui_dashboard_page() -> None:
    response = client.get('/ui/')

    assert response.status_code == 200
    assert 'Hybrid AI Marketing SaaS' in response.text


def test_root_endpoint_message() -> None:
    response = client.get('/')

    assert response.status_code == 200
    assert response.json()['message'] == 'Open /ui for dashboard'
