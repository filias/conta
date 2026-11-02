import pytest
from werkzeug.security import generate_password_hash

from conta import create_app

PASSWORD = "correct horse"


@pytest.fixture
def app(tmp_path):
    private = tmp_path / "private"
    (private / "guides").mkdir(parents=True)
    (private / "videos").mkdir()
    (private / "guides" / "my-accountant.md").write_text(
        "---\ntitle: My accountant\nvideo: secret.mp4\n---\nCall Ana."
    )
    (private / "videos" / "secret.mp4").write_bytes(b"video")
    from conta import auth

    auth._failures.clear()
    return create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "PRIVATE_DIR": str(private),
            "ADMIN_PASSWORD_HASH": generate_password_hash(PASSWORD),
            "CALENDAR_TOKEN": "tok3n",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"password": PASSWORD})
    return client
