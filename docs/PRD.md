# Product Requirements Document (PRD): AETHER-16

| Field | Value |
| :--- | :--- |
| **Project Name** | **AETHER-16** — Pure-Silicon 16-Channel Ultrasonic Phased-Array Acoustic Levitator |
| **Top Module** | `tt_um_ayushmanmalla_top` |
| **Target Shuttle / PDK** | Tiny Tapeout `ttgf26c` / GlobalFoundries 180 nm (`gf180mcuD`, 3.3 V, 7-track std cells) |
| **Tile Footprint** | `1×1` (`346.64 × 160.72 µm`, ~55,712 µm² die area) |
| **Signoff Clock** | `50.000 MHz` (`CLOCK_PERIOD = 20 ns`, all 9 PVT STA corners) |
| **Author** | Ayushman Malla |

---

## 1. Vision & Motivation

**AETHER-16** is a self-contained, screenless kinetic desk sculpture powered by a single `1×1` Tiny Tapeout custom ASIC. The chip drives **16 simultaneous, phase-locked, jitter-free 40 kHz ultrasonic channels** with sub-microsecond phase precision to suspend and smoothly animate real 1–3 mm physical objects (EPS foam beads, micro-droplets) in mid-air.

### Why Custom Silicon?
Unlike general-purpose microcontrollers (e.g., ESP32) that lack 16 independent hardware phase-locked timers and suffer RTOS jitter, a custom `1×1` ASIC natively executes all 16 phase adders, duty/AM comparators, and atomic 3D gradient updates **in parallel on every single 50 MHz clock edge**.

---

## 2. Clocking & Acoustic Physics

### 2.1 Why 50 MHz?
- **Upper bound (Why not 80–100+ MHz?):** `gf180mcuD` slow-corner (`125 °C, 3.0 V`) STA + Tiny Tapeout chip-level mux & Demo Board RP2040/RP2350 practical clock ceiling sit around ~50–66 MHz. Acoustically, `50 MHz` already resolves a 40 kHz period (`25 µs`) into **1,250 discrete ticks (20 ns)**—far finer than visible bead motion.
- **Lower bound (Why not 1–10 MHz?):** An NCO accumulator has ±1 `clk` edge quantization jitter. At `50 MHz`, worst-case jitter is `±20 ns` (`±0.29°`, negligible for a high-Q 40 kHz piezo). At `2–4 MHz`, jitter inflates to `±250–500 ns` (`±3.6°–7.2°`) and throttles 2-FF synchronized SPI speed (`f_SCK ≤ f_clk / 6`).
- **Bring-up & Flexibility:** `CLK_DIV2` (`ui_in[7]`) supports `25 MHz` out of the box without SPI reconfiguration. On Day-1 silicon bring-up, clocking the TT Demo Board at `1 kHz` slows the 40 kHz carrier to `0.8 Hz` for instant visual verification on LEDs before wiring any transducers.

### 2.2 Acoustic Parameters (40 kHz in Air @ 27 °C, $c \approx 347\text{ m/s}$)
- **Wavelength:** $\lambda = 8.68\text{ mm}$
- **Standing-wave node spacing:** $\lambda / 2 = 4.34\text{ mm}$
- **Vertical phase step resolution:**
  - `PHASE_BITS = 6` (`64` steps, `5.625°/step`): **`68 µm`** per step
  - `PHASE_BITS = 7` (`128` steps, `2.8125°/step`): **`34 µm`** per step
- **Geometry — Dual-Opposing 2×8 Symmetric Concave Rings:**
  - `uo_out[7:0]` → Bottom 8-transducer concave ring (`Ch 0..7`, 45° spacing, open ~16 mm central aperture for a warm uplight LED).
  - `uio_out[7:0]` → Top 8-transducer concave ring (`Ch 8..15`, ~70–80 mm above bottom dish).
  - Symmetric 45° ring index signs (`k = i % 8`): `0: (+X,0)`, `1: (+X,+Y)`, `2: (0,+Y)`, `3: (-X,+Y)`, `4: (-X,0)`, `5: (-X,-Y)`, `6: (0,-Y)`, `7: (+X,-Y)`.
  - Effective per-channel phase (modulo $2^P$):
    $$\phi_{\text{eff}}[i] = \phi_{\text{base}}[i] + (\text{is\_top}[i]\ ?\ Z_{\text{off}} : 0) + \text{sign}_x[i]\cdot G_x + \text{sign}_y[i]\cdot G_y$$

