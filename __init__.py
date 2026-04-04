"""Hermes Weather Plugin.

Data: NWS API direct (Python)
Model images: rusbie + wrf-rust (Rust-backed)
Radar images: rustdar / nexrad backends (bootstrapped on demand)
Calculations: metrust-py + ecape-rs (bootstrapped on demand)
"""

import logging
import shutil
from pathlib import Path

from . import schemas
from .tools import data, images, calc

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).parent


def _install_skill():
    """Copy bundled weather skill to ~/.hermes/skills/ on first load."""
    try:
        from hermes_cli.config import get_hermes_home
        dest = get_hermes_home() / "skills" / "weather-plugin" / "SKILL.md"
    except Exception:
        dest = Path.home() / ".hermes" / "skills" / "weather-plugin" / "SKILL.md"

    source = _PLUGIN_DIR / "skill.md"
    if not source.exists() or dest.exists():
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    logger.info("Installed weather-plugin skill to %s", dest)


def register(ctx):
    """Register all weather tools."""

    schema_map = {s["name"]: s for s in schemas.ALL_SCHEMAS}

    _data_tools = {
        "wx_conditions": data.wx_conditions,
        "wx_forecast": data.wx_forecast,
        "wx_alerts": data.wx_alerts,
        "wx_metar": data.wx_metar,
        "wx_brief": data.wx_brief,
        "wx_global": data.wx_global,
        "wx_severe": data.wx_severe,
    }
    for name, handler in _data_tools.items():
        ctx.register_tool(
            name=name, toolset="weather",
            schema=schema_map[name], handler=handler,
        )

    ctx.register_tool(
        name="wx_model_image", toolset="weather",
        schema=schema_map["wx_model_image"], handler=images.wx_model_image,
    )
    ctx.register_tool(
        name="wx_radar_image", toolset="weather",
        schema=schema_map["wx_radar_image"], handler=images.wx_radar_image,
    )
    ctx.register_tool(
        name="wx_storm_image", toolset="weather",
        schema=schema_map["wx_storm_image"], handler=images.wx_storm_image,
    )

    ctx.register_tool(
        name="wx_calc", toolset="weather",
        schema=schema_map["wx_calc"], handler=calc.wx_calc,
    )
    ctx.register_tool(
        name="wx_sounding", toolset="weather",
        schema=schema_map["wx_sounding"], handler=calc.wx_sounding,
    )
    ctx.register_tool(
        name="wx_ecape", toolset="weather",
        schema=schema_map["wx_ecape"], handler=calc.wx_ecape,
    )

    _install_skill()

    logger.info("Weather plugin loaded: 13 tools (data: 7, images: 3, calc: 3)")
