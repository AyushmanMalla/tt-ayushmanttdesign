/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16: Standalone Kinetic Art Engine (4 Modes, Parameterized PHASE_BITS=7)
 *   2'b00: Static Lock + Manual Jog (btn_up / btn_down)
 *   2'b01: Zen Breathing (triangle wave on art_z: 0 .. 2^(PHASE_BITS-2))
 *   2'b10: 3D Halo Orbit (4-quadrant phase-shifted triangle waves on art_gx/art_gy, +-12)
 *   2'b11: Continuous Elevator (modulo 2^PHASE_BITS ramp on art_z)
 *
 * Shares one 7-bit state register & adder across all 4 patterns for compact area.
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

  localparam [PHASE_BITS-1:0] BREATH_PEAK = ({{(PHASE_BITS-1){1'b0}}, 1'b1} << (PHASE_BITS - 2));

  reg [20:0]           prescaler;
  reg                  tap_sel;
  reg                  tap_prev;
  reg [PHASE_BITS-1:0] st;

  // Prescaler speed tap selection
  always @(*) begin
    case (art_speed)
      2'b00:   tap_sel = prescaler[20]; // ~42 ms/step @ 50 MHz
      2'b01:   tap_sel = prescaler[19]; // ~21 ms/step @ 50 MHz
      2'b10:   tap_sel = prescaler[17]; // ~5.2 ms/step @ 50 MHz
      2'b11:   tap_sel = prescaler[6];  // ~2.56 us/step (fast sim / bring-up)
      default: tap_sel = prescaler[20];
    endcase
  end

  wire step_tick = art_en && tap_sel && !tap_prev;
  wire is_orb    = (pat_sel == 2'b10);
  wire z_dec     = (pat_sel == 2'b00) && btn_down && !btn_up;
  wire st_adv    = is_orb || (pat_sel == 2'b01) || (pat_sel == 2'b11) ||
                   ((pat_sel == 2'b00) && (btn_up ^ btn_down));

  // Single shared 7-bit adder: +1 normal, -1 jog down, +5 wraps orbit step 11 -> next quadrant 0
  wire orb_wrap = is_orb && (st[3:0] == 4'd11);
  wire [PHASE_BITS-1:0] st_delta = z_dec    ? {PHASE_BITS{1'b1}} :
                                   orb_wrap ? {{(PHASE_BITS-3){1'b0}}, 3'd5} :
                                              {{(PHASE_BITS-1){1'b0}}, 1'b1};

  always @(posedge clk) begin
    if (!rst_n) begin
      prescaler <= 21'd0;
      tap_prev  <= 1'b0;
      st        <= {PHASE_BITS{1'b0}};
    end else begin
      prescaler <= prescaler + 21'd1;
      tap_prev  <= tap_sel;
      if (step_tick && st_adv) begin
        st <= st + st_delta;
      end
    end
  end

  // Triangle wave for Zen Breathing: 0 .. BREATH_PEAK .. 1 .. 0
  wire [PHASE_BITS-1:0] breath_sub = {2'b00, st[PHASE_BITS-3:0]};
  wire [PHASE_BITS-1:0] breath_val = st[PHASE_BITS-2] ? (BREATH_PEAK - breath_sub) : breath_sub;

  always @(*) begin
    case (pat_sel)
      2'b00:   art_z = st;
      2'b01:   art_z = breath_val;
      2'b11:   art_z = st;
      default: art_z = {PHASE_BITS{1'b0}};
    endcase
  end

  // Compact 4-quadrant phase-shifted triangle waves for 3D Halo Orbit (+-12, 5-bit signed -> 6-bit)
  wire       s_ovf   = st[3] && st[2]; // 1 iff st[3:0] in 12..15
  wire [3:0] orbit_s = s_ovf ? 4'd0 : st[3:0];
  wire [1:0] orbit_q = st[5:4];
  wire [3:0] inv_s   = 4'd12 - orbit_s;
  wire [3:0] mag_x   = orbit_q[0] ? orbit_s : inv_s;
  wire [3:0] mag_y   = orbit_q[0] ? inv_s   : orbit_s;
  wire       neg_x   = orbit_q[0] ^ orbit_q[1];
  wire       neg_y   = orbit_q[1];

  wire [4:0] orb_gx5 = neg_x ? -{1'b0, mag_x} : {1'b0, mag_x};
  wire [4:0] orb_gy5 = neg_y ? -{1'b0, mag_y} : {1'b0, mag_y};

  assign art_gx = is_orb ? {orb_gx5[4], orb_gx5} : {GRAD_BITS{1'b0}};
  assign art_gy = is_orb ? {orb_gy5[4], orb_gy5} : {GRAD_BITS{1'b0}};

endmodule
