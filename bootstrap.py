"""Backend bootstrap helpers for Hermes weather plugin.

Downloads or builds required Rust binaries into ~/.hermes/weather/bin on first use.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parent
OWNER = "FahrenheitResearch"
RUSTDAR_REF = "master"
ECAPE_REF = "main"


def _hermes_home() -> Path:
    try:
        from hermes_cli.config import get_hermes_home
        return get_hermes_home()
    except Exception:
        return Path.home() / ".hermes"


def _weather_root() -> Path:
    root = _hermes_home() / "weather"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _bin_dir() -> Path:
    path = _weather_root() / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _src_dir() -> Path:
    path = _weather_root() / "src"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _exe_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _cargo() -> str | None:
    env = os.environ.get("CARGO")
    if env and Path(env).exists():
        return env
    return shutil.which("cargo")


def _copy_if_newer(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
        shutil.copy2(src, dst)


def _download_repo_archive(repo: str, ref: str, dest: Path) -> tuple[Path | None, str | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive_url = f"https://codeload.github.com/{OWNER}/{repo}/zip/refs/heads/{ref}"
    with tempfile.TemporaryDirectory(prefix=f"{repo}-{ref}-") as tmp:
        zip_path = Path(tmp) / f"{repo}-{ref}.zip"
        try:
            urllib.request.urlretrieve(archive_url, zip_path)
        except Exception as exc:
            return None, f"Failed to download {repo} source archive: {exc}"

        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest.parent)
                roots = [p for p in dest.parent.iterdir() if p.is_dir() and p.name.startswith(f"{repo}-")]
                if not roots:
                    return None, f"Downloaded archive for {repo} but could not locate extracted source"
                extracted = max(roots, key=lambda p: p.stat().st_mtime)
                if dest.exists():
                    shutil.rmtree(dest)
                extracted.rename(dest)
        except Exception as exc:
            return None, f"Failed to extract {repo} source archive: {exc}"

    return dest, None


def _build_binary(source_dir: Path, bin_name: str) -> tuple[Path | None, str | None]:
    cargo = _cargo()
    if not cargo:
        return None, (
            "Rust toolchain not found. Install cargo/rustc or set the binary path explicitly "
            "with the relevant environment variable."
        )

    try:
        subprocess.run(
            [cargo, "build", "--release", "--bin", bin_name],
            cwd=source_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return None, stderr or f"cargo build failed for {bin_name}"

    built = source_dir / "target" / "release" / _exe_name(bin_name)
    if not built.exists():
        return None, f"Built {bin_name} but could not find output binary at {built}"
    return built, None


def _ensure_repo_binary(env_var: str, repo: str, ref: str, bin_name: str, *, auto_build: bool = True) -> tuple[str | None, str | None]:
    env_path = os.environ.get(env_var)
    if env_path:
        env_bin = Path(env_path)
        if env_bin.exists():
            return str(env_bin), None
        return None, f"{env_var} is set but does not exist: {env_bin}"

    cached = _bin_dir() / _exe_name(bin_name)
    if cached.exists():
        return str(cached), None
    if not auto_build:
        return None, None

    source_dir = _src_dir() / f"{repo}-{ref}"
    if not source_dir.exists():
        _, err = _download_repo_archive(repo, ref, source_dir)
        if err:
            return None, err

    built, err = _build_binary(source_dir, bin_name)
    if err:
        return None, err
    _copy_if_newer(built, cached)
    return str(cached), None


def _ensure_bundled_nexrad(auto_build: bool = True) -> tuple[str | None, str | None]:
    env_path = os.environ.get("NEXRAD_RENDER_PATH")
    if env_path:
        env_bin = Path(env_path)
        if env_bin.exists():
            return str(env_bin), None
        return None, f"NEXRAD_RENDER_PATH is set but does not exist: {env_bin}"

    cached = _bin_dir() / _exe_name("nexrad-render-cli")
    if cached.exists():
        return str(cached), None
    if not auto_build:
        return None, None

    bundled_src = PLUGIN_DIR / "radar_backends" / "nexrad-render-cli"
    if not bundled_src.exists():
        return None, "Bundled nexrad-render-cli source is missing from the installed package"

    work_dir = _src_dir() / "nexrad-render-cli"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(bundled_src, work_dir)

    built, err = _build_binary(work_dir, "nexrad-render-cli")
    if err:
        return None, err
    _copy_if_newer(built, cached)
    return str(cached), None


def ensure_radar_binary(backend: str, *, auto_build: bool = True) -> tuple[str | None, str | None]:
    backend = (backend or "rustdar").strip().lower()
    if backend == "rustdar":
        return _ensure_repo_binary("RADAR_RENDER_PATH", "rustdar", RUSTDAR_REF, "radar-render", auto_build=auto_build)
    if backend == "nexrad":
        return _ensure_bundled_nexrad(auto_build=auto_build)
    return None, f"Unsupported RADAR_BACKEND '{backend}'"


def ensure_ecape_runner(*, auto_build: bool = True) -> tuple[str | None, str | None]:
    return _ensure_repo_binary("ECAPE_RS_RUNNER", "ecape-rs", ECAPE_REF, "run_case", auto_build=auto_build)
