# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# Puzzle 04 Grader: Standalone Kinetic Art Engine (src/aether_art_fsm.v)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer

CLK_PERIOD_NS = 20
FAST_TICK_CLKS = 128  # art_speed = 2'b11 -> prescaler[6] rises every 128 clocks


def to_s6(val):
    v = int(val) & 0x3F
    return v - 64 if v >= 32 else v


async def reset_art(dut, pat_sel=0, art_speed=3, art_en=1):
    dut.rst_n.value = 0
    dut.art_en.value = art_en
    dut.pat_sel.value = pat_sel
    dut.art_speed.value = art_speed
    dut.btn_up.value = 0
    dut.btn_down.value = 0
    await ClockCycles(dut.clk, 4)
    await ReadOnly()
    assert int(dut.art_z.value) == 0, "art_z must be 0 in reset"
    if pat_sel == 0b10:
        assert to_s6(dut.art_gx.value) == 12 and to_s6(dut.art_gy.value) == 0, (
            "In Orbit mode with st=0 during reset, expected (art_gx, art_gy) = (+12, 0)"
        )
    else:
        assert to_s6(dut.art_gx.value) == 0, "art_gx must be 0 in reset"
        assert to_s6(dut.art_gy.value) == 0, "art_gy must be 0 in reset"
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1


@cocotb.test()
async def test_art_en_gating(dut):
    """Verify art_en=0 freezes state across multiple prescaler ticks."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_art(dut, pat_sel=0b11, art_speed=0b11, art_en=0)

    await ClockCycles(dut.clk, FAST_TICK_CLKS * 5)
    await ReadOnly()
    assert int(dut.art_z.value) == 0, (
        f"Expected art_z to stay 0 when art_en=0, got {int(dut.art_z.value)}"
    )


@cocotb.test()
async def test_mode00_static_and_manual_jog(dut):
    """Verify Mode 00 holds on idle or both-buttons, increments on btn_up, decrements on btn_down."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_art(dut, pat_sel=0b00, art_speed=0b11, art_en=1)

    # Idle: stays 0
    await ClockCycles(dut.clk, FAST_TICK_CLKS * 3)
    await ReadOnly()
    assert int(dut.art_z.value) == 0
    assert to_s6(dut.art_gx.value) == 0 and to_s6(dut.art_gy.value) == 0
    await Timer(1, unit="ns")

    # Both buttons pressed: XOR prevents stepping
    dut.btn_up.value = 1
    dut.btn_down.value = 1
    await ClockCycles(dut.clk, FAST_TICK_CLKS * 3)
    await ReadOnly()
    assert int(dut.art_z.value) == 0, "Pressing both btn_up and btn_down must hold st unchanged"
    await Timer(1, unit="ns")

    # Jog UP for 5 ticks -> art_z == 5
    dut.btn_up.value = 1
    dut.btn_down.value = 0
    await ClockCycles(dut.clk, FAST_TICK_CLKS * 5)
    await ReadOnly()
    z_up = int(dut.art_z.value)
    assert z_up == 5, f"Expected art_z=5 after 5 UP ticks, got {z_up}"
    await Timer(1, unit="ns")

    # Jog DOWN for 7 ticks -> wraps 5 - 7 = 126 (mod 128)
    dut.btn_up.value = 0
    dut.btn_down.value = 1
    await ClockCycles(dut.clk, FAST_TICK_CLKS * 7)
    await ReadOnly()
    z_dn = int(dut.art_z.value)
    assert z_dn == 126, f"Expected art_z=126 after 7 DOWN ticks from 5, got {z_dn}"


