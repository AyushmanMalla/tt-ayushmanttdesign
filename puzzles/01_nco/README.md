# Puzzle 01 — 20-Bit Tunable Carrier NCO (`src/aether_nco.v`)

**Target File:** `src/aether_nco.v`  
**Verify Command:** `make test-puzzle P=1`

---

## Learning Objectives

- Understand Direct Digital Synthesis (DDS) using a fixed-width **phase accumulator** (Numerically Controlled Oscillator, NCO).
- Compute exact carrier frequency, step resolution, and deterministic phase jitter at `50 MHz` vs `25 MHz`.
- Implement clean, synchronous-reset, lint-free Verilog with parameterized phase output width (`PHASE_BITS = 7`).

---

## Port Contract & Behavioral Spec

Module: `aether_nco #(parameter PHASE_BITS = 7)`

| Port | Dir | Width | Description |
| :--- | :---: | :---: | :--- |
| `clk` | in | 1 | System clock (`50 MHz` nominal, or `25 MHz` when `clk_div2 = 1`) |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `clk_div2` | in | 1 | `0`: add `freq_word` each cycle; `1`: add `2 × freq_word` (`{freq_word, 1'b0}`) each cycle |
| `freq_word` | in | 12 | 12-bit unsigned frequency tuning word (default `12'h347 = 839`) |
| `master_phase` | out | `PHASE_BITS` | Top `PHASE_BITS` MSBs of the 20-bit phase accumulator (`phase_acc[19 -: PHASE_BITS]`) |

### Behavioral Requirements
1. Maintain a 20-bit unsigned phase accumulator `reg [19:0] phase_acc`.
2. On `posedge clk`:
   - If `!rst_n`: reset `phase_acc <= 20'd0`.
   - Else: `phase_acc <= phase_acc + phase_inc`, wrapping naturally modulo $2^{20}$.
3. Phase increment `phase_inc`:
   - When `clk_div2 == 1'b0`: `phase_inc = {8'd0, freq_word}` (zero-extended to 20 bits).
   - When `clk_div2 == 1'b1`: `phase_inc = {7'd0, freq_word, 1'b0}` (shifted left by 1 = `2 × freq_word`).
4. Drive `master_phase = phase_acc[19 -: PHASE_BITS]` (bits `[19:13]` when `PHASE_BITS = 7`).

---

## Math & Hardware Intuition

An NCO generates an arbitrary output frequency from a fixed system clock $f_{\text{clk}}$ using only an adder and register:

$$f_{\text{out}} = f_{\text{clk}} \cdot \frac{\text{phase\_inc}}{2^{20}}$$

- **Default 40 kHz ultrasonic carrier @ 50 MHz (`clk_div2 = 0`):**
  $$\text{freq\_word} = \text{round}\!\left(\frac{40{,}000 \times 2^{20}}{50 \times 10^6}\right) = 839 = \texttt{12'h347}$$
  $$f_{\text{out}} = 50 \times 10^6 \times \frac{839}{1{,}048{,}576} = 40{,}006.64\text{ Hz} \quad (+0.0166\%\text{ error})$$
- **25 MHz board support (`clk_div2 = 1`):** Doubling `phase_inc` preserves the exact same `40,006.64 Hz` output when clocked at `25 MHz` — zero software changes needed!
- **Why 50 MHz matters for acoustics:** Because the accumulator updates on discrete clock edges, the carrier period dithers between `1249` and `1250` cycles (`±1` clock = `±20 ns` deterministic jitter, or `±0.29°` at 40 kHz). That is nearly 10× finer than our 7-bit phase step (`195.3 ns` / `2.8125°`).

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Indexed part-select syntax for parameterized MSBs</summary>

In Verilog-2001 / SystemVerilog, `phase_acc[19 -: PHASE_BITS]` cleanly selects `PHASE_BITS` bits starting at MSB `19` and going downward (`phase_acc[19:13]` when `PHASE_BITS = 7`).
</details>

<details>
<summary>Hint 2: Avoiding Verilator width-mismatch warnings (`WIDTHEXPAND`)</summary>

Explicitly zero-pad both branches of `phase_inc` to 20 bits:
```verilog
wire [19:0] phase_inc = clk_div2 ? {7'd0, freq_word, 1'b0} : {8'd0, freq_word};
```
</details>

<details>
<summary>Common Pitfall: Asynchronous vs Synchronous Reset</summary>

AETHER-16 uses **synchronous** active-low reset (`always @(posedge clk) if (!rst_n) ...`) across all modules for clean `gf180mcuD` scan/STA behavior. Do not put `negedge rst_n` in the sensitivity list.
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=1
```

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/aether_nco.v
```
