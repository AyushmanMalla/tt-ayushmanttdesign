# Puzzle 04 — Standalone Kinetic Art Engine (`src/aether_art_fsm.v`)

**Target File:** `src/aether_art_fsm.v`  
**Verify Command:** `make test-puzzle P=4`

---

## Learning Objectives

- Build a multi-speed **21-bit prescaler** with edge-detected animation ticks (`step_tick`).
- Design an area-compact **single-state-register FSM** (`st[6:0]`) with a single shared adder (`+1`, `-1`, `+5`) driving 4 distinct kinetic levitation patterns.
- Synthesize **4-quadrant phase-shifted triangle waves** (`±12`) for 3D Halo Orbit steering without a sine ROM or multiplier!

---

## Port Contract & Behavioral Spec

Module: `aether_art_fsm #(parameter PHASE_BITS = 7, parameter GRAD_BITS = 6)`

| Port | Dir | Width | Description |
| :--- | :---: | :---: | :--- |
| `clk` | in | 1 | 50 MHz system clock |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `art_en` | in | 1 | Enables animation tick stepping |
| `pat_sel` | in | 2 | Selects one of 4 kinetic art patterns (`00`, `01`, `10`, `11`) |
| `art_speed` | in | 2 | Selects prescaler speed tap (`00` slow → `11` fast simulation) |
| `btn_up` | in | 1 | Synchronized manual jog UP (active in pattern `2'b00`) |
| `btn_down` | in | 1 | Synchronized manual jog DOWN (active in pattern `2'b00`) |
| `art_z` | out reg | `PHASE_BITS` | Vertical standing-wave offset (`0..127`) |
| `art_gx` | out wire signed | `GRAD_BITS` | Signed 6-bit X tilt gradient (`-32..+31`, orbit range `±12`) |
| `art_gy` | out wire signed | `GRAD_BITS` | Signed 6-bit Y tilt gradient (`-32..+31`, orbit range `±12`) |

### 1. Prescaler Speed Taps (`reg [20:0] prescaler`)
`prescaler` increments by `1` every clock cycle (resets to `0`). Select `tap_sel`:

| `art_speed` | Tap Bit | Step Period @ 50 MHz | Purpose |
| :---: | :---: | :---: | :--- |
| `2'b00` | `prescaler[20]` | `~41.9 ms` (`2^21` clks) | Slow, hypnotic levitation drift |
| `2'b01` | `prescaler[19]` | `~21.0 ms` (`2^20` clks) | Medium kinetic sculpture speed |
| `2'b10` | `prescaler[17]` | `~5.24 ms` (`2^18` clks) | Brisk animation |
| `2'b11` | `prescaler[6]` | `2.56 µs` (`128` clks) | Fast RTL/GL simulation & bring-up |

Generate a 1-cycle tick on the rising edge of `tap_sel`:
```verilog
wire step_tick = art_en && tap_sel && !tap_prev;
```

### 2. Shared 7-Bit State Register (`reg [PHASE_BITS-1:0] st`)
On `step_tick && st_adv`, update `st <= st + st_delta`:
- `st_adv` is `1` for patterns `01`, `10`, `11`, OR for pattern `00` when **exactly one** button is pressed (`btn_up ^ btn_down`).
- `st_delta`:
  - Pattern `00` with `btn_down && !btn_up`: `-1` (`{PHASE_BITS{1'b1}}`).
  - Pattern `10` (Orbit) when `st[3:0] == 4'd11`: `+5` (`3'd5`, zero-extended) — jumps `11 → 16`, advancing cleanly from step 11 of quadrant `q` to step `0` of quadrant `q+1`!
  - All other advancing steps: `+1`.

### 3. Output Mapping for All 4 Kinetic Art Modes

