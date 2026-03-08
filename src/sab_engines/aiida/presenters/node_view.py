import sys

from src.aris_apps.aiida.presenters import node_view as _module

sys.modules[__name__] = _module
