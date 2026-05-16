from typing import Any

import boto3

from ai_shorts.config import get_settings


def get_r2_client() -> Any:
    """Create an S3-compatible Cloudflare R2 client."""

    settings = get_settings()
    missing = [
        name
        for name, value in {
            "R2_ACCOUNT_ID": settings.r2_account_id,
            "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
            "R2_BUCKET": settings.r2_bucket,
        }.items()
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        msg = f"Missing R2 settings: {joined}"
        raise RuntimeError(msg)

    endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
