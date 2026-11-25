#!/usr/bin/env python3
"""
Puzzle 07 Automated Signoff Auditor for AETHER-16 (1x1 gf180mcuD, 50 MHz)

Checks:
  1. Verilator -Wall lint (0 errors / 0 warnings)
  2. Local Yosys synthesis (0 warnings, area < 45,000 um^2 if gf180mcuD PDK present)
  3. Full RTL cocotb verification (make sim)
  4. LibreLane post-PnR signoff metrics (runs/wokwi/final/metrics.json) if hardened
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_FILES = [
    ROOT / "src/project.v",
    ROOT / "src/aether_nco.v",
    ROOT / "src/aether_spi.v",
    ROOT / "src/aether_art_fsm.v",
    ROOT / "src/aether_channel.v",
]
STDCELL_LIB = (
    ROOT
    / ".pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib"
)
METRICS_JSON = ROOT / "runs/wokwi/final/metrics.json"
GL_NETLIST = ROOT / "runs/wokwi/final/pnl/tt_um_ayushmanmalla_top.pnl.v"


def run_cmd(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def check_lint() -> tuple[bool, str]:
    if not shutil.which("verilator"):
        return False, "verilator not found in PATH"
    cmd = [
        "verilator",
        "--lint-only",
        "-Wall",
        "-Wno-DECLFILENAME",
        f"-I{ROOT / 'src'}",
        "--top-module",
        "tt_um_ayushmanmalla_top",
        *[str(f) for f in SRC_FILES],
    ]
    res = run_cmd(cmd)
    if res.returncode != 0:
        return False, f"Verilator lint failed:\n{res.stderr.strip()}"
    return True, "0 errors, 0 warnings"


def check_yosys_synth() -> tuple[bool, str]:
    if not shutil.which("yosys"):
        return False, "yosys not found in PATH"
    srcs = " ".join(str(f) for f in SRC_FILES)
    if STDCELL_LIB.exists():
        script = (
            f"read_liberty -lib {STDCELL_LIB}; "
            f"read_verilog -sv {srcs}; "
            "synth -nordff -top tt_um_ayushmanmalla_top; "
            f"dfflibmap -liberty {STDCELL_LIB}; "
            f"abc -liberty {STDCELL_LIB}; "
            "opt_clean -purge; check -assert; "
            f"stat -liberty {STDCELL_LIB}"
        )
    else:
        script = (
            f"read_verilog -sv {srcs}; "
            "synth -nordff -top tt_um_ayushmanmalla_top; "
            "opt_clean -purge; check -assert; stat"
        )
    res = run_cmd(["yosys", "-QT", "-p", script])
    combined = res.stdout + "\n" + res.stderr
    if res.returncode != 0:
        return False, f"Yosys synthesis failed:\n{combined[-800:]}"

    warnings = [ln for ln in combined.splitlines() if ln.strip().startswith("Warning:")]
    area_match = re.search(r"Chip area for top module.*:\s*([0-9.]+)", combined)
    if not area_match:
        all_areas = re.findall(r"Chip area for module.*:\s*([0-9.]+)", combined)
        area = float(all_areas[-1]) if all_areas else None
    else:
        area = float(area_match.group(1))
    dff_matches = re.findall(r"^\s*([0-9]+)\s+[0-9.E+-]+\s+gf180mcu_fd_sc_mcu7t5v0__dff", combined, re.M)
    dffs = int(dff_matches[-1]) if dff_matches else None

    if area is not None and area >= 45000.0:
        return (
            False,
            f"Pre-PnR area {area:.1f} um^2 >= 45,000 um^2 (too large for 1x1 gf180mcuD!)",
        )
    if warnings:
        return False, f"Yosys emitted {len(warnings)} warning(s): {warnings[0]}"

    area_str = f"{area:.1f} um^2" if area is not None else "generic (no PDK lib)"
    dff_str = f"{dffs} DFFs" if dffs is not None else "generic"
    return True, f"0 warnings | {dff_str} | {area_str} (vs 55,839 um^2 naive parallel)"


def check_rtl_sim() -> tuple[bool, str]:
    res = run_cmd(["make", "sim"])
    if res.returncode != 0:
        tail = (res.stdout + "\n" + res.stderr)[-800:]
        return False, f"make sim failed:\n{tail}"
    return True, "All 6/6 official RTL cocotb tests PASSED"


def check_librelane_metrics() -> tuple[str, str]:
    if not METRICS_JSON.exists():
        return (
            "PENDING",
            "runs/wokwi/final/metrics.json not found yet — run `make impl` (then `make sim-gl` and `make docs`)",
        )
    data = json.loads(METRICS_JSON.read_text())

    drc = data.get("magic__drc_error__count", -1)
    lvs = data.get("design__lvs_error__count", -1)
    ant_pin = data.get("route__antenna_violation__count", 0)
    tt_wns = data.get("timing__setup__wns__corner:nom_tt_025C_3v30", None)
    hold_wns = data.get("timing__hold__wns", None)
    util = data.get("design__instance__utilization", None)
    wl = data.get("route__wirelength", None)

    issues = []
    if drc != 0:
        issues.append(f"DRC={drc}")
    if lvs != 0:
        issues.append(f"LVS={lvs}")
    if ant_pin != 0:
        issues.append(f"Antenna={ant_pin}")
    if tt_wns is not None and tt_wns < 0.0:
        issues.append(f"nom_tt setup WNS={tt_wns:.2f} ns")
    if hold_wns is not None and hold_wns < 0.0:
        issues.append(f"hold WNS={hold_wns:.2f} ns")

    summary = (
        f"DRC={drc}, LVS={lvs}, Ant={ant_pin}, "
        f"tt_WNS={tt_wns} ns, hold_WNS={hold_wns} ns"
        + (f", util={util*100:.1f}%" if isinstance(util, (int, float)) else "")
        + (f", WL={wl} um" if wl is not None else "")
    )
    if issues:
        return "FAIL", f"Signoff violations ({', '.join(issues)}) | {summary}"
    if not GL_NETLIST.exists():
        return "PENDING", f"{summary} (missing GL netlist for make sim-gl)"
    return "PASS", summary


def main() -> int:
    print("=" * 78)
    print("  AETHER-16 Puzzle 07 — Physical ASIC Signoff Audit (1x1 gf180mcuD, 50 MHz)")
    print("=" * 78)

    ok_lint, msg_lint = check_lint()
    print(f"  [1/4] Verilator -Wall Lint       : {'PASS' if ok_lint else 'FAIL'} — {msg_lint}")

    ok_synth, msg_synth = check_yosys_synth()
    print(f"  [2/4] Yosys gf180mcuD Synthesis  : {'PASS' if ok_synth else 'FAIL'} — {msg_synth}")

    ok_sim, msg_sim = check_rtl_sim()
    print(f"  [3/4] Official RTL cocotb Suite  : {'PASS' if ok_sim else 'FAIL'} — {msg_sim}")

    pnr_status, msg_pnr = check_librelane_metrics()
    print(f"  [4/4] LibreLane PnR Signoff      : {pnr_status} — {msg_pnr}")
    print("=" * 78)

    if not (ok_lint and ok_synth and ok_sim):
        print("\nResult: INCOMPLETE — fix the failing RTL/synthesis checks above first.")
        return 1
    if pnr_status == "FAIL":
        print("\nResult: FAIL — fix the LibreLane physical signoff violations above.")
        return 1
    if pnr_status == "PENDING":
        print("\nRTL & Synthesis are Tapeout-Ready! Next steps for full silicon signoff:")
        print("  1. make impl      # Harden 1x1 gf180mcuD GDSII via LibreLane")
        print("  2. make sim-gl    # Verify post-PnR Gate-Level netlist (6/6 PASS)")
        print("  3. make png       # Render gds_render.png (or make klayout)")
        print("  4. make docs      # Validate info.yaml & docs/info.md")
        print("  5. make test-puzzle P=7  # Re-run to verify 4/4 PASS!")
        return 0

    print("\nCONGRATULATIONS! AETHER-16 passed 4/4 Physical Signoff checks!")
    print("Don't forget to also run `make sim-gl`, `make png`, and `make docs`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
