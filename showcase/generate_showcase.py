from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'verification'))
from _bootstrap import bootstrap_local_sources, load_plugin

bootstrap_local_sources()
plugin = load_plugin()
from hermes_weather_plugin.model_support import IMAGE_MODELS, PROFILE_MODELS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'showcase' / 'latest'
IMG_DIR = OUT / 'images'
DATA_DIR = OUT / 'data'

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_LOC = {'name': 'Norman, OK', 'lat': 35.333, 'lon': -97.278, 'radius_km': 700}
ALASKA_LOC = {'name': 'Anchorage, AK', 'lat': 61.2181, 'lon': -149.9003, 'radius_km': 700}
PROFILE_LOCS = {model: (ALASKA_LOC if model == 'hrrrak' else DEFAULT_LOC) for model in PROFILE_MODELS}
IMAGE_LOCS = {model: (ALASKA_LOC if model == 'hrrrak' else DEFAULT_LOC) for model in IMAGE_MODELS}

PRODUCT_GROUPS = {
    'severe': {'title': 'Severe Weather Products'},
    'quicklook': {'title': 'Quicklook Maps'},
}

SHOWCASE_VARS_BY_MODEL = {
    'aigfs': {'severe': ['cape'], 'quicklook': ['temp']},
    'gdas': {'severe': ['cape', 'refl'], 'quicklook': ['temp']},
    'gefs': {'severe': ['cape'], 'quicklook': ['temp']},
    'gfs': {'severe': ['cape', 'scp', 'ehi', 'refl'], 'quicklook': ['temp']},
    'graphcast': {'severe': ['cape'], 'quicklook': ['temp']},
    'hiresw': {'severe': ['cape', 'refl'], 'quicklook': ['temp']},
    'hrrr': {'severe': ['cape', 'stp', 'scp', 'ehi', 'refl'], 'quicklook': ['temp']},
    'hrrrak': {'severe': ['cape', 'stp', 'scp', 'ehi', 'refl'], 'quicklook': ['temp']},
    'nam': {'severe': ['cape', 'stp', 'scp', 'ehi', 'refl'], 'quicklook': ['temp']},
    'nbm': {'severe': ['cape'], 'quicklook': ['temp']},
    'rap': {'severe': ['cape', 'refl'], 'quicklook': ['temp']},
}


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


image_results = []
for group_key, group in PRODUCT_GROUPS.items():
    for model in IMAGE_MODELS:
        loc = IMAGE_LOCS[model]
        vars_for_model = SHOWCASE_VARS_BY_MODEL.get(model, {}).get(group_key, [])
        if not vars_for_model:
            continue
        args = {
            'var': ','.join(vars_for_model),
            'model': model,
            'lat': loc['lat'],
            'lon': loc['lon'],
            'radius_km': loc['radius_km'],
            'fhour': 0,
        }
        raw = json.loads(plugin.tools.images.wx_model_image(args))
        files = []
        for item in raw.get('images', []):
            src = item.get('image_path')
            if src and Path(src).exists():
                target_name = f"{group_key}_{model}_{item['variable']}.png"
                target = IMG_DIR / target_name
                shutil.copy2(src, target)
                item['showcase_image'] = target_name
                files.append(target_name)
        result = {
            'group': group_key,
            'group_title': group['title'],
            'model': model,
            'location': loc,
            'cycle': raw.get('cycle'),
            'forecast_hour': raw.get('forecast_hour'),
            'requested_vars': list(vars_for_model),
            'images': raw.get('images', []),
            'image_files': files,
            'error': raw.get('error'),
        }
        image_results.append(result)

sounding_results = []
for model in PROFILE_MODELS:
    loc = PROFILE_LOCS[model]
    sounding = json.loads(plugin.tools.calc.wx_sounding({'lat': loc['lat'], 'lon': loc['lon'], 'model': model}))
    ecape = json.loads(plugin.tools.calc.wx_ecape({'lat': loc['lat'], 'lon': loc['lon'], 'model': model, 'include_parcel_profile': False}))
    snd_path = DATA_DIR / f'sounding_{model}.json'
    ecp_path = DATA_DIR / f'ecape_{model}.json'
    write_json(snd_path, sounding)
    write_json(ecp_path, ecape)
    sounding_results.append({
        'model': model,
        'location': loc,
        'sounding_file': snd_path.name,
        'ecape_file': ecp_path.name,
        'sounding': sounding,
        'ecape': ecape,
    })

summary = {
    'generated_utc': datetime.now(timezone.utc).isoformat(),
    'image_models': IMAGE_MODELS,
    'profile_models': PROFILE_MODELS,
    'product_groups': PRODUCT_GROUPS,
    'image_group_count': len(image_results),
    'image_file_count': sum(len(r.get('image_files', [])) for r in image_results),
    'sounding_count': len(sounding_results),
}
write_json(DATA_DIR / 'summary.json', summary)
write_json(DATA_DIR / 'image_results.json', image_results)


def metric_cell(value):
    if value is None:
        return 'n/a'
    if isinstance(value, float):
        return f'{value:.2f}'
    return escape(str(value))


