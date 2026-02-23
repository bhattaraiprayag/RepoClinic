"""Inventory and ignore policy tests for phase 3."""

from __future__ import annotations

from pathlib import Path

from repoclinic.config.models import ScanPolicyConfig
from repoclinic.scanner.ignore_policy import IgnorePolicy
from repoclinic.scanner.inventory import InventoryEngine


def test_ignore_policy_skips_hard_excluded_paths() -> None:
    """Hard excludes should always be skipped."""
    policy = IgnorePolicy.from_config(ScanPolicyConfig())
    assert policy.should_skip(Path("node_modules/pkg/index.js"))
    assert policy.should_skip(Path(".git/config"))
    assert not policy.should_skip(Path("src/main.py"))


def test_inventory_tracks_encoding_and_size_skips(tmp_path: Path) -> None:
    """Inventory should report oversized and malformed files."""
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "ok.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "src" / "huge.txt").write_text("x" * 5000, encoding="utf-8")
    (tmp_path / "src" / "bad.py").write_bytes(b"\xff\xfe\x00")

    scan_policy = ScanPolicyConfig(max_file_size_bytes=100, max_files=100)
    engine = InventoryEngine(IgnorePolicy.from_config(scan_policy), scan_policy)
    result = engine.collect(tmp_path)

    assert result.stats.files_scanned >= 1
    assert result.stats.skipped_reasons.too_large >= 1
    assert (
        result.stats.skipped_reasons.binary
        + result.stats.skipped_reasons.encoding_error
        >= 1
    )


def test_excluded_lockfiles_are_not_collected(tmp_path: Path) -> None:
    """Lockfiles under excluded paths should not be passed to dependency scanning."""
    (tmp_path / "requirements.txt").write_text("rich==14.0.0", encoding="utf-8")
    fixture_lockfile = (
        tmp_path / "tests" / "fixtures" / "sample_repo" / "requirements.txt"
    )
    fixture_lockfile.parent.mkdir(parents=True)
    fixture_lockfile.write_text("fastapi==0.110.0", encoding="utf-8")

    scan_policy = ScanPolicyConfig(
        exclude_globs=[
            ".git/**",
            "node_modules/**",
            "dist/**",
            "build/**",
            ".venv/**",
            "__pycache__/**",
            "vendor/**",
            "tests/fixtures/**",
        ],
    )
    engine = InventoryEngine(IgnorePolicy.from_config(scan_policy), scan_policy)

    result = engine.collect(tmp_path)

    assert Path("requirements.txt") in result.osv_lockfiles
    assert (
        Path("tests/fixtures/sample_repo/requirements.txt") not in result.osv_lockfiles
    )
    assert result.stats.skipped_reasons.ignored_pathspec >= 1
