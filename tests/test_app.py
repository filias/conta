from conta import models


def test_public_pages(client):
    for path in [
        "/",
        "/calendar",
        "/calendar?year=2027",
        "/guides",
        "/guides/fatura-recibo",
    ]:
        assert client.get(path).status_code == 200, path
    ics = client.get("/calendar/public.ics")
    assert ics.mimetype == "text/calendar"
    assert b"BEGIN:VCALENDAR" in ics.data


def test_private_pages_require_login(client):
    for path in [
        "/app/",
        "/app/settings",
        "/app/guides/my-accountant",
        "/app/media/secret.mp4",
    ]:
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.location
    assert b"My accountant" not in client.get("/guides").data
    assert client.post("/app/toggle", data={"key": "efatura"}).status_code == 302


def test_private_feed_needs_token(client):
    assert client.get("/calendar/wrong.ics").status_code == 404
    assert client.get("/calendar/tok3n.ics").status_code == 200


def test_login_and_private_content(logged_in):
    assert logged_in.get("/app/").status_code == 200
    assert b"My accountant" in logged_in.get("/guides").data
    assert b"Call Ana" in logged_in.get("/app/guides/my-accountant").data
    assert logged_in.get("/app/media/secret.mp4").data == b"video"
    assert logged_in.get("/app/media/../guides/my-accountant.md").status_code == 404


def test_wrong_password_is_throttled(client):
    for _ in range(5):
        assert b"Wrong password" in client.post("/login", data={"password": "x"}).data
    assert client.post("/login", data={"password": "x"}).status_code == 429


def test_open_redirect_blocked(client):
    from tests.conftest import PASSWORD

    response = client.post("/login?next=//evil.example", data={"password": PASSWORD})
    assert response.location == "/app/"


def test_toggle_and_settings(logged_in):
    logged_in.post("/app/toggle", data={"key": "efatura", "period": "IRS 2025"})
    assert "efatura/IRS 2025" in models.done_uids()
    logged_in.post("/app/toggle", data={"key": "efatura", "period": "IRS 2025"})
    assert "efatura/IRS 2025" not in models.done_uids()
    assert (
        logged_in.post("/app/toggle", data={"key": "nope", "period": "x"}).status_code
        == 400
    )

    logged_in.post(
        "/app/toggle",
        data={"key": "ss-payment", "period": "Jan 2026", "amount": "1.189,36"},
    )
    assert models.completions()["ss-payment/Jan 2026"].amount == 1189.36

    logged_in.post(
        "/app/settings",
        data={
            "vat": "quarterly",
            "reminder_days": "10, 2",
            "tracking_since": "2026-03-01",
        },
    )
    s = models.get_settings()
    assert s.vat == "quarterly" and not s.social_security
    assert s.lead_days == [10, 2]
