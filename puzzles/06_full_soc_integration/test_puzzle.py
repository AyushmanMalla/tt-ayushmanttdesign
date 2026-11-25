# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 06 Grader: Full SoC Control Integration
# Verifies CLK_DIV2, ENABLE safety mute, DUTY_CYCLE clamping, SOFT_PWR, 4-level AM_MOD_IN,
# spi_out_en, SOFT_RESET magic key, and Mode 0 / Mode 1 Standalone Art muxing.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

CLK_PERIOD_NS = 20
PHASE_STEPS = 128

REG_FREQ_LO = 0x10
REG_FREQ_HI = 0x11
REG_DUTY = 0x12
REG_CTRL = 0x16
REG_SOFT_RST = 0x17


def ui_mode0(pat=0, btn_up=0, btn_down=0, enable=1, am_mod=0, clk_div2=0):
    return (
        ((clk_div2 & 1) << 7)
        | ((am_mod & 1) << 6)
        | ((enable & 1) << 5)
        | ((pat & 3) << 3)
        | ((btn_down & 1) << 2)
        | ((btn_up & 1) << 1)
        | 0
    )


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


async def reset_dut(dut, init_ui=None):
    if init_ui is None:
        init_ui = ui_mode1(enable=1)
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = init_ui
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def spi_write(
    dut, addr, data, guard=1, enable=1, soft_pwr=0, am_mod=0, clk_div2=0, half_clks=4
):
    frame = ((guard & 1) << 15) | ((addr & 0x1F) << 8) | (data & 0xFF)
    dut.ui_in.value = ui_mode1(0, 0, 0, soft_pwr, enable, am_mod, clk_div2)
    await ClockCycles(dut.clk, half_clks)
    for bit_idx in range(15, -1, -1):
        bit = (frame >> bit_idx) & 1
        dut.ui_in.value = ui_mode1(0, bit, 0, soft_pwr, enable, am_mod, clk_div2)
        await ClockCycles(dut.clk, half_clks)
        dut.ui_in.value = ui_mode1(1, bit, 0, soft_pwr, enable, am_mod, clk_div2)
        await ClockCycles(dut.clk, half_clks)
    dut.ui_in.value = ui_mode1(0, 0, 0, soft_pwr, enable, am_mod, clk_div2)
    await ClockCycles(dut.clk, half_clks)
    dut.ui_in.value = ui_mode1(0, 0, 1, soft_pwr, enable, am_mod, clk_div2)
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
    return (((ref_edge - ch_edge) % period) * PHASE_STEPS) / period


def circular_step_err(measured, expected):
    diff = (measured - expected) % PHASE_STEPS
    if diff > PHASE_STEPS / 2:
        diff -= PHASE_STEPS
    return abs(diff)


