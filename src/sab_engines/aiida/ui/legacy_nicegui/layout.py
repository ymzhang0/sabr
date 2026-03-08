import sys

from src.aris_apps.aiida.ui.legacy_nicegui import layout as _module

sys.modules[__name__] = _module
