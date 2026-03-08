import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(os.getcwd())
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_value(*names: str, default: str = "") -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return default


def _env_flag(*names: str, default: str = "false") -> bool:
    return _env_value(*names, default=default).strip().lower() in _TRUE_VALUES


def _resolve_path(*env_names: str, default_path: Path, legacy_paths: tuple[Path, ...] = ()) -> str:
    explicit = _env_value(*env_names, default="")
    if explicit:
        return explicit
    if default_path.exists():
        return str(default_path)
    for legacy_path in legacy_paths:
        if legacy_path.exists():
            return str(legacy_path)
    return str(default_path)


def _path_variants(raw_path: str) -> set[str]:
    cleaned = str(raw_path or "").strip().rstrip("/").rstrip("\\")
    if not cleaned:
        return set()

    path = Path(cleaned).expanduser()
    lexical_absolute = path if path.is_absolute() else (_REPO_ROOT / path)
    variants = {
        cleaned,
        lexical_absolute.as_posix(),
    }

    try:
        variants.add(lexical_absolute.relative_to(_REPO_ROOT).as_posix())
    except ValueError:
        pass

    try:
        variants.add(lexical_absolute.resolve(strict=False).as_posix())
    except OSError:
        pass

    return {value for value in variants if value}


def _normalize_runtime_path(raw_path: str, *, canonical_path: Path, legacy_paths: tuple[Path, ...]) -> str:
    raw_variants = _path_variants(raw_path)
    canonical = str(canonical_path)
    if not raw_variants:
        return canonical

    canonical_variants = _path_variants(canonical)
    if raw_variants & canonical_variants:
        return canonical

    for legacy_path in legacy_paths:
        if raw_variants & _path_variants(str(legacy_path)):
            return canonical

    return str(raw_path)


