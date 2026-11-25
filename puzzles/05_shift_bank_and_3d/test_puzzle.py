# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 05 Grader: 2x8 Rotating Shift-Bank TDM, X-Free Scrubber, 3D Ring Pipeline & Vortex

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

CLK_PERIOD_NS = 20  # 50 MHz
PHASE_STEPS = 128

REG_CH_BASE = 0x00
REG_FREQ_LO = 0x10
REG_FREQ_HI = 0x11
REG_Z_OFFSET = 0x13
REG_GRAD_X = 0x14
REG_GRAD_Y = 0x15
REG_CTRL = 0x16


def ui_mode1(sck=0, mosi=0, cs_n=1, soft_pwr=0, enable=1, am_mod=0, clk_div2=0):
    return (
        ((clk_div2 & 1) << 7)
        | ((am_mod & 1) << 6)
        | ((enable & 1) << 5)
        | ((soft_pwr & 1) << 4)
        | ((cs_n & 1) << 3)
        | ((mosi & 1) << 2)
        | ((sck & 1) << 1)
        | 1
    )


def read_all_ch(dut):
    return (int(dut.uio_out.value) << 8) | int(dut.uo_out.value)


async def reset_dut(dut, reset_clks=5):
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = ui_mode1(enable=1)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, reset_clks)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def spi_write(dut, addr, data, guard=1, half_clks=4):
    frame = ((guard & 1) << 15) | ((addr & 0x1F) << 8) | (data & 0xFF)
    dut.ui_in.value = ui_mode1(sck=0, mosi=0, cs_n=0, enable=1)
    await ClockCycles(dut.clk, half_clks)
    for bit_idx in range(15, -1, -1):
        bit = (frame >> bit_idx) & 1
        dut.ui_in.value = ui_mode1(sck=0, mosi=bit, cs_n=0, enable=1)
        await ClockCycles(dut.clk, half_clks)
        dut.ui_in.value = ui_mode1(sck=1, mosi=bit, cs_n=0, enable=1)
        await ClockCycles(dut.clk, half_clks)
    dut.ui_in.value = ui_mode1(sck=0, mosi=0, cs_n=0, enable=1)
    await ClockCycles(dut.clk, half_clks)
    dut.ui_in.value = ui_mode1(sck=0, mosi=0, cs_n=1, enable=1)
    await ClockCycles(dut.clk, half_clks)


async def capture_channels(dut, num_cycles):
    rising_edges = [[] for _ in range(16)]
    high_counts = [0] * 16
    await RisingEdge(dut.clk)
    prev = read_all_ch(dut)
    for t in range(num_cycles):
        await RisingEdge(dut.clk)
        curr = read_all_ch(dut)
        rises = curr & (~prev)
        for ch in range(16):
            if (curr >> ch) & 1:
                high_counts[ch] += 1
            if (rises >> ch) & 1:
                rising_edges[ch].append(t)
        prev = curr
    return rising_edges, high_counts


def circular_phase_diff(ref_edge, ch_edge, period):
    delta_clks = (ref_edge - ch_edge) % period
    return (delta_clks * PHASE_STEPS) / period


def circular_step_err(measured, expected):
    diff = (measured - expected) % PHASE_STEPS
    if diff > PHASE_STEPS / 2:
        diff -= PHASE_STEPS
    return abs(diff)


@cocotb.test()
async def test_1cycle_reset_scrubber_and_default_carrier(dut):
    """Verify 1-cycle reset scrubs all 16 shift-bank slots X-free & aligns all 16 channels at 40 kHz."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    # Only 1 clock of reset -> forces the 8-cycle shift-bank scrubber to prove itself!
    await reset_dut(dut, reset_clks=1)

    assert int(dut.uio_oe.value) == 0xFF, f"Expected uio_oe=0xFF, got 0x{int(dut.uio_oe.value):02X}"

    edges, highs = await capture_channels(dut, 2600)
    for ch in range(16):
        assert len(edges[ch]) >= 2, f"Ch {ch} had fewer than 2 rising edges"
        period = edges[ch][1] - edges[ch][0]
        assert 1248 <= period <= 1256, f"Ch {ch} default carrier period {period} != ~1250 (40 kHz)"
        assert edges[ch][0] == edges[0][0], (
            f"Ch {ch} skewed vs Ch 0 ({edges[ch][0]} vs {edges[0][0]}) — check atomic shadow commit!"
        )
        duty_ratio = highs[ch] / 2600.0
        assert 0.47 <= duty_ratio <= 0.53, f"Ch {ch} default duty {duty_ratio:.3f} != 0.50"


@cocotb.test()
async def test_rotating_shift_bank_all_16_channels(dut):
    """Verify 2x8 rotating shift banks store and read back 16 distinct 7-bit phases cleanly."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    target_phases = [0, 1, 2, 15, 31, 32, 47, 63, 64, 65, 79, 95, 96, 111, 126, 127]
    for ch, ph in enumerate(target_phases):
        await spi_write(dut, REG_CH_BASE + ch, ph)

    edges, _ = await capture_channels(dut, 2600)
    period = edges[0][1] - edges[0][0]
    ref_edge = edges[0][1]

    for ch, expected_step in enumerate(target_phases):
        measured_step = circular_phase_diff(ref_edge, edges[ch][0], period)
        err = circular_step_err(measured_step, expected_step)
        assert err <= 0.55, (
            f"Shift bank Ch {ch}: expected step {expected_step}, got {measured_step:.2f} (err={err:.2f})"
        )


