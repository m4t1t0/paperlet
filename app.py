"""Flask application factory."""
from __future__ import annotations
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.src.shared.config import get_settings
from backend.src.shared.service_layer.messagebus import MessageBus
from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.identity.adapters.orm import start_mappers as start_identity_mappers
from backend.src.subscriptions.adapters.orm import start_mappers as start_subscriptions_mappers
from backend.src.publishing.adapters.orm import start_mappers as start_publishing_mappers
from backend.src.adapters.mock_payments import MockPaymentGateway


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)

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
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_per_minute} per minute", f"{settings.rate_limit_per_hour} per hour"],
            storage_uri="memory://",
        )
    else:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_per_minute} per minute", f"{settings.rate_limit_per_hour} per hour"],
            storage_uri=settings.redis_url,
        )
    limiter.init_app(app)

    # Initialize mappers
    start_identity_mappers()
    start_subscriptions_mappers()
    start_publishing_mappers()

    # Create message bus
    message_bus = MessageBus()
    app.message_bus = message_bus

    # Register blueprints
    from backend.src.identity.api import auth_bp
    from backend.src.subscriptions.api import subscriptions_bp
    from backend.src.publishing.api import posts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(posts_bp)

    # Health checks
    @app.route("/health")
    def health() -> tuple:
        return jsonify({"status": "ok"}), 200

    @app.route("/health/ready")
    def ready() -> tuple:
        try:
            with SqlAlchemyUnitOfWork() as uow:
                uow.session.execute("SELECT 1")
            return jsonify({"status": "ready", "database": "connected"}), 200
        except Exception as e:
            return jsonify({"status": "not ready", "database": "disconnected", "error": str(e)}), 503

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e) -> tuple:
        return jsonify({
            "error": "Bad Request",
            "message": str(e),
            "code": "BAD_REQUEST",
        }), 400

    @app.errorhandler(401)
    def unauthorized(e) -> tuple:
        return jsonify({
            "error": "Unauthorized",
            "message": str(e),
            "code": "UNAUTHORIZED",
        }), 401

    @app.errorhandler(404)
    def not_found(e) -> tuple:
        return jsonify({
            "error": "Not Found",
            "message": str(e),
            "code": "NOT_FOUND",
        }), 404

    @app.errorhandler(500)
    def internal_error(e) -> tuple:
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "code": "INTERNAL_ERROR",
        }), 500

    # Register command handlers
    _register_handlers(message_bus)

    return app


