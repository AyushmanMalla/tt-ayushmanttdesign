# SPDX-FileCopyrightText: © 2026 Ayushman Malla
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

# Expected 7-segment encodings (DP=0, segments G..A) for digits 0..7
SEG7_DIGITS = [
    0x3F,  # 0: 0011_1111
    0x06,  # 1: 0000_0110
    0x5B,  # 2: 0101_1011
    0x4F,  # 3: 0100_1111
    0x66,  # 4: 0110_0110
    0x6D,  # 5: 0110_1101
    0x7D,  # 6: 0111_1101
    0x07,  # 7: 0000_0111
]


@cocotb.test()
async def test_counter_and_7seg(dut):
    dut._log.info("Starting 3-bit counter + 7-segment decoder test")

    # Set the clock period to 10 us (100 KHz)
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # Assert synchronous active-low reset
    dut._log.info("Applying synchronous reset")
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)

    # Settle after clock edge and verify reset state (digit 0)
    await Timer(1, unit="us")
    assert int(dut.uo_out.value) == SEG7_DIGITS[0], (
        f"Expected reset output 0x{SEG7_DIGITS[0]:02X}, got 0x{int(dut.uo_out.value):02X}"
    )
    assert int(dut.uio_out.value) == 0
    assert int(dut.uio_oe.value) == 0

    # Release reset before the next rising clock edge
    dut.rst_n.value = 1

    # Verify two full cycles (0..7, 0..7)
    for cycle in range(2):
        for digit, expected in enumerate(SEG7_DIGITS):
            await Timer(1, unit="us")
            actual = int(dut.uo_out.value)
            dut._log.info(
                f"Cycle {cycle} digit {digit}: uo_out=0x{actual:02X} (expected 0x{expected:02X})"
            )
            assert actual == expected, (
                f"Mismatch at cycle {cycle}, digit {digit}: got 0x{actual:02X}, expected 0x{expected:02X}"
            )
            await RisingEdge(dut.clk)
