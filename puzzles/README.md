# AETHER-16 Guided ASIC Learning Curriculum (`learn/aether16-puzzles`)

Welcome to the interactive **AETHER-16** learning branch!

Here, you will rebuild and master **every single module** of the tapeout-ready **`1×1` `gf180mcuD` (180 nm, 50 MHz) 16-Channel Ultrasonic Acoustic Levitator ASIC** from scratch through **7 progressive, self-contained Verilog + ASIC verification puzzles**.

Each puzzle gives you:
- A crisp engineering specification (`puzzles/0X_<name>/README.md`) with hardware intuition, math derivations, and collapsible hints
- A cleanly commented starter skeleton in `src/` with the **exact same module names, file paths, and port lists** as `main`
- An automated `cocotb` 2.0.0 testbench or physical signoff checker invoked with `make test-puzzle P=X`

---

## 7-Puzzle Roadmap

| Puzzle | Directory | Target File(s) | Core Silicon Skill | Grader Command |
| :---: | :--- | :--- | :--- | :--- |
| **01** | `puzzles/01_nco` | `src/aether_nco.v` | 20-bit NCO / DDS phase accumulator & `CLK_DIV2` frequency scaling | `make test-puzzle P=1` |
| **02** | `puzzles/02_channel` | `src/aether_channel.v` | Modulo-128 phase shifting, 6-bit simplified PWM comparator, glitch-free FFs | `make test-puzzle P=2` |
| **03** | `puzzles/03_spi` | `src/aether_spi.v` | 2-FF CDC synchronizers, SPI Mode 0 edge detect, write guard, pin reuse | `make test-puzzle P=3` |
| **04** | `puzzles/04_art_fsm` | `src/aether_art_fsm.v` | Multi-tap prescaler, single-register shared FSM, 4-quadrant orbit math | `make test-puzzle P=4` |
| **05** | `puzzles/05_shift_bank_and_3d` | `src/project.v` *(Part A)* | 2×8 packed shift-bank TDM, X-free scrubber, 1-cycle lookahead, 45° ring + Vortex | `make test-puzzle P=5` |
| **06** | `puzzles/06_full_soc_integration` | `src/project.v` *(Part B)* | Registered pins, duty clamp, `SOFT_PWR`, 4-level AM, Mode 0/1 mux, Gor'kov physics | `make test-puzzle P=6` |
| **07** | `puzzles/07_physical_signoff` | Full ASIC Flow | Verilator lint, Yosys `gf180mcuD` synth, LibreLane PnR, 9-corner STA, GDS & GL sim | `make test-puzzle P=7` |

---

## Quick Start Workflow

1. **Read the puzzle brief** (start at `puzzles/01_nco/README.md`).
2. **Run the grader first** to see the failing assertions on the starter skeleton:
   ```bash
   make test-puzzle P=1
   ```
3. **Implement the `// TODO(puzzle-N)` blocks** in the target `src/*.v` file.
4. **Re-run the grader** until every test passes!
5. **Check lint** at any time to keep your RTL synthesis-clean:
   ```bash
   make lint
   ```
6. **Stuck? Compare against the tapeout reference on `main`!**
   Because this branch keeps the exact same 5 `src/*.v` filenames and port interfaces as `main`, you can inspect or diff any module cleanly:
   ```bash
   # See line-by-line diff against the tapeout-ready solution
   git diff main -- src/aether_nco.v

   # Or print the reference file without modifying your working tree
   git show main:src/aether_nco.v
   ```

---

## The 7 Core Silicon Lessons Behind AETHER-16

1. **NCO / DDS Math (`Puzzle 01`):** A 20-bit phase accumulator clocked at 50 MHz with `freq_word = 12'h347 (839)` generates `40,006.6 Hz` (`+0.016%` error vs 40 kHz) with only `±20 ns` deterministic edge jitter (`±0.29°`) — easily fitting inside the narrow Q-factor resonance of 40 kHz piezoelectric transducers.
2. **Glitch-Free Registered PWM (`Puzzle 02`):** Ultrasonic H-bridge drivers hate combinational glitches. Registering `ch_out` guarantees clean transitions, and exploiting `eff_duty <= 64` reduces the 7-bit magnitude comparator to 6 bits + 2 gates.
3. **2-FF CDC SPI Mode 0 (`Puzzle 03`):** Asynchronous external SPI pins (`SCK`, `MOSI`, `CS_N`) must cross into the 50 MHz clock domain through 2-FF synchronizers to eliminate metastability. Reusing those exact sync flops for Mode 0 `BTN_UP` / `BTN_DOWN` saves silicon area for free.
4. **Area-Compact Shared-State FSM (`Puzzle 04`):** Four completely different kinetic art animations (Static + Jog, Zen Breathing, 3D Halo Orbit, Continuous Elevator) share a single 7-bit state register and one adder (`+1`, `-1`, or `+5` quadrant wrap).
5. **2-Way Rotating Shift-Bank TDM + 1-Cycle Lookahead (`Puzzle 05`):**
   - *Why naive parallel fails:* In `gf180mcuD` (180 nm, 5 V, 7-track cells), 16 parallel phase channels + resettable register muxes synthesize to **55,839 µm²** — larger than the entire **55,712 µm²** `1×1` Tiny Tapeout die!
   - *The TDM breakthrough:* Two packed 56-bit (`8 × 7-bit`) circular shift banks + two `aether_channel` evaluators + an atomic 16-pin shadow commit every 8 clocks (`160 ns` < `195.3 ns` 7-bit phase step!) cuts synthesis area by **~39%** (`~35.9k µm²`) with **0.00 ns inter-channel skew** and **0 Yosys memory warnings**.
   - *The STA breakthrough:* Precomputing the 45° ring gradient + Hardware Acoustic Vortex (`k × 16`) for `slot_next = slot + 1` in a 1-cycle lookahead stage breaks the 4-adder critical path and wins **+11.5 ns** on worst-case STA!
6. **Full SoC Control & Acoustic Physics (`Puzzle 06`):** Registering external pins removes `4.0 ns` external delay from the datapath, `SOFT_PWR` and 4-level `AM_MOD_IN` shape acoustic levitation force without dropping phase lock, and `scripts/sim_acoustic_field.py` verifies real 3D Gor'kov levitation traps for 2 mm EPS spheres.
7. **Physical ASIC Signoff (`Puzzle 07`):** Real silicon isn't done at RTL sim. You will run Yosys `gf180mcuD` synthesis, LibreLane RTL-to-GDSII placement & routing, 9-corner Static Timing Analysis, DRC/LVS/Antenna checks, KLayout GDS inspection, and Gate-Level simulation (`make sim-gl`) where every X-propagation bug shows up!
