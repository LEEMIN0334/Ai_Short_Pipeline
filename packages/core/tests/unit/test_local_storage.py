from pathlib import Path

import pytest
from ai_shorts.storage.local import LocalStorage


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(root=tmp_path)

    uri = await storage.put_bytes("reports/hello.txt", b"hello")

    assert uri.endswith("reports/hello.txt")
    assert await storage.exists("reports/hello.txt")
    assert await storage.get_bytes("reports/hello.txt") == b"hello"

    await storage.delete("reports/hello.txt")

    assert not await storage.exists("reports/hello.txt")


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(root=tmp_path)

    with pytest.raises(ValueError):
        await storage.put_bytes("../outside.txt", b"nope")
