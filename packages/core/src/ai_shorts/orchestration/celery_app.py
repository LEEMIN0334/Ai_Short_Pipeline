from typing import cast

from celery import Celery

from ai_shorts.config import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the shared Celery app for AI Shorts background work."""

    active_settings = settings or get_settings()
    app = Celery(
        "ai_shorts",
        broker=active_settings.redis_url,
        backend=active_settings.redis_url,
        include=["ai_shorts.orchestration.phase1"],
    )
    app.conf.update(
        accept_content=["json"],
        enable_utc=True,
        result_serializer="json",
        task_default_queue="ai_shorts",
        task_serializer="json",
        timezone="UTC",
    )
    return cast(Celery, app)


celery_app = create_celery_app()
