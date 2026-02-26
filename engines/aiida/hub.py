from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from engines.aiida.bridge_client import (
    BridgeAPIError,
    BridgeOfflineError,
    request_json_sync,
)
from src.sab_core.logging_utils import log_event


@dataclass
class ProfileItem:
    type: str = "configured"
    path: Path | None = None
    object: dict | None = None


class AiiDAHub:
    """Worker-backed profile hub (no local AiiDA imports)."""

    def __init__(self) -> None:
        self._ALL_PROFILES: dict[str, ProfileItem] = {}
        self._CURRENT_PROFILE: str | None = None

    def start(self) -> None:
        logger.info(log_event("aiida.hub.start.begin", current_profile=self.current_profile))
        try:
            payload = request_json_sync("GET", "/management/profiles", timeout=6.0)
            self._apply_profiles_payload(payload)
            logger.success(log_event("aiida.hub.start.done", profiles=len(self._ALL_PROFILES)))
        except BridgeOfflineError:
            logger.warning(log_event("aiida.hub.start.offline"))
        except Exception as exc:  # noqa: BLE001
            logger.exception(log_event("aiida.hub.start.failed", error=str(exc)))

    @property
    def current_profile(self) -> str | None:
        return self._CURRENT_PROFILE

    def _apply_profiles_payload(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        current_profile = payload.get("current_profile")
        if isinstance(current_profile, str) and current_profile.strip():
            self._CURRENT_PROFILE = current_profile.strip()

        remote_profiles = payload.get("profiles")
        if not isinstance(remote_profiles, list):
            return

        imported_profiles = {
            name: item for name, item in self._ALL_PROFILES.items() if item.type == "imported"
        }
        self._ALL_PROFILES = imported_profiles

        for entry in remote_profiles:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            if name in self._ALL_PROFILES and self._ALL_PROFILES[name].type == "imported":
                continue
            self._ALL_PROFILES[name] = ProfileItem(type="configured", object=entry)

    def switch_profile(self, name: str) -> None:
        cleaned = str(name or "").strip()
        if not cleaned:
            logger.warning(log_event("aiida.profile.switch.missing", profile=name))
            return

        if cleaned == self.current_profile:
            logger.info(log_event("aiida.profile.switch.skip", profile=cleaned))
            return

        logger.info(
            log_event(
                "aiida.profile.switch.begin",
                old_profile=self.current_profile,
                new_profile=cleaned,
                profile_type=self._ALL_PROFILES.get(cleaned).type if cleaned in self._ALL_PROFILES else "unknown",
            )
        )

        try:
            item = self._ALL_PROFILES.get(cleaned)
            if item and item.type == "imported" and item.path is not None:
                payload = request_json_sync(
                    "POST",
                    "/management/profiles/load-archive",
                    json={"path": str(item.path)},
                    timeout=10.0,
                )
            else:
                payload = request_json_sync(
                    "POST",
                    "/management/profiles/switch",
                    json={"profile": cleaned},
                    timeout=8.0,
                )
        except (BridgeOfflineError, BridgeAPIError) as exc:
            logger.warning(log_event("aiida.profile.switch.failed", profile=cleaned, error=str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception(log_event("aiida.profile.switch.failed", profile=cleaned, error=str(exc)))
            return

        if isinstance(payload, dict):
            current = payload.get("current_profile")
            if isinstance(current, str) and current.strip():
                self._CURRENT_PROFILE = current.strip()
            else:
                self._CURRENT_PROFILE = cleaned
        else:
            self._CURRENT_PROFILE = cleaned

        self.start()
        logger.success(log_event("aiida.profile.switch.done", profile=self._CURRENT_PROFILE))

    def import_archive(self, path: Path) -> str:
        archive_path = Path(path).expanduser().resolve()

        try:
            payload = request_json_sync(
                "POST",
                "/management/profiles/load-archive",
                json={"path": str(archive_path)},
                timeout=15.0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(log_event("aiida.profile.import.failed", path=str(archive_path), error=str(exc)))
            return archive_path.stem

        profile_name = None
        if isinstance(payload, dict):
            maybe_current = payload.get("current_profile")
            if isinstance(maybe_current, str) and maybe_current.strip():
                profile_name = maybe_current.strip()

        if not profile_name:
            profile_name = archive_path.stem

        self._ALL_PROFILES[profile_name] = ProfileItem(type="imported", path=archive_path, object=None)
        self._CURRENT_PROFILE = profile_name

        logger.success(log_event("aiida.profile.import.done", profile=profile_name, path=str(archive_path)))
        return profile_name

    def get_display_list(self) -> list[list[object]]:
        return [
            [
                name,
                f"{name} (imported)" if meta.type == "imported" else name,
                name == self.current_profile,
            ]
            for name, meta in self._ALL_PROFILES.items()
        ]


hub = AiiDAHub()
