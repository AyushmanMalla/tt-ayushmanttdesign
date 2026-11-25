/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16 — Puzzles 05 & 06 Starter Skeleton: Top-Level 16-Channel Acoustic Levitator SoC
 *   Part A (Puzzle 05): puzzles/05_shift_bank_and_3d/README.md    -> make test-puzzle P=5
 *   Part B (Puzzle 06): puzzles/06_full_soc_integration/README.md -> make test-puzzle P=6
 *   Signoff (Puzzle 07): puzzles/07_physical_signoff/README.md    -> make test-puzzle P=7
 *   Diff vs tapeout:    git diff main -- src/project.v
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

  // ===========================================================================
  // TODO(puzzle-6): Registered Input Pin Mapping (breaks 4 ns external delay)
  //   Register ui_in[0] (mode_sel_r), ui_in[4] (ui4_r), ui_in[5] (hw_enable_r),
  //   ui_in[6] (am_mod_r), ui_in[7] (clk_div2_r). Derive `soft_pwr = mode_sel && ui4_r`.
  //   Route ui_in[1..3] (spi_sck, spi_mosi, spi_cs_n) straight to u_spi.
  // ===========================================================================

  // ===========================================================================
  // TODO(puzzle-5): Instantiate `aether_spi` (u_spi) and SPI Global Registers
  //   Registers 0x10..0x16: freq_word (default 12'h347), duty_cycle (HALF_CYCLE),
  //   z_offset (0), grad_x (0), grad_y (0), ctrl_reg (8'h05).
  //   TODO(puzzle-6): Add `soft_reset` (addr 5'h17, data 8'hA5), `reg_rst`,
  //   and `pat_latched` (latches `{ui4_r, ui_in[3]}` while `!mode_sel`).
  // ===========================================================================

  // ===========================================================================
  // TODO(puzzle-5): Packed 2x8 Rotating Shift Banks (`bank_bot`, `bank_top`)
  //   - `reg [8*PHASE_BITS-1:0] bank_bot, bank_top;` (pure resetless DFF-to-DFF shift!)
  //   - `slot[2:0]` counter (0..7), `ch_wr_pend` write-on-slot-match using `lat_ch_addr/data`
  //   - 8-cycle X-free reset scrubber (`ch_clr_act`, `ch_clr_cnt = 3'd7..0`) on `reg_rst`
  // ===========================================================================

  // ===========================================================================
  // TODO(puzzle-5): Instantiate `aether_nco` (u_nco)
  // TODO(puzzle-6): Instantiate `aether_art_fsm` (u_art_fsm) & `use_art` mux
  // ===========================================================================

  // ===========================================================================
  // TODO(puzzle-6): Duty-Cycle Clamping (<= 64), SOFT_PWR (>> 1),
  //   4-Level Parametric AM (`am_depth` = ctrl_reg[2:1]), and `out_en` / `eval_en`
  // ===========================================================================

  // ===========================================================================
  // TODO(puzzle-5): 2-Way Pipelined Lookahead 8-Ring Evaluator & Atomic Commit
  //   - Precompute 45-deg ring gradient + Hardware Acoustic Vortex (`k*16` when `ctrl_reg[7]`)
  //     for `slot_next = slot + 3'd1` and register into `g_signed_r` every cycle.
  //   - At `slot == 3'd7`, snapshot `bot_snap <= master_phase`,
  //     `top_snap <= master_phase + top_z` (applying `top_invert = ctrl_reg[6]`),
  //     and `eff_duty_r <= eff_duty`.
  //   - Instantiate `u_ch_bot` & `u_ch_top` (`aether_channel`).
  //   - Shift `ch_bot_q` / `ch_top_q` into `sh_bot[6:0]` / `sh_top[6:0]`, and commit all
  //     16 channels atomically (`uo_out_reg`, `uio_out_reg`) when `slot == 3'd0`
  //     (or clear to 8'h00 immediately whenever `!eval_en`).
  // ===========================================================================

  // Starter stub (replace when implementing Puzzles 05 & 06):
  assign uo_out  = 8'h00;
  assign uio_out = 8'h00;
  assign uio_oe  = 8'hFF;

  // Tie off unused inputs/params to prevent lint warnings in starter skeleton
  wire [GRAD_BITS-1:0] _unused_grad = {GRAD_BITS{1'b0}};
  wire _unused = &{ena, clk, rst_n, ui_in, uio_in, HALF_CYCLE, _unused_grad, 1'b0};

endmodule
