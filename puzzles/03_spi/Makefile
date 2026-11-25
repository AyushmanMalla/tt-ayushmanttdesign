# Puzzle 03: 2-FF Synchronized SPI Mode 0 Slave (src/aether_spi.v)

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

SRC_DIR = $(PWD)/../../src
VERILOG_SOURCES += $(SRC_DIR)/aether_spi.v

TOPLEVEL = aether_spi
COCOTB_TEST_MODULES = test_puzzle

include $(shell cocotb-config --makefiles)/Makefile.sim
