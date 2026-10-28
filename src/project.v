/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_ayushmanmalla_top (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  reg [2:0] count;
  reg [6:0] seg7;

  // 3-bit synchronous counter with active-low synchronous reset
  always @(posedge clk) begin
    if (!rst_n) begin
      count <= 3'd0;
    end else begin
      count <= count + 3'd1;
    end
  end

  // 7-segment display decoder (segments G..A mapped to seg7[6:0])
  always @(*) begin
    case (count)
      3'd0:    seg7 = 7'b0111111; // 0x3F
      3'd1:    seg7 = 7'b0000110; // 0x06
      3'd2:    seg7 = 7'b1011011; // 0x5B
      3'd3:    seg7 = 7'b1001111; // 0x4F
      3'd4:    seg7 = 7'b1100110; // 0x66
      3'd5:    seg7 = 7'b1101101; // 0x6D
      3'd6:    seg7 = 7'b1111101; // 0x7D
      3'd7:    seg7 = 7'b0000111; // 0x07
      default: seg7 = 7'b0000000;
    endcase
  end

  // Dedicated outputs: uo_out[6:0] = segments A..G, uo_out[7] = decimal point (off)
  assign uo_out  = {1'b0, seg7};
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;

  // List all unused inputs to prevent warnings
  wire _unused = &{ena, ui_in, uio_in, 1'b0};

endmodule
