# Puzzle 02: Glitch-Free Ultrasonic PWM Channel (src/aether_channel.v)

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

SRC_DIR = $(PWD)/../../src
VERILOG_SOURCES += $(SRC_DIR)/aether_channel.v

TOPLEVEL = aether_channel
COCOTB_TEST_MODULES = test_puzzle

include $(shell cocotb-config --makefiles)/Makefile.sim
