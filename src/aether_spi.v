/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16 — Puzzle 03 Starter Skeleton: 2-FF Synchronized SPI Mode 0 Slave
 * Brief:  puzzles/03_spi/README.md
 * Verify: make test-puzzle P=3
 * Diff:   git diff main -- src/aether_spi.v
 */

`default_nettype none

module aether_spi (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       mode_sel,
    input  wire       spi_sck,
    input  wire       spi_mosi,
    input  wire       spi_cs_n,
    output wire       sck_sync_o,
    output wire       mosi_sync_o,
    output wire       wr_en,
    output wire [4:0] wr_addr,
    output wire [7:0] wr_data,
    output wire [3:0] lat_ch_addr,
    output wire [6:0] lat_ch_data
);

  // TODO(puzzle-3): Implement the 2-FF synchronized SPI Mode 0 slave:
  //   1. 2-FF CDC synchronizers (plus 3rd FF on SCK for rising-edge detect):
  //        - `reg [2:0] sck_sync;`  (resets to 3'b000, always shifts spi_sck)
  //        - `reg [1:0] mosi_sync;` (resets to 2'b00, always shifts spi_mosi)
  //        - `reg [1:0] cs_n_sync;` (resets to 2'b11, shifts `mode_sel ? spi_cs_n : 1'b1`)
  //      Export `sck_sync_o = sck_sync[1]` and `mosi_sync_o = mosi_sync[1]` (reused for Mode 0 buttons!).
  //   2. Activity & edge detection:
  //        - `active   = mode_sel && !cs_n_sync[1]`
  //        - `sck_rise = sck_sync[1] && !sck_sync[2]`
  //   3. 4-bit `bit_cnt` (resets to 0 on `!rst_n` or `!active`, increments on `active && sck_rise`)
  //      and resetless 15-bit `shift_reg` (shifts `{shift_reg[13:0], mosi_sync[1]}` on `active && sck_rise`).
  //   4. Decode 16-bit frame `{wr_guard[15]=1, rsvd[14:13], addr[12:8], data[7:0]}`:
  //        - `wr_en       = active && sck_rise && (bit_cnt == 4'd15) && shift_reg[14]`
  //        - `wr_addr     = shift_reg[11:7]`
  //        - `wr_data     = {shift_reg[6:0], mosi_sync[1]}`
  //        - `lat_ch_addr = shift_reg[11:8]` (valid on cycles after 16th edge!)
  //        - `lat_ch_data = shift_reg[6:0]`

  // Starter stub (replace when implementing Puzzle 03):
  assign sck_sync_o  = 1'b0;
  assign mosi_sync_o = 1'b0;
  assign wr_en       = 1'b0;
  assign wr_addr     = 5'd0;
  assign wr_data     = 8'd0;
  assign lat_ch_addr = 4'd0;
  assign lat_ch_data = 7'd0;
  wire _unused = &{clk, rst_n, mode_sel, spi_sck, spi_mosi, spi_cs_n, 1'b0};

endmodule
