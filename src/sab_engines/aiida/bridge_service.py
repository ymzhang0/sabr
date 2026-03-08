import sys

from src.aris_apps.aiida import bridge_service as _module

sys.modules[__name__] = _module
