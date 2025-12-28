"""Utility helpers for managing the UnRen-forall toolkit.

This module downloads, caches and launches Lurmel's UnRen batch scripts,
allowing RenLocalizer to automatically extract/decompile Ren'Py projects
before parsing them.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from src.utils.config import ConfigManager


@dataclass
class UnRenDownloadResult:
    """Metadata for the downloaded UnRen package."""

    root_path: Path
    version_label: str
    source_url: str


class UnRenManager:
    """Handles downloading and launching the UnRen batch scripts."""

    DEFAULT_RELEASE_URL = (
        "https://github.com/Lurmel/UnRen-forall/releases/download/"
        "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.17/"
        "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.14.zip"
    )
    FALLBACK_RELEASE_URLS = [
        (
            "https://github.com/Lurmel/UnRen-forall/releases/download/"
            "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.17/UnRen-link.txt"
        ),
        "https://github.com/Lurmel/UnRen-forall/releases/latest/download/UnRen-forall.zip",
        (
            "https://github.com/Lurmel/UnRen-forall/releases/download/"
            "UnRen-forall_la_0.35-le_9.6.47-cu_9.7.14/"
            "UnRen-forall-la_0.35-le_9.6.47-cu_9.7.14.zip"
        ),
    ]

    SCRIPT_NAMES = {
        "auto": "UnRen-forall.bat",
        "forall": "UnRen-forall.bat",
        "legacy": "UnRen-legacy.bat",
        "current": "UnRen-current.bat",
    }

    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Paths & availability
    # ------------------------------------------------------------------
    def get_cache_dir(self) -> Path:
        """Return the folder where UnRen should be cached."""

        if os.name == "nt":
            base = Path(os.getenv("LOCALAPPDATA", Path.home()))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "RenLocalizer" / "unren"

    def get_custom_path(self) -> Optional[Path]:
        """Return user-provided UnRen location, if any."""

        custom = (self.config.app_settings.unren_custom_path or "").strip()
        if custom:
            path = Path(custom)
            if path.exists():
                # Only accept custom path if it contains .bat scripts for UnRen
                found_script = any(path.glob('**/*.bat'))
                if found_script:
                    return path
                self.logger.warning("Configured UnRen path doesn't contain batch scripts: %s", path)
                return None
            self.logger.warning("Configured UnRen path does not exist: %s", path)
        return None

    def get_unren_root(self) -> Optional[Path]:
        """Locate the folder containing the UnRen batch files."""

        custom = self.get_custom_path()
        if custom:
            return custom

        cache_dir = self.get_cache_dir()
        if cache_dir.exists():
            return cache_dir
        return None

    def is_available(self) -> bool:
        """Check if any UnRen script is ready for use."""

        root = self.get_unren_root()
        if not root:
            return False
        for script in self.SCRIPT_NAMES.values():
            if (root / script).exists():
                return True
        return False

    def verify_installation(self) -> dict:
        """Return a dict with details about the installed UnRen package.

        Useful for UI preflight checks and debug reporting.
        """
        root = self.get_unren_root()
        details = {
            'installed': False,
            'root': str(root) if root else None,
            'scripts': [],
            'errors': []
        }
        if not root:
            details['errors'].append('UnRen root not found')
            return details
        try:
            # enumerate candidate scripts
            for s in root.glob('**/*.bat'):
                details['scripts'].append(str(s))
            details['installed'] = len(details['scripts']) > 0
        except Exception as exc:  # pragma: no cover - introspection
            details['errors'].append(str(exc))
        return details

    # ------------------------------------------------------------------
    # Download / extraction
    # ------------------------------------------------------------------
    def ensure_available(self, force_download: bool = False) -> Path:
        """Ensure UnRen exists locally, downloading if required."""

        if not force_download and self.is_available():
            return self.get_unren_root()  # type: ignore

        if not self.config.app_settings.unren_auto_download and not force_download:
            raise RuntimeError("UnRen is not available locally and auto-download is disabled.")

        download_result = self._download_and_extract()
        self.config.app_settings.unren_cached_version = download_result.version_label
        self.config.app_settings.unren_last_checked = datetime.utcnow().isoformat()
        if self.config.app_settings.auto_save_settings:
            self.config.save_config()
        return download_result.root_path

    def _download_and_extract(self) -> UnRenDownloadResult:
        """Download the UnRen zip and extract it to cache dir."""

        target_dir = self.get_cache_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        urls = [self.DEFAULT_RELEASE_URL, *self.FALLBACK_RELEASE_URLS]
        last_error: Optional[Exception] = None
        zip_path = target_dir / "UnRen-forall.zip"

        for url in urls:
            try:
                self.logger.info("Downloading UnRen package from %s", url)
                self._stream_download(url, zip_path)
                version = self._infer_version_from_filename(zip_path.name)
                self._extract_zip(zip_path, target_dir)
                zip_path.unlink(missing_ok=True)
                return UnRenDownloadResult(root_path=target_dir, version_label=version, source_url=url)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.logger.warning("Failed to download from %s: %s", url, exc)

        raise RuntimeError("Could not download UnRen package") from last_error

    def _stream_download(self, url: str, destination: Path) -> None:
        """Download a URL to the given destination path."""

        if url.lower().endswith(".txt"):
            resolved = self._extract_url_from_text_link(url)
            if not resolved:
                raise RuntimeError("Could not resolve download URL from link file")
            self.logger.info("Resolved UnRen link helper to %s", resolved)
            self._stream_download(resolved, destination)
            return

        with urlopen(url, timeout=60) as response, open(destination, "wb") as out_file:
            chunk = response.read(8192)
            while chunk:
                out_file.write(chunk)
                chunk = response.read(8192)

    def _extract_url_from_text_link(self, url: str) -> Optional[str]:
        """Download a helper text file and extract the first https URL."""

        try:
            with urlopen(url, timeout=30) as response:
                data = response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError) as exc:  # pragma: no cover - network
            self.logger.warning("Failed to read redirect link %s: %s", url, exc)
            return None

        match = re.search(r"https?://\S+", data)
        if match:
            candidate = match.group(0).strip()
            # Strip trailing punctuation/newlines
            candidate = candidate.rstrip('\n\r\t\'"')
            return candidate
        self.logger.warning("Could not find download URL inside %s", url)
        return None

    def _extract_zip(self, zip_path: Path, destination: Path) -> None:
        """Extract the downloaded archive into destination."""

        temp_dir = Path(tempfile.mkdtemp(prefix="unren_extract_"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            # Some archives place everything inside a top-level folder like 'UnRen-forall'
            # We want to flatten the archive contents into our destination so looking
            # for scripts is deterministic.
            # Move extracted content up one level if needed.
            entries = list(temp_dir.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                # Single top-level folder found, use its content
                top = entries[0]
                for item in top.iterdir():
                    target = destination / item.name
                    if target.exists():
                        if target.is_file():
                            target.unlink()
                        else:
                            shutil.rmtree(target)
                    shutil.move(str(item), target)
            else:
                # Move everything directly
                for item in entries:
                    target = destination / item.name
                    if target.exists():
                        if target.is_file():
                            target.unlink()
                        else:
                            shutil.rmtree(target)
                    shutil.move(str(item), target)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _infer_version_from_filename(self, filename: str) -> str:
        """Best-effort extraction of version label from archive name."""

        stem = filename.replace(".zip", "")
        return stem or f"downloaded-{datetime.utcnow().strftime('%Y%m%d')}"

    # ------------------------------------------------------------------
    # Variant detection & invocation
    # ------------------------------------------------------------------
    def detect_variant_for_project(self, project_dir: Path) -> str:
        """Heuristic to decide which UnRen script to run for a project."""

        project_dir = project_dir.resolve()
        version_file = project_dir / "renpy-version.txt"
        if version_file.exists():
            try:
                version_text = version_file.read_text(encoding="utf-8", errors="ignore")
                major = self._parse_major_version(version_text)
                if major and major >= 8:
                    return "current"
                if major and major < 8:
                    return "legacy"
            except Exception:  # noqa: BLE001
                pass

        # Fallback: let UnRen-forall auto-detect
        return "auto"

    def _parse_major_version(self, version_text: str) -> Optional[int]:
        digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in version_text)
        parts = [p for p in digits.split() if p]
        if not parts:
            return None
        try:
            return int(parts[0].split(".")[0])
        except ValueError:
            return None

    def run_unren(
        self,
        project_dir: Path,
        variant: str = "auto",
        wait: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
        automation_script: Optional[str] = None,
        timeout: Optional[int] = 300,  # 5 minute default timeout for automation
    ) -> subprocess.Popen:
        """Launch the UnRen script and return the Popen process.

        Also makes safety checks and throws a clear FileNotFoundError if no .bat
        script exists in the UnRen root.

        Notes:
        - If the caller passes a 'game' subfolder, normalize to the project's
          root (the folder that contains 'game', 'lib' or 'renpy').
        - Returns the spawned process, or raises detailed errors on failure.
        """

        """Launch the UnRen batch script for a project directory."""

        if os.name != "nt":
            raise RuntimeError("Automated UnRen support is currently available only on Windows.")

        root = self.ensure_available()
        project_dir = project_dir.resolve()

        # Normalize the project root: prefer a directory that contains 'game', 'lib' or 'renpy'.
        norm_dir = project_dir
        try:
            if project_dir.name.lower() == 'game':
                self.logger.debug("Project directory ends with 'game', normalizing to parent: %s", project_dir.parent)
                norm_dir = project_dir.parent
            elif not any((project_dir / d).exists() for d in ('game', 'lib', 'renpy')):
                parent = project_dir.parent
                if any((parent / d).exists() for d in ('game', 'lib', 'renpy')):
                    self.logger.debug("Project directory missing expected subfolders, normalizing to parent: %s", parent)
                    norm_dir = parent
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug("Error while normalizing project root: %s", exc)
        project_dir = norm_dir

        if variant == "auto":
            variant = self.detect_variant_for_project(project_dir)

        script_name = self.SCRIPT_NAMES.get(variant, self.SCRIPT_NAMES["auto"])
        script_path = root / script_name
        if not script_path.exists():
            # Try to find any batch file that looks like UnRen
            candidates = list(root.glob('*.bat')) + list(root.glob('**/*.bat'))
            found = None
            for c in candidates:
                name = c.name.lower()
                if 'unren' in name or 'unren-forall' in name:
                    found = c
                    break
            if found:
                self.logger.warning("Requested UnRen script %s not found; falling back to %s", script_path.name, found.name)
                script_path = found
            else:
                raise FileNotFoundError(f"UnRen script not found: {script_path}")

        interactive = automation_script is None and not wait and log_callback is None

        self.logger.info("Launching %s for %s", script_name, project_dir)

        creation_flags = 0
        if os.name == "nt":
            if interactive:
                creation_flags = subprocess.CREATE_NEW_CONSOLE
            else:
                creation_flags = subprocess.CREATE_NO_WINDOW

        popen_kwargs = {
            "cwd": str(project_dir),
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = creation_flags

        if interactive:
            # Give control to the spawned console so the user can interact.
            popen_kwargs["stdout"] = None
            popen_kwargs["stderr"] = None
        else:
            popen_kwargs["stdout"] = subprocess.PIPE
            popen_kwargs["stderr"] = subprocess.STDOUT
            popen_kwargs["text"] = True

        if automation_script is not None:
            popen_kwargs["stdin"] = subprocess.PIPE

        # Always invoke via cmd.exe /c on Windows - this is more deterministic
        # and avoids issues when launching .bat files directly.
        if os.name == 'nt':
            # Use 'call' to ensure batch file returns
            command = ["cmd.exe", "/c", "call", str(script_path), str(project_dir)]
        else:
            command = [str(script_path), str(project_dir)]

        process = subprocess.Popen(  # noqa: S603
            command,
            **popen_kwargs,
        )

        # If interactive and on Windows, the above will open a new console.
        # If the process couldn't be spawned, raise a clear error.
        if process is None:
            raise RuntimeError(f"Failed to launch UnRen script: {script_path}")

        # Logging for debugging
        self.logger.debug("UnRen command: %s", ' '.join(map(str, command)))

        if automation_script and process.stdin:
            process.stdin.write(automation_script)
            process.stdin.flush()
            process.stdin.close()

        if wait and process.stdout:
            import time
            start_time = time.time()
            lines_read = 0
            last_activity = start_time
            
            for line in process.stdout:
                lines_read += 1
                last_activity = time.time()
                if log_callback:
                    log_callback(line.rstrip())
                else:
                    self.logger.info("[UnRen] %s", line.rstrip())
                
                # Check for timeout during automation
                if automation_script and timeout:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        self.logger.warning("UnRen automation timed out after %d seconds", timeout)
                        process.terminate()
                        break
            
            # Wait for process to finish, with timeout
            try:
                if automation_script and timeout:
                    remaining = max(10, timeout - (time.time() - start_time))
                    process.wait(timeout=remaining)
                else:
                    process.wait()
            except subprocess.TimeoutExpired:
                self.logger.warning("UnRen process did not exit cleanly, terminating...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            finally:
                # If non-zero exit, include last lines for debugging
                if process.returncode != 0:
                    try:
                        # Attempt to read any remaining lines
                        remaining_lines = []
                        # Not safe to call readlines() as process stdout is already being iterated
                        # So this is best-effort to log that process returned non-zero
                        self.logger.warning("UnRen process ended with exit code %s; check logs for details", process.returncode)
                    except Exception:
                        pass
