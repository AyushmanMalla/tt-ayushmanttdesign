# Puzzle 05 — 2×8 Rotating Shift-Bank TDM, 3D Ring Pipeline & Acoustic Vortex (`src/project.v` Part A)

**Target File:** `src/project.v` (`TODO(puzzle-5)` sections)  
**Verify Command:** `make test-puzzle P=5`

---

## Learning Objectives

- Understand why naive 16-channel parallel hardware **fails to fit** inside a `1×1` `gf180mcuD` Tiny Tapeout tile (`55,712 µm²`).
- Implement AETHER-16's **2-way packed rotating shift-bank TDM engine** (`bank_bot`, `bank_top`) with an **8-cycle X-free reset scrubber** (critical for Gate-Level simulation!).
- Design the **1-cycle lookahead pipeline** (`slot_next = slot + 1`, `g_signed_r`, `bot_snap`, `top_snap`) that breaks a 4-adder critical path and wins **+11.5 ns** on Static Timing Analysis!
- Implement the **45° 8-ring 3D gradient combiner**, `top_invert` (180°), **0-FF Hardware Acoustic Vortex** (`k × 16`), and **0.00 ns inter-channel skew atomic shadow commit**.

---

## Architecture & Spec (`src/project.v` Part A)

### 1. Why Naive Parallelism Fails `1×1` `gf180mcuD`
In `gf180mcu_fd_sc_mcu7t5v0` (180 nm 5 V 7-track standard cells), a single flip-flop costs `63.66 µm²`.
- **Naive 16 parallel channels** (16 adders + 16 comparators + 16 random-access resettable register muxes): **55,839 µm²** — *larger than the entire `55,712 µm²` die!*
- **AETHER-16 2-Way Shift-Bank TDM:** Only **2** `aether_channel` evaluators (`u_ch_bot`, `u_ch_top`) evaluate 1 bottom + 1 top channel per clock cycle (`slot = 0..7`), then commit all 16 pins atomically every 8 clocks (`160 ns` @ 50 MHz — **finer than one `195.3 ns` 7-bit phase step!**).
  - Synthesis area drops by **~39%** to `~35,890 µm²`!
  - Inter-channel pin skew is **`0.00 ns`**!

### 2. Packed 2×8 Rotating Shift Banks (`CH_BASE_PHASE[0..15]`)
Pack all 8 channels of each ring into a single 56-bit vector (eliminates all Yosys unpacked-array memory warnings!):
```verilog
reg [8*PHASE_BITS-1:0] bank_bot; // Ch 0..7, head at bank_bot[6:0]
reg [8*PHASE_BITS-1:0] bank_top; // Ch 8..15, head at bank_top[6:0]
```
Every clock cycle, both banks rotate right by 7 bits (`bank <= {bank_next, bank[55:7]}`), synchronized with `reg [2:0] slot` (`0..7`):
- **Write-on-slot-match:** When `spi_wr_en && !spi_wr_addr[4]` (channel register `0x00..0x0F`), assert `ch_wr_pend <= 1'b1`. The target channel (`lat_ch_addr[2:0]`) and 7-bit phase (`lat_ch_data`) stay latched inside `u_spi`! When `ch_wr_pend && (slot == lat_ch_addr[2:0])`, overwrite `bank_bot_next` (if `!lat_ch_addr[3]`) or `bank_top_next` (if `lat_ch_addr[3]`) and clear `ch_wr_pend <= 1'b0`.
- **8-Cycle X-Free Reset Scrubber:** Interior shift stages have **no reset gates** (saving 98 reset cells!). On `reg_rst`, assert `ch_clr_act <= 1'b1` and `ch_clr_cnt <= 3'd7`. While `ch_clr_now = reg_rst || ch_clr_act`, inject `7'd0` into both `bank_bot_next` and `bank_top_next`, and mute outputs (`eval_en = out_en && !ch_clr_act`). After 8 cycles (`ch_clr_cnt == 0`), every single bit of all 16 shift-bank slots is guaranteed `0` — even after a 1-cycle reset in Gate-Level simulation!

### 3. SPI Global Registers (`0x10..0x16`)
On `reg_rst`, reset to:
- `freq_word <= 12'h347` (`40,006.6 Hz` @ 50 MHz)
- `duty_cycle <= 7'd64` (`HALF_CYCLE` = 50% duty)
- `z_offset <= 7'd0`, `grad_x <= 6'sd0`, `grad_y <= 6'sd0`
- `ctrl_reg <= 8'h05` (`spi_out_en=1`, `am_depth=2'b10`, `art_spd=0`, `run_art=0`, `top_invert=0`, `vortex_en=0`)

On `spi_wr_en && spi_wr_addr[4]`, decode `spi_wr_addr[3:0]`:
- `4'h0`: `freq_word[7:0] <= spi_wr_data`
- `4'h1`: `freq_word[11:8] <= spi_wr_data[3:0]`
- `4'h2`: `duty_cycle <= spi_wr_data[6:0]`
- `4'h3`: `z_offset <= spi_wr_data[6:0]`
- `4'h4`: `grad_x <= spi_wr_data[5:0]`
- `4'h5`: `grad_y <= spi_wr_data[5:0]`
- `4'h6`: `ctrl_reg <= spi_wr_data`

