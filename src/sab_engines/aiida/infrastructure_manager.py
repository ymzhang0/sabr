from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict

import yaml

from src.sab_core.config import settings


class InfrastructureManager:
    @property
    def config_path(self) -> Path:
        return Path(settings.SABR_PRESETS_FILE)

    def __init__(self):
        # We load presets on demand or at least don't hardcode the path in __init__ 
        # to ensure settings are loaded first.
        self._presets = None

    @property
    def presets(self) -> Dict[str, Any]:
        if self._presets is None:
            self._presets = self._load_presets()
        return self._presets

    def _load_presets(self) -> Dict[str, Any]:
        """Loads presets from the YAML configuration file."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("presets", {})
        except Exception:
            return {}

    def match_hostname(self, hostname: str) -> tuple[str, Dict[str, Any]] | None:
        """Finds matching preset for a given hostname via fnmatch."""
        for pattern, config in self.presets.items():
            if fnmatch.fnmatch(hostname, pattern) or hostname.endswith(pattern.replace("*", "")):
                return pattern, config
        return None

    def merge_preset(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merges parsed dynamic info with static preset data."""
        hostname = parsed_data.get("hostname", "")
        username = parsed_data.get("username", "")
        
        match = self.match_hostname(hostname)
        if not match:
            return {"matched": False, "config": parsed_data}
            
        pattern, preset_config = match
        
        merged = parsed_data.copy()
        
        # Merge basic parameters
        for key in ["description", "transport_type", "scheduler_type", "mpiprocs_per_machine", 
                    "mpirun_command", "prepend_text", "append_text", "use_login_shell", 
                    "safe_interval", "connection_timeout"]:
            if key in preset_config and not merged.get(key):
                merged[key] = preset_config[key]
                
        # Resolve work_dir correctly
        if preset_config.get("work_dir"):
            merged["work_dir"] = preset_config["work_dir"].replace("{username}", username or "unknown")

        codes = preset_config.get("codes", [])
        if codes:
            # Provide default code from the first available in preset
            first_code = codes[0]
            if not merged.get("code_label"):
                merged["code_label"] = first_code.get("label", "code")  # Use generic "code" default
            if not merged.get("default_calc_job_plugin"):
                merged["default_calc_job_plugin"] = first_code.get("default_calc_job_plugin", "")
            if not merged.get("remote_abspath"):
                merged["remote_abspath"] = first_code.get("remote_abspath", "")
                
        return {"matched": True, "domain_pattern": pattern, "config": merged}


infrastructure_manager = InfrastructureManager()
