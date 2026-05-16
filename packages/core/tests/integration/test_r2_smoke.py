import pytest
from ai_shorts.config import get_settings
from ai_shorts.storage.r2 import get_r2_client


def test_r2_list_objects_smoke() -> None:
    settings = get_settings()
    if not (
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    ):
        pytest.skip("R2 settings are not configured")

    client = get_r2_client()
    response = client.list_objects_v2(Bucket=settings.r2_bucket, MaxKeys=1)

    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
