# Puzzle 02 — Glitch-Free Ultrasonic PWM Channel (`src/aether_channel.v`)

**Target File:** `src/aether_channel.v`  
**Verify Command:** `make test-puzzle P=2`

---

## Learning Objectives

- Implement modulo-128 (`PHASE_BITS = 7`) phase shifting for a single ultrasonic output lane.
- Exploit an architectural invariant (`eff_duty <= 64`) to cut comparator area while staying mathematically exact.
- Understand why registering the output flop (`ch_out`) eliminates combinational glitches on external H-bridge ultrasonic transducer drivers.

---

## Port Contract & Behavioral Spec

Module: `aether_channel #(parameter PHASE_BITS = 7)`

| Port | Dir | Width | Description |
| :--- | :---: | :---: | :--- |
| `clk` | in | 1 | System clock |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `out_en` | in | 1 | Channel output enable (`0` forces `ch_out <= 0` on next clock) |
| `master_phase` | in | `PHASE_BITS` | Current carrier phase (`0..127`) |
| `eff_phase` | in | `PHASE_BITS` | Per-channel phase lead (`0..127`) |
| `eff_duty` | in | `PHASE_BITS` | Effective pulse width (`0..64`, clamped upstream to `HALF_CYCLE = 64`) |
| `ch_out` | out reg | 1 | Glitch-free registered ultrasonic drive signal |

### Behavioral Requirements
1. Compute the modulo-128 shifted phase:
   ```verilog
   wire [PHASE_BITS-1:0] shifted = master_phase + eff_phase;
   ```
   *(Positive `eff_phase` advances the waveform earlier in time — a phase lead!)*
2. Compare `shifted < eff_duty` assuming `eff_duty <= 2^(PHASE_BITS-1)` (`64`):
   - When `shifted[PHASE_BITS-1] == 1` (`shifted >= 64`): `cmp_lt` is **always `0`**!
   - When `shifted[PHASE_BITS-1] == 0` (`shifted` in `0..63`):
     - If `eff_duty[PHASE_BITS-1] == 1` (i.e. `eff_duty == 64`, 50% duty): `cmp_lt` is **always `1`**!
     - Otherwise compare the lower 6 bits: `shifted[PHASE_BITS-2:0] < eff_duty[PHASE_BITS-2:0]`.
3. Register the output on `posedge clk`:
   - If `!rst_n`: `ch_out <= 1'b0`.
   - Else: `ch_out <= out_en && cmp_lt`.

---

## Math & Hardware Intuition

### Why Clamp Duty Cycle to `<= 50%` (`64 / 128`)?
Piezoelectric 40 kHz transducers are resonant bandpass elements; their fundamental acoustic amplitude is proportional to $\sin(\pi D)$, which peaks at $D = 50\%$ (`eff_duty = 64`). Driving $D > 50\%$ only wastes DC/harmonic power and heats up the driver!

Because `eff_duty` is guaranteed $\le 64$ (`7'b100_0000`), we never need a full 7-bit comparator:
$$\text{cmp\_lt} = \neg \text{shifted}[6] \land \bigl(\text{eff\_duty}[6] \lor (\text{shifted}[5:0] < \text{eff\_duty}[5:0])\bigr)$$
That saves combinational depth right in front of the output register — critical for meeting 50 MHz setup timing in `gf180mcuD`.

### Why Must `ch_out` Be Registered?
When `master_phase` transitions from `7'b011_1111` (63) to `7'b100_0000` (64), all 7 bits toggle simultaneously. A combinational comparator directly feeding a chip pin will emit narrow nanosecond **glitches** (hazards) that can shoot-through an external MOSFET half-bridge. Putting a single DFF after `out_en && cmp_lt` makes every edge 100% glitch-free.

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Exact 6-bit simplified comparator expression</summary>

```verilog
wire [PHASE_BITS-1:0] shifted = master_phase + eff_phase;
wire cmp_lt = (!shifted[PHASE_BITS-1]) &&
              (eff_duty[PHASE_BITS-1] || (shifted[PHASE_BITS-2:0] < eff_duty[PHASE_BITS-2:0]));
```
Verify the edge cases mentally:
- `eff_duty = 0`: `eff_duty[6]=0`, `shifted[5:0] < 0` is always false → `0` (0% duty).
- `eff_duty = 64`: `eff_duty[6]=1`, so `cmp_lt = !shifted[6]` → `1` for `0..63`, `0` for `64..127` (exact 50% duty!).
- `eff_duty = 32`: `eff_duty[6]=0`, `cmp_lt = !shifted[6] && (shifted[5:0] < 32)` → `1` for `0..31`, `0` for `32..127` (exact 25% duty!).
</details>

<details>
<summary>Common Pitfall: Using `&lt;=` instead of `&lt;`</summary>

If you write `shifted <= eff_duty`, then `eff_duty = 0` would still emit a 1-step pulse at `shifted = 0`, and `eff_duty = 64` would be high for 65/128 steps instead of 64/128! Strict `<` gives exact `eff_duty / 128` duty cycle.
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=2
```

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/aether_channel.v
```
