from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from src.sab_core.deps.base import BaseSABRDeps
from src.sab_core.config import settings

@dataclass
class AiiDADeps(BaseSABRDeps):
    """
    AiiDA-specific dependency injection object.
    
    This class extends the core BaseSABRDeps to provide the AiiDA agent 
    with necessary context such as archive paths and database profiles.
    """
    
    # The absolute path to the .aiida archive or the profile name
    archive_path: Optional[str] = None
    profile_name: str = settings.SABR_AIIDA_PROFILE # Injected from .env
    
    # Metadata for the current research session
    session_id: Optional[str] = None
    
    # Dictionary to store intermediate AiiDA objects or PKs 
    # that need to be shared between different tools in the same loop
    registry: Dict[str, Any] = field(default_factory=dict)
    context_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """
        Optional: Logic to run after initialization, 
        such as validating the archive path.
        """
        if self.archive_path:
            # You could trigger a silent environment check here if needed
            pass

    def set_registry_value(self, key: str, value: Any):
        """
        Store a value in the session registry for cross-tool communication.
        """
        self.registry[key] = value

    def get_registry_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from the session registry.
        """
        return self.registry.get(key, default)
