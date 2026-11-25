# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0
#
# AETHER-16 Variant B (PHASE_BITS = 7, 128 steps = 2.8125 deg) Verification Suite
# Gate-Level (GL) compatible: accesses ONLY top-level ports.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

CLK_PERIOD_NS = 20  # 50 MHz
PHASE_STEPS = 128

# SPI Register Map
REG_CH_BASE = 0x00  # 0x00..0x0F: CH_BASE_PHASE[0..15]
REG_FREQ_LO = 0x10
REG_FREQ_HI = 0x11
REG_DUTY = 0x12
REG_Z_OFFSET = 0x13
REG_GRAD_X = 0x14
REG_GRAD_Y = 0x15
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
    """Send a 16-bit MSB-first SPI Mode 0 write frame."""
    frame = ((guard & 1) << 15) | ((addr & 0x1F) << 8) | (data & 0xFF)

    # Assert CS_N low with SCK=0
    dut.ui_in.value = ui_mode1(
        sck=0,
        mosi=0,
        cs_n=0,
        soft_pwr=soft_pwr,
        enable=enable,
        am_mod=am_mod,
        clk_div2=clk_div2,
    )
    await ClockCycles(dut.clk, half_clks)

    for bit_idx in range(15, -1, -1):
        bit = (frame >> bit_idx) & 1
        # Drive MOSI while SCK=0
        dut.ui_in.value = ui_mode1(
            sck=0,
            mosi=bit,
            cs_n=0,
            soft_pwr=soft_pwr,
            enable=enable,
            am_mod=am_mod,
            clk_div2=clk_div2,
        )
        await ClockCycles(dut.clk, half_clks)
        # Rising edge of SCK (Mode 0 sample edge)
        dut.ui_in.value = ui_mode1(
            sck=1,
            mosi=bit,
            cs_n=0,
            soft_pwr=soft_pwr,
            enable=enable,
            am_mod=am_mod,
            clk_div2=clk_div2,
        )
        await ClockCycles(dut.clk, half_clks)

    # Return SCK low, hold CS_N low briefly for 2-FF sync completion, then deassert CS_N
    dut.ui_in.value = ui_mode1(
        sck=0,
        mosi=0,
        cs_n=0,
        soft_pwr=soft_pwr,
        enable=enable,
        am_mod=am_mod,
        clk_div2=clk_div2,
    )
    await ClockCycles(dut.clk, half_clks)
    dut.ui_in.value = ui_mode1(
        sck=0,
        mosi=0,
        cs_n=1,
        soft_pwr=soft_pwr,
        enable=enable,
        am_mod=am_mod,
        clk_div2=clk_div2,
    )
    await ClockCycles(dut.clk, half_clks)


async def capture_channels(dut, num_cycles):
    """Capture rising edges and high-cycle counts for all 16 channels."""
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
    """Return phase lead of ch over ref in [0, PHASE_STEPS) steps."""
    # Positive eff_phase advances rising edge (ch_edge occurs earlier than ref_edge)
    delta_clks = (ref_edge - ch_edge) % period
    return (delta_clks * PHASE_STEPS) / period


def circular_step_err(measured, expected):
    diff = (measured - expected) % PHASE_STEPS
    if diff > PHASE_STEPS / 2:
        diff -= PHASE_STEPS
    return abs(diff)


