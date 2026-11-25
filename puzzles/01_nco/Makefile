# Puzzle 01: 20-bit Tunable NCO (src/aether_nco.v)

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

SRC_DIR = $(PWD)/../../src
VERILOG_SOURCES += $(SRC_DIR)/aether_nco.v

TOPLEVEL = aether_nco
COCOTB_TEST_MODULES = test_puzzle

include $(shell cocotb-config --makefiles)/Makefile.sim
