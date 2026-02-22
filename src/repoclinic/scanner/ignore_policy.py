"""Path include/exclude policy for scanner traversal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pathspec import PathSpec

from repoclinic.config.models import ScanPolicyConfig

HARD_EXCLUDED_SEGMENTS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "vendor",
    ".venv",
    "__pycache__",
}


@dataclass
class IgnorePolicy:
    """Combined hard excludes + pathspec-based filtering."""

    include_spec: PathSpec
    exclude_spec: PathSpec

    @classmethod
    def from_config(cls, policy: ScanPolicyConfig) -> "IgnorePolicy":
        include_spec = PathSpec.from_lines("gitignore", policy.include_globs)
        exclude_spec = PathSpec.from_lines("gitignore", policy.exclude_globs)
        return cls(include_spec=include_spec, exclude_spec=exclude_spec)

    def should_skip(self, rel_path: Path) -> bool:
        rel = rel_path.as_posix()
        if any(part in HARD_EXCLUDED_SEGMENTS for part in rel_path.parts):
            return True
        if self.exclude_spec.match_file(rel):
            return True
        if self.include_spec.patterns and not self.include_spec.match_file(rel):
            return True
        return False