html_parts = [
    '<!doctype html>',
    '<html><head><meta charset="utf-8">',
    '<title>Hermes Weather Plugin Showcase</title>',
    '<style>',
    'body{font-family:Segoe UI,Arial,sans-serif;background:#0b1320;color:#e8eef7;margin:0;padding:24px;}',
    'h1,h2,h3,h4{margin:0 0 12px 0;} .muted{color:#9fb2c8;} .group{margin:18px 0 38px;} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:18px;margin:18px 0 32px;} ',
    '.card{background:#152033;border:1px solid #27364e;border-radius:12px;padding:14px;} .thumb-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:10px;} ',
    'img{width:100%;border-radius:8px;border:1px solid #314661;background:#08101b;} table{width:100%;border-collapse:collapse;margin-top:10px;} th,td{border-bottom:1px solid #27364e;padding:8px 6px;text-align:left;font-size:14px;vertical-align:top;} a{color:#8cc8ff;} code{background:#0f1a2a;padding:2px 5px;border-radius:4px;display:inline-block;}',
    '</style></head><body>',
    '<h1>Hermes Weather Plugin Showcase</h1>',
    f'<p class="muted">Generated {escape(summary["generated_utc"])}. {summary["image_file_count"]} model-map PNGs across {len(IMAGE_MODELS)} verified image models and {len(PRODUCT_GROUPS)} product groups. {len(PROFILE_MODELS)} verified sounding/ECAPE models.</p>',
]

for group_key, group in PRODUCT_GROUPS.items():
    html_parts.append(f'<div class="group"><h2>{escape(group["title"])}</h2>')
    group_requested = sorted({var for item in image_results if item['group'] == group_key for var in item.get('requested_vars', [])})
    html_parts.append(f'<p class="muted">Requested products: {escape(", ".join(group_requested))}</p>')
    html_parts.append('<div class="grid">')
    for item in [r for r in image_results if r['group'] == group_key]:
        html_parts.append('<div class="card">')
        html_parts.append(f'<h3>{escape(item["model"].upper())}</h3>')
        html_parts.append(f'<p class="muted">{escape(item["location"]["name"])} | Cycle: {escape(str(item.get("cycle", "n/a")))} | F{escape(str(item.get("forecast_hour", "n/a")))}</p>')
        successes = [img for img in item['images'] if img.get('showcase_image')]
        failures = [img for img in item['images'] if img.get('error')]
        if successes:
            html_parts.append('<div class="thumb-grid">')
            for img in successes:
                label = f"{item['model'].upper()} {img['variable']}"
                html_parts.append(f'<div><a href="images/{escape(img["showcase_image"])}"><img src="images/{escape(img["showcase_image"])}" alt="{escape(label)}"></a><div class="muted">{escape(img["variable"])}</div></div>')
            html_parts.append('</div>')
        if failures:
            html_parts.append('<table>')
            html_parts.append('<tr><th>Failed variable</th><th>Error</th></tr>')
            for img in failures:
                html_parts.append(f'<tr><td>{escape(str(img.get("variable", "n/a")))}</td><td><code>{escape(str(img.get("error", "unknown")))}</code></td></tr>')
            html_parts.append('</table>')
        if item.get('error'):
            html_parts.append(f'<p><code>{escape(str(item["error"]))}</code></p>')
        html_parts.append('</div>')
    html_parts.append('</div></div>')

html_parts.append('<h2>Sounding and ECAPE Summaries</h2>')
html_parts.append('<div class="grid">')
for item in sounding_results:
    snd = item['sounding']
    ecp = item['ecape']
    params = snd.get('parameters', {})
    metrics = ecp.get('metrics', {})
    html_parts.append('<div class="card">')
    html_parts.append(f'<h3>{escape(item["model"].upper())} - {escape(item["location"]["name"])}</h3>')
    html_parts.append(f'<p class="muted">Cycle: {escape(str(snd.get("cycle", "n/a")))} | Levels: {escape(str(snd.get("levels_available", "n/a")))}</p>')
    html_parts.append('<table>')
    rows = [
        ('SBCAPE J/kg', params.get('sbcape_jkg')),
        ('MUCAPE J/kg', params.get('mucape_jkg')),
        ('LCL hPa', params.get('lcl_pressure_hpa')),
        ('Bulk shear 0-6km kt', params.get('bulk_shear_0_6km_kt')),
        ('ECAPE J/kg', metrics.get('ecape_jkg')),
        ('NCAPE J/kg', metrics.get('ncape_jkg')),
        ('CAPE J/kg', metrics.get('cape_jkg')),
        ('LFC m', metrics.get('lfc_m')),
        ('EL m', metrics.get('el_m')),
    ]
    for label, value in rows:
        html_parts.append(f'<tr><th>{escape(label)}</th><td>{metric_cell(value)}</td></tr>')
    html_parts.append('</table>')
    html_parts.append(f'<p><a href="data/{escape(item["sounding_file"])}">Raw sounding JSON</a> | <a href="data/{escape(item["ecape_file"])}">Raw ECAPE JSON</a></p>')
    html_parts.append('</div>')
html_parts.append('</div>')

html_parts.append('<h2>Files</h2>')
html_parts.append('<ul>')
html_parts.append('<li><a href="data/summary.json">data/summary.json</a></li>')
html_parts.append('<li><a href="data/image_results.json">data/image_results.json</a></li>')
for item in image_results:
    for image_file in item.get('image_files', []):
        html_parts.append(f'<li><a href="images/{escape(image_file)}">images/{escape(image_file)}</a></li>')
for item in sounding_results:
    html_parts.append(f'<li><a href="data/{escape(item["sounding_file"])}">data/{escape(item["sounding_file"])} </a></li>')
    html_parts.append(f'<li><a href="data/{escape(item["ecape_file"])}">data/{escape(item["ecape_file"])} </a></li>')
html_parts.append('</ul>')
html_parts.append('</body></html>')

(OUT / 'index.html').write_text('\n'.join(html_parts), encoding='utf-8')
print(json.dumps({'out_dir': str(OUT), 'image_group_count': summary['image_group_count'], 'image_file_count': summary['image_file_count'], 'sounding_count': summary['sounding_count']}, indent=2))
