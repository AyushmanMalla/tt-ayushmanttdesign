/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16: 20-bit Numerically Controlled Oscillator (NCO)
 * Default freq_word = 12'h347 (839) -> 40,006.6 Hz @ 50 MHz (and @ 25 MHz with clk_div2=1)
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

  reg [19:0] phase_acc;

  wire [19:0] phase_inc = clk_div2 ? {7'd0, freq_word, 1'b0} : {8'd0, freq_word};

  always @(posedge clk) begin
    if (!rst_n) begin
      phase_acc <= 20'd0;
    end else begin
      phase_acc <= phase_acc + phase_inc;
    end
  end

  assign master_phase = phase_acc[19 -: PHASE_BITS];

endmodule
