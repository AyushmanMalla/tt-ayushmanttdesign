# Puzzle 07 — Full ASIC Physical Design & Tapeout Signoff Lab (`gf180mcuD`, `1×1`, `50 MHz`)

**Target Flow:** End-to-End RTL-to-GDSII Signoff  
**Verify Command:** `make test-puzzle P=7`

---

## Learning Objectives

Passing RTL simulation is only **half** the journey of building real silicon! In this capstone physical design lab, you will take your finished AETHER-16 RTL through the exact open-source ASIC tapeout signoff flow used for Tiny Tapeout on **`gf180mcuD` (180 nm, `1×1` tile = `346.64 × 160.72 µm` = `55,712 µm²`)**:

1. **Static Linting & Port/YAML Compliance** (`make lint`)
2. **Standard-Cell Synthesis & Area Analysis** (`make synth`) — comparing your TDM shift-bank area against naive 16-parallel hardware
3. **Full RTL-to-GDSII Place & Route** (`make impl`) via LibreLane / OpenROAD
4. **9-Corner Static Timing Analysis (STA)** & **Physical Signoff** (Magic DRC, Netgen LVS, Antenna)
5. **GDSII Layout Inspection** (`make klayout` / `make openroad` / `make png`)
6. **Post-PnR Gate-Level Simulation (`make sim-gl`)** — proving zero X-propagation on real `gf180mcuD` DFF models!
7. **Datasheet & Submission Validation** (`make docs`)

---

## Step-by-Step Lab Procedure

### Step 1: Zero-Warning Lint & Tiny Tapeout Interface Check
```bash
make lint
```
Verify:
- `0` Verilator `-Wall` warnings across all 5 `src/*.v` files.
- `tt_tool.py --create-user-config` accepts `info.yaml` and all port widths cleanly.

### Step 2: Fast Local Yosys Synthesis (`gf180mcu_fd_sc_mcu7t5v0`)
```bash
make synth
```
Inspect the `stat -liberty` table at the bottom of the output:
- **Compare against Naive Parallel:** A naive 16-channel parallel design synthesizes to **`55,839 µm²`** — larger than the entire `55,712 µm²` `1×1` die before routing!
- **Your TDM Shift-Bank Target:** Should synthesize to **`~35,000–37,000 µm²`** with **`~308` DFFs** and **`0` Yosys warnings** (packing `bank_bot` and `bank_top` as 56-bit vectors avoids Yosys unpacked-array warnings!).

### Step 3: Full LibreLane RTL-to-GDSII Hardening (`50 MHz`)
Start Docker (or `make colima` on macOS), then run:
```bash
make impl
```
When hardening finishes (~1–2 minutes), inspect the printed stats and `runs/wokwi/final/metrics.json`:

| Signoff Metric | Tapeout Reference (`main`) | Your Goal |
| :--- | :---: | :---: |
| **Post-PnR Active Std Cells** | `1,476` (`308` DFFs) | Fits cleanly in `1×1` |
| **Routing Utilization** | `81.05%` | `< 88%` (no routing congestion) |
| **Setup WNS @ 50 MHz (`nom_tt_025C_3v30`)** | **`0.00 ns` PASS** | **`>= 0.00 ns`** |
| **Hold WNS (All 9 PVT Corners)** | **`0.00 ns` PASS** | **`>= 0.00 ns`** |
| **Magic DRC Violations** | **`0`** | **`0`** |
| **Netgen LVS Errors** | **`0`** | **`0`** |
| **Antenna Violations** | **`0`** | **`0`** |

### Step 4: Inspect Your Real Silicon Layout!
```bash
make png       # Render gds_render.png
make klayout   # Open GDSII in KLayout (or make openroad for OpenROAD GUI)
```
Look closely at the layout: notice how the two compact 56-bit shift banks and shared NCO/Art FSM pack densely into the `346.64 × 160.72 µm` `1×1` tile with clean Metal 2–4 routing channels!

### Step 5: Post-PnR Gate-Level Simulation (`make sim-gl`)
```bash
make sim-gl
```
**Why Gate-Level Sim Catches Real Silicon Bugs:**
In RTL simulation, uninitialized registers sometimes hide behind simulator defaults. In `make sim-gl`, Icarus simulates the **actual synthesized `gf180mcu_fd_sc_mcu7t5v0` standard-cell gate netlist** with `X`-initialized flip-flops!
- If your **8-cycle shift-bank reset scrubber** (`ch_clr_act` / `ch_clr_cnt` from Puzzle 05) wasn't wired properly, `X`s in the resetless interior shift stages will leak out to `uo_out`/`uio_out` and immediately fail `make sim-gl`!
- Passing **6 / 6 Gate-Level `cocotb` tests** proves your real netlist is 100% X-free and functionally identical to RTL.

### Step 6: Datasheet & Submission Check
```bash
make docs
```
Validates `info.yaml` and `docs/info.md` for Tiny Tapeout tapeout readiness.

---

## Automated Signoff Checker

Run the Puzzle 07 signoff audit at any time:
```bash
make test-puzzle P=7
```
`check_signoff.py` automatically verifies:
1. Verilator `-Wall` lint (`0` warnings/errors)
2. Local Yosys `gf180mcuD` synthesis (`0` warnings + pre-PnR area `< 45,000 µm²`)
3. Full RTL `cocotb` suite (`6 / 6 PASS`)
4. LibreLane post-PnR metrics (`runs/wokwi/final/metrics.json`: DRC=0, LVS=0, Antenna=0, `nom_tt_025C_3v30` setup WNS >= 0, all-corner hold WNS >= 0) — if you haven't run `make impl` yet, it tells you the exact next command to complete physical signoff!