@cocotb.test()
async def test_lookahead_3d_ring_z_top_invert_and_grad_xy(dut):
    """Verify Z_OFFSET, top_invert (180 deg), and 45-deg 8-ring GRAD_X/GRAD_Y lookahead pipeline."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    # Exact 1024-clock period = exact 8 clocks per 7-bit step
    await spi_write(dut, REG_FREQ_LO, 0x00)
    await spi_write(dut, REG_FREQ_HI, 0x04)

    # 1. Z_OFFSET = 20 -> top ring leads bottom ring by 20 steps
    await spi_write(dut, REG_Z_OFFSET, 20)
    await ClockCycles(dut.clk, 16)
    edges, _ = await capture_channels(dut, 2100)
    ref = edges[0][1]
    for k in range(8):
        assert circular_step_err(circular_phase_diff(ref, edges[k][0], 1024), 0) <= 0.5
        assert circular_step_err(circular_phase_diff(ref, edges[k + 8][0], 1024), 20) <= 0.5

    # 2. top_invert (CTRL_REG[6]=1) -> top ring = 20 + 64 = 84 steps
    await spi_write(dut, REG_CTRL, 0x45)
    await ClockCycles(dut.clk, 16)
    edges, _ = await capture_channels(dut, 2100)
    ref = edges[0][1]
    for k in range(8):
        assert circular_step_err(circular_phase_diff(ref, edges[k][0], 1024), 0) <= 0.5
        assert circular_step_err(circular_phase_diff(ref, edges[k + 8][0], 1024), 84) <= 0.5

    # 3. Signed 6-bit GRAD_X = +10, GRAD_Y = -20 across all 8 45-deg ring slots
    await spi_write(dut, REG_Z_OFFSET, 0)
    await spi_write(dut, REG_CTRL, 0x05)
    gx, gy = 10, -20
    await spi_write(dut, REG_GRAD_X, gx & 0x3F)
    await spi_write(dut, REG_GRAD_Y, gy & 0x3F)
    await ClockCycles(dut.clk, 16)

    edges, _ = await capture_channels(dut, 2100)
    ring_offsets = [gx, gx + gy, gy, -gx + gy, -gx, -gx - gy, -gy, gx - gy]
    ref_ch0 = edges[0][1]
    for k in range(8):
        rel_exp = (ring_offsets[k] - ring_offsets[0]) % PHASE_STEPS
        meas_bot = circular_phase_diff(ref_ch0, edges[k][0], 1024)
        meas_top = circular_phase_diff(ref_ch0, edges[k + 8][0], 1024)
        assert circular_step_err(meas_bot, rel_exp) <= 0.5, (
            f"Ring Bot Ch {k}: expected rel {rel_exp}, got {meas_bot:.2f}"
        )
        assert circular_step_err(meas_top, rel_exp) <= 0.5, (
            f"Ring Top Ch {k + 8}: expected rel {rel_exp}, got {meas_top:.2f}"
        )


@cocotb.test()
async def test_hardware_acoustic_vortex(dut):
    """Verify CTRL_REG[7]=1 helical acoustic vortex (k*16) and opposing bottle trap (0xC5)."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)

    await spi_write(dut, REG_FREQ_LO, 0x00)
    await spi_write(dut, REG_FREQ_HI, 0x04)

    # Helical vortex staircase: k * 16 on both rings
    await spi_write(dut, REG_CTRL, 0x85)
    await ClockCycles(dut.clk, 20)
    edges, _ = await capture_channels(dut, 2100)
    ref = edges[0][1]
    for k in range(8):
        exp = (k * 16) % PHASE_STEPS
        assert circular_step_err(circular_phase_diff(ref, edges[k][0], 1024), exp) <= 0.5, (
            f"Vortex Bot Ch {k}: expected {exp}"
        )
        assert circular_step_err(circular_phase_diff(ref, edges[k + 8][0], 1024), exp) <= 0.5, (
            f"Vortex Top Ch {k + 8}: expected {exp}"
        )

    # Opposing acoustic bottle trap: vortex_en + top_invert (0xC5)
    await spi_write(dut, REG_CTRL, 0xC5)
    await ClockCycles(dut.clk, 20)
    edges, _ = await capture_channels(dut, 2100)
    ref = edges[0][1]
    for k in range(8):
        exp_bot = (k * 16) % PHASE_STEPS
        exp_top = (k * 16 + 64) % PHASE_STEPS
        assert circular_step_err(circular_phase_diff(ref, edges[k][0], 1024), exp_bot) <= 0.5
        assert circular_step_err(circular_phase_diff(ref, edges[k + 8][0], 1024), exp_top) <= 0.5
