from pathlib import Path

from ai_shorts.config import get_settings


class LocalStorage:
    """Filesystem-backed storage used for local development."""

    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = root or Path(settings.local_storage_root)

    def _resolve_key(self, key: str) -> Path:
        normalized = Path(key)
        if normalized.is_absolute() or ".." in normalized.parts:
            msg = f"Invalid local storage key: {key}"
            raise ValueError(msg)
        return self.root / normalized

    async def put_bytes(self, key: str, data: bytes) -> str:
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_posix()

    async def get_bytes(self, key: str) -> bytes:
        return self._resolve_key(key).read_bytes()

    async def delete(self, key: str) -> None:
        path = self._resolve_key(key)
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return self._resolve_key(key).exists()
