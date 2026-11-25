/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16 — Puzzle 04 Starter Skeleton: Standalone Kinetic Art Engine (4 Modes)
 * Brief:  puzzles/04_art_fsm/README.md
 * Verify: make test-puzzle P=4
 * Diff:   git diff main -- src/aether_art_fsm.v
 */

`default_nettype none

module aether_art_fsm #(
    parameter PHASE_BITS = 7,
    parameter GRAD_BITS  = 6
) (
    input  wire                        clk,
    input  wire                        rst_n,
    input  wire                        art_en,
    input  wire [1:0]                  pat_sel,
    input  wire [1:0]                  art_speed,
    input  wire                        btn_up,
    input  wire                        btn_down,
    output reg  [PHASE_BITS-1:0]       art_z,
    output wire signed [GRAD_BITS-1:0] art_gx,
    output wire signed [GRAD_BITS-1:0] art_gy
);

  // TODO(puzzle-4): Implement the compact 4-mode Standalone Kinetic Art Engine:
  //   1. 21-bit `prescaler` with 4 speed taps (`art_speed`):
  //        2'b00 -> prescaler[20] (~42 ms @ 50 MHz)
  //        2'b01 -> prescaler[19] (~21 ms)
  //        2'b10 -> prescaler[17] (~5.2 ms)
  //        2'b11 -> prescaler[6]  (2.56 us — fast simulation!)
  //      Generate rising-edge `step_tick = art_en && tap_sel && !tap_prev;`.
  //   2. Single shared 7-bit state register `st` & shared adder (`st_delta`):
  //        - Mode 00 (Static + Jog): advance only on `btn_up ^ btn_down` (+1 up, -1 down)
  //        - Mode 01 (Zen Breathing): +1 each tick; map `st` to triangle 0..32..1..0 on `art_z`
  //        - Mode 10 (3D Halo Orbit): +1 normally, +5 when `st[3:0] == 4'd11` (wraps to next quadrant!)
  //          Clamp `s_ovf = st[3] && st[2]` so `orbit_s = s_ovf ? 4'd0 : st[3:0]`, and generate
  //          4-quadrant phase-shifted triangle waves (+-12) on `art_gx` / `art_gy`, with `art_z = 0`.
  //        - Mode 11 (Continuous Elevator): +1 each tick; `art_z = st` (modulo-128 ramp).

  // Starter stub (replace when implementing Puzzle 04):
  always @(*) begin
    case (pat_sel)
      default: art_z = {PHASE_BITS{1'b0}};
    endcase
  end
  assign art_gx = {GRAD_BITS{1'b0}};
  assign art_gy = {GRAD_BITS{1'b0}};
  wire _unused = &{clk, rst_n, art_en, art_speed, btn_up, btn_down, 1'b0};

endmodule