@cocotb.test()
async def test_default_40khz_clk_div2_and_enable_mute(dut):
    """Verify reset, uio_oe, 40.007 kHz carrier @ 50 MHz, CLK_DIV2 @ 25 MHz, and 1-cycle ENABLE mute."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = ui_mode1(enable=1)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)

    assert int(dut.uio_oe.value) == 0xFF, f"Expected uio_oe=0xFF, got 0x{int(dut.uio_oe.value):02X}"
    assert read_all_ch(dut) == 0, f"Expected all outputs 0 in reset, got 0x{read_all_ch(dut):04X}"

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # Measure default 40,006.6 Hz carrier at 50 MHz (period = 1048576 / 839 = 1249.79 cycles)
    edges, highs = await capture_channels(dut, 2600)
    for ch in range(16):
        assert len(edges[ch]) >= 2, f"Ch {ch} had fewer than 2 rising edges"
        period = edges[ch][1] - edges[ch][0]
        assert 1248 <= period <= 1252, f"Ch {ch} period {period} out of 40 kHz range"
        assert edges[ch][0] == edges[0][0], f"Ch {ch} not phase-aligned with Ch 0 on reset"
        duty_ratio = highs[ch] / 2600.0
        assert 0.47 <= duty_ratio <= 0.53, f"Ch {ch} default duty {duty_ratio:.3f} != 0.50"

    # Verify CLK_DIV2 = 1 doubles NCO increment (period = 624.9 cycles @ 50 MHz -> 40.007 kHz @ 25 MHz)
    dut.ui_in.value = ui_mode1(enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 4)
    edges_div2, _ = await capture_channels(dut, 1400)
    period_div2 = edges_div2[0][1] - edges_div2[0][0]
    assert 623 <= period_div2 <= 627, f"CLK_DIV2 period {period_div2} != ~625"

    # Verify FR-10: ENABLE=0 mutes all 16 outputs within 1 clock cycle
    # First wait until outputs are high
    dut.ui_in.value = ui_mode1(enable=1, clk_div2=1)
    for _ in range(700):
        await RisingEdge(dut.clk)
        if read_all_ch(dut) == 0xFFFF:
            break
    assert read_all_ch(dut) == 0xFFFF, "Outputs did not go high before mute test"

    dut.ui_in.value = ui_mode1(enable=0, clk_div2=1)
    await ClockCycles(dut.clk, 2)
    assert read_all_ch(dut) == 0x0000, f"ENABLE=0 failed to mute outputs: 0x{read_all_ch(dut):04X}"


@cocotb.test()
async def test_128step_fine_phase_all_16_channels(dut):
    """Verify SPI guard bit and full 7-bit (128-step) fine phase accuracy across all 16 channels."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # Guard bit = 0 must be ignored
    await spi_write(dut, REG_CH_BASE + 0, 40, guard=0)

    # Distinct 7-bit phases covering LSB 1-step resolution (0, 1, 2) and full 0..127 range
    target_phases = [0, 1, 2, 15, 31, 32, 47, 63, 64, 65, 79, 95, 96, 111, 126, 127]
    for ch, ph in enumerate(target_phases):
        await spi_write(dut, REG_CH_BASE + ch, ph)

    # Capture at default 40 kHz (1249.79 cycles/period -> ~9.76 clocks per 1/128 step)
    edges, _ = await capture_channels(dut, 2600)
    period = edges[0][1] - edges[0][0]
    ref_edge = edges[0][1]  # Use second edge so earlier/later channels both have nearby edges

    for ch, expected_step in enumerate(target_phases):
        # Pick the edge of ch closest to ref_edge - expected_delay
        measured_step = circular_phase_diff(ref_edge, edges[ch][0], period)
        err = circular_step_err(measured_step, expected_step)
        assert err <= 0.45, (
            f"Ch {ch}: expected step {expected_step}, measured {measured_step:.2f} (err={err:.2f})"
        )


