from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_PORT = 3001
PROXY_PORT = 8080


@dataclass
class ListenerInfo:
    port: int
    pid: int
    name: str
    path: str

    def summary(self) -> str:
        parts = [f"端口 {self.port}", f"PID {self.pid}"]
        if self.name:
            parts.append(self.name)
        return " | ".join(parts)


@dataclass
class RuntimePaths:
    workspace: Path
    scripts_dir: Path
    runtime_root: Path
    app_stderr_log: Path
    proxy_access_log: Path
    proxy_error_log: Path
    tailscale: Path | None


def _candidate_workspace_roots(seed: Path) -> list[Path]:
    candidates = [seed]
    candidates.extend(list(seed.parents)[:8])
    ordered: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(candidate)
    return ordered


def _contains_runtime_scripts(candidate: Path) -> bool:
    scripts_dir = candidate / "scripts"
    return (scripts_dir / "start-mobile-codex-stack.ps1").exists() or (scripts_dir / "start-mobile-codex-stack.sh").exists()


def resolve_workspace() -> Path:
    if getattr(sys, "frozen", False):
        seed = Path(sys.executable).resolve().parent
    else:
        seed = Path(__file__).resolve().parent

    for candidate in _candidate_workspace_roots(seed):
        if _contains_runtime_scripts(candidate):
            return candidate

    return seed


def _resolve_runtime_root(workspace: Path) -> Path:
    configured = os.environ.get("MOBILE_CODEX_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser()

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.name.endswith(".app"):
                return parent.parent / ".runtime"

    return workspace / ".runtime"


def _resolve_command_path(
    env_name: str,
    command_names: list[str],
    fallback_paths: list[Path],
) -> Path | None:
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured).expanduser()

    for command_name in command_names:
        found = shutil.which(command_name)
        if found:
            return Path(found)

    for fallback in fallback_paths:
        if fallback.exists():
            return fallback

    return None


class HostRuntime:
    script_extension = ""
    platform_label = "unknown"

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.paths = self.resolve_paths()

    def resolve_paths(self) -> RuntimePaths:
        raise NotImplementedError

    def subprocess_options(self) -> dict[str, Any]:
        return {}

    def command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("MOBILE_CODEX_RUNTIME_DIR", str(self.paths.runtime_root))
        return env

    def run_command(
        self,
        args: list[str],
        timeout: int = 20,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = self.command_env()
        if env:
            merged_env.update(env)
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=str(cwd or self.workspace),
            env=merged_env,
            **self.subprocess_options(),
        )

    def run_script(self, script_base_name: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        script_path = self.paths.scripts_dir / f"{script_base_name}{self.script_extension}"
        raise NotImplementedError

    def start_stack(self) -> subprocess.CompletedProcess[str]:
        return self.run_script("start-mobile-codex-stack", timeout=30)

    def stop_stack(self) -> subprocess.CompletedProcess[str]:
        return self.run_script("stop-mobile-codex-stack", timeout=20)

    def enable_remote(self) -> subprocess.CompletedProcess[str]:
        if not self.paths.tailscale or not self.paths.tailscale.exists():
            return self._missing_command_result("Tailscale CLI 未找到")
        return self.run_command([str(self.paths.tailscale), "serve", "--bg", f"http://127.0.0.1:{PROXY_PORT}"], timeout=20)

    def disable_remote(self) -> subprocess.CompletedProcess[str]:
        if not self.paths.tailscale or not self.paths.tailscale.exists():
            return self._missing_command_result("Tailscale CLI 未找到")
        return self.run_command([str(self.paths.tailscale), "serve", "reset"], timeout=10)

    def load_tailscale_status(self) -> dict[str, Any]:
        if not self.paths.tailscale or not self.paths.tailscale.exists():
            return {"ok": False, "error": "Tailscale CLI 未找到"}
        result = self.run_command([str(self.paths.tailscale), "status", "--json"])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or result.stdout.strip() or "读取 Tailscale 状态失败"}
        try:
            return {"ok": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Tailscale 返回的 JSON 无法解析: {exc}"}

    def load_serve_status(self) -> dict[str, Any]:
        if not self.paths.tailscale or not self.paths.tailscale.exists():
            return {"ok": False, "error": "Tailscale CLI 未找到"}
        result = self.run_command([str(self.paths.tailscale), "serve", "status", "--json"])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or result.stdout.strip() or "读取远程发布状态失败"}
        try:
            return {"ok": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"远程发布状态 JSON 无法解析: {exc}"}

    def get_listener_map(self, ports: list[int] | None = None) -> dict[int, ListenerInfo]:
        raise NotImplementedError

    def tail_proxy_logs(self, limit: int = 40) -> dict[str, list[str]]:
        return {
            "access": self._tail_lines(self.paths.proxy_access_log, limit),
            "error": self._tail_lines(self.paths.proxy_error_log, limit),
        }

    @staticmethod
    def _tail_lines(file_path: Path, max_lines: int = 200) -> list[str]:
        if not file_path.exists():
            return []
        lines: deque[str] = deque(maxlen=max_lines)
        with file_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.rstrip()
                if stripped:
                    lines.append(stripped)
        return list(lines)

    @staticmethod
    def _missing_command_result(message: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=127, stdout="", stderr=message)