@cocotb.test()
async def test_mode01_zen_breathing(dut):
    """Verify Mode 01 generates exact 64-tick triangle wave 0..32..1..0 on art_z."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_art(dut, pat_sel=0b01, art_speed=0b11, art_en=1)

    # First tick occurs at prescaler == 64 (after 65 clocks from reset release)
    # Sample right after each tick: clock 70, 70+128, 70+256, ...
    await ClockCycles(dut.clk, 70)
    samples = []
    for k in range(1, 66):
        await ReadOnly()
        z = int(dut.art_z.value)
        assert to_s6(dut.art_gx.value) == 0 and to_s6(dut.art_gy.value) == 0
        km = k % 64
        expected = km if km < 32 else (64 - km)
        assert z == expected, f"Breathing tick {k}: expected art_z={expected}, got {z}"
        samples.append(z)
        await ClockCycles(dut.clk, FAST_TICK_CLKS)

    assert max(samples) == 32, f"Breathing peak must reach 32, got {max(samples)}"
    assert min(samples) == 0, f"Breathing trough must return to 0, got {min(samples)}"


@cocotb.test()
async def test_mode10_3d_halo_orbit_and_overflow_clamp(dut):
    """Verify exact 48-step 4-quadrant Halo Orbit (+-12, |Gx|+|Gy|=12, art_z=0) & s_ovf clamp."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_art(dut, pat_sel=0b10, art_speed=0b11, art_en=1)

    # Check initial state st=0 -> Q0, s=0 -> (+12, 0)
    await ReadOnly()
    assert int(dut.art_z.value) == 0
    assert (to_s6(dut.art_gx.value), to_s6(dut.art_gy.value)) == (12, 0), (
        f"Orbit st=0 expected (+12, 0), got ({to_s6(dut.art_gx.value)}, {to_s6(dut.art_gy.value)})"
    )

    # Build expected 48-step orbit sequence (st=1..48 wrapping back to (+12, 0) at step 48)
    expected_orbit = []
    for q in range(4):
        for s in range(12):
            inv_s = 12 - s
            mx = s if (q & 1) else inv_s
            my = inv_s if (q & 1) else s
            gx = -mx if ((q & 1) ^ ((q >> 1) & 1)) else mx
            gy = -my if ((q >> 1) & 1) else my
            expected_orbit.append((gx, gy))

    # Sample after each of the next 48 ticks (st visits steps 1..47 then back to 0!)
    await ClockCycles(dut.clk, 70)
    for step in range(1, 49):
        await ReadOnly()
        z = int(dut.art_z.value)
        gx = to_s6(dut.art_gx.value)
        gy = to_s6(dut.art_gy.value)
        exp_gx, exp_gy = expected_orbit[step % 48]
        assert z == 0, f"Orbit step {step}: expected art_z=0, got {z}"
        assert (gx, gy) == (exp_gx, exp_gy), (
            f"Orbit step {step}: expected ({exp_gx}, {exp_gy}), got ({gx}, {gy})"
        )
        assert abs(gx) + abs(gy) == 12, f"Orbit step {step}: |gx|+|gy| != 12 ({gx}, {gy})"
        if step < 48:
            await ClockCycles(dut.clk, FAST_TICK_CLKS)

    # Verify s_ovf clamp: step st to 14 in Elevator mode (pat_sel=11), then switch to Orbit (pat_sel=10)
    await Timer(1, unit="ns")
    await reset_art(dut, pat_sel=0b11, art_speed=0b11, art_en=1)
    await ClockCycles(dut.clk, 70 + 13 * FAST_TICK_CLKS)  # st == 14 (4'b1110 -> s_ovf=1)
    await ReadOnly()
    assert int(dut.art_z.value) == 14, f"Setup failed: expected st=14, got {int(dut.art_z.value)}"
    await Timer(1, unit="ns")
    dut.pat_sel.value = 0b10
    await Timer(1, unit="ns")
    await ReadOnly()
    gx = to_s6(dut.art_gx.value)
    gy = to_s6(dut.art_gy.value)
    assert abs(gx) <= 12 and abs(gy) <= 12, (
        f"s_ovf clamp failed at st=14: got ({gx}, {gy}), exceeds +-12!"
    )
    assert (gx, gy) == (12, 0), f"At st=14 (q=0, s_ovf->0), expected (+12, 0), got ({gx}, {gy})"


@cocotb.test()
async def test_mode11_continuous_elevator(dut):
    """Verify Mode 11 increments art_z modulo 128 continuously with art_gx=art_gy=0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_art(dut, pat_sel=0b11, art_speed=0b11, art_en=1)

    await ClockCycles(dut.clk, 70)
    for k in range(1, 132):
        await ReadOnly()
        got = int(dut.art_z.value)
        exp = k % 128
        assert got == exp, f"Elevator tick {k}: expected {exp}, got {got}"
        assert to_s6(dut.art_gx.value) == 0 and to_s6(dut.art_gy.value) == 0
        if k < 131:
            await ClockCycles(dut.clk, FAST_TICK_CLKS)
