/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16 — Puzzle 02 Starter Skeleton: Single Glitch-Free Ultrasonic Output Channel
 * Brief:  puzzles/02_channel/README.md
 * Verify: make test-puzzle P=2
 * Diff:   git diff main -- src/aether_channel.v
 */

`default_nettype none

module aether_channel #(
    parameter PHASE_BITS = 7
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  out_en,
    input  wire [PHASE_BITS-1:0] master_phase,
    input  wire [PHASE_BITS-1:0] eff_phase,
    input  wire [PHASE_BITS-1:0] eff_duty,
    output reg                   ch_out
);

  // TODO(puzzle-2): Implement the glitch-free ultrasonic PWM channel:
  //   1. Compute modulo-2^PHASE_BITS shifted phase:
  //        `wire [PHASE_BITS-1:0] shifted = master_phase + eff_phase;`
  //   2. Exploit `eff_duty <= HALF_CYCLE (64)` to build a compact 6-bit comparator:
  //        `cmp_lt` is 1 iff `!shifted[PHASE_BITS-1]` AND
  //        (`eff_duty[PHASE_BITS-1]` OR `shifted[PHASE_BITS-2:0] < eff_duty[PHASE_BITS-2:0]`)
  //   3. Register `ch_out` on posedge clk:
  //        - if (!rst_n) ch_out <= 1'b0;
  //        - else        ch_out <= out_en && cmp_lt;

  // Starter stub (replace when implementing Puzzle 02):
  always @(posedge clk) begin
    if (!rst_n) begin
      ch_out <= 1'b0;
    end else begin
      ch_out <= 1'b0;
    end
  end

  wire _unused = &{out_en, master_phase, eff_phase, eff_duty, 1'b0};

endmodule
