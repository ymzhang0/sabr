import sys

from src.aris_apps.aiida.agent import prompts as _module

sys.modules[__name__] = _module
