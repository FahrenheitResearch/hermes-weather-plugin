import argparse
import json
import os
import subprocess
from pathlib import Path

from _bootstrap import bootstrap_local_sources, load_plugin

bootstrap_local_sources()
plugin = load_plugin()
from hermes_weather_plugin.model_support import PROFILE_MODELS

REPORT = Path(__file__).resolve().parents[1] / 'verification' / 'verify_wx_ecape_report.json'
RUNNER = Path(os.environ.get('ECAPE_RS_RUNNER', Path.home() / 'ecape-rs' / 'target' / 'release' / ('run_case.exe' if os.name == 'nt' else 'run_case')))
LAT = 35.333
LON = -97.278


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('models', nargs='*')
    return parser.parse_args()


def main():
    args = parse_args()
    models = args.models or PROFILE_MODELS
    out = []
    for model in models:
        try:
            plugin_json = json.loads(plugin.tools.calc.wx_ecape({'lat': LAT, 'lon': LON, 'model': model, 'include_parcel_profile': False}))
            prof = plugin.tools.calc._load_model_profile({'lat': LAT, 'lon': LON, 'model': model})
            payload = {
                'pressure_hpa': prof['pressure_hpa'],
                'height_m': prof['height_m'],
                'temperature_k': prof['temperature_k'],
                'dewpoint_k': prof['dewpoint_k'],
                'u_wind_ms': prof['u_ms'],
                'v_wind_ms': prof['v_ms'],
                'options': {
                    'cape_type': 'most_unstable',
                    'storm_motion_type': 'right_moving',
                    'pseudoadiabatic': True,
                },
                'reps': 1,
            }
            proc = subprocess.run([str(RUNNER)], input=json.dumps(payload), text=True, capture_output=True, check=True)
            direct = json.loads(proc.stdout)
            pm = plugin_json.get('metrics', {})
            out.append({
                'model': model,
                'status': 'ok',
                'plugin_ecape_jkg': pm.get('ecape_jkg'),
                'direct_ecape_jkg': direct.get('ecape_jkg'),
                'abs_diff_ecape_jkg': abs(float(pm.get('ecape_jkg', 0.0)) - float(direct.get('ecape_jkg', 0.0))),
                'plugin_ncape_jkg': pm.get('ncape_jkg'),
                'direct_ncape_jkg': direct.get('ncape_jkg'),
                'abs_diff_ncape_jkg': abs(float(pm.get('ncape_jkg', 0.0)) - float(direct.get('ncape_jkg', 0.0))),
                'plugin_cape_jkg': pm.get('cape_jkg'),
                'direct_cape_jkg': direct.get('cape_jkg'),
                'abs_diff_cape_jkg': abs(float(pm.get('cape_jkg', 0.0)) - float(direct.get('cape_jkg', 0.0))),
            })
        except Exception as e:
            out.append({'model': model, 'status': 'error', 'error_type': type(e).__name__, 'error': str(e)})
        REPORT.write_text(json.dumps(out, indent=2), encoding='utf-8')

    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
