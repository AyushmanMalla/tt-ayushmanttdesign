# Puzzle 06 — Full SoC Control Integration & Acoustic Field Physics (`src/project.v` Part B)

**Target File:** `src/project.v` (`TODO(puzzle-6)` sections)  
**Verify Command:** `make test-puzzle P=6`

---

## Learning Objectives

- Register external control pins (`ui_in[0,4,5,6,7]`) to break Tiny Tapeout's `4.0 ns` external input delay out of the 50 MHz datapath.
- Implement **duty-cycle clamping** (`<= 64`), **`SOFT_PWR`** (`÷2`), and **4-level parametric AM modulation** (`0%, 25%, 50%, 75%`).
- Wire **Mode 0 (Standalone Kinetic Art) vs Mode 1 (SPI Host)** muxing, hardware safety mute (`ENABLE=0`), `CLK_DIV2`, and magic-key **`SOFT_RESET` (`0x17 ← 0xA5`)**.
- Pass the complete official tapeout verification suite (`make sim`) and simulate real **3D Gor'kov acoustic levitation traps** with `scripts/sim_acoustic_field.py`!

---

## Behavioral Spec (`src/project.v` Part B)

### 1. Registered Input Pin Mapping
Register `ui_in[0,4,5,6,7]` on `posedge clk` (reset to `0` on `!rst_n`):
- `mode_sel_r  <= ui_in[0]` (`0` = Standalone Art, `1` = SPI Host)
- `ui4_r       <= ui_in[4]` (`PAT_1` in Mode 0, `SOFT_PWR` in Mode 1)
- `hw_enable_r <= ui_in[5]` (`1` = active, `0` = hardware safety mute)
- `am_mod_r    <= ui_in[6]` (1-bit parametric AM / pulse modulation)
- `clk_div2_r  <= ui_in[7]` (`0` = 50 MHz, `1` = 25 MHz)
- `soft_pwr = mode_sel && ui4_r`

*(Leave `spi_sck = ui_in[1]`, `spi_mosi = ui_in[2]`, `spi_cs_n = ui_in[3]` feeding `u_spi` directly so `u_spi`'s 2-FF synchronizers handle their CDC cleanly!)*

### 2. Mode 0 / Mode 1 Muxing & `aether_art_fsm` Integration
- Latch pattern selection when in Mode 0:
  ```verilog
  if (!rst_n)          pat_latched <= 2'b00;
  else if (!mode_sel)  pat_latched <= {ui4_r, ui_in[3]};
  ```
- Route Mode 0 buttons from `u_spi`'s 2-FF synchronizers:
  - `art_btn_up = !mode_sel && sck_synced`
  - `art_btn_dn = !mode_sel && mosi_synced`
- Enable art engine when `use_art = (!mode_sel) || run_art_in_spi` (`ctrl_reg[5]`).
- Mux active 3D steering inputs into the lookahead pipeline:
  - `active_z  = use_art ? art_z  : z_offset`
  - `active_gx = use_art ? art_gx : grad_x`
  - `active_gy = use_art ? art_gy : grad_y`

### 3. Duty Clamping, `SOFT_PWR`, and 4-Level Parametric AM
1. **Clamp `duty_cycle` to `HALF_CYCLE = 7'd64`:**
   ```verilog
   wire [PHASE_BITS-1:0] duty_clamped = (duty_cycle[6] && (|duty_cycle[5:0]))
                                        ? HALF_CYCLE : duty_cycle;
   ```
2. **Apply `SOFT_PWR` (50% power reduction when `soft_pwr == 1`):**
   ```verilog
   wire [PHASE_BITS-1:0] duty_soft = soft_pwr ? {1'b0, duty_clamped[6:1]} : duty_clamped;
   ```
3. **Apply `am_mod_in` with `am_depth = ctrl_reg[2:1]`:**
   - When `!am_mod_in`: `eff_duty = duty_soft`
   - When `am_mod_in`:
     - `2'b00`: `duty_soft` (`0%` AM — off)
     - `2'b01`: `duty_soft - (duty_soft >> 2)` (`25%` AM depth → 75% remaining)
     - `2'b10`: `duty_soft >> 1` (`50%` AM depth → 50% remaining)
     - `2'b11`: `duty_soft >> 2` (`75%` AM depth → 25% remaining)

### 4. Output Safety Mute & Magic-Key `SOFT_RESET`
- `out_en = hw_enable && (mode_sel ? spi_out_en : 1'b1)`
- `eval_en = out_en && !ch_clr_act`
- When `!eval_en`, force `uo_out_reg <= 8'h00` and `uio_out_reg <= 8'h00` on the very next clock cycle!
- `soft_reset = spi_wr_en && (spi_wr_addr == 5'h17) && (spi_wr_data == 8'hA5)`
- `reg_rst = (!rst_n) || soft_reset` (resets all SPI registers **and** triggers the 8-cycle shift-bank scrubber!).

---

## Math & Hardware Intuition

### Why Register `ui_in[0]`?
In Tiny Tapeout's open-source STA environment, external inputs arrive with up to **4.0 ns** input delay (`20%` of a 20 ns 50 MHz clock!). On our initial `exp/phase7-hires` build, an unregistered `ui_in[0]` (`mode_sel`) fanned out into `use_art` → `active_gx/gy` → 4 cascaded adders, causing a `-0.52 ns` setup violation at typical corner (`nom_tt_025C_3v30`). Registering `ui_in[0,4,5,6,7]` cuts that 4 ns penalty completely out of the datapath!

### Gor'kov Acoustic Levitation Physics
When you run `make test-puzzle P=6`, after passing all RTL simulations, the grader automatically runs:
```bash
.venv/bin/python3 scripts/sim_acoustic_field.py --phase-bits 7 --out puzzles/06_full_soc_integration/acoustic_trap_xz.png
```
Open that PNG to see the simulated 40 kHz Huygens–Fresnel pressure field and **Gor'kov acoustic radiation potential** $U(x, y, z)$ for 2 mm EPS spheres — proving your chip's exact 7-bit (`34 µm`) phase words form deep standing-wave levitation traps!

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Shift-only 25% / 50% / 75% AM reduction (zero multipliers!)</summary>

```verilog
case (am_depth)
  2'b00:   eff_duty = duty_soft;                                      // 100%
  2'b01:   eff_duty = duty_soft - {2'b00, duty_soft[PHASE_BITS-1:2]}; // 75% (25% AM)
  2'b10:   eff_duty = {1'b0, duty_soft[PHASE_BITS-1:1]};              // 50% (50% AM)
  2'b11:   eff_duty = {2'b00, duty_soft[PHASE_BITS-1:2]};             // 25% (75% AM)
  default: eff_duty = duty_soft;
endcase
```
</details>

<details>
<summary>Common Pitfall: `SOFT_RESET` clearing `rst_n` vs `reg_rst`</summary>

`soft_reset` resets the SPI register bank and triggers the 8-cycle shift-bank scrubber via `reg_rst = (!rst_n) || soft_reset`, while `u_spi`, `u_nco`, `u_art_fsm`, and `slot` remain on hard `!rst_n`. That way an SPI `SOFT_RESET` never corrupts the SPI slave mid-frame or desynchronizes `slot`!
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=6
```
This runs:
1. `puzzles/06_full_soc_integration/test_puzzle.py` (Part B SoC integration suite)
2. Official tapeout `make sim` (`test/test.py` — all 6 tests)
3. 3D Gor'kov acoustic field heatmap generation (`scripts/sim_acoustic_field.py --phase-bits 7`)

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/project.v
```
