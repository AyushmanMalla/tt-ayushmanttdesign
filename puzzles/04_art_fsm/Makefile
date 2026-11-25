# Puzzle 04: Standalone Kinetic Art Engine (src/aether_art_fsm.v)

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

SRC_DIR = $(PWD)/../../src
VERILOG_SOURCES += $(SRC_DIR)/aether_art_fsm.v

TOPLEVEL = aether_art_fsm
COCOTB_TEST_MODULES = test_puzzle

include $(shell cocotb-config --makefiles)/Makefile.sim
