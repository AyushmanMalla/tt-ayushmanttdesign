# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 02 Grader: Glitch-Free Ultrasonic PWM Channel (src/aether_channel.v)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge

CLK_PERIOD_NS = 20
PHASE_STEPS = 128


async def reset_channel(dut):
    dut.rst_n.value = 0
    dut.out_en.value = 0
    dut.master_phase.value = 0
    dut.eff_phase.value = 0
    dut.eff_duty.value = 64
    await ClockCycles(dut.clk, 3)
    await ReadOnly()
    assert int(dut.ch_out.value) == 0, "ch_out must be 0 during reset"
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1


@cocotb.test()
async def test_reset_and_out_en_mute(dut):
    """Verify synchronous reset and 1-cycle out_en mute."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_channel(dut)

    # Drive active phase (shifted=0 < eff_duty=64) with out_en=1 -> ch_out must be 1 next cycle
    dut.out_en.value = 1
    dut.master_phase.value = 0
    dut.eff_phase.value = 0
    dut.eff_duty.value = 64
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.ch_out.value) == 1, "Expected ch_out=1 when out_en=1 and shifted=0 < 64"

    # Drop out_en=0 -> ch_out must mute to 0 on the very next rising edge
    await RisingEdge(dut.clk)
    dut.out_en.value = 0
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert int(dut.ch_out.value) == 0, "Expected ch_out=0 within 1 cycle of out_en=0"


@cocotb.test()
async def test_duty_sweep_zero_phase(dut):
    """Verify exact registered PWM output across all 128 phases for duty in {0, 1, 16, 32, 63, 64}."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_channel(dut)

    dut.out_en.value = 1
    dut.eff_phase.value = 0

    for duty in (0, 1, 16, 32, 63, 64):
        dut.eff_duty.value = duty
        high_count = 0
        for ph in range(PHASE_STEPS):
            dut.master_phase.value = ph
            await RisingEdge(dut.clk)
            await ReadOnly()
            got = int(dut.ch_out.value)
            exp = 1 if ph < duty else 0
            assert got == exp, (
                f"eff_duty={duty}, master_phase={ph}: expected ch_out={exp}, got {got}"
            )
            high_count += got
            # Step off ReadOnly before next drive
            if ph < PHASE_STEPS - 1:
                await cocotb.triggers.Timer(1, unit="ns")
        assert high_count == duty, (
            f"eff_duty={duty}: expected {duty}/128 high cycles, got {high_count}"
        )
        await cocotb.triggers.Timer(1, unit="ns")


@cocotb.test()
async def test_phase_shift_wraparound(dut):
    """Verify modulo-128 phase shift across eff_phase values including wraparound boundaries."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_channel(dut)

    dut.out_en.value = 1
    dut.eff_duty.value = 48

    for eff_phase in (0, 1, 32, 64, 96, 127):
        dut.eff_phase.value = eff_phase
        for mp in range(PHASE_STEPS):
            dut.master_phase.value = mp
            await RisingEdge(dut.clk)
            await ReadOnly()
            shifted = (mp + eff_phase) & 0x7F
            exp = 1 if shifted < 48 else 0
            got = int(dut.ch_out.value)
            assert got == exp, (
                f"mp={mp}, eff_phase={eff_phase} (shifted={shifted}), duty=48: "
                f"expected {exp}, got {got}"
            )
            await cocotb.triggers.Timer(1, unit="ns")


@cocotb.test()
async def test_boundary_shifted_64_with_duty_64(dut):
    """Catch classic comparator bug: shifted=64 with eff_duty=64 MUST output 0 (not 1)."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_channel(dut)

    dut.out_en.value = 1
    dut.eff_duty.value = 64

    cases = [
        (63, 0, 1),   # shifted = 63 -> high
        (64, 0, 0),   # shifted = 64 -> low!
        (127, 0, 0),  # shifted = 127 -> low
        (127, 1, 1),  # shifted = 0 (wrapped) -> high
        (32, 32, 0),  # shifted = 64 -> low!
        (32, 31, 1),  # shifted = 63 -> high
    ]
    for mp, ep, exp in cases:
        dut.master_phase.value = mp
        dut.eff_phase.value = ep
        await RisingEdge(dut.clk)
        await ReadOnly()
        got = int(dut.ch_out.value)
        assert got == exp, (
            f"Boundary case mp={mp}, ep={ep} (shifted={(mp+ep)&0x7F}), duty=64: "
            f"expected {exp}, got {got}"
        )
        await cocotb.triggers.Timer(1, unit="ns")
