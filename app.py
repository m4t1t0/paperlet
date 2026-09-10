"""Flask application factory."""

from __future__ import annotations
import os
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.src.shared.config import get_settings
from backend.src.shared.service_layer.messagebus import MessageBus
from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.shared.logging import setup_logging, inject_request_id
from backend.src.identity.adapters.orm import start_mappers as start_identity_mappers
from backend.src.subscriptions.adapters.orm import (
    start_mappers as start_subscriptions_mappers,
)
from backend.src.publishing.adapters.orm import (
    start_mappers as start_publishing_mappers,
)


def _decode_sub_unverified(token: str) -> str | None:
    """Decode JWT `sub` without expiry verification (rate limiting / logging only)."""
    try:
        import jwt

        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        return payload.get("sub")
    except Exception:
        return None


def _problem(title: str, detail: str, code: str, status: int) -> tuple:
    """RFC 7807 hybrid problem response (custom `code` + `message` alias)."""
    slug = title.lower().replace(" ", "-")
    return jsonify(
        {
            "type": f"https://paperlet.local/problems/{slug}",
            "title": title,
            "status": status,
            "detail": detail,
            "message": detail,  # backwards-compatible alias
            "code": code,
        }
    ), status


def _check_database() -> dict:
    """Check database connectivity."""
    try:
        from sqlalchemy import text

        with SqlAlchemyUnitOfWork() as uow:
            uow.session.execute(text("SELECT 1"))
        return {"ok": True, "detail": "connected"}
    except Exception as e:
        return {"ok": False, "detail": f"disconnected: {e}"}


def _check_redis() -> dict:
    """Check Redis connectivity."""
    try:
        import redis

        client = redis.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=2
        )
        client.ping()
        return {"ok": True, "detail": "connected"}
    except Exception as e:
        return {"ok": False, "detail": f"disconnected: {e}"}


def _check_migrations() -> dict:
    """Check applied migrations match alembic heads (skipped on SQLite bootstrap)."""
    try:
        settings = get_settings()
        if "sqlite" in settings.database_url:
            return {"ok": True, "detail": "skipped (sqlite bootstrap)", "skipped": True}
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text

        repo_root = Path(__file__).resolve().parent
        cfg = Config()
        cfg.set_main_option("script_location", str(repo_root / "backend" / "alembic"))
        heads = set(ScriptDirectory.from_config(cfg).get_heads())
        with SqlAlchemyUnitOfWork() as uow:
            rows = uow.session.execute(text("SELECT version_num FROM alembic_version")).all()
        applied = {r[0] for r in rows}
        if heads <= applied:
            return {"ok": True, "detail": f"up to date ({len(applied)} applied)"}
        missing = sorted(heads - applied)
        return {"ok": False, "detail": f"pending migrations: {missing}"}
    except Exception as e:
        return {"ok": False, "detail": f"check failed: {e}"}