def _register_handlers(bus: MessageBus) -> None:
    """Register all command and event handlers."""
    # Identity
    from backend.src.identity.handlers import (
        GetProfileHandler,
        LoginHandler,
        RegisterHandler,
        RefreshTokenHandler,
    )
    from backend.src.identity.adapters.sqlalchemy_repository import SqlAlchemyUserRepository
    from backend.src.identity.service import AuthService, JwtService

    def get_user_repo():
        uow = SqlAlchemyUnitOfWork()
        uow.__enter__()
        return SqlAlchemyUserRepository(uow.session), uow

    def release_uow(uow):
        uow.__exit__(None, None, None)

    # We need to handle UoW lifecycle properly - for now use a simplified approach
    # In production, use a proper dependency injection container

    # For now, register handlers with factory functions
    from backend.src.identity.commands import (
        GetProfileCommand,
        LoginCommand,
        RegisterCommand,
        RefreshTokenCommand,
    )

    jwt_service = JwtService()

    class IdentityHandlers:
        def __init__(self):
            self._jwt = jwt_service

        def _get_repo(self):
            uow = SqlAlchemyUnitOfWork()
            uow.__enter__()
            repo = SqlAlchemyUserRepository(uow.session)
            return repo, uow

        def _release(self, uow):
            uow.__exit__(None, None, None)

        def handle_register(self, command: RegisterCommand):
            repo, uow = self._get_repo()
            try:
                handler = RegisterHandler(repo, self._jwt)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_login(self, command: LoginCommand):
            repo, uow = self._get_repo()
            try:
                handler = LoginHandler(repo, self._jwt)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_refresh(self, command: RefreshTokenCommand):
            repo, uow = self._get_repo()
            try:
                handler = RefreshTokenHandler(repo, self._jwt)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_profile(self, command: GetProfileCommand):
            repo, uow = self._get_repo()
            try:
                handler = GetProfileHandler(repo)
                result = handler.handle(command)
                return result
            finally:
                self._release(uow)

    identity_handlers = IdentityHandlers()
    bus.register_command(RegisterCommand, identity_handlers.handle_register)
    bus.register_command(LoginCommand, identity_handlers.handle_login)
    bus.register_command(RefreshTokenCommand, identity_handlers.handle_refresh)
    bus.register_command(GetProfileCommand, identity_handlers.handle_profile)

    # Subscriptions
    from backend.src.subscriptions.handlers import (
        AssignAllocationHandler,
        GetAllocationsHandler,
        ReleaseAllocationHandler,
        SubscribeHandler,
        SwapAllocationHandler,
    )
    from backend.src.subscriptions.adapters.sqlalchemy_repository import SqlAlchemySubscriptionRepository
    from backend.src.subscriptions.service import SubscriptionService

    class SubscriptionHandlers:
        def _get_repos(self):
            uow = SqlAlchemyUnitOfWork()
            uow.__enter__()
            sub_repo = SqlAlchemySubscriptionRepository(uow.session)
            user_repo = SqlAlchemyUserRepository(uow.session)
            payment_gateway = MockPaymentGateway()
            service = SubscriptionService(sub_repo, payment_gateway)
            return sub_repo, service, uow

        def _release(self, uow):
            uow.__exit__(None, None, None)

        def handle_subscribe(self, command):
            sub_repo, service, uow = self._get_repos()
            try:
                handler = SubscribeHandler(sub_repo, service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_allocations(self, command):
            sub_repo, _, uow = self._get_repos()
            try:
                handler = GetAllocationsHandler(sub_repo)
                result = handler.handle(command)
                return result
            finally:
                self._release(uow)

        def handle_assign(self, command):
            sub_repo, _, uow = self._get_repos()
            try:
                handler = AssignAllocationHandler(sub_repo)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_swap(self, command):
            sub_repo, _, uow = self._get_repos()
            try:
                handler = SwapAllocationHandler(sub_repo)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_release(self, command):
            sub_repo, _, uow = self._get_repos()
            try:
                handler = ReleaseAllocationHandler(sub_repo)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

    sub_handlers = SubscriptionHandlers()
    bus.register_command(
        __import__("backend.src.subscriptions.commands", fromlist=["SubscribeCommand"]).SubscribeCommand,
        sub_handlers.handle_subscribe,
    )
    bus.register_command(
        __import__("backend.src.subscriptions.commands", fromlist=["GetAllocationsCommand"]).GetAllocationsCommand,
        sub_handlers.handle_allocations,
    )
    bus.register_command(
        __import__("backend.src.subscriptions.commands", fromlist=["AssignAllocationCommand"]).AssignAllocationCommand,
        sub_handlers.handle_assign,
    )
    bus.register_command(
        __import__("backend.src.subscriptions.commands", fromlist=["SwapAllocationCommand"]).SwapAllocationCommand,
        sub_handlers.handle_swap,
    )
    bus.register_command(
        __import__("backend.src.subscriptions.commands", fromlist=["ReleaseAllocationCommand"]).ReleaseAllocationCommand,
        sub_handlers.handle_release,
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
    from backend.src.publishing.adapters.sqlalchemy_repository import SqlAlchemyPostRepository

    class PublishingHandlers:
        def _get_service(self):
            uow = SqlAlchemyUnitOfWork()
            uow.__enter__()
            post_repo = SqlAlchemyPostRepository(uow.session)
            sub_repo = SqlAlchemySubscriptionRepository(uow.session)
            service = PublishingService(post_repo, sub_repo, bus)
            return service, uow

        def _release(self, uow):
            uow.__exit__(None, None, None)

        def handle_create(self, command):
            service, uow = self._get_service()
            try:
                handler = CreatePostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_create_scheduled(self, command):
            service, uow = self._get_service()
            try:
                handler = CreateScheduledPostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_publish(self, command):
            service, uow = self._get_service()
            try:
                handler = PublishPostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_schedule(self, command):
            service, uow = self._get_service()
            try:
                handler = SchedulePostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_cancel(self, command):
            service, uow = self._get_service()
            try:
                handler = CancelPostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_update(self, command):
            service, uow = self._get_service()
            try:
                handler = UpdatePostHandler(service)
                result = handler.handle(command)
                uow.commit()
                return result
            finally:
                self._release(uow)

        def handle_get_post(self, command):
            service, uow = self._get_service()
            try:
                handler = GetPostHandler(service)
                result = handler.handle(command)
                return result
            finally:
                self._release(uow)

        def handle_get_writer_posts(self, command):
            service, uow = self._get_service()
            try:
                handler = GetWriterPostsHandler(service)
                result = handler.handle(command)
                return result
            finally:
                self._release(uow)

        def handle_get_feed(self, command):
            service, uow = self._get_service()
            try:
                handler = GetFeedHandler(service)
                result = handler.handle(command)
                return result
            finally:
                self._release(uow)

    pub_handlers = PublishingHandlers()
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["CreatePostCommand"]).CreatePostCommand,
        pub_handlers.handle_create,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["CreateScheduledPostCommand"]).CreateScheduledPostCommand,
        pub_handlers.handle_create_scheduled,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["PublishPostCommand"]).PublishPostCommand,
        pub_handlers.handle_publish,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["SchedulePostCommand"]).SchedulePostCommand,
        pub_handlers.handle_schedule,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["CancelPostCommand"]).CancelPostCommand,
        pub_handlers.handle_cancel,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["UpdatePostCommand"]).UpdatePostCommand,
        pub_handlers.handle_update,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["GetPostCommand"]).GetPostCommand,
        pub_handlers.handle_get_post,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["GetWriterPostsCommand"]).GetWriterPostsCommand,
        pub_handlers.handle_get_writer_posts,
    )
    bus.register_command(
        __import__("backend.src.publishing.commands", fromlist=["GetFeedCommand"]).GetFeedCommand,
        pub_handlers.handle_get_feed,
    )


# Only create global app when not testing
if not os.environ.get("PYTEST_CURRENT_TEST"):
    app = create_app()
else:
    app = None


if __name__ == "__main__":
    if app is None:
        app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)