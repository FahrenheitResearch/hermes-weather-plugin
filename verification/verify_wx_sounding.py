import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_local_sources, load_plugin

bootstrap_local_sources()
plugin = load_plugin()
from hermes_weather_plugin.model_support import PROFILE_MODELS
from metrust import calc
from metrust.units import units as ureg

REPORT = Path(__file__).resolve().parents[1] / 'verification' / 'verify_wx_sounding_report.json'
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
            plugin_json = json.loads(plugin.tools.calc.wx_sounding({'lat': LAT, 'lon': LON, 'model': model}))
            prof = plugin.tools.calc._load_model_profile({'lat': LAT, 'lon': LON, 'model': model})
            p = ureg.Quantity(prof['pressure_hpa'], 'hPa')
            t = ureg.Quantity([v - 273.15 for v in prof['temperature_k']], 'degC')
            td = ureg.Quantity([v - 273.15 for v in prof['dewpoint_k']], 'degC')
            sbcape, sbcin = calc.surface_based_cape_cin(p, t, td)
            mucape, mucin = calc.most_unstable_cape_cin(p, t, td)
            params = plugin_json.get('parameters', {})
            out.append({
                'model': model,
                'status': 'ok',
                'plugin_sbcape_jkg': params.get('sbcape_jkg'),
                'direct_sbcape_jkg': float(sbcape.magnitude),
                'abs_diff_sbcape_jkg': abs(float(params.get('sbcape_jkg', 0.0)) - float(sbcape.magnitude)),
                'plugin_mucape_jkg': params.get('mucape_jkg'),
                'direct_mucape_jkg': float(mucape.magnitude),
                'abs_diff_mucape_jkg': abs(float(params.get('mucape_jkg', 0.0)) - float(mucape.magnitude)),
                'levels_available': plugin_json.get('levels_available'),
            })
        except Exception as e:
            out.append({'model': model, 'status': 'error', 'error_type': type(e).__name__, 'error': str(e)})
        REPORT.write_text(json.dumps(out, indent=2), encoding='utf-8')

    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
