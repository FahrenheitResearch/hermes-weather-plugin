from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO_BASE = ROOT.parent

LOCAL_SOURCE_DIRS = [
    REPO_BASE / 'rustweather' / 'python',
    REPO_BASE / 'rusbie' / 'python',
    REPO_BASE / 'cfrust' / 'python',
    REPO_BASE / 'rustplots' / 'python',
    REPO_BASE / 'wrf-rust' / 'python',
]


def bootstrap_local_sources():
    for path in LOCAL_SOURCE_DIRS:
        if path.exists():
            sys.path.insert(0, str(path))


def load_plugin(alias='hermes_weather_plugin'):
    plugin_init = ROOT / '__init__.py'
    spec = importlib.util.spec_from_file_location(
        alias,
        plugin_init,
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module
