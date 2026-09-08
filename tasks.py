"""Invoke tasks for Paperlet."""

from __future__ import annotations
import os
import signal
import subprocess
import sys
import time

from invoke import task


@task
def start(c, port=5000, debug=False):
    """Start the Flask development server."""
    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["FLASK_ENV"] = "development" if debug else "production"
    env["PORT"] = str(port)

    cmd = [sys.executable, "app.py"]
    proc = subprocess.Popen(cmd, env=env)

    # Wait for server to be ready
    for _ in range(30):
        try:
            import requests

            response = requests.get(f"http://localhost:{port}/health", timeout=1)
            if response.status_code == 200:
                print(f"Server started on http://localhost:{port}")
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        print("Server failed to start in time")
        proc.terminate()
        sys.exit(1)

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


@task
def stop(c, port=5000):
    """Stop the Flask server."""
    # Find and kill process on port
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["cmdline"] and "app.py" in " ".join(proc.info["cmdline"]):
                    proc.terminate()
                    proc.wait(timeout=5)
                    print(f"Stopped server (PID: {proc.info['pid']})")
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        print("No server found running")
    except ImportError:
        # Fallback using lsof
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
                print(f"Stopped server (PID: {pid})")
        else:
            print("No server found running")


@task
def restart(c, port=5000, debug=False):
    """Restart the Flask server."""
    stop(c, port)
    time.sleep(1)
    start(c, port, debug)


@task
def install(c):
    """Install dependencies."""
    c.run("pip install -r requirements.txt")


@task
def test(c, unit=False, integration=False, e2e=False, coverage=False):
    """Run tests."""
    args = ["-v"]
    if coverage:
        args.extend(["--cov=backend", "--cov-report=term-missing"])

    if unit:
        args.append("tests/unit")
    elif integration:
        args.append("tests/integration")
    elif e2e:
        args.append("tests/e2e")
    else:
        args.append("tests")

    c.run(f"python -m pytest {' '.join(args)}")


@task
def lint(c):
    """Run linters."""
    c.run("ruff check backend")
    c.run("ruff check app.py")
    c.run("ruff check tasks.py")


@task
def format(c):
    """Format code."""
    c.run("ruff format backend")
    c.run("ruff format app.py")
    c.run("ruff format tasks.py")


@task
def typecheck(c):
    """Run type checking."""
    c.run("mypy backend")


@task
def migrate(c, message=None):
    """Create a new migration."""
    from backend.src.shared.config import get_settings

    settings = get_settings()

    cmd = ["alembic", "revision", "--autogenerate"]
    if message:
        cmd.extend(["-m", message])
    else:
        cmd.extend(["-m", "Auto migration"])

    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    c.run(" ".join(cmd), env=env)


@task
def upgrade(c):
    """Apply migrations."""
    from backend.src.shared.config import get_settings

    settings = get_settings()

    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    c.run("alembic upgrade head", env=env)


@task
def downgrade(c, revision="-1"):
    """Downgrade migrations."""
    from backend.src.shared.config import get_settings

    settings = get_settings()

    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    c.run(f"alembic downgrade {revision}", env=env)


@task
def seed(c):
    """Seed development data."""
    c.run("python -m scripts.seed_dev")


@task
def clean(c):
    """Clean cache files."""
    c.run("find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true")
    c.run("find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true")
    c.run("find . -type d -name '.ruff_cache' -exec rm -rf {} + 2>/dev/null || true")
    c.run("find . -type f -name '*.pyc' -delete 2>/dev/null || true")
    c.run("find . -type f -name '.coverage' -delete 2>/dev/null || true")


@task
def db_init(c):
    """Initialize database tables (for SQLite dev)."""
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.identity.adapters.orm import (
        create_tables as create_identity_tables,
    )
    from backend.src.subscriptions.adapters.orm import (
        create_tables as create_sub_tables,
    )
    from backend.src.publishing.adapters.orm import create_tables as create_pub_tables

    with SqlAlchemyUnitOfWork() as uow:
        create_identity_tables(uow.session.bind)
        create_sub_tables(uow.session.bind)
        create_pub_tables(uow.session.bind)
    print("Database tables created")


@task
def celery_worker(c, concurrency=4):
    """Start Celery worker."""
    from backend.src.notifications.tasks import celery_app

    celery_app.worker_main(
        ["worker", f"--concurrency={concurrency}", "--loglevel=info"]
    )


@task
def celery_beat(c):
    """Start Celery beat scheduler."""
    from backend.src.notifications.tasks import celery_app

    celery_app.worker_main(["beat", "--loglevel=info"])
