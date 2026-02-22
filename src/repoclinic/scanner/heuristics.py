"""Deterministic heuristics for repo profiling."""

from __future__ import annotations

import json
import re

from repoclinic.scanner.inventory import FileRecord
from repoclinic.schemas.scanner_models import FolderSummary, ManifestSummary

ENTRYPOINT_CANDIDATE_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "index.js",
    "server.js",
    "main.ts",
    "manage.py",
}
FRAMEWORK_KEYWORDS = {
    "express": "Express",
    "nestjs": "NestJS",
    "next": "Next.js",
    "react": "React",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring-boot": "Spring Boot",
}
FOLDER_PURPOSES = {
    "src": ("Core application source", 0.95),
    "api": ("API handlers and endpoints", 0.85),
    "routes": ("Route/controller definitions", 0.85),
    "services": ("Service/business logic layer", 0.85),
    "models": ("Domain and data models", 0.85),
    "tests": ("Test suites", 0.9),
    ".": ("Repository root and entry assets", 0.6),
}


def detect_languages(files: list[FileRecord]) -> list[str]:
    """Detect languages present in scanned files."""
    languages = {record.language for record in files if record.language}
    return sorted(languages)


def detect_entry_points(files: list[FileRecord]) -> list[str]:
    """Find likely runtime entrypoint files."""
    entry_points: list[str] = []
    for record in files:
        if record.rel_path.name in ENTRYPOINT_CANDIDATE_NAMES:
            entry_points.append(record.rel_path.as_posix())
    return sorted(set(entry_points))


def detect_frameworks(files: list[FileRecord]) -> list[str]:
    """Infer frameworks from manifest and dependency files."""
    discovered: set[str] = set()
    for record in files:
        if record.rel_path.name == "package.json":
            discovered.update(_frameworks_from_package_json(record.content))
        elif record.rel_path.name in {"requirements.txt", "pyproject.toml"}:
            discovered.update(_frameworks_from_python_dependencies(record.content))
    return sorted(discovered)


def detect_architecture_hints(files: list[FileRecord]) -> list[str]:
    """Infer high-level architecture hints from path layout."""
    paths = [record.rel_path.as_posix().lower() for record in files]
    hints: set[str] = set()
    if any("/services/" in path or path.startswith("services/") for path in paths):
        hints.add("layered-service-structure")
    if any("/routes/" in path or path.startswith("routes/") for path in paths):
        hints.add("route-controller-pattern")
    if any(path.endswith("dockerfile") for path in paths):
        hints.add("containerized-runtime")
    return sorted(hints)


def summarize_folders(top_level_dirs: list[str]) -> list[FolderSummary]:
    """Map top-level folders to purpose guesses."""
    summaries: list[FolderSummary] = []
    for folder in top_level_dirs:
        purpose, confidence = FOLDER_PURPOSES.get(
            folder, ("General project assets", 0.5)
        )
        summaries.append(
            FolderSummary(path=folder, purpose_guess=purpose, confidence=confidence)
        )
    return summaries


def summarize_manifests(files: list[FileRecord]) -> list[ManifestSummary]:
    """Summarize dependency manifests and direct dependency counts."""
    summaries: list[ManifestSummary] = []
    for record in files:
        name = record.rel_path.name
        if name not in {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "pom.xml",
        }:
            continue
        ecosystem, dependency_count = _manifest_dependency_count(name, record.content)
        summaries.append(
            ManifestSummary(
                path=record.rel_path.as_posix(),
                ecosystem=ecosystem,
                direct_dependency_count=dependency_count,
            )
        )
    return summaries


def _frameworks_from_package_json(content: str) -> set[str]:
    discovered: set[str] = set()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return discovered
    dependencies = {}
    dependencies.update(payload.get("dependencies", {}))
    dependencies.update(payload.get("devDependencies", {}))
    for dep_name in dependencies:
        key = dep_name.lower()
        if key in FRAMEWORK_KEYWORDS:
            discovered.add(FRAMEWORK_KEYWORDS[key])
    return discovered


def _frameworks_from_python_dependencies(content: str) -> set[str]:
    discovered: set[str] = set()
    lower_content = content.lower()
    for keyword, framework in FRAMEWORK_KEYWORDS.items():
        if keyword in {"express", "nestjs", "next", "react", "spring-boot"}:
            continue
        if re.search(rf"\b{re.escape(keyword)}\b", lower_content):
            discovered.add(framework)
    return discovered


def _manifest_dependency_count(filename: str, content: str) -> tuple[str, int]:
    if filename == "package.json":
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return "npm", 0
        dependencies = payload.get("dependencies", {})
        dev_dependencies = payload.get("devDependencies", {})
        return "npm", len(dependencies) + len(dev_dependencies)
    if filename == "requirements.txt":
        lines = [
            line for line in content.splitlines() if line and not line.startswith("#")
        ]
        return "pip", len(lines)
    if filename == "pyproject.toml":
        count = len(re.findall(r'^\s*"[A-Za-z0-9_.\-]+', content, flags=re.MULTILINE))
        return "python", count
    if filename == "pom.xml":
        count = len(re.findall(r"<dependency>", content))
        return "maven", count
    return "unknown", 0