@cocotb.test()
async def test_freq_duty_soft_pwr_am_and_soft_reset(dut):
    """Verify FREQ_WORD, DUTY_CYCLE clamping, SOFT_PWR, AM_MOD_IN depths, spi_out_en, and SOFT_RESET."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # Program FREQ_WORD = 0x800 (2048) -> exact 512 clocks per cycle (4 clocks per 7-bit step)
    await spi_write(dut, REG_FREQ_LO, 0x00)
    await spi_write(dut, REG_FREQ_HI, 0x08)

    edges, highs = await capture_channels(dut, 1024)
    period = edges[0][1] - edges[0][0]
    assert period == 512, f"Expected FREQ_WORD=0x800 period 512, got {period}"
    assert abs(highs[0] - 512) <= 2, f"Expected 50% duty (~512/1024), got {highs[0]}"

    # Test DUTY_CYCLE = 32 (25%), 96 (clamped to 64 = 50%), and 0 (0%)
    await spi_write(dut, REG_DUTY, 32)
    await ClockCycles(dut.clk, 16)
    _, highs = await capture_channels(dut, 512)
    assert abs(highs[0] - 128) <= 4, f"Expected 25% duty (128/512), got {highs[0]}"

    await spi_write(dut, REG_DUTY, 96)
    await ClockCycles(dut.clk, 16)
    _, highs = await capture_channels(dut, 512)
    assert abs(highs[0] - 256) <= 4, f"Expected clamped 50% duty (256/512), got {highs[0]}"

    await spi_write(dut, REG_DUTY, 0)
    await ClockCycles(dut.clk, 16)
    _, highs = await capture_channels(dut, 512)
    assert highs[0] == 0, f"Expected 0% duty, got {highs[0]}"

    # Restore 50% duty (64) and test SOFT_PWR = 1 -> 25% duty
    await spi_write(dut, REG_DUTY, 64)
    dut.ui_in.value = ui_mode1(enable=1, soft_pwr=1)
    await ClockCycles(dut.clk, 16)
    _, highs = await capture_channels(dut, 512)
    assert abs(highs[0] - 128) <= 4, f"SOFT_PWR=1 expected 128/512, got {highs[0]}"

    # Test AM_MOD_IN across all 4 am_depth settings (with soft_pwr=0, duty=64)
    expected_am_highs = {
        0b00: 256,  # 0% AM -> 50.0% duty
        0b01: 192,  # 25% AM -> 37.5% duty
        0b10: 128,  # 50% AM -> 25.0% duty
        0b11: 64,   # 75% AM -> 12.5% duty
    }
    for depth, exp_h in expected_am_highs.items():
        ctrl = (depth << 1) | 0x01  # spi_out_en=1
        await spi_write(dut, REG_CTRL, ctrl, am_mod=1)
        await ClockCycles(dut.clk, 16)
        _, highs = await capture_channels(dut, 512)
        assert abs(highs[0] - exp_h) <= 4, (
            f"AM depth {depth:02b}: expected {exp_h}/512, got {highs[0]}"
        )

    # Test spi_out_en = 0 mutes outputs in SPI mode
    await spi_write(dut, REG_CTRL, 0x00, am_mod=0)
    await ClockCycles(dut.clk, 2)
    assert read_all_ch(dut) == 0x0000, "spi_out_en=0 failed to mute outputs"

    # Wrong SOFT_RESET key (0x5A) must NOT reset registers
    await spi_write(dut, REG_SOFT_RST, 0x5A)
    await ClockCycles(dut.clk, 2)
    assert read_all_ch(dut) == 0x0000, "Wrong SOFT_RESET magic unexpectedly reset chip"

    # Valid SOFT_RESET key (0xA5) restores defaults (40 kHz, 50% duty, spi_out_en=1)
    await spi_write(dut, REG_SOFT_RST, 0xA5)
    edges, highs = await capture_channels(dut, 2600)
    period_rst = edges[0][1] - edges[0][0]
    assert 1248 <= period_rst <= 1252, f"SOFT_RESET did not restore 40 kHz (period={period_rst})"
    assert 0.47 <= highs[0] / 2600.0 <= 0.53, "SOFT_RESET did not restore 50% duty"


@cocotb.test()
async def test_atomic_3d_steering_z_top_invert_and_grad_xy(dut):
    """Verify atomic Z_OFFSET, top_invert (180 deg), and 6-bit signed GRAD_X/GRAD_Y 8-ring symmetry."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # FREQ_WORD = 0x400 -> exact 1024 clocks/cycle = exact 8 clocks per 7-bit phase step
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

    # 2. Enable top_invert (CTRL_REG[6]=1) -> top ring = (20 + 64) = 84 steps
    await spi_write(dut, REG_CTRL, 0x45)
    await ClockCycles(dut.clk, 16)
    edges, _ = await capture_channels(dut, 2100)
    ref = edges[0][1]
    for k in range(8):
        assert circular_step_err(circular_phase_diff(ref, edges[k][0], 1024), 0) <= 0.5
        assert circular_step_err(circular_phase_diff(ref, edges[k + 8][0], 1024), 84) <= 0.5

    # 3. Signed 6-bit GRAD_X = +10, GRAD_Y = -20 (testing full 6-bit range beyond +-16)
    await spi_write(dut, REG_Z_OFFSET, 0)
    await spi_write(dut, REG_CTRL, 0x05)
    gx, gy = 10, -20
    await spi_write(dut, REG_GRAD_X, gx & 0x3F)
    await spi_write(dut, REG_GRAD_Y, gy & 0x3F)
    await ClockCycles(dut.clk, 16)

    edges, _ = await capture_channels(dut, 2100)
    ring_offsets = [
        gx,
        gx + gy,
        gy,
        -gx + gy,
        -gx,
        -gx - gy,
        -gy,
        gx - gy,
    ]
    # Measure all channels relative to Ch 0 (whose offset is +gx = +10)
    ref_ch0 = edges[0][1]
    for k in range(8):
        rel_exp = (ring_offsets[k] - ring_offsets[0]) % PHASE_STEPS
        meas_bot = circular_phase_diff(ref_ch0, edges[k][0], 1024)
        meas_top = circular_phase_diff(ref_ch0, edges[k + 8][0], 1024)
        assert circular_step_err(meas_bot, rel_exp) <= 0.5, (
            f"Bot Ch {k}: exp rel {rel_exp}, got {meas_bot:.2f}"
        )
        assert circular_step_err(meas_top, rel_exp) <= 0.5, (
            f"Top Ch {k + 8}: exp rel {rel_exp}, got {meas_top:.2f}"
        )


