# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 03 Grader: 2-FF Synchronized SPI Mode 0 Slave (src/aether_spi.v)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer

CLK_PERIOD_NS = 20


async def reset_spi(dut, mode_sel=1):
    dut.rst_n.value = 0
    dut.mode_sel.value = mode_sel
    dut.spi_sck.value = 0
    dut.spi_mosi.value = 0
    dut.spi_cs_n.value = 1
    await ClockCycles(dut.clk, 4)
    await ReadOnly()
    assert int(dut.wr_en.value) == 0, "wr_en must be 0 during reset"
    assert int(dut.sck_sync_o.value) == 0, "sck_sync_o must be 0 during reset"
    assert int(dut.mosi_sync_o.value) == 0, "mosi_sync_o must be 0 during reset"
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def send_spi_frame_and_capture(dut, addr, data, guard=1, half_clks=4, deassert_cs=True):
    """Drive one 16-bit MSB-first SPI Mode 0 frame and record all (wr_en, wr_addr, wr_data) pulses."""
    frame = ((guard & 1) << 15) | ((addr & 0x1F) << 8) | (data & 0xFF)
    pulses = []

    async def step_clks(n):
        for _ in range(n):
            await RisingEdge(dut.clk)
            await ReadOnly()
            if int(dut.wr_en.value) == 1:
                pulses.append((int(dut.wr_addr.value), int(dut.wr_data.value)))
            await Timer(1, unit="ns")

    dut.spi_cs_n.value = 0
    dut.spi_sck.value = 0
    await step_clks(half_clks)

    for bit_idx in range(15, -1, -1):
        bit = (frame >> bit_idx) & 1
        dut.spi_sck.value = 0
        dut.spi_mosi.value = bit
        await step_clks(half_clks)
        dut.spi_sck.value = 1
        await step_clks(half_clks)

    dut.spi_sck.value = 0
    dut.spi_mosi.value = 0
    await step_clks(half_clks)
    if deassert_cs:
        dut.spi_cs_n.value = 1
        await step_clks(half_clks)
    return pulses


@cocotb.test()
async def test_2ff_sync_passthrough_in_mode0(dut):
    """Verify sck_sync_o and mosi_sync_o have exact 2-FF latency even when mode_sel=0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_spi(dut, mode_sel=0)

    # Toggle spi_sck=1 and spi_mosi=1 in Mode 0 (BTN_UP / BTN_DOWN reuse)
    dut.spi_sck.value = 1
    dut.spi_mosi.value = 1
    dut.spi_cs_n.value = 0

    # After 1st rising edge: first FF captures 1, output (2nd FF) is still 0
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.sck_sync_o.value) == 0, "sck_sync_o updated in 1 cycle instead of 2-FF CDC!"
    assert int(dut.mosi_sync_o.value) == 0, "mosi_sync_o updated in 1 cycle instead of 2-FF CDC!"

    # After 2nd rising edge: 2nd FF outputs 1
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.sck_sync_o.value) == 1, "sck_sync_o did not propagate after 2 clocks"
    assert int(dut.mosi_sync_o.value) == 1, "mosi_sync_o did not propagate after 2 clocks"
    assert int(dut.wr_en.value) == 0, "wr_en must remain 0 in mode_sel=0"


@cocotb.test()
async def test_valid_spi_write_frames_and_latched_channel(dut):
    """Verify 1-cycle wr_en pulse, wr_addr/wr_data decode, and post-edge lat_ch_addr/lat_ch_data."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_spi(dut, mode_sel=1)

    vectors = [
        (0x05, 0x5A),
        (0x0F, 0x7F),
        (0x10, 0x47),
        (0x16, 0xC5),
        (0x00, 0x01),
    ]
    for addr, data in vectors:
        pulses = await send_spi_frame_and_capture(dut, addr, data, guard=1)
        assert len(pulses) == 1, (
            f"Frame addr=0x{addr:02X}, data=0x{data:02X}: expected exactly 1 wr_en pulse, got {len(pulses)}"
        )
        got_addr, got_data = pulses[0]
        assert got_addr == addr, f"Expected wr_addr=0x{addr:02X}, got 0x{got_addr:02X}"
        assert got_data == data, f"Expected wr_data=0x{data:02X}, got 0x{got_data:02X}"

        # Post-edge latched channel address/data remain held in shift_reg[11:8] / [6:0]
        await ReadOnly()
        assert int(dut.lat_ch_addr.value) == (addr & 0x0F), (
            f"Expected lat_ch_addr=0x{addr & 0x0F:X}, got 0x{int(dut.lat_ch_addr.value):X}"
        )
        assert int(dut.lat_ch_data.value) == (data & 0x7F), (
            f"Expected lat_ch_data=0x{data & 0x7F:02X}, got 0x{int(dut.lat_ch_data.value):02X}"
        )
        await Timer(1, unit="ns")


@cocotb.test()
async def test_guard_bit_mode_sel_and_cs_abort(dut):
    """Verify guard=0 rejection, mode_sel=0 gating, and mid-frame CS_N deassert reset."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_spi(dut, mode_sel=1)

    # 1. Guard bit = 0 must suppress wr_en
    pulses = await send_spi_frame_and_capture(dut, 0x03, 0x33, guard=0)
    assert len(pulses) == 0, f"guard=0 frame must not assert wr_en, saw {pulses}"

    # 2. mode_sel = 0 must suppress wr_en even with valid guard=1 frame
    dut.mode_sel.value = 0
    await ClockCycles(dut.clk, 4)
    pulses = await send_spi_frame_and_capture(dut, 0x03, 0x33, guard=1)
    assert len(pulses) == 0, f"mode_sel=0 must suppress wr_en, saw {pulses}"

    # 3. Return to mode_sel=1, send a truncated 7-bit frame, abort with CS_N=1, then send a valid frame
    dut.mode_sel.value = 1
    await ClockCycles(dut.clk, 4)
    dut.spi_cs_n.value = 0
    for _ in range(7):
        dut.spi_sck.value = 0
        dut.spi_mosi.value = 1
        await ClockCycles(dut.clk, 3)
        dut.spi_sck.value = 1
        await ClockCycles(dut.clk, 3)
    dut.spi_sck.value = 0
    dut.spi_cs_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Next complete 16-bit frame must decode cleanly (bit_cnt was reset by CS_N=1)
    pulses = await send_spi_frame_and_capture(dut, 0x12, 0x40, guard=1)
    assert pulses == [(0x12, 0x40)], (
        f"After CS_N abort, expected [(0x12, 0x40)], got {pulses}"
    )


@cocotb.test()
async def test_back_to_back_frames_while_cs_low(dut):
    """Verify bit_cnt wraps cleanly for consecutive 16-bit frames with CS_N held low."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_spi(dut, mode_sel=1)

    p1 = await send_spi_frame_and_capture(dut, 0x0A, 0x2A, guard=1, deassert_cs=False)
    p2 = await send_spi_frame_and_capture(dut, 0x0B, 0x55, guard=1, deassert_cs=True)
    assert p1 == [(0x0A, 0x2A)], f"First burst frame mismatch: {p1}"
    assert p2 == [(0x0B, 0x55)], f"Second burst frame mismatch: {p2}"
