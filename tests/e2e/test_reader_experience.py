"""E2E tests: public preview, writers catalog, feed/archival, webhook, audit."""
from __future__ import annotations

import jwt

from backend.src.shared.config import get_settings


def _auth(client, token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client, email: str) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201, resp.get_json()


def _login(client, email: str) -> dict:
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).get_json()


def _user_id(token: str) -> str:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])["sub"]


def _publish(client, writer_token: str, title: str, preview: str, full: str) -> str:
    post_id = client.post(
        "/api/v1/posts",
        json={"title": title, "preview_content": preview, "subscriber_content": full},
        headers=_auth(client, writer_token),
    ).get_json()["id"]
    resp = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(client, writer_token))
    assert resp.status_code == 200, resp.get_json()
    return post_id


class TestReaderExperience:
    def test_public_preview_and_catalog(self, client):
        _register(client, "pub-w@test.com")
        wt = _login(client, "pub-w@test.com")["access_token"]
        post_id = _publish(client, wt, "Hello", "PREVIEW", "FULL")

        # Unauthenticated single-post read: preview only
        resp = client.get(f"/api/v1/posts/{post_id}")
        assert resp.status_code == 200
        assert resp.get_json()["preview_content"] == "PREVIEW"
        assert resp.get_json()["subscriber_content"] is None

        # Missing post -> RFC7807 404 envelope
        resp = client.get("/api/v1/posts/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["code"] == "NOT_FOUND"
        assert body["status"] == 404
        assert body["title"] == "Not Found"
        assert body["detail"] == body["message"]

        # Writers catalog (public)
        resp = client.get("/api/v1/writers")
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1
        resp = client.get("/api/v1/writers?q=pub-w")
        assert any("pub-w" in w["email"] for w in resp.get_json()["writers"])

        # Writer detail unauthenticated: posts masked
        writer_id = _user_id(wt)
        resp = client.get(f"/api/v1/writers/{writer_id}")
        assert resp.status_code == 200
        posts = resp.get_json()["posts"]
        assert len(posts) == 1
        assert posts[0]["subscriber_content"] is None

        # Bad writer id -> 404 envelope
        resp = client.get("/api/v1/writers/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "NOT_FOUND"

    def test_feed_and_archival(self, client):
        _register(client, "feed-w@test.com")
        wt = _login(client, "feed-w@test.com")["access_token"]
        old_id = _publish(client, wt, "Old Post", "OLD-PRE", "OLD-FULL")
        new_id = _publish(client, wt, "New Post", "NEW-PRE", "NEW-FULL")

        _register(client, "feed-r@test.com")
        rt = _login(client, "feed-r@test.com")["access_token"]

        # No allocation -> empty feed
        resp = client.get("/api/v1/posts/feed", headers=_auth(client, rt))
        assert resp.get_json()["posts"] == []

        client.post("/api/v1/subscriptions/subscribe", json={}, headers=_auth(client, rt))
        client.post(
            "/api/v1/subscriptions/allocations/assign",
            json={"writer_id": _user_id(wt)},
            headers=_auth(client, rt),
        )

        # Feed has both posts with full content (archival included)
        resp = client.get("/api/v1/posts/feed", headers=_auth(client, rt))
        posts = resp.get_json()["posts"]
        assert {p["id"] for p in posts} == {old_id, new_id}
        assert all(p["subscriber_content"] is not None for p in posts)
        assert all(p["has_full_access"] for p in posts)

        # Single old (archived) post readable in full
        resp = client.get(f"/api/v1/posts/{old_id}", headers=_auth(client, rt))
        assert resp.get_json()["subscriber_content"] == "OLD-FULL"


class TestRoleInference:
    """Roles are inferred from activity, never chosen at signup."""

    def test_register_grants_no_roles_and_ignores_role_field(self, client):
        # A client-sent role is ignored for backwards compatibility.
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "norole@test.com", "password": "password123", "role": "writer"},
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["email"] == "norole@test.com"
        assert "roles" not in body

        tokens = _login(client, "norole@test.com")
        resp = client.get("/api/v1/auth/me", headers=_auth(client, tokens["access_token"]))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["is_writer"] is False
        assert body["is_reader"] is False

    def test_first_post_grants_writer(self, client):
        _register(client, "new-writer@test.com")
        wt = _login(client, "new-writer@test.com")["access_token"]

        # Any authenticated user may create a first post (no prior WRITER needed).
        resp = client.post(
            "/api/v1/posts",
            json={"title": "First", "preview_content": "PRE", "subscriber_content": "FULL"},
            headers=_auth(client, wt),
        )
        assert resp.status_code == 201, resp.get_json()

        resp = client.get("/api/v1/auth/me", headers=_auth(client, wt))
        assert resp.get_json()["is_writer"] is True

        # Inferred writer shows up in the public catalog.
        resp = client.get("/api/v1/writers?q=new-writer")
        assert any("new-writer" in w["email"] for w in resp.get_json()["writers"])

    def test_subscribe_and_follow_grant_reader(self, client):
        _register(client, "inf-w@test.com")
        wt = _login(client, "inf-w@test.com")["access_token"]
        _publish(client, wt, "P", "PRE", "FULL")

        _register(client, "inf-r@test.com")
        rt = _login(client, "inf-r@test.com")["access_token"]

        client.post("/api/v1/subscriptions/subscribe", json={}, headers=_auth(client, rt))
        resp = client.get("/api/v1/auth/me", headers=_auth(client, rt))
        assert resp.get_json()["is_reader"] is True

        client.post(
            "/api/v1/subscriptions/allocations/assign",
            json={"writer_id": _user_id(wt)},
            headers=_auth(client, rt),
        )
        resp = client.get("/api/v1/auth/me", headers=_auth(client, rt))
        assert resp.get_json()["is_reader"] is True


class TestWebhookAndAudit:
    def test_webhook_route_and_allocation_log(self, client):
        from sqlalchemy import text

        from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork

        _register(client, "wh-w@test.com")
        wt = _login(client, "wh-w@test.com")["access_token"]
        writer_id = _user_id(wt)

        _register(client, "wh-r@test.com")
        rt = _login(client, "wh-r@test.com")["access_token"]
        client.post("/api/v1/subscriptions/subscribe", json={}, headers=_auth(client, rt))

        # Public webhook, Stripe shape with unknown id: accepted, no crash
        resp = client.post(
            "/api/v1/subscriptions/webhook",
            json={"type": "invoice.payment_failed", "data": {"object": {}}},
        )
        assert resp.status_code == 200
        assert resp.get_json() == {"received": True}

        _register(client, "wh-w2@test.com")
        wt2 = _login(client, "wh-w2@test.com")["access_token"]
        post_id = _publish(client, wt, "WH Post", "WH-PRE", "WH-FULL")
        client.post(
            "/api/v1/subscriptions/allocations/assign",
            json={"writer_id": writer_id},
            headers=_auth(client, rt),
        )

        # Internal shape with real subscription id
        with SqlAlchemyUnitOfWork() as uow:
            from backend.src.subscriptions.adapters.sqlalchemy_repository import (
                SqlAlchemySubscriptionRepository,
            )

            repo = SqlAlchemySubscriptionRepository(uow.session)
            sub = repo.get_by_reader(__import__("uuid").UUID(_user_id(rt)))
            ext_id = sub.external_subscription_id

        client.post(
            "/api/v1/subscriptions/webhook",
            json={
                "event_type": "invoice.payment_failed",
                "payload": {"subscription_id": ext_id},
            },
        )
        # past_due loses subscriber access (behavioral)
        resp = client.get(f"/api/v1/posts/{post_id}", headers=_auth(client, rt))
        assert resp.get_json()["subscriber_content"] is None
        resp = client.get("/api/v1/posts/feed", headers=_auth(client, rt))
        assert resp.get_json()["posts"] == []

        client.post(
            "/api/v1/subscriptions/webhook",
            json={
                "event_type": "invoice.payment_succeeded",
                "payload": {"subscription_id": ext_id},
            },
        )
        # Access restored after successful renewal
        resp = client.get(f"/api/v1/posts/{post_id}", headers=_auth(client, rt))
        assert resp.get_json()["subscriber_content"] == "WH-FULL"

        # Webhook missing event_type -> 400 RFC7807 envelope
        resp = client.post("/api/v1/subscriptions/webhook", json={})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_REQUEST"

        # Swap after renewal -> allocation_log has assign + swap rows
        client.post(
            "/api/v1/subscriptions/allocations/swap",
            json={"current_writer_id": writer_id, "new_writer_id": _user_id(wt2)},
            headers=_auth(client, rt),
        )
        with SqlAlchemyUnitOfWork() as uow:
            count = uow.session.execute(text("SELECT COUNT(*) FROM allocation_log")).scalar()
            assert count >= 2
