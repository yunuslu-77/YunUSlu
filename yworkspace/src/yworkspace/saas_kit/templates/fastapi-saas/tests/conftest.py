import re

import pytest
from app import emails
from app.main import create_app
from app.settings import Settings
from fastapi.testclient import TestClient


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path}/test.db", secret_key="test-secret",
                    superadmin_emails=["boss@example.com"], login_rate_per_minute=5)


@pytest.fixture
def client(settings):
    emails.OUTBOX.clear()
    return TestClient(create_app(settings))


def csrf(client, path="/login"):
    html = client.get(path).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def signup(client, email="ayse@example.com", password="guclu-parola-1", org="Ayşe Kuaför"):
    token = csrf(client, "/signup")
    return client.post("/signup", data={"csrf": token, "name": "Ayşe", "email": email, "password": password,
                                        "org_name": org}, follow_redirects=False)


def last_link(path):
    body = emails.OUTBOX[-1].get_content()
    return re.search(rf"(/{path}\?token=[\w-]+)", body).group(1)
