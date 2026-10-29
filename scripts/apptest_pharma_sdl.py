#!/usr/bin/env python3
"""Streamlit AppTest harness for pharma-sdl.

Verifies the full app boots and works end-to-end without exceptions:
  1. 12 tabs rendered (10 legacy + Docking + PGx)
  2. Sidebar language switcher (العربية / English) — both directions
  3. 5 live interactions: Make → Predict → Capstone (offline) → Docking (Vina) → PGx (live CPIC)
  4. Docking results persisted (energies sane) + pose download buttons present

Run:  python scripts/apptest_pharma_sdl.py 2>/dev/null
Exit code 0 = all checks passed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

PGX_LIVE_LABEL = "🌐 CPIC حي (كاش 24 ساعة)"
PGX_OFFLINE_LABEL = "📚 مدمج فوري (بلا شبكة)"


def main() -> int:
    t0 = time.time()
    at = AppTest.from_file(str(APP_PATH), default_timeout=300)

    # ── 1. Boot ──────────────────────────────────────────────
    at.run()
    assert not at.exception, f"app raised on boot: {at.exception}"

    # ── 2. Tabs + language switcher ─────────────────────────
    tabs = at.tabs
    assert len(tabs) == 12, f"expected 12 tabs, got {len(tabs)}"
    lang_sel = at.selectbox(key="lang")
    assert lang_sel is not None, "sidebar language switcher missing"

    title_ar = at.title[0].value
    at.selectbox(key="lang").set_value("English").run()
    assert not at.exception, f"exception after EN switch: {at.exception}"
    title_en = at.title[0].value
    assert title_en != title_ar, "title did not change after language switch"

    # Docking/PGx tab labels must localize in English mode
    tabs_en = [tb.label for tb in at.tabs]
    assert any("Docking" in lb for lb in tabs_en), f"EN docking tab missing: {tabs_en}"
    assert any("PGx" in lb for lb in tabs_en), f"EN pgx tab missing: {tabs_en}"

    at.selectbox(key="lang").set_value("العربية").run()
    assert not at.exception, f"exception after AR switch: {at.exception}"

    # ── 3. Interaction 1: Make (RDKit enumeration) ──────────
    at.button(key="make_btn").click().run()
    assert not at.exception, f"Make tab raised: {at.exception}"

    # ── 4. Interaction 2: Predict (ML potency) ──────────────
    at.button(key="pred_btn").click().run()
    assert not at.exception, f"Predict tab raised: {at.exception}"

    # ── 5. Interaction 3: Capstone (offline library) ────────
    at.button(key="cap_btn").click().run()
    assert not at.exception, f"Capstone tab raised: {at.exception}"

    # ── 6. Interaction 4: Docking (real Vina, fast preset) ──
    at.select_slider(key="dock_exh").set_value(4).run()
    at.button(key="dock_btn").click().run()
    assert not at.exception, f"Docking tab raised: {at.exception}"
    res = at.session_state["dock_res"]
    assert res is not None, "docking result missing from session state"
    best = res.best
    assert best is not None and -15.0 < best < 0.0, f"implausible ΔG: {best}"
    dl = at.get("download_button")
    assert len(dl) >= 4, f"expected >=4 download buttons (cap+pdf+poses), got {len(dl)}"

    # ── 7. Interaction 5: PGx live CPIC (network, defensive) ─
    at.radio(key="pgx_src").set_value(PGX_LIVE_LABEL).run()
    assert not at.exception, f"PGx live raised: {at.exception}"
    at.radio(key="pgx_src").set_value(PGX_OFFLINE_LABEL).run()
    assert not at.exception, f"PGx offline raised: {at.exception}"

    dt = time.time() - t0
    print(f"OK: 12 tabs | i18n ar<->en | 5 interactions | dock ΔG={best:.2f} kcal/mol"
          f" | downloads={len(dl)} | {dt:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
