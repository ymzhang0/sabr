import sys

from src.aris_apps.aiida import router as _module

sys.modules[__name__] = _module
