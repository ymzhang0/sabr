# engines/aiida/hub.py
from aiida import load_profile
from aiida.manage import Profile
from loguru import logger
from .tools import get_default_profile, list_system_profiles, load_archive_profile
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from src.sab_core.logging_utils import log_event

# UI display model used by FastUI.
class ProfileItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: str = None
    path: Path | None = None
    object: Profile | None = None

class AiiDAHub:
    """
    Backend state hub for the AiiDA engine.
    It is started by the framework to keep the AiiDA environment ready.
    """
    def __init__(self):
        # Core registry: {"name": {"type": "configured"|"imported", ...}}
        self._ALL_PROFILES: dict[str, ProfileItem] = {}
        self._CURRENT_PROFILE = None

    def start(self):
        logger.info(log_event("aiida.hub.start.begin", current_profile=self.current_profile))
        try:
            default_profile = get_default_profile()
            load_profile(default_profile, allow_switch=True)
            self._CURRENT_PROFILE = default_profile.name

            # Preserve user-imported archives across re-initialization.
            imported_profiles = {
                name: item for name, item in self._ALL_PROFILES.items() if item.type == "imported"
            }
            self._ALL_PROFILES = imported_profiles
            for p in list_system_profiles():
                self._ALL_PROFILES[p.name] = ProfileItem(
                    type="configured",
                    path=None,
                    object=p,
                )
                
            logger.success(log_event("aiida.hub.start.done", profiles=len(self._ALL_PROFILES)))
        except Exception as e:
            logger.exception(log_event("aiida.hub.start.failed", error=str(e)))

    @property
    def current_profile(self):
        return self._CURRENT_PROFILE

    def switch_profile(self, name: str):
        if not name in self._ALL_PROFILES:
            logger.warning(log_event("aiida.profile.switch.missing", profile=name))
            return
        # Fast path: avoid reloading when the target profile is already active.
        if name == self.current_profile:
            logger.info(log_event("aiida.profile.switch.skip", profile=name))
            self._CURRENT_PROFILE = name  # Keep internal UI state consistent.
            return
        profileitem = self._ALL_PROFILES[name]
        logger.info(
            log_event(
                "aiida.profile.switch.begin",
                old_profile=self.current_profile,
                new_profile=name,
                profile_type=profileitem.type,
            )
        )
        if profileitem.type == 'configured':
            load_profile(self._ALL_PROFILES[name].object, allow_switch=True)
        elif profileitem.type == 'imported':
            load_archive_profile(filepath = str(profileitem.path))

        self._CURRENT_PROFILE = name
        logger.success(log_event("aiida.profile.switch.done", profile=name))

    def import_archive(self, path: Path):
        """
        Add an imported archive profile to the hub registry.
        If the name conflicts, append a numeric suffix (for example, _1, _2).
        """
        base_name = path.stem
        unique_name = base_name
        counter = 1

        # Core collision-resolution loop.
        while unique_name in self._ALL_PROFILES:
            unique_name = f"{base_name}_{counter}"
            counter += 1

        # Record renaming when a collision occurs.
        if unique_name != base_name:
            logger.warning(
                log_event(
                    "aiida.profile.import.rename",
                    original=base_name,
                    renamed=unique_name,
                )
            )

        # Register in the profile pool.
        self._ALL_PROFILES[unique_name] = ProfileItem(
            type="imported",
            path=path,
            object=None,
        )

        logger.success(log_event("aiida.profile.import.done", profile=unique_name, path=str(path)))
        
        return unique_name  # Return the final profile key for follow-up actions.

    def get_display_list(self):
        """Return API-friendly profile display data."""
        return [
            [name, name + " (imported)" if meta.type=='imported' else name, (name == self.current_profile)]
            for name, meta in self._ALL_PROFILES.items()
        ]
# Singleton shared by the API layer.
hub = AiiDAHub()
