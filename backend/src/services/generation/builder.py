"""Phase 3 + Phase 4 — per-course implementation build & hosting.

Each course becomes its OWN compiled Vite/React/TS application (no shared
renderer): the builder copies the per-course app template, bakes in this course's
`course.json` (the Lastenheft) and `asset_map.json`, runs `npm run build`, and
publishes that course's own `dist/` to the public `courses` bucket under a
versioned prefix. Nginx proxies `/storage/courses/...` for iframe embedding.

If the Node build toolchain is unavailable (or the build fails), a self-contained
static renderer is published instead so the pipeline always yields a hostable
artifact.
"""

import json
import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.config.settings import settings
from src.db.minio import ensure_bucket_exists, public_object_url, put_bytes, put_file

logger = logging.getLogger(__name__)


class BuildError(Exception):
    """Raised when a per-course build fails, carrying captured logs."""

    def __init__(self, message: str, logs: str) -> None:
        super().__init__(message)
        self.logs = logs


_REPO_ROOT = Path(__file__).resolve().parents[4]
_APP_TEMPLATE_FALLBACK = _REPO_ROOT / "course-app-template"


def course_prefix(company_slug: str, course_id: str, version: int) -> str:
    return f"{company_slug}/{course_id}/v{version}"


def index_url(prefix: str) -> str:
    return public_object_url(f"{prefix}/index.html", settings.courses_bucket)


def _app_template_dir() -> Path | None:
    configured = Path(settings.course_app_template)
    if (configured / "package.json").is_file():
        return configured
    if (_APP_TEMPLATE_FALLBACK / "package.json").is_file():
        return _APP_TEMPLATE_FALLBACK
    return None


def _course_json(spec: dict) -> dict:
    """Derive the runtime course.json (drop the asset manifest)."""
    course = {k: v for k, v in spec.items() if k != "asset_manifest"}
    course.setdefault("chapters", [])
    return course


def _npm() -> str | None:
    return shutil.which("npm")


def _finish_build(work: Path, npm: str, course: dict, asset_map: dict) -> Path | None:
    """Bake runtime data, run `npm run build`, return the dist path or None."""
    public = work / "public"
    public.mkdir(exist_ok=True)
    (public / "course.json").write_text(json.dumps(course), encoding="utf-8")
    (public / "asset_map.json").write_text(json.dumps(asset_map), encoding="utf-8")

    subprocess.run(
        [npm, "run", "build"],
        cwd=work,
        check=True,
        timeout=settings.course_build_timeout,
    )
    dist = work / "dist"
    if not (dist / "index.html").is_file():
        logger.warning("per-course build produced no index.html")
        return None
    # Ensure runtime data ships in dist (vite copies public/, but be safe).
    (dist / "course.json").write_text(json.dumps(course), encoding="utf-8")
    (dist / "asset_map.json").write_text(json.dumps(asset_map), encoding="utf-8")
    return dist


def _build_vite_app(template: Path, course: dict, asset_map: dict) -> Path | None:
    """Copy the template, bake data, run the build; return the dist path or None."""
    npm = _npm()
    if npm is None:
        logger.info("npm not found — skipping per-course Vite build")
        return None

    work = Path(tempfile.mkdtemp(prefix="coursebuild-"))
    try:
        for item in template.iterdir():
            if item.name in {"node_modules", "dist", ".git"}:
                continue
            dst = work / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

        # Reuse the template's installed dependencies if present.
        tpl_modules = template / "node_modules"
        if tpl_modules.is_dir():
            try:
                (work / "node_modules").symlink_to(tpl_modules, target_is_directory=True)
            except OSError:
                shutil.copytree(tpl_modules, work / "node_modules")
        else:
            subprocess.run([npm, "ci"], cwd=work, check=True, timeout=settings.course_build_timeout)

        return _finish_build(work, npm, course, asset_map)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("per-course Vite build failed (%s); using static fallback", exc)
        return None


