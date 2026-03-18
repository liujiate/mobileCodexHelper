#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


EXPECTED_UPSTREAM_DIR = "claudecodeui-1.25.2"
EXPECTED_SESSION_TYPES = {"session_meta", "event_msg", "response_item"}


def result_item(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"name": name, "ok": ok, "detail": detail}


def check_upstream(repo_root: Path) -> dict[str, object]:
    upstream_dir = Path(os.environ.get("MOBILE_CODEX_UPSTREAM_DIR") or (repo_root / "vendor" / EXPECTED_UPSTREAM_DIR))
    if not upstream_dir.exists():
        return result_item("upstream", False, f"missing {upstream_dir}")
    package_json = upstream_dir / "package.json"
    if not package_json.exists():
        return result_item("upstream", False, f"missing {package_json}")
    try:
        package = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return result_item("upstream", False, f"invalid package.json: {exc}")
    version = str(package.get("version") or "").strip()
    if version and version != "1.25.2":
        return result_item("upstream", False, f"expected version 1.25.2, got {version}")
    return result_item("upstream", True, str(upstream_dir))


def check_codex_cli() -> dict[str, object]:
    try:
        result = subprocess.run(
            ["codex", "mcp", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        return result_item("codex_cli", False, "codex not found on PATH")
    except subprocess.TimeoutExpired:
        return result_item("codex_cli", False, "codex mcp list timed out")

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        return result_item("codex_cli", False, detail)
    return result_item("codex_cli", True, "codex mcp list ok")


def check_codex_config() -> dict[str, object]:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return result_item("codex_config", False, f"missing {config_path}")
    if tomllib is None:
        try:
            config_path.read_text(encoding="utf-8")
        except OSError as exc:
            return result_item("codex_config", False, f"failed to read config: {exc}")
        return result_item("codex_config", True, f"{config_path} (readable, parse skipped: tomllib unavailable)")
    try:
        with config_path.open("rb") as handle:
            tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        return result_item("codex_config", False, f"invalid TOML: {exc}")
    return result_item("codex_config", True, str(config_path))


def iter_session_files(sessions_root: Path) -> list[Path]:
    if not sessions_root.exists():
        return []
    return sorted(
        path for path in sessions_root.rglob("*.jsonl")
        if path.is_file() and not path.name.startswith("agent-")
    )


def check_codex_sessions() -> dict[str, object]:
    sessions_root = Path.home() / ".codex" / "sessions"
    session_files = iter_session_files(sessions_root)
    if not session_files:
        return result_item("codex_sessions", False, f"no jsonl found under {sessions_root}")

    for session_file in session_files:
        seen_types: set[str] = set()
        try:
            with session_file.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry_type = entry.get("type")
                    if isinstance(entry_type, str):
                        seen_types.add(entry_type)
                    if EXPECTED_SESSION_TYPES.issubset(seen_types):
                        return result_item("codex_sessions", True, str(session_file))
        except OSError as exc:
            return result_item("codex_sessions", False, f"failed to read {session_file}: {exc}")

    return result_item(
        "codex_sessions",
        False,
        "found session files but no file contained session_meta, event_msg, and response_item",
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    checks = [
        check_upstream(repo_root),
        check_codex_cli(),
        check_codex_config(),
        check_codex_sessions(),
    ]
    payload = {
        "ok": all(bool(item["ok"]) for item in checks),
        "checks": checks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
