import sys

from src.aris_apps.aiida.presenters import workflow_view as _module

sys.modules[__name__] = _module
