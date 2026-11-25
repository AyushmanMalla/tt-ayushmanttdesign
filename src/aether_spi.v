/*
 * Copyright (c) 2026 Ayushman Malla
 * SPDX-License-Identifier: Apache-2.0
 *
 * AETHER-16: 2-FF Synchronized SPI Mode 0 (CPOL=0, CPHA=0) Slave
 * 16-bit MSB-first frame: {wr_guard[15]=1'b1, rsvd[14:13], addr[12:8], data[7:0]}
 * Exports 2-FF synchronized ui_in[1]/ui_in[2] (for Mode 0 BTN_UP / BTN_DOWN) and
 * post-edge latched channel address/data (shift_reg[11:0]) for rotating-bank writes.
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

  // 2-FF synchronizers (plus 1-cycle delayed SCK for rising-edge detect)
  reg [2:0]  sck_sync;
  reg [1:0]  mosi_sync;
  reg [1:0]  cs_n_sync;

  // 15-bit shift register (16th bit is sampled directly from mosi_sync[1]);
  // flushed by 15 sck_rise shifts before bit_cnt == 15 so no reset logic needed.
  reg [14:0] shift_reg;
  reg [3:0]  bit_cnt;

  wire cs_n_gated = mode_sel ? spi_cs_n : 1'b1;
  wire active     = mode_sel && !cs_n_sync[1];
  wire sck_rise   = sck_sync[1] && !sck_sync[2];

  always @(posedge clk) begin
    if (!rst_n) begin
      sck_sync  <= 3'b000;
      mosi_sync <= 2'b00;
      cs_n_sync <= 2'b11;
      bit_cnt   <= 4'd0;
    end else begin
      sck_sync  <= {sck_sync[1:0], spi_sck};
      mosi_sync <= {mosi_sync[0], spi_mosi};
      cs_n_sync <= {cs_n_sync[0], cs_n_gated};

      if (!active) begin
        bit_cnt <= 4'd0;
      end else if (sck_rise) begin
        bit_cnt <= bit_cnt + 4'd1;
      end
    end
  end

  always @(posedge clk) begin
    if (active && sck_rise) begin
      shift_reg <= {shift_reg[13:0], mosi_sync[1]};
    end
  end

  assign sck_sync_o  = sck_sync[1];
  assign mosi_sync_o = mosi_sync[1];

  // Pulse 1-cycle wr_en on 16th rising edge of sck_sync when frame[15] (guard bit) == 1
  assign wr_en       = active && sck_rise && (bit_cnt == 4'd15) && shift_reg[14];
  assign wr_addr     = shift_reg[11:7];
  assign wr_data     = {shift_reg[6:0], mosi_sync[1]};

  // Post-edge latched channel address/data (valid immediately after 16th rising edge)
  assign lat_ch_addr = shift_reg[11:8];
  assign lat_ch_data = shift_reg[6:0];

endmodule
