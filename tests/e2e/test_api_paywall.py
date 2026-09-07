"""E2E tests for API paywall logic."""
from __future__ import annotations
import pytest

# No need for setup_db fixture - tables are created at session scope
# Data is cleared between tests by the _clear_data fixture in conftest.py


class TestPaywallAPI:
    """E2E tests for paywall functionality."""

    def _register_user(self, client, email: str, password: str = "password123", role: str = "reader"):
        """Helper to register a user."""
        return client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "role": role,
        })

    def _login(self, client, email: str, password: str = "password123"):
        """Helper to login and get tokens."""
        resp = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
        })
        return resp.get_json()

    def _auth_header(self, access_token: str):
        """Create auth header."""
        return {"Authorization": f"Bearer {access_token}"}

    def _get_user_id_from_token(self, access_token: str) -> str:
        """Extract user ID from JWT token."""
        import jwt
        from backend.src.shared.config import get_settings
        settings = get_settings()
        payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload["sub"]

    def _create_post(self, client, writer_token: str, title: str, preview: str, subscriber: str, scheduled_at: str = None):
        """Helper to create a post."""
        data = {
            "title": title,
            "preview_content": preview,
            "subscriber_content": subscriber,
        }
        if scheduled_at:
            data["scheduled_at"] = scheduled_at
        return client.post("/api/v1/posts", json=data, headers=self._auth_header(writer_token))

    def _publish_post(self, client, writer_token: str, post_id: str):
        """Helper to publish a post."""
        return client.post(f"/api/v1/posts/{post_id}/publish", headers=self._auth_header(writer_token))

    def _subscribe(self, client, reader_token: str, payment_method_id: str = "pm_mock_default"):
        """Helper to create subscription."""
        return client.post("/api/v1/subscriptions/subscribe", json={
            "payment_method_id": payment_method_id,
        }, headers=self._auth_header(reader_token))

    def _assign_allocation(self, client, reader_token: str, writer_token: str):
        """Helper to assign allocation."""
        # Get writer's user ID from their token
        import jwt
        from backend.src.shared.config import get_settings
        settings = get_settings()
        payload = jwt.decode(writer_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        writer_user_id = payload["sub"]
        return client.post("/api/v1/subscriptions/allocations/assign", json={
            "writer_id": writer_user_id,
        }, headers=self._auth_header(reader_token))

    def test_public_can_read_preview_only(self, client):
        """Test that non-subscribers only see preview content on single post."""
        # Register writer and create post
        self._register_user(client, "writer@test.com", role="writer")
        writer_tokens = self._login(client, "writer@test.com")

        post_resp = self._create_post(client, writer_tokens["access_token"],
            "Test Post", "This is preview", "This is subscriber content")
        post_id = post_resp.get_json()["id"]
        self._publish_post(client, writer_tokens["access_token"], post_id)

        # Register reader without subscription
        self._register_user(client, "reader@test.com")
        reader_tokens = self._login(client, "reader@test.com")

        # Get single post - should see preview only
        resp = client.get(f"/api/v1/posts/{post_id}", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 200
        post = resp.get_json()
        assert post["preview_content"] == "This is preview"
        assert post["subscriber_content"] is None
        assert post["has_full_access"] is False

    def test_subscriber_with_allocation_sees_full_content(self, client):
        """Test that subscribers with allocation see full content."""
        # Register writer and create post
        self._register_user(client, "writer2@test.com", role="writer")
        writer_tokens = self._login(client, "writer2@test.com")

        post_resp = self._create_post(client, writer_tokens["access_token"],
            "Test Post 2", "Preview 2", "Subscriber content 2")
        post_id = post_resp.get_json()["id"]

        # Register reader and subscribe
        self._register_user(client, "reader2@test.com")
        reader_tokens = self._login(client, "reader2@test.com")

        self._subscribe(client, reader_tokens["access_token"])
        self._assign_allocation(client, reader_tokens["access_token"], writer_tokens["access_token"])

        # Get single post
        resp = client.get(f"/api/v1/posts/{post_id}", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 200
        post = resp.get_json()
        assert post["preview_content"] == "Preview 2"
        assert post["subscriber_content"] == "Subscriber content 2"
        assert post["has_full_access"] is True

    def test_subscriber_without_allocation_sees_preview_only(self, client):
        """Test that subscribers without allocation to writer see preview only."""
        # Register two writers
        self._register_user(client, "writer3a@test.com", role="writer")
        writer_a_tokens = self._login(client, "writer3a@test.com")

        self._register_user(client, "writer3b@test.com", role="writer")
        writer_b_tokens = self._login(client, "writer3b@test.com")
        writer_b_id = self._get_user_id_from_token(writer_b_tokens["access_token"])

        # Writer A creates post
        post_resp = self._create_post(client, writer_a_tokens["access_token"],
            "Writer A Post", "Preview A", "Full A")
        post_id = post_resp.get_json()["id"]

        # Register reader, subscribe, but allocate to Writer B only
        self._register_user(client, "reader3@test.com")
        reader_tokens = self._login(client, "reader3@test.com")

        self._subscribe(client, reader_tokens["access_token"])
        self._assign_allocation(client, reader_tokens["access_token"], writer_b_tokens["access_token"])

        # Get Writer A's post - should only see preview
        resp = client.get(f"/api/v1/posts/{post_id}", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 200
        post = resp.get_json()
        assert post["preview_content"] == "Preview A"
        assert post["subscriber_content"] is None
        assert post["has_full_access"] is False

    def test_allocation_swap_consumes_credit(self, client):
        """Test that swapping allocation consumes change credit."""
        # Register two writers
        self._register_user(client, "writer4a@test.com", role="writer")
        writer_a_tokens = self._login(client, "writer4a@test.com")
        writer_a_id = self._get_user_id_from_token(writer_a_tokens["access_token"])

        self._register_user(client, "writer4b@test.com", role="writer")
        writer_b_tokens = self._login(client, "writer4b@test.com")
        writer_b_id = self._get_user_id_from_token(writer_b_tokens["access_token"])

        # Register reader and subscribe
        self._register_user(client, "reader4@test.com")
        reader_tokens = self._login(client, "reader4@test.com")

        self._subscribe(client, reader_tokens["access_token"])

        # Assign to Writer A (fills empty slot, 0 credits)
        self._assign_allocation(client, reader_tokens["access_token"], writer_a_tokens["access_token"])

        # Check credits
        resp = client.get("/api/v1/subscriptions/allocations", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.get_json()["change_credits_remaining"] == 2

        # Swap to Writer B (consumes 1 credit)
        resp = client.post("/api/v1/subscriptions/allocations/swap", json={
            "current_writer_id": writer_a_id,
            "new_writer_id": writer_b_id,
        }, headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 200
        assert resp.get_json()["credits_spent"] == 1

        # Check credits
        resp = client.get("/api/v1/subscriptions/allocations", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.get_json()["change_credits_remaining"] == 1

    def test_allocation_release_consumes_credit(self, client):
        """Test that releasing allocation consumes change credit."""
        # Register writer
        self._register_user(client, "writer5@test.com", role="writer")
        writer_tokens = self._login(client, "writer5@test.com")
        writer_id = self._get_user_id_from_token(writer_tokens["access_token"])

        # Register reader and subscribe
        self._register_user(client, "reader5@test.com")
        reader_tokens = self._login(client, "reader5@test.com")

        self._subscribe(client, reader_tokens["access_token"])
        self._assign_allocation(client, reader_tokens["access_token"], writer_tokens["access_token"])

        # Release (consumes 1 credit)
        resp = client.delete(f"/api/v1/subscriptions/allocations/{writer_id}", headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 200
        assert resp.get_json()["credits_spent"] == 1

    def test_no_credits_prevents_swap(self, client):
        """Test that zero credits prevents swap."""
        # Register three writers
        self._register_user(client, "writer6a@test.com", role="writer")
        writer_a_tokens = self._login(client, "writer6a@test.com")
        writer_a_id = self._get_user_id_from_token(writer_a_tokens["access_token"])

        self._register_user(client, "writer6b@test.com", role="writer")
        writer_b_tokens = self._login(client, "writer6b@test.com")
        writer_b_id = self._get_user_id_from_token(writer_b_tokens["access_token"])

        self._register_user(client, "writer6c@test.com", role="writer")
        writer_c_tokens = self._login(client, "writer6c@test.com")
        writer_c_id = self._get_user_id_from_token(writer_c_tokens["access_token"])

        # Register reader and subscribe
        self._register_user(client, "reader6@test.com")
        reader_tokens = self._login(client, "reader6@test.com")

        self._subscribe(client, reader_tokens["access_token"])

        # Use up both credits: assign to A, swap to B, swap to C
        self._assign_allocation(client, reader_tokens["access_token"], writer_a_tokens["access_token"])

        # First swap (1 credit)
        client.post("/api/v1/subscriptions/allocations/swap", json={
            "current_writer_id": writer_a_id,
            "new_writer_id": writer_b_id,
        }, headers=self._auth_header(reader_tokens["access_token"]))

        # Second swap (1 credit)
        client.post("/api/v1/subscriptions/allocations/swap", json={
            "current_writer_id": writer_b_id,
            "new_writer_id": writer_c_id,
        }, headers=self._auth_header(reader_tokens["access_token"]))

        # Try third swap - should fail
        resp = client.post("/api/v1/subscriptions/allocations/swap", json={
            "current_writer_id": writer_c_id,
            "new_writer_id": writer_a_id,
        }, headers=self._auth_header(reader_tokens["access_token"]))
        assert resp.status_code == 400
        assert "no change credits" in resp.get_json()["message"].lower()

    def test_writer_can_see_own_subscriber_content(self, client):
        """Test that writers can see their own subscriber content."""
        self._register_user(client, "writer7@test.com", role="writer")
        writer_tokens = self._login(client, "writer7@test.com")

        post_resp = self._create_post(client, writer_tokens["access_token"],
            "My Post", "Preview", "My subscriber content")
        post_id = post_resp.get_json()["id"]

        # Writer views own post
        resp = client.get(f"/api/v1/posts/{post_id}", headers=self._auth_header(writer_tokens["access_token"]))
        assert resp.status_code == 200
        post = resp.get_json()
        assert post["subscriber_content"] == "My subscriber content"
        assert post["has_full_access"] is True