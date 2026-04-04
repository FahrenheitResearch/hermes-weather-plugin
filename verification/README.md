# Hermes Weather Plugin Verification

This directory contains focused verification scripts for expanded Hermes model support.

Scripts:
- `model_matrix.py`: preflight image and profile model support against local backend sources
- `verify_wx_calc.py`: compares `wx_calc` to direct `metrust.calc`
- `verify_wx_sounding.py`: compares `wx_sounding` key CAPE values to direct `metrust` on the same extracted profile
- `verify_wx_ecape.py`: compares `wx_ecape` to direct `ecape-rs`

These scripts are written to work against local source checkouts for `rustweather`, `rusbie`, `cfrust`, `rustplots`, and `wrf-rust` when they exist under `C:/Users/drew`.
