from celery import Celery

from ai_shorts.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "ai_shorts",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["ai_shorts.orchestration.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery_app = create_celery_app()
