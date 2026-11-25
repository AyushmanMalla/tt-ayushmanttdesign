/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16: Single Glitch-Free Ultrasonic Output Channel (PHASE_BITS = 7)
 * Exploits eff_duty <= HALF_CYCLE (64) to simplify comparator to 6 bits.
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

  wire [PHASE_BITS-1:0] shifted = master_phase + eff_phase;
  wire cmp_lt = (!shifted[PHASE_BITS-1]) &&
                (eff_duty[PHASE_BITS-1] || (shifted[PHASE_BITS-2:0] < eff_duty[PHASE_BITS-2:0]));

  always @(posedge clk) begin
    if (!rst_n) begin
      ch_out <= 1'b0;
    end else begin
      ch_out <= out_en && cmp_lt;
    end
  end

endmodule
