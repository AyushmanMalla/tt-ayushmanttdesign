# Puzzle 03 — 2-FF Synchronized SPI Mode 0 Slave (`src/aether_spi.v`)

**Target File:** `src/aether_spi.v`  
**Verify Command:** `make test-puzzle P=3`

---

## Learning Objectives

- Implement a **2-FF Clock-Domain Crossing (CDC)** synchronizer chain for asynchronous external SPI inputs (`SCK`, `MOSI`, `CS_N`).
- Detect rising edges cleanly in the 50 MHz domain using a 3rd flip-flop (`sck_sync[1] && !sck_sync[2]`).
- Build an area-minimal **15-bit shift register** that decodes 16-bit MSB-first SPI Mode 0 frames with a hardware write-guard bit and post-edge channel latching.
- Reuse the SPI CDC flops as Mode 0 button synchronizers (`sck_sync_o`, `mosi_sync_o`) at zero extra silicon cost.

---

## Port Contract & Behavioral Spec

Module: `aether_spi`

| Port | Dir | Width | Description |
| :--- | :---: | :---: | :--- |
| `clk` | in | 1 | 50 MHz system clock |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `mode_sel` | in | 1 | `1` = SPI Host Mode; `0` = Standalone Art Mode (gates SPI inactive) |
| `spi_sck` | in | 1 | External SPI clock (or `BTN_UP` in Mode 0) |
| `spi_mosi` | in | 1 | External SPI MOSI (or `BTN_DOWN` in Mode 0) |
| `spi_cs_n` | in | 1 | Active-low SPI chip select |
| `sck_sync_o` | out | 1 | 2-FF synchronized `spi_sck` (`sck_sync[1]`) — reused for `BTN_UP` |
| `mosi_sync_o` | out | 1 | 2-FF synchronized `spi_mosi` (`mosi_sync[1]`) — reused for `BTN_DOWN` |
| `wr_en` | out | 1 | 1-cycle write strobe on the 16th rising `sck_sync` edge when guard bit == `1` |
| `wr_addr` | out | 5 | 5-bit register address (`frame[12:8]`) valid during `wr_en` |
| `wr_data` | out | 8 | 8-bit register data (`frame[7:0]`) valid during `wr_en` |
| `lat_ch_addr` | out | 4 | Post-edge latched channel index (`frame[11:8]`) valid after 16th edge |
| `lat_ch_data` | out | 7 | Post-edge latched 7-bit phase (`frame[6:0]`) valid after 16th edge |

### 16-Bit SPI Mode 0 Frame Format (MSB-First, CPOL=0, CPHA=0)

```
Bit:   15         14:13     12:8        7:0
     +----------+--------+-----------+-----------+
     | wr_guard |  rsvd  | addr[4:0] | data[7:0] |
     +----------+--------+-----------+-----------+
       must = 1   ignore   0x00..0x17  payload
```

### Behavioral Requirements
1. **2-FF Synchronizers (Always Running):**
   - `sck_sync[2:0]`: resets to `3'b000`, shifts `{sck_sync[1:0], spi_sck}` every clock.
   - `mosi_sync[1:0]`: resets to `2'b00`, shifts `{mosi_sync[0], spi_mosi}` every clock.
   - `cs_n_sync[1:0]`: resets to `2'b11`, shifts `{cs_n_sync[0], cs_n_gated}` every clock, where `cs_n_gated = mode_sel ? spi_cs_n : 1'b1`.
   - Always export `sck_sync_o = sck_sync[1]` and `mosi_sync_o = mosi_sync[1]` (even when `mode_sel == 0`, so Mode 0 buttons stay synchronized!).
2. **Activity & Edge Detection:**
   - `active = mode_sel && !cs_n_sync[1]`
   - `sck_rise = sck_sync[1] && !sck_sync[2]`
3. **Bit Counter & 15-Bit Shift Register:**
   - `bit_cnt[3:0]`: resets to `0` on `!rst_n` or `!active`; increments by `1` on `active && sck_rise` (wraps 15 → 0 cleanly for back-to-back frames).
   - `shift_reg[14:0]`: on `active && sck_rise`, shifts `{shift_reg[13:0], mosi_sync[1]}` *(no reset needed because 15 valid shifts flush it before `bit_cnt == 15`!)*.