def try_build_from_sources(
    source_files: dict[str, str],
    course: dict,
    asset_map: dict,
    *,
    run_quality_checks: bool = True,
) -> Path:
    """Build a Devin-authored project; raise :class:`BuildError` on failure.

    Unlike :func:`_build_from_sources` this captures *all* npm output so the
    caller can feed exact error logs into a repair prompt.
    """
    npm = _npm()
    if npm is None:
        raise BuildError("npm not found", "npm executable not found on PATH")

    work = Path(tempfile.mkdtemp(prefix="coursebuild-devin-"))
    try:
        for rel, content in source_files.items():
            dst = work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")

        # ── npm install ────────────────────────────────────────────────
        install_cmd = "ci" if (work / "package-lock.json").is_file() else "install"
        result = subprocess.run(
            [npm, install_cmd],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=settings.course_build_timeout,
        )
        if result.returncode != 0:
            logs = (
                f"=== npm {install_cmd} (exit {result.returncode}) ===\n"
                f"STDOUT:\n{result.stdout[-4000:]}\n"
                f"STDERR:\n{result.stderr[-4000:]}"
            )
            raise BuildError(f"npm {install_cmd} failed", logs)

        # ── optional quality checks (typecheck / lint / test) ──────────
        if run_quality_checks:
            pkg_path = work / "package.json"
            if pkg_path.is_file():
                pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
                scripts = pkg.get("scripts", {})
                check_failures: list[str] = []
                for script_name in ("typecheck", "lint", "test"):
                    if script_name not in scripts:
                        continue
                    qr = subprocess.run(
                        [npm, "run", script_name],
                        cwd=work,
                        capture_output=True,
                        text=True,
                        timeout=settings.course_build_timeout,
                    )
                    if qr.returncode != 0:
                        check_failures.append(
                            f"=== npm run {script_name} (exit {qr.returncode}) ===\n"
                            f"STDOUT:\n{qr.stdout[-4000:]}\n"
                            f"STDERR:\n{qr.stderr[-4000:]}"
                        )
                if check_failures:
                    raise BuildError(
                        "quality checks failed", "\n\n".join(check_failures)
                    )

        # ── npm run build ──────────────────────────────────────────────
        public = work / "public"
        public.mkdir(exist_ok=True)
        (public / "course.json").write_text(json.dumps(course), encoding="utf-8")
        (public / "asset_map.json").write_text(json.dumps(asset_map), encoding="utf-8")

        build_result = subprocess.run(
            [npm, "run", "build"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=settings.course_build_timeout,
        )
        if build_result.returncode != 0:
            logs = (
                f"=== npm run build (exit {build_result.returncode}) ===\n"
                f"STDOUT:\n{build_result.stdout[-4000:]}\n"
                f"STDERR:\n{build_result.stderr[-4000:]}"
            )
            raise BuildError("npm run build failed", logs)

        dist = work / "dist"
        if not (dist / "index.html").is_file():
            raise BuildError(
                "build produced no index.html",
                "npm run build completed but dist/index.html was not generated",
            )
        (dist / "course.json").write_text(json.dumps(course), encoding="utf-8")
        (dist / "asset_map.json").write_text(json.dumps(asset_map), encoding="utf-8")
        return dist

    except BuildError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise BuildError("build timed out", str(exc)) from exc
    except OSError as exc:
        raise BuildError(f"OS error during build: {exc}", str(exc)) from exc


def _build_from_sources(
    source_files: dict[str, str], course: dict, asset_map: dict
) -> Path | None:
    """Build a Devin-authored project (path -> content) into a dist/."""
    try:
        return try_build_from_sources(
            source_files, course, asset_map, run_quality_checks=False
        )
    except BuildError as exc:
        logger.warning("Devin-authored build failed (%s); using template/static fallback", exc)
        return None


_FALLBACK_TEMPLATE = Path(__file__).with_name("static_fallback.html")


def _static_fallback_html(course: dict) -> str:
    """A dependency-free renderer used when the Vite build can't run."""
    template = _FALLBACK_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("__TITLE__", str(course.get("title", "Course")))
        .replace("__BRAND__", str(course.get("primaryColor", "#5145E5")))
        .replace("__COURSE_DATA__", json.dumps(course))
    )


def _upload_dir(dist: Path, prefix: str) -> None:
    for root, _dirs, files in os.walk(dist):
        for name in files:
            local = Path(root) / name
            rel = local.relative_to(dist).as_posix()
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            put_file(str(local), f"{prefix}/{rel}", settings.courses_bucket, content_type)


def publish_built_course(
    company_slug: str,
    course_id: str,
    version: int,
    spec: dict,
    asset_map: dict | None = None,
    source_files: dict[str, str] | None = None,
) -> dict:
    """Build (or statically render) the course and upload it. Returns hosting info.

    If `source_files` (a Devin-authored project) is supplied, it is built first;
    otherwise the prebuilt app template is used, then a static fallback.
    """
    ensure_bucket_exists(settings.courses_bucket)
    asset_map = asset_map or {}
    course = _course_json(spec)
    prefix = course_prefix(company_slug, course_id, version)

    dist: Path | None = None
    if settings.course_build_enabled and source_files:
        dist = _build_from_sources(source_files, course, asset_map)
    if dist is None and settings.course_build_enabled:
        template = _app_template_dir()
        if template is not None:
            dist = _build_vite_app(template, course, asset_map)

    if dist is not None:
        _upload_dir(dist, prefix)
        built = True
    else:
        put_bytes(
            _static_fallback_html(course).encode("utf-8"),
            f"{prefix}/index.html",
            settings.courses_bucket,
            "text/html",
        )
        built = False

    put_bytes(
        json.dumps(course).encode("utf-8"),
        f"{prefix}/course.json",
        settings.courses_bucket,
        "application/json",
    )
    put_bytes(
        json.dumps(asset_map).encode("utf-8"),
        f"{prefix}/asset_map.json",
        settings.courses_bucket,
        "application/json",
    )
    url = index_url(prefix)
    logger.info("published course %s v%s -> %s (built=%s)", course_id, version, prefix, built)
    return {"prefix": prefix, "course_url": url, "iframe_url": url, "built": built}
