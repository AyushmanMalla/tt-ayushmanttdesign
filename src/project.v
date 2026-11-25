/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16: Pure-Silicon 16-Channel Ultrasonic Phased-Array Acoustic Levitator
 * Variant B (exp/phase7-hires): PHASE_BITS = 7 (128 steps = 2.8125 deg = 34 um)
 *
 * Area-optimized 2-way rotating shift-bank phase/PWM engine with atomic
 * shadow-buffered 16-channel output commit:
 *   - 2 circular 8x7-bit shift banks (Bottom Ch 0..7, Top Ch 8..15) eliminate all
 *     16-ch read muxes, 87.5% of write muxes, and 98 interior reset gates
 *   - 0.00 ns inter-channel skew (atomic 16-pin commit every 8 cycles = 160 ns @ 50 MHz,
 *     finer than 195.3 ns 7-bit phase step for full 128-step resolution)
 *   - 1-cycle hardware safety mute (ENABLE=0)
 */

`default_nettype none

module tt_um_ayushmanmalla_top (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs (Bottom Ring Ch 0..7)
    input  wire [7:0] uio_in,   // IOs: Input path (unused)
    output wire [7:0] uio_out,  // IOs: Output path (Top Ring Ch 8..15)
    output wire [7:0] uio_oe,   // IOs: Enable path (all outputs: 8'hFF)
    input  wire       ena,      // always 1 when powered
    input  wire       clk,      // 50 MHz system clock (or 25 MHz with clk_div2=1)
    input  wire       rst_n     // active-low synchronous reset
);

  localparam PHASE_BITS = 7;
  localparam GRAD_BITS  = 6;
  localparam [PHASE_BITS-1:0] HALF_CYCLE = 7'd64;

  // ---------------------------------------------------------------------------
  // Input Pin Mapping
  // ---------------------------------------------------------------------------
  wire mode_sel  = ui_in[0]; // 0 = Standalone Art, 1 = SPI Host
  wire hw_enable = ui_in[5]; // 1 = active, 0 = hardware safety mute
  wire am_mod_in = ui_in[6]; // 1-bit parametric AM / pulse modulation
  wire clk_div2  = ui_in[7]; // 0 = 50 MHz, 1 = 25 MHz

  wire spi_sck   = ui_in[1];
  wire spi_mosi  = ui_in[2];
  wire spi_cs_n  = ui_in[3];
  wire soft_pwr  = mode_sel && ui_in[4];

  // ---------------------------------------------------------------------------
  // SPI Mode 0 Slave (reuses 2-FF syncs for Mode 0 BTN_UP / BTN_DOWN)
  // ---------------------------------------------------------------------------
  wire       sck_synced;
  wire       mosi_synced;
  wire       spi_wr_en;
  wire [4:0] spi_wr_addr;
  wire [7:0] spi_wr_data;
  wire [3:0] lat_ch_addr;
  wire [6:0] lat_ch_data;

  aether_spi u_spi (
      .clk         (clk),
      .rst_n       (rst_n),
      .mode_sel    (mode_sel),
      .spi_sck     (spi_sck),
      .spi_mosi    (spi_mosi),
      .spi_cs_n    (spi_cs_n),
      .sck_sync_o  (sck_synced),
      .mosi_sync_o (mosi_synced),
      .wr_en       (spi_wr_en),
      .wr_addr     (spi_wr_addr),
      .wr_data     (spi_wr_data),
      .lat_ch_addr (lat_ch_addr),
      .lat_ch_data (lat_ch_data)
  );

  wire art_btn_up = !mode_sel && sck_synced;
  wire art_btn_dn = !mode_sel && mosi_synced;

  // ---------------------------------------------------------------------------
  // Control / Global SPI Registers (0x10..0x17) with Unified Hard/Soft Reset
  // ---------------------------------------------------------------------------
  reg [11:0]                 freq_word;
  reg [PHASE_BITS-1:0]       duty_cycle;
  reg [PHASE_BITS-1:0]       z_offset;
  reg signed [GRAD_BITS-1:0] grad_x;
  reg signed [GRAD_BITS-1:0] grad_y;
  reg [6:0]                  ctrl_reg;
  reg [1:0]                  pat_latched;

  wire spi_out_en     = ctrl_reg[0];
  wire [1:0] am_depth = ctrl_reg[2:1];
  wire [1:0] art_spd  = ctrl_reg[4:3];
  wire run_art_in_spi = ctrl_reg[5];
  wire top_invert     = ctrl_reg[6];

  wire soft_reset = spi_wr_en && (spi_wr_addr == 5'h17) && (spi_wr_data == 8'hA5);
  wire reg_rst    = (!rst_n) || soft_reset;

  always @(posedge clk) begin
    if (!rst_n) begin
      pat_latched <= 2'b00;
    end else if (!mode_sel) begin
      pat_latched <= ui_in[4:3];
    end
  end

  always @(posedge clk) begin
    if (reg_rst) begin
      freq_word  <= 12'h347;
      duty_cycle <= HALF_CYCLE;
      z_offset   <= {PHASE_BITS{1'b0}};
      grad_x     <= {GRAD_BITS{1'b0}};
      grad_y     <= {GRAD_BITS{1'b0}};
      ctrl_reg   <= 7'h05;
    end else if (spi_wr_en && spi_wr_addr[4]) begin
      case (spi_wr_addr[3:0])
        4'h0: freq_word[7:0]  <= spi_wr_data;
        4'h1: freq_word[11:8] <= spi_wr_data[3:0];
        4'h2: duty_cycle      <= spi_wr_data[PHASE_BITS-1:0];
        4'h3: z_offset        <= spi_wr_data[PHASE_BITS-1:0];
        4'h4: grad_x          <= spi_wr_data[GRAD_BITS-1:0];
        4'h5: grad_y          <= spi_wr_data[GRAD_BITS-1:0];
        4'h6: ctrl_reg        <= spi_wr_data[6:0];
        default: begin
        end
      endcase
    end
  end

  // ---------------------------------------------------------------------------
  // 2x8 Rotating Shift-Bank Channel Phase Storage (CH_BASE_PHASE[0..15])
  //   bank_bot[0..7]: Ch 0..7   | bank_top[0..7]: Ch 8..15
  //   Interior stages [0..6] are pure resetless DFF-to-DFF shift registers!
  //   Hard reset / SOFT_RESET sweeps zeros through all 8 slots while muting
  //   channel outputs so GL simulation is 100% X-free even on a 1-cycle reset.
  // ---------------------------------------------------------------------------
  reg [2:0]            slot;
  reg                  ch_wr_pend;
  reg                  ch_clr_act;
  reg [2:0]            ch_clr_cnt;

  reg [PHASE_BITS-1:0] bank_bot [0:7];
  reg [PHASE_BITS-1:0] bank_top [0:7];

  wire ch_wr_hit  = ch_wr_pend && (slot == lat_ch_addr[2:0]);
  wire ch_clr_now = reg_rst || ch_clr_act;
  wire wr_bot     = ch_wr_hit && !lat_ch_addr[3];
  wire wr_top     = ch_wr_hit &&  lat_ch_addr[3];

  always @(posedge clk) begin
    if (reg_rst) begin
      ch_wr_pend <= 1'b0;
      ch_clr_act <= 1'b1;
      ch_clr_cnt <= 3'd7;
    end else begin
      if (spi_wr_en && !spi_wr_addr[4]) begin
        ch_wr_pend <= 1'b1;
      end else if (ch_wr_hit) begin
        ch_wr_pend <= 1'b0;
      end

      if (ch_clr_act) begin
        if (ch_clr_cnt == 3'd0) begin
          ch_clr_act <= 1'b0;
        end else begin
          ch_clr_cnt <= ch_clr_cnt - 3'd1;
        end
      end
    end
  end

  // Pure DFF-to-DFF rotation for [0..6]; tail [7] handles clear/write/recirculate
  integer s;
  always @(posedge clk) begin
    for (s = 0; s < 7; s = s + 1) begin
      bank_bot[s] <= bank_bot[s + 1];
      bank_top[s] <= bank_top[s + 1];
    end
    bank_bot[7] <= ch_clr_now ? {PHASE_BITS{1'b0}} : (wr_bot ? lat_ch_data : bank_bot[0]);
    bank_top[7] <= ch_clr_now ? {PHASE_BITS{1'b0}} : (wr_top ? lat_ch_data : bank_top[0]);
  end

  // ---------------------------------------------------------------------------
  // 20-Bit Carrier NCO
  // ---------------------------------------------------------------------------
  wire [PHASE_BITS-1:0] master_phase;

  aether_nco #(
      .PHASE_BITS(PHASE_BITS)
  ) u_nco (
      .clk          (clk),
      .rst_n        (rst_n),
      .clk_div2     (clk_div2),
      .freq_word    (freq_word),
      .master_phase (master_phase)
  );

  // ---------------------------------------------------------------------------
  // Standalone Kinetic Art Engine
  // ---------------------------------------------------------------------------
  wire                        use_art = (!mode_sel) || run_art_in_spi;
  wire [1:0]                  eff_pat = mode_sel ? pat_latched : ui_in[4:3];
  wire [PHASE_BITS-1:0]       art_z;
  wire signed [GRAD_BITS-1:0] art_gx;
  wire signed [GRAD_BITS-1:0] art_gy;

  aether_art_fsm #(
      .PHASE_BITS(PHASE_BITS),
      .GRAD_BITS (GRAD_BITS)
  ) u_art_fsm (
      .clk       (clk),
      .rst_n     (rst_n),
      .art_en    (use_art),
      .pat_sel   (eff_pat),
      .art_speed (art_spd),
      .btn_up    (art_btn_up),
      .btn_down  (art_btn_dn),
      .art_z     (art_z),
      .art_gx    (art_gx),
      .art_gy    (art_gy)
  );

  // ---------------------------------------------------------------------------
  // Global Duty-Cycle Clamping, SOFT_PWR Reduction & Parametric AM
  // ---------------------------------------------------------------------------
  wire [PHASE_BITS-1:0] duty_clamped = (duty_cycle[PHASE_BITS-1] && (|duty_cycle[PHASE_BITS-2:0]))
                                       ? HALF_CYCLE : duty_cycle;
  wire [PHASE_BITS-1:0] duty_soft    = soft_pwr ? {1'b0, duty_clamped[PHASE_BITS-1:1]} : duty_clamped;

  reg [PHASE_BITS-1:0] eff_duty;
  always @(*) begin
    if (!am_mod_in) begin
      eff_duty = duty_soft;
    end else begin
      case (am_depth)
        2'b00:   eff_duty = duty_soft;                                      // 0% AM (off)
        2'b01:   eff_duty = duty_soft - {2'b00, duty_soft[PHASE_BITS-1:2]}; // 25% AM
        2'b10:   eff_duty = {1'b0, duty_soft[PHASE_BITS-1:1]};              // 50% AM
        2'b11:   eff_duty = {2'b00, duty_soft[PHASE_BITS-1:2]};             // 75% AM
        default: eff_duty = duty_soft;
      endcase
    end
  end

  wire out_en     = hw_enable && (mode_sel ? spi_out_en : 1'b1);
  wire eval_en    = out_en && !ch_clr_act;

  // ---------------------------------------------------------------------------
  // 2-Way Shadow-Buffered Symmetric 8-Ring Evaluator (1 Bot + 1 Top / cycle)
  //   slot[2:0] = k (0..7):
  //     k=0: +Gx      | k=1: +Gx+Gy | k=2: +Gy | k=3: -Gx+Gy
  //     k=4: -Gx      | k=5: -Gx-Gy | k=6: -Gy | k=7: +Gx-Gy
  // ---------------------------------------------------------------------------
  reg [PHASE_BITS-1:0] phase_snap;

  wire [PHASE_BITS-1:0]       active_z  = use_art ? art_z  : z_offset;
  wire signed [GRAD_BITS-1:0] active_gx = use_art ? art_gx : grad_x;
  wire signed [GRAD_BITS-1:0] active_gy = use_art ? art_gy : grad_y;

  wire [PHASE_BITS-1:0] gx7   = {active_gx[GRAD_BITS-1], active_gx};
  wire [PHASE_BITS-1:0] gy7   = {active_gy[GRAD_BITS-1], active_gy};
  wire [PHASE_BITS-1:0] ga_a  = (slot[1:0] == 2'd0) ? {PHASE_BITS{1'b0}} : gy7;
  wire [PHASE_BITS-1:0] ga_b  = (slot[1:0] == 2'd2) ? {PHASE_BITS{1'b0}} : gx7;
  wire [PHASE_BITS-1:0] g_mag = (slot[1:0] == 2'd3) ? (ga_a - ga_b) : (ga_a + ga_b);

  wire [PHASE_BITS-1:0] top_z      = {active_z[PHASE_BITS-1] ^ top_invert, active_z[PHASE_BITS-2:0]};
  wire [PHASE_BITS-1:0] eval_phase = (slot == 3'd0) ? master_phase : phase_snap;
  wire [PHASE_BITS-1:0] p_bot      = slot[2] ? (eval_phase - g_mag) : (eval_phase + g_mag);
  wire [PHASE_BITS-1:0] p_top      = p_bot + top_z;

  wire ch_bot_q;
  wire ch_top_q;

  aether_channel #(.PHASE_BITS(PHASE_BITS)) u_ch_bot (
      .clk          (clk),
      .rst_n        (rst_n),
      .out_en       (eval_en),
      .master_phase (p_bot),
      .eff_phase    (bank_bot[0]),
      .eff_duty     (eff_duty),
      .ch_out       (ch_bot_q)
  );

  aether_channel #(.PHASE_BITS(PHASE_BITS)) u_ch_top (
      .clk          (clk),
      .rst_n        (rst_n),
      .out_en       (eval_en),
      .master_phase (p_top),
      .eff_phase    (bank_top[0]),
      .eff_duty     (eff_duty),
      .ch_out       (ch_top_q)
  );

  // Pure shift shadow registers (no reset needed; flushed with 0s during ch_clr_act)
  reg [6:0] sh_bot; // Ch 0..6
  reg [6:0] sh_top; // Ch 8..14
  reg [7:0] uo_out_reg;
  reg [7:0] uio_out_reg;

  always @(posedge clk) begin
    sh_bot <= {ch_bot_q, sh_bot[6:1]};
    sh_top <= {ch_top_q, sh_top[6:1]};
    if (slot == 3'd0) begin
      phase_snap <= master_phase;
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      slot        <= 3'd0;
      uo_out_reg  <= 8'h00;
      uio_out_reg <= 8'h00;
    end else begin
      slot <= slot + 3'd1;

      if (!eval_en) begin
        uo_out_reg  <= 8'h00;
        uio_out_reg <= 8'h00;
      end else if (slot == 3'd0) begin
        // slot == 0: ch_*_q holds k=7 (Ch 7, 15); sh_* holds k=6..0 -> atomic 16-ch commit
        uo_out_reg  <= {ch_bot_q, sh_bot};
        uio_out_reg <= {ch_top_q, sh_top};
      end
    end
  end

  assign uo_out  = uo_out_reg;
  assign uio_out = uio_out_reg;
  assign uio_oe  = 8'hFF;

  // Tie off unused inputs to prevent lint warnings
  wire _unused = &{ena, uio_in, 1'b0};

endmodule
