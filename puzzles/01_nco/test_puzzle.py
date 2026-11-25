# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 01 Grader: 20-Bit Tunable Carrier NCO (src/aether_nco.v)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer

CLK_PERIOD_NS = 20  # 50 MHz
ACC_MASK = (1 << 20) - 1
PHASE_SHIFT = 20 - 7  # PHASE_BITS = 7 -> top bits [19:13]


async def reset_nco(dut, freq_word=0x347, clk_div2=0):
    dut.clk_div2.value = clk_div2
    dut.freq_word.value = freq_word
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    await ReadOnly()
    assert int(dut.master_phase.value) == 0, (
        f"Expected master_phase=0 during reset, got {int(dut.master_phase.value)}"
    )
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1


@cocotb.test()
async def test_reset_state(dut):
    """Verify synchronous active-low reset forces master_phase to 0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.clk_div2.value = 0
    dut.freq_word.value = 0x347
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    await ReadOnly()
    assert int(dut.master_phase.value) == 0, "master_phase must be 0 when rst_n=0"


@cocotb.test()
async def test_default_40khz_50mhz(dut):
    """Verify default freq_word=0x347 (839) matches 20-bit NCO golden model & 40.007 kHz period."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    freq_word = 0x347
    await reset_nco(dut, freq_word=freq_word, clk_div2=0)

    acc = 0
    prev_phase = 0
    wrap_cycles = []

    for cyc in range(2600):
        await RisingEdge(dut.clk)
        acc = (acc + freq_word) & ACC_MASK
        await ReadOnly()
        got = int(dut.master_phase.value)
        exp = acc >> PHASE_SHIFT
        assert got == exp, (
            f"Cycle {cyc}: expected master_phase={exp} (acc=0x{acc:05X}), got {got}"
        )
        if prev_phase == 127 and got == 0:
            wrap_cycles.append(cyc)
        prev_phase = got

    assert len(wrap_cycles) >= 2, f"Expected >=2 full carrier cycles, saw {len(wrap_cycles)}"
    period = wrap_cycles[1] - wrap_cycles[0]
    assert 1249 <= period <= 1250, (
        f"Expected 40.007 kHz wrap period 1249..1250 cycles @ 50 MHz, got {period}"
    )


@cocotb.test()
async def test_clk_div2_25mhz_mode(dut):
    """Verify clk_div2=1 doubles the phase increment (2x freq_word) for 25 MHz clock operation."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    freq_word = 0x347
    await reset_nco(dut, freq_word=freq_word, clk_div2=1)

    acc = 0
    prev_phase = 0
    wrap_cycles = []

    for cyc in range(1400):
        await RisingEdge(dut.clk)
        acc = (acc + (freq_word << 1)) & ACC_MASK
        await ReadOnly()
        got = int(dut.master_phase.value)
        exp = acc >> PHASE_SHIFT
        assert got == exp, (
            f"clk_div2=1 cycle {cyc}: expected master_phase={exp}, got {got}"
        )
        if prev_phase > 100 and got < 20:
            wrap_cycles.append(cyc)
        prev_phase = got

    assert len(wrap_cycles) >= 2, "Expected >=2 wraps in clk_div2=1 mode"
    period = wrap_cycles[1] - wrap_cycles[0]
    assert 624 <= period <= 626, f"Expected clk_div2=1 period ~625 cycles, got {period}"


@cocotb.test()
async def test_custom_freq_words(dut):
    """Verify exact phase progression for freq_word = 0x800 (exact 512), 0x000 (hold), and 0xFFF."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    # 1. Exact power-of-two period: 0x800 (2048) -> 2^20 / 2048 = 512 cycles/period
    await reset_nco(dut, freq_word=0x800, clk_div2=0)
    acc = 0
    for cyc in range(600):
        await RisingEdge(dut.clk)
        acc = (acc + 0x800) & ACC_MASK
        await ReadOnly()
        assert int(dut.master_phase.value) == (acc >> PHASE_SHIFT), (
            f"freq_word=0x800 cycle {cyc}: mismatch"
        )

    # 2. freq_word = 0x000 freezes the accumulator at its current value
    await RisingEdge(dut.clk)
    dut.freq_word.value = 0x000
    acc = (acc + 0x800) & ACC_MASK  # one more edge with 0x800 before 0x000 takes effect
    await ReadOnly()
    frozen_phase = int(dut.master_phase.value)
    assert frozen_phase == (acc >> PHASE_SHIFT)
    for _ in range(20):
        await RisingEdge(dut.clk)
        await ReadOnly()
        assert int(dut.master_phase.value) == frozen_phase, (
            "freq_word=0x000 must freeze master_phase"
        )

    # 3. Max freq_word = 0xFFF with clk_div2 = 1 (tests full 13-bit phase_inc without truncation)
    await Timer(1, unit="ns")
    await reset_nco(dut, freq_word=0xFFF, clk_div2=1)
    acc = 0
    for cyc in range(300):
        await RisingEdge(dut.clk)
        acc = (acc + (0xFFF << 1)) & ACC_MASK
        await ReadOnly()
        got = int(dut.master_phase.value)
        exp = acc >> PHASE_SHIFT
        assert got == exp, (
            f"freq_word=0xFFF clk_div2=1 cycle {cyc}: expected {exp}, got {got}"
        )