---

## 3. Functional Requirements

| ID | Requirement | Acceptance Criteria |
| :---: | :--- | :--- |
| **FR-01** | 16 Simultaneous 40 kHz Phase-Locked Outputs | `uo_out[7:0]` and `uio_out[7:0]` (`uio_oe = 8'hFF`) drive glitch-free registered 40 kHz square waves with independent phases. |
| **FR-02** | Tunable 20-Bit Carrier NCO | 12-bit `FREQ_WORD` (default `0x347` = `839` → `40,006.6 Hz` @ 50 MHz) tunes carrier across ~30–50 kHz in ~48 Hz steps. |
| **FR-03** | Dual Clock Support (`50 MHz` / `25 MHz`) | `CLK_DIV2` (`ui_in[7]=1`) shifts NCO increment left by 1, preserving `40,006.6 Hz` at 25 MHz. |
| **FR-04** | Scalable Phase Resolution | Parameterized `PHASE_BITS` (`6` or `7`), selected empirically via parallel LibreLane `1×1` implementation runs. |
| **FR-05** | Atomic 3D Phase-Gradient Steering | `Z_OFFSET`, `GRAD_X`, `GRAD_Y` update all 16 channels atomically on the exact same clock edge with zero phase tearing. |
| **FR-06** | Per-Channel Calibration & Holography | 16 independent `CH_BASE_PHASE[0..15]` registers writable via SPI for transducer skew calibration or arbitrary phased-array holograms (2×8 arch or 4×4 planar). |
| **FR-07** | Duty-Cycle Power & Parametric AM | Programmable `DUTY_CYCLE` (`0` to `50%`) scales acoustic pressure as $\sin(\pi D)$ with `TC4428A` 24 Vpp differential drivers. `AM_MOD_IN` (`ui_in[6]`) modulates duty cycle for parametric audio / trap pulsing. |
| **FR-08** | Standalone Kinetic Art Engine (4 Modes) | When `MODE_SEL = 0`, zero SPI required: `00` Static Lock + Manual Jog (`BTN_UP`/`BTN_DOWN`), `01` Zen Breathing, `10` 3D Halo Orbit, `11` Continuous Elevator. |
| **FR-09** | Clock-Domain-Safe SPI Mode 0 Slave | When `MODE_SEL = 1`, 2-FF synchronized `SCK`/`MOSI`/`CS_N` accepts 16-bit write frames (`frame[15]=1` guard bit) up to `f_clk / 6`. |
| **FR-10** | Hardware Safety Mute | `ENABLE` (`ui_in[5] = 0`) cleanly drives all 16 outputs low within 1 clock cycle. |

---

## 4. Non-Functional & Tapeout Requirements

| ID | Constraint | Target |
| :---: | :--- | :--- |
| **NFR-01** | Die Footprint | `1×1` `gf180mcuD` tile; post-placement utilization ≤ 68% (hard ceiling ≤ 75%). |
| **NFR-02** | Timing Signoff | `0` setup and `0` hold violations across all 9 `gf180mcuD` PVT corners at `CLOCK_PERIOD = 20 ns`. |
| **NFR-03** | Physical Signoff | `0` Verilator lint warnings, `0` Yosys synth warnings, `0` Magic DRC/LVS/antenna/PDN errors. |
| **NFR-04** | Verification Parity | 100% pass on both RTL (`make sim`) and post-PnR Gate-Level (`make sim-gl`) cocotb testbenches. |
| **NFR-05** | Delivery Compatibility | Operates both as a PMOD shield on the stock Tiny Tapeout Demo Board and on a custom motherboard (TT Carrier socket + boot MCU + single USB-C PD 12V supply). |

---

## 5. Pinout Specification (`info.yaml`)