def get_user_id_from_jwt() -> str:
    """Extract user ID from JWT token for rate limiting (IP fallback)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        sub = _decode_sub_unverified(auth_header[7:])
        if sub:
            return f"user:{sub}"
    # Fallback to IP-based rate limiting
    return f"ip:{get_remote_address()}"


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)

    # Setup JSON structured logging
    setup_logging(app)

    # Load settings
    settings = get_settings()

    # Apply config overrides
    if config_overrides:
        for key, value in config_overrides.items():
            app.config[key] = value

    # Configure Flask
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["JSON_SORT_KEYS"] = False

    # Enable CORS
    CORS(app, origins=["http://localhost:3000", "http://localhost:5173"])

    # Rate limiting - use in-memory storage for testing
    if app.config.get("TESTING"):
        limiter = Limiter(
            key_func=get_user_id_from_jwt,
            default_limits=[
                f"{settings.rate_limit_per_minute} per minute",
                f"{settings.rate_limit_per_hour} per hour",
            ],
            storage_uri="memory://",
        )
    else:
        limiter = Limiter(
            key_func=get_user_id_from_jwt,
            default_limits=[
                f"{settings.rate_limit_per_minute} per minute",
                f"{settings.rate_limit_per_hour} per hour",
            ],
            storage_uri=settings.redis_url,
        )
    limiter.init_app(app)

    # Request ID middleware
    @app.before_request
    def _inject_request_id() -> None:
        inject_request_id()
        # Also extract user_id from JWT for logging
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            sub = _decode_sub_unverified(auth_header[7:])
            if sub:
                g.user_id = sub

    # Initialize mappers
    start_identity_mappers()
    start_subscriptions_mappers()
    start_publishing_mappers()

    # Create message bus
    message_bus = MessageBus()
    app.message_bus = message_bus

    # Register blueprints
    from backend.src.identity.api import auth_bp
    from backend.src.identity.writers_api import writers_bp
    from backend.src.subscriptions.api import subscriptions_bp
    from backend.src.publishing.api import posts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(writers_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(posts_bp)

    # Health checks
    @app.route("/health")
    def health() -> tuple:
        return jsonify({"status": "ok"}), 200

    @app.route("/health/ready")
    def ready() -> tuple:
        checks = {
            "database": _check_database(),
            "redis": _check_redis(),
            "migrations": _check_migrations(),
        }
        ready = all(c["ok"] for c in checks.values())
        status = "ready" if ready else "not ready"
        code = 200 if ready else 503
        return jsonify({"status": status, "checks": checks}), code

    # Error handlers (RFC 7807 hybrid: type/title/status/detail + custom code;
    # `message` kept as alias of `detail` for backwards compatibility)
    @app.errorhandler(400)
    def bad_request(e) -> tuple:
        return _problem("Bad Request", str(e), "BAD_REQUEST", 400)

    @app.errorhandler(401)
    def unauthorized(e) -> tuple:
        return _problem("Unauthorized", str(e), "UNAUTHORIZED", 401)

    @app.errorhandler(404)
    def not_found(e) -> tuple:
        return _problem("Not Found", str(e), "NOT_FOUND", 404)

    @app.errorhandler(500)
    def internal_error(e) -> tuple:
        return _problem(
            "Internal Server Error", "An unexpected error occurred", "INTERNAL_ERROR", 500
        )

    # Register command handlers
    _register_handlers(message_bus)

    return app


def _command_handler_with_uow(bus: MessageBus, handler_factory):
    """Decorator that provides UoW lifecycle management for command handlers."""

    def wrapper(command):
        uow = SqlAlchemyUnitOfWork()
        uow.__enter__()
        try:
            handler = handler_factory(uow, bus)
            result = handler.handle(command)
            uow.commit()
            return result
        finally:
            uow.__exit__(None, None, None)

    return wrapper


def _register_handlers(bus: MessageBus) -> None:
    """Register all command and event handlers."""
    # Identity
    from backend.src.identity.handlers import (
        GetProfileHandler,
        LoginHandler,
        RegisterHandler,
        RefreshTokenHandler,
    )
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
        SqlAlchemySessionRepository,
    )
    from backend.src.identity.service import JwtService

    jwt_service = JwtService()

    bus.register_command(
        __import__(
            "backend.src.identity.commands", fromlist=["RegisterCommand"]
        ).RegisterCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: RegisterHandler(
                SqlAlchemyUserRepository(uow.session),
                SqlAlchemySessionRepository(uow.session),
                jwt_service,
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.identity.commands", fromlist=["LoginCommand"]
        ).LoginCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: LoginHandler(
                SqlAlchemyUserRepository(uow.session),
                SqlAlchemySessionRepository(uow.session),
                jwt_service,
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.identity.commands", fromlist=["RefreshTokenCommand"]
        ).RefreshTokenCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: RefreshTokenHandler(
                SqlAlchemyUserRepository(uow.session),
                SqlAlchemySessionRepository(uow.session),
                jwt_service,
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.identity.commands", fromlist=["GetProfileCommand"]
        ).GetProfileCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: GetProfileHandler(SqlAlchemyUserRepository(uow.session))
        ),
    )

    # Subscriptions
    from backend.src.subscriptions.handlers import (
        AssignAllocationHandler,
        GetAllocationsHandler,
        HandlePaymentWebhookHandler,
        ReleaseAllocationHandler,
        SubscribeHandler,
        SwapAllocationHandler,
    )
    from backend.src.subscriptions.adapters.sqlalchemy_repository import (
        SqlAlchemySubscriptionRepository,
    )
    from backend.src.subscriptions.service import SubscriptionService
    from backend.src.adapters import create_payment_gateway

    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["SubscribeCommand"]
        ).SubscribeCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: SubscribeHandler(
                SqlAlchemySubscriptionRepository(uow.session),
                SubscriptionService(
                    SqlAlchemySubscriptionRepository(uow.session), create_payment_gateway()
                ),
                SqlAlchemyUserRepository(uow.session),
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["GetAllocationsCommand"]
        ).GetAllocationsCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: GetAllocationsHandler(
                SqlAlchemySubscriptionRepository(uow.session)
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["AssignAllocationCommand"]
        ).AssignAllocationCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: AssignAllocationHandler(
                SqlAlchemySubscriptionRepository(uow.session),
                SqlAlchemyUserRepository(uow.session),
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["SwapAllocationCommand"]
        ).SwapAllocationCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: SwapAllocationHandler(
                SqlAlchemySubscriptionRepository(uow.session),
                SqlAlchemyUserRepository(uow.session),
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["ReleaseAllocationCommand"]
        ).ReleaseAllocationCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: ReleaseAllocationHandler(
                SqlAlchemySubscriptionRepository(uow.session)
            ),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.subscriptions.commands", fromlist=["HandlePaymentWebhookCommand"]
        ).HandlePaymentWebhookCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: HandlePaymentWebhookHandler(
                SqlAlchemySubscriptionRepository(uow.session),
                SubscriptionService(
                    SqlAlchemySubscriptionRepository(uow.session), create_payment_gateway()
                ),
            ),
        ),
    )

# Read model projections for notifications
    from backend.src.subscriptions.adapters.read_model import (
        AllocationLogProjection,
        WriterSubscribersProjection,
        SubscriptionStatusProjection,
    )
    from backend.src.subscriptions.domain.model import AllocationChanged
    from backend.src.shared.domain.events import DomainEvent, EventHandler

    class _UowEventHandler(EventHandler):
        """Wrapper to adapt function to EventHandler protocol."""

        def __init__(self, handler_factory):
            self._handler_factory = handler_factory

        def handle(self, event: DomainEvent) -> None:
            uow = SqlAlchemyUnitOfWork()
            uow.__enter__()
            try:
                handler = self._handler_factory(uow)
                handler.handle(event)
                uow.commit()
            finally:
                uow.__exit__(None, None, None)

    # Register event handlers for read model projections
    bus.register_event_handler(
        AllocationChanged,
        _UowEventHandler(lambda uow: WriterSubscribersProjection(uow.session)),
    )
    bus.register_event_handler(
        AllocationChanged,
        _UowEventHandler(lambda uow: AllocationLogProjection(uow.session)),
    )
    bus.register_event_handler(
        DomainEvent,
        _UowEventHandler(lambda uow: SubscriptionStatusProjection(uow.session)),
    )

    # Publishing
    from backend.src.publishing.service import (
        CancelPostHandler,
        CreatePostHandler,
        CreateScheduledPostHandler,
        GetFeedHandler,
        GetPostHandler,
        GetWriterPostsHandler,
        PublishPostHandler,
        PublishingService,
        SchedulePostHandler,
        UpdatePostHandler,
    )
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )

    def _make_publishing_service(uow, b):
        post_repo = SqlAlchemyPostRepository(uow.session)
        sub_repo = SqlAlchemySubscriptionRepository(uow.session)
        user_repo = SqlAlchemyUserRepository(uow.session)
        return PublishingService(post_repo, sub_repo, b, user_repo)

    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["CreatePostCommand"]
        ).CreatePostCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: CreatePostHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["CreateScheduledPostCommand"]
        ).CreateScheduledPostCommand,
        _command_handler_with_uow(
            bus,
            lambda uow, b: CreateScheduledPostHandler(_make_publishing_service(uow, b)),
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["PublishPostCommand"]
        ).PublishPostCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: PublishPostHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["SchedulePostCommand"]
        ).SchedulePostCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: SchedulePostHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["CancelPostCommand"]
        ).CancelPostCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: CancelPostHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["UpdatePostCommand"]
        ).UpdatePostCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: UpdatePostHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["GetPostCommand"]
        ).GetPostCommand,
        _command_handler_with_uow(bus, lambda uow, b: GetPostHandler(_make_publishing_service(uow, b))),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["GetWriterPostsCommand"]
        ).GetWriterPostsCommand,
        _command_handler_with_uow(
            bus, lambda uow, b: GetWriterPostsHandler(_make_publishing_service(uow, b))
        ),
    )
    bus.register_command(
        __import__(
            "backend.src.publishing.commands", fromlist=["GetFeedCommand"]
        ).GetFeedCommand,
        _command_handler_with_uow(bus, lambda uow, b: GetFeedHandler(_make_publishing_service(uow, b))),
    )

    # Event handlers for Celery tasks
    from backend.src.publishing.domain.model import PostPublished
    from backend.src.notifications.tasks import send_post_published_emails

    class _EnqueuePostEmailsHandler(EventHandler):
        def handle(self, event: PostPublished) -> None:
            send_post_published_emails.delay(str(event.post_id))

    bus.register_event_handler(PostPublished, _EnqueuePostEmailsHandler())


# Only create global app when not testing
if not os.environ.get("PYTEST_CURRENT_TEST"):
    app = create_app()
else:
    app = None


if __name__ == "__main__":
    if app is None:
        app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