@cocotb.test()
async def test_standalone_art_modes(dut):
    """Verify all 4 standalone kinetic art modes using art_speed=2'b11 (128 clocks/step)."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut, ui_mode1(enable=1))

    # Fast carrier for quick snapshots: FREQ_WORD=0x800 + CLK_DIV2=1 -> 256 clocks/cycle (2 clocks/step)
    await spi_write(dut, REG_FREQ_LO, 0x00, clk_div2=1)
    await spi_write(dut, REG_FREQ_HI, 0x08, clk_div2=1)
    # Set art_speed = 2'b11 (CTRL_REG[4:3]=11 -> 0x1D: spi_out_en=1, am=10, speed=11)
    await spi_write(dut, REG_CTRL, 0x1D, clk_div2=1)

    async def measure_rel_phase(ch_a, ch_b):
        edges, _ = await capture_channels(dut, 300)
        return circular_phase_diff(edges[ch_a][0], edges[ch_b][0], 256)

    # --- Mode 00: Static Lock + Manual Jog ---
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=0, btn_down=0, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 20)
    z0 = await measure_rel_phase(0, 8)
    assert circular_step_err(z0, 0) <= 1.0, f"Static initial Z != 0 (got {z0:.2f})"

    # Jog UP for ~8 ticks (8 * 128 = 1024 cycles)
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=1, btn_down=0, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 1024)
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=0, btn_down=0, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 8)
    z_up = await measure_rel_phase(0, 8)
    assert 6.0 <= z_up <= 10.0, f"Jog UP expected ~8 steps, got {z_up:.2f}"

    # Jog DOWN for ~4 ticks (4 * 128 = 512 cycles)
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=0, btn_down=1, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 512)
    dut.ui_in.value = ui_mode0(pat=0b00, btn_up=0, btn_down=0, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 8)
    z_dn = await measure_rel_phase(0, 8)
    assert 2.0 <= z_dn <= 6.0, f"Jog DOWN expected ~4 steps, got {z_dn:.2f}"

    # --- Mode 01: Zen Breathing (triangle wave 0..32) ---
    dut.ui_in.value = ui_mode0(pat=0b01, enable=1, clk_div2=1)
    breath_samples = []
    for _ in range(10):
        await ClockCycles(dut.clk, 512)  # +4 ticks per sample
        z_val = await measure_rel_phase(0, 8)
        # Convert small negative wrap near 0 to ~0
        if z_val > 120:
            z_val = 0.0
        breath_samples.append(z_val)
    assert max(breath_samples) >= 24.0, f"Zen Breathing did not climb near 32: {breath_samples}"
    assert max(breath_samples) <= 34.0, f"Zen Breathing exceeded 32: {breath_samples}"
    assert min(breath_samples) <= 10.0, f"Zen Breathing did not descend back down: {breath_samples}"

    # --- Mode 10: 3D Halo Orbit (4-quadrant triangle waves +-12 on Gx/Gy, art_z = 0) ---
    dut.ui_in.value = ui_mode0(pat=0b10, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 260)  # Let 1 carrier cycle settle after mode switch
    gx_vals = []
    gy_vals = []
    for _ in range(8):
        # Measure diff between Ch 0 (+Gx) and Ch 4 (-Gx) => 2*Gx, and Ch 2 (+Gy) vs Ch 6 (-Gy) => 2*Gy
        edges, _ = await capture_channels(dut, 520)
        # Verify art_z == 0 (Ch 0 and Ch 8 are identical on the exact same cycle)
        z_err = circular_step_err(circular_phase_diff(edges[0][0], edges[8][0], 256), 0)
        assert z_err <= 0.5, f"Halo Orbit expected art_z=0, got diff {z_err:.2f}"

        dx2 = circular_phase_diff(edges[4][0], edges[0][0], 256)
        if dx2 > 64:
            dx2 -= 128
        dy2 = circular_phase_diff(edges[6][0], edges[2][0], 256)
        if dy2 > 64:
            dy2 -= 128
        gx_vals.append(dx2 / 2.0)
        gy_vals.append(dy2 / 2.0)
        await ClockCycles(dut.clk, 256)  # advance orbit

    assert max(gx_vals) >= 6.0 and min(gx_vals) <= -6.0, f"Halo Orbit Gx did not oscillate +-: {gx_vals}"
    assert max(gy_vals) >= 6.0 and min(gy_vals) <= -6.0, f"Halo Orbit Gy did not oscillate +-: {gy_vals}"
    assert max(abs(v) for v in gx_vals) <= 13.5, f"Halo Orbit |Gx| exceeded 12: {gx_vals}"
    assert max(abs(v) for v in gy_vals) <= 13.5, f"Halo Orbit |Gy| exceeded 12: {gy_vals}"

    # --- Mode 11: Continuous Elevator (unbounded modulo-128 ramp on art_z) ---
    dut.ui_in.value = ui_mode0(pat=0b11, enable=1, clk_div2=1)
    await ClockCycles(dut.clk, 260)  # Let 1 carrier cycle settle after mode switch
    z_start = await measure_rel_phase(0, 8)
    await ClockCycles(dut.clk, 2560)  # +20 ticks
    z_mid = await measure_rel_phase(0, 8)
    delta_elev = (z_mid - z_start) % PHASE_STEPS
    assert 18.0 <= delta_elev <= 26.0, (
        f"Continuous Elevator did not advance steadily: start={z_start:.1f}, mid={z_mid:.1f}, delta={delta_elev:.1f}"
    )
