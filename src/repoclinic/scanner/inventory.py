"""Deterministic file inventory engine."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from repoclinic.config.models import ScanPolicyConfig
from repoclinic.scanner.ignore_policy import IgnorePolicy
from repoclinic.schemas.scanner_models import ScanStats

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cs": "C#",
}
MANIFEST_FILES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
}
OSV_LOCKFILE_FILES = {
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements.txt",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}


@dataclass(frozen=True)
class FileRecord:
    """File record collected from inventory."""

    path: Path
    rel_path: Path
    size_bytes: int
    language: str | None
    content: str


@dataclass(frozen=True)
class InventoryResult:
    """Inventory result payload."""

    files: list[FileRecord]
    manifests: list[Path]
    osv_lockfiles: list[Path]
    top_level_dirs: list[str]
    stats: ScanStats


class InventoryEngine:
    """Collect files deterministically using rg + policy checks."""

    def __init__(self, policy: IgnorePolicy, scan_policy: ScanPolicyConfig) -> None:
        self.policy = policy
        self.scan_policy = scan_policy

    def collect(self, repo_path: Path) -> InventoryResult:
        file_paths = self._list_files_with_rg(repo_path)
        stats = ScanStats()
        records: list[FileRecord] = []
        manifests: list[Path] = []
        lockfiles: set[Path] = set()
        top_level_dirs: set[str] = set()

        for rel in file_paths:
            if len(records) >= self.scan_policy.max_files:
                break
            stats.total_files_seen += 1
            if rel.name in OSV_LOCKFILE_FILES:
                lockfiles.add(rel)
            if self.policy.should_skip(rel):
                stats.files_skipped += 1
                stats.skipped_reasons.ignored_pathspec += 1
                continue

            full_path = repo_path / rel
            try:
                size_bytes = full_path.stat().st_size
            except OSError:
                stats.files_skipped += 1
                stats.skipped_reasons.encoding_error += 1
                continue

            if size_bytes > self.scan_policy.max_file_size_bytes:
                stats.files_skipped += 1
                stats.skipped_reasons.too_large += 1
                continue

            if self._is_binary_file(full_path):
                stats.files_skipped += 1
                stats.skipped_reasons.binary += 1
                continue

            try:
                content = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                stats.files_skipped += 1
                stats.skipped_reasons.encoding_error += 1
                continue

            language = LANGUAGE_BY_EXTENSION.get(full_path.suffix.lower())
            records.append(
                FileRecord(
                    path=full_path,
                    rel_path=rel,
                    size_bytes=size_bytes,
                    language=language,
                    content=content,
                )
            )
            stats.files_scanned += 1

            if full_path.name in MANIFEST_FILES:
                manifests.append(rel)

            top_level_dirs.add(rel.parts[0] if len(rel.parts) > 1 else ".")

        return InventoryResult(
            files=records,
            manifests=manifests,
            osv_lockfiles=sorted(lockfiles),
            top_level_dirs=sorted(top_level_dirs),
            stats=stats,
        )

    @staticmethod
    def _list_files_with_rg(repo_path: Path) -> list[Path]:
        cmd = ["rg", "--files", "--hidden", "-g", "!.git"]
        result = subprocess.run(
            cmd, cwd=repo_path, capture_output=True, text=True, check=False
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(f"rg --files failed: {result.stderr.strip()}")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [Path(line) for line in sorted(lines)]

    @staticmethod
    def _is_binary_file(path: Path) -> bool:
        chunk = path.read_bytes()[:1024]
        return b"\x00" in chunk
