# engines/aiida/hub.py
from aiida import load_profile
from aiida.manage import Profile
from loguru import logger
from .tools import get_default_profile, list_system_profiles, load_archive_profile
from pathlib import Path
from pydantic import BaseModel, ConfigDict

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
        logger.info(f"🚀 [AiiDA Hub] Initializing backend environment: {self.current_profile}")
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
                
            logger.success(f"✅ [AiiDA Hub] Hub started with {len(self._ALL_PROFILES)} system profiles.")
        except Exception as e:
            logger.error(f"❌ [AiiDA Hub] Failed to initialize: {e}")

    @property
    def current_profile(self):
        return self._CURRENT_PROFILE

    def switch_profile(self, name: str):
        if not name in self._ALL_PROFILES:
            logger.warning(f"⚠️ [AiiDA Hub] {name} not found in registered profiles")
            return
        # Fast path: avoid reloading when the target profile is already active.
        if name == self.current_profile:
            logger.info(f"✨ [AiiDA Hub] Profile '{name}' is already active, skipping load.")
            self._CURRENT_PROFILE = name  # Keep internal UI state consistent.
            return
        profileitem = self._ALL_PROFILES[name]
        logger.warning(f"🔄 [AiiDA Hub] Switching context: {self.current_profile} -> {name}")
        if profileitem.type == 'configured':
            load_profile(self._ALL_PROFILES[name].object, allow_switch=True)
        elif profileitem.type == 'imported':
            load_archive_profile(filepath = str(profileitem.path))

        self._CURRENT_PROFILE = name

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
            logger.warning(f"⚠️ [AiiDA Hub] Collision detected: Renaming profile '{base_name}' -> '{unique_name}' for UI display.")

        # Register in the profile pool.
        self._ALL_PROFILES[unique_name] = ProfileItem(
            type="imported",
            path=path,
            object=None,
        )

        logger.success(f"✅ [AiiDA Hub] {unique_name} registered.")
        
        return unique_name  # Return the final profile key for follow-up actions.

    def get_display_list(self):
        """Return API-friendly profile display data."""
        return [
            [name, name + " (imported)" if meta.type=='imported' else name, (name == self.current_profile)]
            for name, meta in self._ALL_PROFILES.items()
        ]
# Singleton shared by the API layer.
hub = AiiDAHub()
