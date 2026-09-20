"""Persisted resume-state records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FileState:
    size: int
    etag: str
    downloaded: datetime

    def to_dict(self) -> dict:
        return {
            "Size": self.size,
            "ETag": self.etag,
            "Downloaded": self.downloaded.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileState":
        downloaded_raw = data["Downloaded"]
        downloaded = (
            datetime.fromisoformat(downloaded_raw)
            if isinstance(downloaded_raw, str)
            else downloaded_raw
        )
        return cls(size=data["Size"], etag=data.get("ETag", ""), downloaded=downloaded)

    @classmethod
    def now(cls, size: int, etag: str) -> "FileState":
        return cls(size=size, etag=etag, downloaded=datetime.now(timezone.utc))


@dataclass
class DownloadState:
    files: dict[str, FileState] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"Files": {key: state.to_dict() for key, state in self.files.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadState":
        files_raw = data.get("Files", {})
        files = {key: FileState.from_dict(value) for key, value in files_raw.items()}
        return cls(files=files)
