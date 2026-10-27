"""Load numerical utilities without requiring Blender in the unit-test process."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load_utils():
    path = Path(__file__).resolve().parents[1] / 'blenderneuron/blender/utils.py'
    spec = importlib.util.spec_from_file_location('_rdp_utils', str(path))
    module = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', {'bpy': SimpleNamespace(app=SimpleNamespace(version=(4, 0, 0)))}):
        spec.loader.exec_module(module)
    return module
