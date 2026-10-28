<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

`tt_um_ayushmanmalla_top` implements a 3-bit synchronous binary counter (`0` through `7`) with an active-low synchronous reset (`rst_n`) and a combinational 7-segment display decoder. On every rising edge of `clk`:
- When `rst_n` is low (`0`), the 3-bit counter resets to `0`.
- When `rst_n` is high (`1`), the counter increments by `1` modulo 8.
- The counter value is decoded onto `uo_out[6:0]` (`SEG_A` through `SEG_G`) to drive a common-cathode 7-segment display, with `uo_out[7]` (`DP`) held low.

## How to test

Run the cocotb RTL testbench from the project root:

```sh
make sim
```

The testbench (`test/test.py`) drives a 100 kHz clock on `clk`, asserts synchronous reset (`rst_n = 0`), verifies the initial `0` digit encoding (`0x3F`), releases reset (`rst_n = 1`), and verifies all 8 states (`0`–`7`) across multiple wrap-around cycles.

## External hardware

Standard Tiny Tapeout onboard 7-segment display (`uo_out[6:0]` mapped to segments A–G, `uo_out[7]` mapped to DP).