| Pin | Dir | Mode 0: Standalone Art (`ui_in[0]=0`) | Mode 1: SPI Host (`ui_in[0]=1`) |
| :--- | :---: | :--- | :--- |
| `ui_in[0]` | In | `MODE_SEL = 0` | `MODE_SEL = 1` |
| `ui_in[1]` | In | `BTN_UP` (nudge Z up / speed up) | `SPI_SCK` |
| `ui_in[2]` | In | `BTN_DOWN` (nudge Z down / slow down) | `SPI_MOSI` |
| `ui_in[3]` | In | `PAT_0` (Pattern select bit 0) | `SPI_CS_N` (active low) |
| `ui_in[4]` | In | `PAT_1` (Pattern select bit 1) | `SOFT_PWR` (`1` = 50% duty reduction / capture mode) |
| `ui_in[5]` | In | `ENABLE` (`1` = active, `0` = mute all) | `ENABLE` (`1` = active, `0` = mute all) |
| `ui_in[6]` | In | `AM_MOD_IN` (1-bit audio/pulse AM) | `AM_MOD_IN` (1-bit audio/pulse AM) |
| `ui_in[7]` | In | `CLK_DIV2` (`0` = 50 MHz, `1` = 25 MHz) | `CLK_DIV2` (`0` = 50 MHz, `1` = 25 MHz) |
| `uo_out[7:0]` | Out | **Channels 0..7** (Bottom Ring) | **Channels 0..7** (Bottom Ring) |
| `uio[7:0]` | Out (`oe=0xFF`) | **Channels 8..15** (Top Ring) | **Channels 8..15** (Top Ring) |

---

## 6. SPI Mode 0 Register Map

16-bit MSB-first frame per `CS_N` low transaction: `{wr_guard[15]=1'b1, rsvd[14:13]=2'b00, addr[12:8], data[7:0]}`.

| Addr | Name | Width | Reset | Description |
| :---: | :--- | :---: | :---: | :--- |
| `0x00..0x0F` | `CH_BASE_PHASE[0..15]` | `P` | `0` | Per-channel static calibration / hologram phase |
| `0x10` | `FREQ_WORD_LO` | 8 | `0x47` | Low byte of 12-bit NCO tuning word |
| `0x11` | `FREQ_WORD_HI` | 4 | `0x03` | High nibble (`0x347` = `839` → `40,006.6 Hz` @ 50 MHz) |
| `0x12` | `DUTY_CYCLE` | `P` | `2^(P-1)` | Global duty (`32` for P=6 / `64` for P=7 = 50% max) |
| `0x13` | `Z_OFFSET` | `P` | `0` | Atomic global Top-Ring Z phase offset |
| `0x14` | `GRAD_X` | 5 (signed) | `0` | Atomic X-axis ring phase gradient (`-16..+15`) |
| `0x15` | `GRAD_Y` | 5 (signed) | `0` | Atomic Y-axis ring phase gradient (`-16..+15`) |
| `0x16` | `CTRL_REG` | 7 | `0x05` | `[0]` SPI out en; `[2:1]` AM depth (`00`=off, `01`=25%, `10`=50%, `11`=75%); `[4:3]` Art speed; `[5]` Keep Art FSM running in SPI mode; `[6]` Top-ring 180° invert |
| `0x17` | `SOFT_RESET` | 8 | `0x00` | Write `0xA5` to restore all registers to reset defaults |

*(Note: Variant `exp/phase6-extra` extends `0x18..0x1A` with `CH_MUTE_LO`, `CH_MUTE_HI`, and `SHADOW_COMMIT` for atomic multi-channel arbitrary hologram commits.)*

---

## 7. Hardware Delivery & Physical Build Architecture (2027)

- **Single-Cable Power:** USB-C PD 12V Sink (`CH224K`) → `3.3V` buck (`TPS562201`) for ASIC/logic + clean `12V` bulk rail for drivers.
- **24 Vpp Differential Transducer Drive:** 16× `TC4428A` (SOIC-8: 1 inverting + 1 non-inverting driver per IC). One 3.3V ASIC pin drives both inputs of one `TC4428A`, applying **24 Vpp** across each 10mm 40 kHz piezo (`MA40S4S` / `TCT40-10T`) → **4× stronger acoustic trapping force** than a 12V half-bridge.
- **TT Mux Selection:** Either plug the driver PCB into the stock **TT Demo Board PMOD headers**, or socket the small **TT ASIC Carrier Board** onto a custom matte-black motherboard with a tiny underside RP2040/XIAO handling boot mux selection + optional SPI choreography.
