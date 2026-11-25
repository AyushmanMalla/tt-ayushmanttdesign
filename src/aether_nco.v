/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16 — Puzzle 01 Starter Skeleton: 20-bit Numerically Controlled Oscillator (NCO)
 * Brief:  puzzles/01_nco/README.md
 * Verify: make test-puzzle P=1
 * Diff:   git diff main -- src/aether_nco.v
 */

`default_nettype none

module aether_nco #(
    parameter PHASE_BITS = 7
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clk_div2,
    input  wire [11:0]           freq_word,
    output wire [PHASE_BITS-1:0] master_phase
);

  // TODO(puzzle-1): Implement the 20-bit tunable NCO phase accumulator:
  //   1. Declare `reg [19:0] phase_acc;`
  //   2. Compute 20-bit `phase_inc`:
  //        - clk_div2 == 0 -> {8'd0, freq_word}
  //        - clk_div2 == 1 -> {7'd0, freq_word, 1'b0} (2x increment for 25 MHz clock)
  //   3. On posedge clk: synchronous active-low reset (`!rst_n`) clears `phase_acc <= 20'd0`,
  //      otherwise accumulate `phase_acc <= phase_acc + phase_inc;`
  //   4. Drive `master_phase = phase_acc[19 -: PHASE_BITS];`

  // Starter stub (replace when implementing Puzzle 01):
  assign master_phase = {PHASE_BITS{1'b0}};
  wire _unused = &{clk, rst_n, clk_div2, freq_word, 1'b0};

endmodule