4. **Write Strobe & Post-Edge Latch Outputs:**
   - On the 16th rising edge (`active && sck_rise && bit_cnt == 4'd15`):
     - `shift_reg` currently holds bits `[15:1]` of the frame, and `mosi_sync[1]` holds bit `[0]`!
     - Therefore:
       - `wr_en = active && sck_rise && (bit_cnt == 4'd15) && shift_reg[14]` (guard bit is `shift_reg[14]`)
       - `wr_addr = shift_reg[11:7]` (frame bits `[12:8]`)
       - `wr_data = {shift_reg[6:0], mosi_sync[1]}` (frame bits `[7:0]`)
   - Immediately **after** that clock edge, `shift_reg` has shifted left by 1, so it holds frame bits `[14:0]`!
     - `lat_ch_addr = shift_reg[11:8]` (channel address `frame[11:8]`, i.e., `0..15`)
     - `lat_ch_data = shift_reg[6:0]` (7-bit phase `frame[6:0]`)

---

## Math & Hardware Intuition

### Why Never Clock Flip-Flops Directly on `spi_sck`?
Using an external pin (`spi_sck`) as a clock inside a Tiny Tapeout ASIC creates a second asynchronous clock tree, breaks single-clock Static Timing Analysis (STA), and risks hold violations. Oversampling `spi_sck` at 50 MHz through a 2-FF synchronizer supports SPI clocks up to ~5–8 MHz with **one single clock domain** and zero CDC metastability!

### Why a 15-Bit Shift Register + `lat_ch_addr` / `lat_ch_data`?
1. Saving 1 resetless flip-flop (`15` bits instead of `16`) directly saves `63.66 µm²` in `gf180mcuD` because the 16th bit (`mosi_sync[1]`) is already sitting in a flip-flop on the 16th edge!
2. In Puzzle 05, channel phase writes (`0x00..0x0F`) target a **rotating 8-slot shift bank**, which may take up to 8 cycles to rotate the target slot to the head. Because `shift_reg` naturally holds `frame[14:0]` right after the 16th `sck_rise` (until the next SPI bit arrives many cycles later), `lat_ch_addr` and `lat_ch_data` give us a **free 11-bit write buffer** with zero extra flip-flops!

---

## Hints & Common Pitfalls

<details>
<summary>Hint 1: Bit alignment before vs after the 16th `sck_rise`</summary>

Before the 16th `sck_rise` (`bit_cnt == 15`), `shift_reg[14:0]` contains `frame[15:1]`:
- `shift_reg[14]` = `frame[15]` (guard bit)
- `shift_reg[11:7]` = `frame[12:8]` (`wr_addr`)
- `shift_reg[6:0]` = `frame[7:1]`, combined with `mosi_sync[1]` = `frame[0]` gives `wr_data`

After that `posedge clk` finishes shifting `mosi_sync[1]` in, `shift_reg[14:0]` contains `frame[14:0]`:
- `shift_reg[11:8]` = `frame[11:8]` (`lat_ch_addr`)
- `shift_reg[6:0]` = `frame[6:0]` (`lat_ch_data`)
</details>

<details>
<summary>Common Pitfall: Gating `sck_sync` / `mosi_sync` on `mode_sel`</summary>

Do **not** gate `spi_sck` or `spi_mosi` with `mode_sel`! Only gate `spi_cs_n` (`cs_n_gated = mode_sel ? spi_cs_n : 1'b1`). In Mode 0 (`mode_sel = 0`), `ui_in[1]` and `ui_in[2]` are the `BTN_UP` and `BTN_DOWN` manual jog buttons, which rely on `sck_sync_o` and `mosi_sync_o` continuing to update every clock.
</details>

---

## Verify Your Solution

```bash
make test-puzzle P=3
```

Stuck? Compare against the tapeout reference:
```bash
git diff main -- src/aether_spi.v
```
