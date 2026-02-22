"""Source resolution for local paths and GitHub URLs."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from repoclinic.schemas.input_models import AnalyzeInput

GITHUB_REPO_PATTERN = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)")


@dataclass(frozen=True)
class ResolvedSource:
    """Resolved repository source location."""

    repo_name: str
    resolved_path: Path
    source_type: str


class SourceResolver:
    """Resolve incoming source into a local directory."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def resolve(self, source: AnalyzeInput, run_id: str) -> ResolvedSource:
        """Resolve source into local path for scanner stage."""
        if source.source_type == "local_path":
            assert source.local_path is not None
            local_path = Path(source.local_path).expanduser().resolve()
            if not local_path.exists() or not local_path.is_dir():
                raise ValueError(f"Invalid local path: {local_path}")
            return ResolvedSource(
                repo_name=local_path.name,
                resolved_path=local_path,
                source_type=source.source_type,
            )

        assert source.github_url is not None
        repo_name = self._extract_repo_name(source.github_url)
        destination = self.workspace_root / f"{repo_name}-{run_id}"
        if destination.exists():
            return ResolvedSource(
                repo_name=repo_name,
                resolved_path=destination,
                source_type=source.source_type,
            )

        clone_cmd = ["git", "clone", "--depth", "1", source.github_url, str(destination)]
        clone_result = subprocess.run(clone_cmd, capture_output=True, text=True, check=False)
        if clone_result.returncode != 0:
            raise RuntimeError(f"git clone failed: {clone_result.stderr.strip()}")

        if source.branch:
            branch_cmd = ["git", "-C", str(destination), "checkout", source.branch]
            branch_result = subprocess.run(
                branch_cmd, capture_output=True, text=True, check=False
            )
            if branch_result.returncode != 0:
                raise RuntimeError(f"git checkout branch failed: {branch_result.stderr.strip()}")

        if source.commit:
            commit_cmd = ["git", "-C", str(destination), "checkout", source.commit]
            commit_result = subprocess.run(
                commit_cmd, capture_output=True, text=True, check=False
            )
            if commit_result.returncode != 0:
                raise RuntimeError(f"git checkout commit failed: {commit_result.stderr.strip()}")

        return ResolvedSource(
            repo_name=repo_name,
            resolved_path=destination,
            source_type=source.source_type,
        )

    @staticmethod
    def _extract_repo_name(url: str) -> str:
        match = GITHUB_REPO_PATTERN.search(url)
        if not match:
            raise ValueError(f"Unsupported GitHub URL: {url}")
        return match.group("repo")
