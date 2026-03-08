import sys

from src.aris_apps.aiida.chat import service as _module

sys.modules[__name__] = _module
