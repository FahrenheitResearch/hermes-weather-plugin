import argparse
import json
import time
from pathlib import Path

from _bootstrap import bootstrap_local_sources, load_plugin

bootstrap_local_sources()
plugin = load_plugin()
from hermes_weather_plugin.model_support import IMAGE_MODELS, PROFILE_MODELS, guess_profile_product
from rustweather.core import _download_xarray, _make_herbie
from rustweather.models import resolve_alias

calc = plugin.tools.calc
REPORT = Path(__file__).resolve().parents[1] / 'verification' / 'model_matrix_report.json'
LAT = 35.333
LON = -97.278


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-models', nargs='*')
    parser.add_argument('--profile-models', nargs='*')
    parser.add_argument('--skip-images', action='store_true')
    parser.add_argument('--skip-profiles', action='store_true')
    return parser.parse_args()


def probe_image_model(model):
    t0 = time.perf_counter()
    try:
        search = resolve_alias('temp', model)
        H = _make_herbie(model=model, search=search, fxx=0)
        ds = _download_xarray(H, search)
        data_vars = list(ds.data_vars) if hasattr(ds, 'data_vars') else []
        return {
            'status': 'ok',
            'elapsed_ms': (time.perf_counter() - t0) * 1000.0,
            'product': getattr(H, 'product', None),
            'data_vars': data_vars,
        }
    except Exception as e:
        return {
            'status': 'error',
            'elapsed_ms': (time.perf_counter() - t0) * 1000.0,
            'error_type': type(e).__name__,
            'error': str(e),
        }


def probe_profile_model(model):
    t0 = time.perf_counter()
    try:
        prof = calc._load_model_profile({'lat': LAT, 'lon': LON, 'model': model})
        return {
            'status': 'ok',
            'elapsed_ms': (time.perf_counter() - t0) * 1000.0,
            'levels': len(prof['pressure_hpa']),
            'cycle': prof['cycle'],
            'product': guess_profile_product(model),
        }
    except Exception as e:
        return {
            'status': 'error',
            'elapsed_ms': (time.perf_counter() - t0) * 1000.0,
            'product': guess_profile_product(model),
            'error_type': type(e).__name__,
            'error': str(e),
        }


def main():
    args = parse_args()
    report = {'image_models': {}, 'profile_models': {}}

    if not args.skip_images:
        models = args.image_models or IMAGE_MODELS
        for model in models:
            report['image_models'][model] = probe_image_model(model)
            REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')

    if not args.skip_profiles:
        models = args.profile_models or PROFILE_MODELS
        for model in models:
            report['profile_models'][model] = probe_profile_model(model)
            REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