### 4. 1-Cycle Lookahead 45° Ring Gradient & Hardware Acoustic Vortex
Each ring has 8 transducers spaced every 45° around a circle (`k = 0..7`). The 3D tilt gradient offset for slot `k` is:

| Slot `k` | Angle | Gradient Offset `g_dir(k)` | Vortex Offset (`vortex_en=1`) |
| :---: | :---: | :---: | :---: |
| `0` | `0°` | `+Gx` | `+0` |
| `1` | `45°` | `+Gx + Gy` | `+16` |
| `2` | `90°` | `+Gy` | `+32` |
| `3` | `135°` | `-Gx + Gy` | `+48` |
| `4` | `180°` | `-Gx` | `+64` |
| `5` | `225°` | `-Gx - Gy` | `+80` |
| `6` | `270°` | `-Gy` | `+96` |
| `7` | `315°` | `+Gx - Gy` | `+112` |

**Why Lookahead (`slot_next = slot + 3'd1`)?**
If you compute `master_phase + top_z + g_dir + vortex_add + bank_head` in a single cycle before `u_ch_top`'s comparator, **4 cascaded 7-bit adders + comparator** blow past the 20 ns (`50 MHz`) clock period in `gf180mcuD`!
Instead, compute `g_tot_next = g_dir_next + vortex_add` for **`slot_next = slot + 3'd1`** and register it into `g_signed_r` every cycle! At `slot == 3'd7`, also snapshot:
- `bot_snap <= master_phase`
- `top_snap <= master_phase + top_z` (where `top_z = {active_z[6] ^ top_invert, active_z[5:0]}` adds `64` = 180° when `top_invert = 1`)
- `eff_duty_r <= eff_duty`

Then on `slot = 0..7`, each channel evaluator sees only **two tiny additions**:
`p_bot = bot_snap + g_signed_r` → `u_ch_bot(.master_phase(p_bot), .eff_phase(bank_bot_head), .eff_duty(eff_duty_r))`!

### 5. Atomic 16-Channel Shadow Commit (`0.00 ns` Skew)
- `u_ch_bot` / `u_ch_top` register `ch_bot_q` / `ch_top_q` with 1-cycle latency: when `slot == k`, they evaluate slot `k`, so on `slot == (k+1) mod 8`, `ch_*_q` holds the result for slot `k`!
- Shift `ch_bot_q` into `reg [6:0] sh_bot <= {ch_bot_q, sh_bot[6:1]}` (and same for `sh_top`) every clock.
- When `slot == 3'd0`: `ch_bot_q` holds **Ch 7**, and `sh_bot` holds **Ch 6..0**! Commit all 16 pins simultaneously:
  ```verilog
  uo_out_reg  <= {ch_bot_q, sh_bot};
  uio_out_reg <= {ch_top_q, sh_top};
  ```
- Drive `uio_oe = 8'hFF` (all 8 bidirectional pins configured as outputs for Top Ring Ch 8..15).

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Compact 45° ring gradient formula (zero multipliers!)</summary>

Notice the half-ring anti-symmetry: slots `4..7` are simply the negation of slots `0..3`!
```verilog
wire [PHASE_BITS-1:0] gx7        = {active_gx[GRAD_BITS-1], active_gx};
wire [PHASE_BITS-1:0] gy7        = {active_gy[GRAD_BITS-1], active_gy};
wire [PHASE_BITS-1:0] ga_a       = (slot_next[1:0] == 2'd0) ? 7'd0 : gy7;
wire [PHASE_BITS-1:0] ga_b       = (slot_next[1:0] == 2'd2) ? 7'd0 : gx7;
wire [PHASE_BITS-1:0] g_mag_next = (slot_next[1:0] == 2'd3) ? (ga_a - ga_b) : (ga_a + ga_b);
wire [PHASE_BITS-1:0] g_dir_next = slot_next[2] ? -g_mag_next : g_mag_next;
wire [PHASE_BITS-1:0] vortex_add = vortex_en ? {slot_next, 4'b0000} : 7'd0;
wire [PHASE_BITS-1:0] g_tot_next = g_dir_next + vortex_add;
```
Check all 8 slots: `k=0: +Gx`, `k=1: +Gy+Gx`, `k=2: +Gy`, `k=3: +Gy-Gx`, `k=4..7: -(k-4)`!
</details>

<details>
<summary>Common Pitfall: Off-by-1 slot alignment between `slot`, `bank_*_head`, and `sh_*`</summary>

Trace carefully:
- At `slot == 7` clock edge: `slot` becomes `0`, `g_signed_r` latches `g_tot(slot_next=0)`, `bot_snap` & `top_snap` latch, and `bank_bot_head` rotates to slot `0`.
- During `slot == 0`: `u_ch_bot` computes Ch 0 (`slot 0`). At the `slot == 0 → 1` edge, `ch_bot_q` becomes Ch 0.
- During `slot == 1..7`: `ch_bot_q` shifts into `sh_bot` 7 times, placing Ch 0 into `sh_bot[0]` .. Ch 6 into `sh_bot[6]`.
- At the `slot == 7 → 0` edge: `ch_bot_q` becomes Ch 7!
- At the `slot == 0` check: `{ch_bot_q, sh_bot}` = `{Ch7, Ch6, Ch5, Ch4, Ch3, Ch2, Ch1, Ch0}` — exact bit order!
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=5
```

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/project.v
```