| `pat_sel` | Mode | `art_z` | `art_gx`, `art_gy` |
| :---: | :--- | :--- | :--- |
| `2'b00` | **Static Lock + Manual Jog** | `st` | `0`, `0` |
| `2'b01` | **Zen Breathing** | Triangle `0 .. 32 .. 1 .. 0` (`BREATH_PEAK = 1 << (PHASE_BITS-2) = 32`) | `0`, `0` |
| `2'b10` | **3D Halo Orbit** | `0` | 4-quadrant triangle waves `±12` |
| `2'b11` | **Continuous Elevator** | `st` (modulo-128 ramp) | `0`, `0` |

#### Zen Breathing Formula (`pat_sel == 2'b01`)
```verilog
wire [PHASE_BITS-1:0] breath_sub = {2'b00, st[PHASE_BITS-3:0]}; // 0..31
wire [PHASE_BITS-1:0] breath_val = st[PHASE_BITS-2] ? (BREATH_PEAK - breath_sub) : breath_sub;
```
When `st[5:0]` counts `0..31`, `breath_val` rises `0..31`; when `st[5:0]` counts `32..63`, `breath_val` falls `32..1`.

#### 3D Halo Orbit Formula (`pat_sel == 2'b10`)
Treat `orbit_q = st[5:4]` as quadrant (`0..3`) and `orbit_s = s_ovf ? 4'd0 : st[3:0]` as step within the quadrant (`0..11`, where `s_ovf = st[3] && st[2]` safely clamps states `12..15` if the user switched into Orbit from another mode!):
- `inv_s = 4'd12 - orbit_s`
- `mag_x = orbit_q[0] ? orbit_s : inv_s`
- `mag_y = orbit_q[0] ? inv_s   : orbit_s`
- `neg_x = orbit_q[0] ^ orbit_q[1]`
- `neg_y = orbit_q[1]`
- Sign-apply in 5 bits (`orb_gx5`, `orb_gy5`), then sign-extend to 6-bit `art_gx` / `art_gy` when `is_orb`, else `0`.

Trace the 4 quadrant corners (`orbit_s = 0`):
- `Q0 (00)`: `(+12,   0)`
- `Q1 (01)`: `(  0, +12)`
- `Q2 (10)`: `(-12,   0)`
- `Q3 (11)`: `(  0, -12)`

---

## Math & Hardware Intuition

Why use `+5` wrap on a single 7-bit register instead of separate `(z_reg, dir_reg, orbit_q_reg, orbit_s_reg)` registers?
In `gf180mcuD`, every flip-flop costs `63.66 µm²` plus reset/mux overhead. Sharing **one** 7-bit register and **one** 7-bit adder across all 4 modes saves >1,200 µm² while still giving smooth 48-step circular-ish (`|Gx| + |Gy| = 12`) 3D orbits and 64-step breathing waves!

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Signed 5-bit to 6-bit sign extension</summary>

```verilog
wire [4:0] orb_gx5 = neg_x ? -{1'b0, mag_x} : {1'b0, mag_x};
wire [4:0] orb_gy5 = neg_y ? -{1'b0, mag_y} : {1'b0, mag_y};

assign art_gx = is_orb ? {orb_gx5[4], orb_gx5} : {GRAD_BITS{1'b0}};
assign art_gy = is_orb ? {orb_gy5[4], orb_gy5} : {GRAD_BITS{1'b0}};
```
Since `mag_x <= 12`, `+{1'b0, mag_x}` fits in `[0..+12]` and `-{1'b0, mag_x}` fits in `[-12..0]` as 5-bit two's complement (`-16..+15`). Duplicating MSB `orb_gx5[4]` sign-extends cleanly to 6 bits!
</details>

<details>
<summary>Common Pitfall: Forgetting `s_ovf` clamp when switching into Orbit mode</summary>

If `st` was `14` (`st[3:0] == 4'd14`) in Elevator mode and the user switches `pat_sel` to `2'b10` (Orbit), without `s_ovf = st[3] && st[2]`, `4'd12 - st[3:0]` would underflow modulo 16 (`12 - 14 = 14`), sending a huge glitch gradient to the transducers! Clamping `orbit_s` to `0` whenever `st[3:0] >= 12` guarantees `|art_gx|, |art_gy| <= 12` on every possible state.
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=4
```

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/aether_art_fsm.v
```