@cocotb.test()
async def test_clk_div2_and_hardware_safety_mute(dut):
    """Verify CLK_DIV2=1 doubles carrier rate and ENABLE=0 mutes all 16 pins cleanly."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1, clk_div2=1))

    edges, _ = await capture_channels(dut, 1400)
    period = edges[0][1] - edges[0][0]
    assert 623 <= period <= 627, f"CLK_DIV2=1 expected period ~625, got {period}"

    # Wait for outputs to go high, then assert ENABLE=0
    for _ in range(700):
        await RisingEdge(dut.clk)
        if read_all_ch(dut) == 0xFFFF:
            break
    assert read_all_ch(dut) == 0xFFFF, "Outputs did not go high before safety mute check"

    dut.ui_in.value = ui_mode1(enable=0, clk_div2=1)
    await ClockCycles(dut.clk, 3)
    assert read_all_ch(dut) == 0x0000, f"ENABLE=0 failed to mute: 0x{read_all_ch(dut):04X}"


@cocotb.test()
async def test_duty_clamp_soft_pwr_am_and_soft_reset(dut):
    """Verify duty clamping (>64->64), SOFT_PWR, 4-level AM_MOD_IN, spi_out_en, and SOFT_RESET."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # FREQ_WORD = 0x800 -> exact 512 clocks/cycle
    await spi_write(dut, REG_FREQ_LO, 0x00)
    await spi_write(dut, REG_FREQ_HI, 0x08)

    # Duty = 32 (25%), Duty = 100 (clamped to 64 = 50%), Duty = 0 (0%)
    for duty_val, exp_high in [(32, 128), (100, 256), (0, 0)]:
        await spi_write(dut, REG_DUTY, duty_val)
        await ClockCycles(dut.clk, 16)
        _, highs = await capture_channels(dut, 512)
        assert abs(highs[0] - exp_high) <= 4, (
            f"DUTY={duty_val}: expected ~{exp_high}/512, got {highs[0]}"
        )

    # Restore duty=64 and test SOFT_PWR=1 -> 25% duty (128/512)
    await spi_write(dut, REG_DUTY, 64)
    dut.ui_in.value = ui_mode1(enable=1, soft_pwr=1)
    await ClockCycles(dut.clk, 16)
    _, highs = await capture_channels(dut, 512)
    assert abs(highs[0] - 128) <= 4, f"SOFT_PWR=1 expected ~128/512, got {highs[0]}"

    # Test all 4 AM_MOD_IN depths with am_mod=1, soft_pwr=0
    for depth, exp_h in [(0, 256), (1, 192), (2, 128), (3, 64)]:
        await spi_write(dut, REG_CTRL, (depth << 1) | 0x01, am_mod=1)
        await ClockCycles(dut.clk, 16)
        _, highs = await capture_channels(dut, 512)
        assert abs(highs[0] - exp_h) <= 4, (
            f"AM depth {depth:02b}: expected ~{exp_h}/512, got {highs[0]}"
        )

    # spi_out_en=0 mutes; wrong SOFT_RESET key (0x5A) ignored; valid key (0xA5) restores defaults
    await spi_write(dut, REG_CTRL, 0x00, am_mod=0)
    await ClockCycles(dut.clk, 2)
    assert read_all_ch(dut) == 0x0000, "spi_out_en=0 did not mute outputs"

    await spi_write(dut, REG_SOFT_RST, 0x5A)
    await ClockCycles(dut.clk, 2)
    assert read_all_ch(dut) == 0x0000, "Wrong SOFT_RESET magic unexpectedly triggered reset"

    await spi_write(dut, REG_SOFT_RST, 0xA5)
    await ClockCycles(dut.clk, 20)  # Let 8-cycle shift-bank scrubber finish before measuring
    edges, highs = await capture_channels(dut, 2600)
    period = edges[0][1] - edges[0][0]
    assert 1248 <= period <= 1256, f"SOFT_RESET failed to restore 40 kHz (period={period})"
    assert 0.47 <= highs[0] / 2600.0 <= 0.53, "SOFT_RESET failed to restore 50% duty"


@cocotb.test()
async def test_mode0_standalone_art_and_run_art_in_spi(dut):
    """Verify Mode 0 Standalone Art patterns + run_art_in_spi (CTRL_REG[5]) muxing."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # Fast carrier (256 clks/cycle) + fast art speed (art_spd=2'b11 -> CTRL=0x1D)
    await spi_write(dut, REG_FREQ_LO, 0x00, clk_div2=1)
    await spi_write(dut, REG_FREQ_HI, 0x08, clk_div2=1)
    await spi_write(dut, REG_CTRL, 0x1D, clk_div2=1)

    async def measure_z():
        edges, _ = await capture_channels(dut, 300)
        return circular_phase_diff(edges[0][0], edges[8][0], 256)

    # Mode 00: Static Lock + Jog UP 8 ticks
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=1, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 1024)
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=0, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 10)
    z_up = await measure_z()
    assert 6.0 <= z_up <= 10.0, f"Mode 00 Jog UP expected ~8 steps, got {z_up:.2f}"

    # Switch to Mode 11 (Continuous Elevator) and verify steady advance
    dut.ui_in.value = ui_mode0(pat=0b11, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 260)
    z_a = await measure_z()
    await ClockCycles(dut.clk, 2560)
    z_b = await measure_z()
    delta = (z_b - z_a) % PHASE_STEPS
    assert 18.0 <= delta <= 26.0, f"Mode 11 Elevator delta expected ~20, got {delta:.2f}"

    # Transition cleanly to SPI mode (hold PAT bits = 11 for 2 clocks while mode_sel_r registers 1)
    dut.ui_in.value = ui_mode1(cs_n=1, soft_pwr=1, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 2)
    # Enable run_art_in_spi=1 (CTRL_REG=0x3D) -> pat_latched stays 2'b11 & keeps climbing!
    await spi_write(dut, REG_CTRL, 0x3D, clk_div2=1)
    z_c = await measure_z()
    await ClockCycles(dut.clk, 2048)
    z_d = await measure_z()
    delta_spi = (z_d - z_c) % PHASE_STEPS
    assert 12.0 <= delta_spi <= 22.0, (
        f"run_art_in_spi=1 failed to keep Elevator running in SPI mode (delta={delta_spi:.2f})"
    )
