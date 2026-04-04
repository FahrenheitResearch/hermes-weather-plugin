import json
import os
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "radar-backends" / "latest"
RAW_DIR = OUT_DIR / "raw"
IMG_DIR = OUT_DIR / "images"
DATA_DIR = OUT_DIR / "data"

RUSTDAR = Path.home() / "rustdar" / "target" / "release" / ("radar-render.exe" if os.name == "nt" else "radar-render")
NEXRAD = ROOT.parent / "radar_backends" / "nexrad-render-cli" / "target" / "release" / ("nexrad-render-cli.exe" if os.name == "nt" else "nexrad-render-cli")

AWS_BASE = "https://unidata-nexrad-level2.s3.amazonaws.com"
SITE = os.environ.get("RADAR_COMPARE_SITE", "KDTX").strip().upper()


def reset_output():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _list_keys(site: str, day: datetime.date):
    prefix = f"{day.year:04d}/{day.month:02d}/{day.day:02d}/{site}/"
    url = f"{AWS_BASE}?list-type=2&prefix={prefix}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read()
    root = ET.fromstring(body)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = []
    for key in root.findall(".//s3:Key", ns):
        text = key.text or ""
        display = text.rsplit("/", 1)[-1]
        if display.endswith("_MDM") or display.endswith(".md") or not text:
            continue
        keys.append(text)
    return sorted(keys)


def download_latest_volume(site: str) -> Path:
    now = datetime.now(timezone.utc)
    for offset in (0, 1):
        day = (now - timedelta(days=offset)).date()
        keys = _list_keys(site, day)
        if not keys:
            continue
        key = keys[-1]
        local_name = key.rsplit("/", 1)[-1]
        local_path = RAW_DIR / local_name
        with urllib.request.urlopen(f"{AWS_BASE}/{key}", timeout=60) as resp:
            local_path.write_bytes(resp.read())
        return local_path
    raise RuntimeError(f"No recent Level II file found for {site}")


def run_backend(binary: Path, backend: str, product: str, raw_path: Path, *, storm_cells: bool = False):
    output_path = IMG_DIR / f"{backend}_{product}{'_storm' if storm_cells else ''}.png"
    cmd = [
        str(binary),
        "--site", SITE,
        "--input", str(raw_path),
        "--product", product,
        "--size", "1024",
        "--range-km", "200",
        "--min-dbz", "10",
        "-o", str(output_path),
    ]
    if storm_cells:
        cmd.append("--storm-cells")

    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    payload = {
        "backend": backend,
        "product": product,
        "storm_cells": storm_cells,
        "latency_ms": elapsed_ms,
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if result.returncode == 0 and result.stdout.strip():
        payload["result"] = json.loads(result.stdout)
    else:
        payload["error"] = result.stderr.strip() or result.stdout.strip() or f"{backend} failed"
    return payload


def write_html(report):
    rows = []
    for item in report["comparisons"]:
        rows.append(
            f"""
            <tr>
              <td>{item['label']}</td>
              <td>{item['rustdar'].get('latency_ms', 0):.1f} ms</td>
              <td>{item['nexrad'].get('latency_ms', 0):.1f} ms</td>
            </tr>
            """
        )

    cards = []
    for item in report["comparisons"]:
        rust_img = Path(item["rustdar"]["result"]["image_path"]).name if item["rustdar"].get("result") else ""
        nex_img = Path(item["nexrad"]["result"]["image_path"]).name if item["nexrad"].get("result") else ""
        cards.append(
            f"""
            <section class="compare">
              <h2>{item['label']}</h2>
              <div class="meta">rustdar: {item['rustdar'].get('latency_ms', 0):.1f} ms | nexrad: {item['nexrad'].get('latency_ms', 0):.1f} ms</div>
              <div class="grid">
                <figure>
                  <figcaption>rustdar</figcaption>
                  <img src="images/{rust_img}" alt="{item['label']} rustdar">
                </figure>
                <figure>
                  <figcaption>nexrad</figcaption>
                  <img src="images/{nex_img}" alt="{item['label']} nexrad">
                </figure>
              </div>
            </section>
            """
        )

    bonus = []
    for item in report["bonus"]:
        img = Path(item["result"]["image_path"]).name if item.get("result") else ""
        bonus.append(
            f"""
            <section class="bonus">
              <h2>rustdar bonus: {item['product']}</h2>
              <div class="meta">{item.get('latency_ms', 0):.1f} ms</div>
              <figure>
                <img src="images/{img}" alt="rustdar {item['product']}">
              </figure>
            </section>
            """
        )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Radar backend comparison</title>
  <style>
    body {{ background:#11131a; color:#eef2ff; font-family:Segoe UI, Arial, sans-serif; margin:24px; }}
    table {{ border-collapse:collapse; width:100%; max-width:720px; margin-bottom:24px; }}
    th,td {{ border:1px solid #2a3040; padding:10px 12px; text-align:left; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
    img {{ width:100%; height:auto; border:1px solid #2a3040; background:#0d1018; }}
    .compare,.bonus {{ margin:28px 0; padding:18px; background:#171b26; border:1px solid #252c3d; }}
    .meta {{ color:#9fb0d6; margin-bottom:12px; }}
    figure {{ margin:0; }}
    figcaption {{ margin-bottom:8px; color:#cbd5f5; }}
  </style>
</head>
<body>
  <h1>Radar backend comparison</h1>
  <p>Shared raw volume: {report['raw_file']}</p>
  <table>
    <thead><tr><th>Case</th><th>rustdar</th><th>nexrad</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  {''.join(cards)}
  {''.join(bonus)}
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")


def main():
    reset_output()
    raw_path = download_latest_volume(SITE)

    comparisons = []
    for label, product, storm_cells in [
        ("Reflectivity", "ref", False),
        ("Velocity", "vel", False),
        ("Storm analysis", "ref", True),
    ]:
        rustdar = run_backend(RUSTDAR, "rustdar", product, raw_path, storm_cells=storm_cells)
        nexrad = run_backend(NEXRAD, "nexrad", product, raw_path, storm_cells=storm_cells)
        comparisons.append({
            "label": label,
            "product": product,
            "storm_cells": storm_cells,
            "rustdar": rustdar,
            "nexrad": nexrad,
        })

    bonus = []
    for product in ["srv", "vil"]:
        bonus.append(run_backend(RUSTDAR, "rustdar", product, raw_path, storm_cells=False))

    report = {
        "site": SITE,
        "raw_file": raw_path.name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "comparisons": comparisons,
        "bonus": bonus,
    }
    (DATA_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_html(report)
    print(json.dumps({
        "index": str(OUT_DIR / "index.html"),
        "report": str(DATA_DIR / "report.json"),
        "raw_file": str(raw_path),
    }))


if __name__ == "__main__":
    main()