class WindowsHostRuntime(HostRuntime):
    script_extension = ".ps1"
    platform_label = "windows"

    def resolve_paths(self) -> RuntimePaths:
        runtime_root = _resolve_runtime_root(self.workspace)
        scripts_dir = self.workspace / "scripts"
        app_stderr_log = self.workspace / "tmp" / "logs" / "mobile-codex-app.stderr.log"
        system_drive = os.environ.get("SystemDrive", "C:")
        ascii_alias = Path(os.environ.get("MOBILE_CODEX_ASCII_ALIAS") or (Path(system_drive) / "mobileCodexHelper_ascii"))
        runtime_leaf = runtime_root.name or ".runtime"
        proxy_log_root = ascii_alias / runtime_leaf / "nginx" / "logs"
        tailscale = _resolve_command_path(
            "MOBILE_CODEX_TAILSCALE",
            ["tailscale"],
            [Path(r"C:\Program Files\Tailscale\tailscale.exe")],
        )
        return RuntimePaths(
            workspace=self.workspace,
            scripts_dir=scripts_dir,
            runtime_root=runtime_root,
            app_stderr_log=app_stderr_log,
            proxy_access_log=proxy_log_root / "mobile-codex.access.log",
            proxy_error_log=proxy_log_root / "mobile-codex.error.log",
            tailscale=tailscale,
        )

    def subprocess_options(self) -> dict[str, Any]:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }

    def run_script(self, script_base_name: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        script_path = self.paths.scripts_dir / f"{script_base_name}{self.script_extension}"
        return self.run_command(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            timeout=timeout,
        )

    def get_listener_map(self, ports: list[int] | None = None) -> dict[int, ListenerInfo]:
        target_ports = ports or [APP_PORT, PROXY_PORT]
        ports_literal = ",".join(str(port) for port in target_ports)
        command = f"""
$ports = @({ports_literal})
$listeners = foreach ($item in Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $ports -contains $_.LocalPort }}) {{
    $proc = Get-Process -Id $item.OwningProcess -ErrorAction SilentlyContinue
    [PSCustomObject]@{{
        port = [int]$item.LocalPort
        pid = [int]$item.OwningProcess
        name = if ($proc) {{ $proc.ProcessName }} else {{ '' }}
        path = if ($proc -and $proc.Path) {{ $proc.Path }} else {{ '' }}
    }}
}}
if ($listeners) {{
    $listeners | ConvertTo-Json -Compress
}}
"""
        result = self.run_command(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            timeout=12,
        )
        if result.returncode != 0:
            return {}
        text = result.stdout.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
        items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        listener_map: dict[int, ListenerInfo] = {}
        for item in items:
            try:
                port = int(item.get("port"))
                listener_map[port] = ListenerInfo(
                    port=port,
                    pid=int(item.get("pid")),
                    name=str(item.get("name") or ""),
                    path=str(item.get("path") or ""),
                )
            except (TypeError, ValueError):
                continue
        return listener_map


class MacHostRuntime(HostRuntime):
    script_extension = ".sh"
    platform_label = "macos"

    def resolve_paths(self) -> RuntimePaths:
        runtime_root = _resolve_runtime_root(self.workspace)
        scripts_dir = self.workspace / "scripts"
        app_stderr_log = self.workspace / "tmp" / "logs" / "mobile-codex-app.stderr.log"
        proxy_log_root = runtime_root / "nginx" / "logs"
        tailscale = _resolve_command_path(
            "MOBILE_CODEX_TAILSCALE",
            ["tailscale"],
            [
                Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale"),
                Path("/opt/homebrew/bin/tailscale"),
                Path("/usr/local/bin/tailscale"),
            ],
        )
        return RuntimePaths(
            workspace=self.workspace,
            scripts_dir=scripts_dir,
            runtime_root=runtime_root,
            app_stderr_log=app_stderr_log,
            proxy_access_log=proxy_log_root / "mobile-codex.access.log",
            proxy_error_log=proxy_log_root / "mobile-codex.error.log",
            tailscale=tailscale,
        )

    def run_script(self, script_base_name: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        script_path = self.paths.scripts_dir / f"{script_base_name}{self.script_extension}"
        return self.run_command(["/bin/bash", str(script_path)], timeout=timeout)

    def get_listener_map(self, ports: list[int] | None = None) -> dict[int, ListenerInfo]:
        target_ports = ports or [APP_PORT, PROXY_PORT]
        listener_map: dict[int, ListenerInfo] = {}
        for port in target_ports:
            result = self.run_command(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpctn"],
                timeout=8,
            )
            if result.returncode not in {0, 1}:
                continue
            pid = None
            name = ""
            for raw_line in result.stdout.splitlines():
                if not raw_line:
                    continue
                prefix, value = raw_line[0], raw_line[1:]
                if prefix == "p" and pid is None:
                    try:
                        pid = int(value)
                    except ValueError:
                        pid = None
                elif prefix == "c" and not name:
                    name = value
            if pid is None:
                continue
            path = ""
            ps_result = self.run_command(["ps", "-p", str(pid), "-o", "command="], timeout=5)
            if ps_result.returncode == 0:
                path = ps_result.stdout.strip()
            listener_map[port] = ListenerInfo(port=port, pid=pid, name=name, path=path)
        return listener_map


def create_host_runtime(workspace: Path) -> HostRuntime:
    if sys.platform == "win32":
        return WindowsHostRuntime(workspace)
    return MacHostRuntime(workspace)
