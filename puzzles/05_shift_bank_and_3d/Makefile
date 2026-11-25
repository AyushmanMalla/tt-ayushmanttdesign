# Puzzle 05: 2x8 Rotating Shift-Bank TDM, 3D Ring Pipeline & Acoustic Vortex

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

SRC_DIR = $(PWD)/../../src
VERILOG_SOURCES += $(SRC_DIR)/project.v \
                   $(SRC_DIR)/aether_nco.v \
                   $(SRC_DIR)/aether_spi.v \
                   $(SRC_DIR)/aether_art_fsm.v \
                   $(SRC_DIR)/aether_channel.v

TOPLEVEL = tt_um_ayushmanmalla_top
COCOTB_TEST_MODULES = test_puzzle

include $(shell cocotb-config --makefiles)/Makefile.sim
