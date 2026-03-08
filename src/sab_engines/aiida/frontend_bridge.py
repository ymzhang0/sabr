import sys

from src.aris_apps.aiida import frontend_bridge as _module

sys.modules[__name__] = _module