class Settings(BaseSettings):
    """
    Runtime configuration for the current ARIS codebase.

    New `ARIS_*` variables are accepted first. Existing `SABR_*` variables remain
    supported so the current deployment and tests do not break during refactoring.
    """

    ENGINE_TYPE: str = _env_value("ARIS_ENGINE_TYPE", "SABR_ENGINE_TYPE", default="")
    DEPS_CLASS: str = _env_value("ARIS_DEPS_CLASS", "SABR_DEPS_CLASS", default="")
    GEMINI_API_KEY: str = _env_value("GEMINI_API_KEY", default="your-key-here")
    DEFAULT_MODEL: str = _env_value("ARIS_DEFAULT_MODEL", "SABR_DEFAULT_MODEL", default="gemini-3-flash-preview")
    GEMINI_API_VERSION: str = _env_value("ARIS_GEMINI_API_VERSION", "SABR_GEMINI_API_VERSION", default="v1beta")
    GEMINI_MAX_OUTPUT_TOKENS: int = int(
        _env_value("ARIS_GEMINI_MAX_OUTPUT_TOKENS", "GEMINI_MAX_OUTPUT_TOKENS", default="32768")
    )
    GEMINI_UNAVAILABLE_RETRIES: int = int(
        _env_value("ARIS_GEMINI_UNAVAILABLE_RETRIES", "SABR_GEMINI_UNAVAILABLE_RETRIES", default="2")
    )
    GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS: float = float(
        _env_value(
            "ARIS_GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS",
            "SABR_GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS",
            default="2.0",
        )
    )

    ARIS_RUNTIME_ROOT: str = _resolve_path(
        "ARIS_RUNTIME_ROOT",
        "SABR_RUNTIME_ROOT",
        default_path=_REPO_ROOT / "runtime",
    )
    ARIS_MEMORY_DIR: str = _env_value(
        "ARIS_MEMORY_DIR",
        "SABR_MEMORY_DIR",
        default=str(Path(ARIS_RUNTIME_ROOT) / "memories"),
    )
    ARIS_PRESETS_FILE: str = _env_value(
        "ARIS_AIIDA_PRESETS_FILE",
        "SABR_PRESETS_FILE",
        default=_resolve_path(
            "ARIS_AIIDA_PRESETS_FILE",
            "SABR_PRESETS_FILE",
            default_path=_REPO_ROOT / "config" / "apps" / "aiida" / "presets.yaml",
            legacy_paths=(
                _REPO_ROOT / "config" / "aiida_presets.yaml",
            ),
        ),
    )
    ARIS_AIIDA_SETTINGS_FILE: str = _env_value(
        "ARIS_AIIDA_SETTINGS_FILE",
        "SABR_AIIDA_SETTINGS_FILE",
        default=_resolve_path(
            "ARIS_AIIDA_SETTINGS_FILE",
            "SABR_AIIDA_SETTINGS_FILE",
            default_path=_REPO_ROOT / "config" / "apps" / "aiida" / "settings.yaml",
            legacy_paths=(
                _REPO_ROOT / "config" / "aiida_settings.yaml",
            ),
        ),
    )
    ARIS_AIIDA_SPECIALIZATIONS_ROOT: str = _resolve_path(
        "ARIS_AIIDA_SPECIALIZATIONS_ROOT",
        "SABR_AIIDA_SPECIALIZATIONS_ROOT",
        default_path=_REPO_ROOT / "config" / "apps" / "aiida" / "specializations",
        legacy_paths=(
            _REPO_ROOT / "config" / "specializations",
        ),
    )
    ARIS_PROJECTS_ROOT: str = _env_value(
        "ARIS_PROJECTS_ROOT",
        "SABR_PROJECTS_ROOT",
        default=str(Path(ARIS_RUNTIME_ROOT) / "projects"),
    )
    ARIS_SCRIPT_ARCHIVE_DIR: str = _env_value(
        "ARIS_SCRIPT_ARCHIVE_DIR",
        "SABR_SCRIPT_ARCHIVE_DIR",
        default=str(Path(ARIS_RUNTIME_ROOT) / "scripts"),
    )

    ARIS_DEBUG_LEVEL: str = _env_value("ARIS_DEBUG_LEVEL", "SABR_DEBUG_LEVEL", default="default")
    PRODUCTION_MODE: bool = _env_flag("ARIS_PRODUCTION_MODE", "PRODUCTION_MODE", default="false")

    HTTPS_PROXY: str = _env_value("HTTPS_PROXY", default="")
    HTTP_PROXY: str = _env_value("HTTP_PROXY", default="")
    ARIS_USE_OUTBOUND_PROXY: bool = _env_flag("ARIS_USE_OUTBOUND_PROXY", "SABR_USE_OUTBOUND_PROXY", default="false")
    ARIS_FRONTEND_ORIGINS: str = _env_value(
        "ARIS_FRONTEND_ORIGINS",
        "SABR_FRONTEND_ORIGINS",
        default="http://localhost:5173,http://127.0.0.1:5173,https://aiida.yiming-zhang.com",
    )
    FRONTEND_DIST_DIR: str = _resolve_path(
        "ARIS_FRONTEND_DIST_DIR",
        "SABR_FRONTEND_DIST_DIR",
        default_path=_REPO_ROOT / "apps" / "web" / "dist",
        legacy_paths=(
            _REPO_ROOT / "frontend" / "dist",
        ),
    )
    FRONTEND_ASSETS_DIR: str = _resolve_path(
        "ARIS_FRONTEND_ASSETS_DIR",
        "SABR_FRONTEND_ASSETS_DIR",
        default_path=_REPO_ROOT / "apps" / "web" / "dist" / "assets",
        legacy_paths=(
            _REPO_ROOT / "frontend" / "dist" / "assets",
        ),
    )
    FRONTEND_INDEX_FILE: str = _resolve_path(
        "ARIS_FRONTEND_INDEX_FILE",
        "SABR_FRONTEND_INDEX_FILE",
        default_path=_REPO_ROOT / "apps" / "web" / "dist" / "index.html",
        legacy_paths=(
            _REPO_ROOT / "frontend" / "dist" / "index.html",
        ),
    )

    def model_post_init(self, __context) -> None:
        runtime_root = Path(self.ARIS_RUNTIME_ROOT)
        object.__setattr__(
            self,
            "ARIS_MEMORY_DIR",
            _normalize_runtime_path(
                self.ARIS_MEMORY_DIR,
                canonical_path=runtime_root / "memories",
                legacy_paths=(
                    _REPO_ROOT / "default",
                    _REPO_ROOT / "data" / "memories",
                    _REPO_ROOT / "src" / "sab_engines" / "aiida" / "data" / "memories",
                    _REPO_ROOT / "engines" / "aiida" / "data" / "memories",
                ),
            ),
        )
        object.__setattr__(
            self,
            "ARIS_PROJECTS_ROOT",
            _normalize_runtime_path(
                self.ARIS_PROJECTS_ROOT,
                canonical_path=runtime_root / "projects",
                legacy_paths=(
                    _REPO_ROOT / "data" / "projects",
                ),
            ),
        )
        object.__setattr__(
            self,
            "ARIS_SCRIPT_ARCHIVE_DIR",
            _normalize_runtime_path(
                self.ARIS_SCRIPT_ARCHIVE_DIR,
                canonical_path=runtime_root / "scripts",
                legacy_paths=(
                    _REPO_ROOT / "src" / "sab_engines" / "aiida" / "data" / "scripts",
                    _REPO_ROOT / "engines" / "aiida" / "data" / "scripts",
                ),
            ),
        )

    @property
    def SABR_MEMORY_DIR(self) -> str:
        return self.ARIS_MEMORY_DIR

    @SABR_MEMORY_DIR.setter
    def SABR_MEMORY_DIR(self, value: str) -> None:
        object.__setattr__(self, "ARIS_MEMORY_DIR", str(value))

    @property
    def SABR_PRESETS_FILE(self) -> str:
        return self.ARIS_PRESETS_FILE

    @SABR_PRESETS_FILE.setter
    def SABR_PRESETS_FILE(self, value: str) -> None:
        object.__setattr__(self, "ARIS_PRESETS_FILE", str(value))

    @property
    def SABR_AIIDA_SETTINGS_FILE(self) -> str:
        return self.ARIS_AIIDA_SETTINGS_FILE

    @SABR_AIIDA_SETTINGS_FILE.setter
    def SABR_AIIDA_SETTINGS_FILE(self, value: str) -> None:
        object.__setattr__(self, "ARIS_AIIDA_SETTINGS_FILE", str(value))

    @property
    def SABR_PROJECTS_ROOT(self) -> str:
        return self.ARIS_PROJECTS_ROOT

    @SABR_PROJECTS_ROOT.setter
    def SABR_PROJECTS_ROOT(self, value: str) -> None:
        object.__setattr__(self, "ARIS_PROJECTS_ROOT", str(value))

    @property
    def SABR_DEBUG_LEVEL(self) -> str:
        return self.ARIS_DEBUG_LEVEL

    @SABR_DEBUG_LEVEL.setter
    def SABR_DEBUG_LEVEL(self, value: str) -> None:
        object.__setattr__(self, "ARIS_DEBUG_LEVEL", str(value))

    @property
    def SABR_USE_OUTBOUND_PROXY(self) -> bool:
        return self.ARIS_USE_OUTBOUND_PROXY

    @SABR_USE_OUTBOUND_PROXY.setter
    def SABR_USE_OUTBOUND_PROXY(self, value: bool) -> None:
        object.__setattr__(self, "ARIS_USE_OUTBOUND_PROXY", bool(value))

    @property
    def SABR_FRONTEND_ORIGINS(self) -> str:
        return self.ARIS_FRONTEND_ORIGINS

    @SABR_FRONTEND_ORIGINS.setter
    def SABR_FRONTEND_ORIGINS(self, value: str) -> None:
        object.__setattr__(self, "ARIS_FRONTEND_ORIGINS", str(value))

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()

__all__ = ["Settings", "settings"]
