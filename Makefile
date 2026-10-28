# Root Makefile for Tiny Tapeout Open-Source ASIC Workflow (Verilog + cocotb + Yosys + LibreLane)

SHELL := /bin/bash

ROOT_DIR      := $(CURDIR)
VENV_DIR      := $(ROOT_DIR)/.venv
PYTHON        := $(if $(wildcard $(VENV_DIR)/bin/python3),$(VENV_DIR)/bin/python3,python3)
CIEL          := $(if $(wildcard $(VENV_DIR)/bin/ciel),$(VENV_DIR)/bin/ciel,ciel)
PDK_ROOT      ?= $(ROOT_DIR)/.pdk
PDK           ?= gf180mcuD
TT_DIR        := $(ROOT_DIR)/tt
TT_SCRIPT     := $(TT_DIR)/tt_tool.py
# On macOS (Apple Silicon / Intel), Homebrew shared libraries (e.g. libcairo.2.dylib) live in /opt/homebrew/lib or /usr/local/lib.
# Invoke python3 directly rather than via /usr/bin/env shebang so macOS SIP does not strip DYLD_FALLBACK_LIBRARY_PATH.
TT_ENV        := DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:$${DYLD_FALLBACK_LIBRARY_PATH:-}"
TT_TOOL       := $(TT_ENV) $(PYTHON) $(TT_SCRIPT)
TT_ARGS       ?= --gf

TOP_MODULE    ?= tt_um_ayushmanmalla_top
SRC_DIR       := $(ROOT_DIR)/src
TEST_DIR      := $(ROOT_DIR)/test
VERILOG_SRCS  := $(SRC_DIR)/project.v

# Automatically prepend .venv/bin to PATH when present
ifneq ($(wildcard $(VENV_DIR)/bin),)
  export PATH := $(VENV_DIR)/bin:$(PATH)
endif

export PDK_ROOT
export PDK

STDCELL_LIB   := $(PDK_ROOT)/$(PDK)/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
GL_NETLIST    := $(ROOT_DIR)/runs/wokwi/final/pnl/$(TOP_MODULE).pnl.v

.PHONY: help setup pdk colima lint sim test sim-gl test-gl waves synth config impl harden gds stats submission png svg docs openroad klayout clean distclean

help:
	@echo "================================================================================"
	@echo "  Tiny Tapeout Open-Source ASIC Flow ($(TOP_MODULE) | PDK: $(PDK))"
	@echo "================================================================================"
	@echo "Environment & Setup:"
	@echo "  make setup        Install macOS tools, ./tt, ./.venv, and ./.pdk ($(PDK))"
	@echo "  make pdk          Download/enable $(PDK) PDK in ./.pdk via ciel"
	@echo "  make colima       Start Colima Docker runtime on macOS (for LibreLane)"
	@echo ""
	@echo "Verification & Linting:"
	@echo "  make lint         Run Verilator lint & Tiny Tapeout port/config checks"
	@echo "  make sim          Run cocotb RTL simulation (alias: make test)"
	@echo "  make sim-gl       Run cocotb Gate-Level simulation (alias: make test-gl)"
	@echo "  make waves        Open waveform (test/tb.fst) in Surfer"
	@echo ""
	@echo "Synthesis & Implementation (LibreLane / OpenROAD):"
	@echo "  make synth        Run fast local Yosys synthesis & cell usage report"
	@echo "  make config       Generate LibreLane user_config.json & config_merged.json"
	@echo "  make impl         Run full RTL-to-GDSII LibreLane flow (aliases: harden, gds)"
	@echo "  make stats        Print synthesis warnings, routing stats & cell summary"
	@echo "  make submission   Package hardened outputs into tt_submission/"
	@echo ""
	@echo "Visualization & Documentation:"
	@echo "  make openroad     Open hardened design in OpenROAD GUI"
	@echo "  make klayout      Open hardened design in KLayout"
	@echo "  make png          Render GDSII layout to gds_render.png"
	@echo "  make docs         Validate info.yaml/docs and build datasheet"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        Remove simulation & temporary config build artifacts"
	@echo "  make distclean    Remove all build outputs, runs/, .venv/, .pdk/, and tt/"
	@echo "================================================================================"

# ------------------------------------------------------------------------------
# Setup & Environment
# ------------------------------------------------------------------------------

setup:
	./scripts/setup_macos.sh $(SETUP_ARGS)

pdk:
	@mkdir -p "$(PDK_ROOT)"
	@OPDKS_REV=$$($(PYTHON) -c "from librelane.common import get_pdk_hash; print(get_pdk_hash('$(PDK)'))"); \
	echo "[pdk] Enabling gf180mcu ($(PDK), rev $$OPDKS_REV) in $(PDK_ROOT)..."; \
	$(CIEL) enable --pdk-family gf180mcu --pdk-root "$(PDK_ROOT)" "$$OPDKS_REV"

colima:
	@if command -v colima >/dev/null 2>&1; then \
		colima status >/dev/null 2>&1 || colima start --cpu 4 --memory 8; \
	else \
		echo "Colima is not installed. Run 'make setup' or install Docker Desktop / Colima."; \
		exit 1; \
	fi

# ------------------------------------------------------------------------------
# Linting & Verification (cocotb)
# ------------------------------------------------------------------------------

lint:
	@echo "[lint] Running Verilator lint on $(VERILOG_SRCS)..."
	verilator --lint-only -Wall -Wno-DECLFILENAME -I$(SRC_DIR) --top-module $(TOP_MODULE) $(VERILOG_SRCS)
	@if [ -f "$(TT_SCRIPT)" ]; then \
		echo "[lint] Validating Tiny Tapeout port interface & YAML config..."; \
		$(TT_TOOL) --create-user-config $(TT_ARGS); \
	fi
	@echo "[lint] All checks passed!"

sim:
	@echo "[sim] Running cocotb RTL simulation..."
	$(MAKE) -C $(TEST_DIR) clean
	$(MAKE) -C $(TEST_DIR)
	$(PYTHON) -m cocotb_tools.check_results $(TEST_DIR)/results.xml

test: sim

sim-gl:
	@if [ ! -f "$(GL_NETLIST)" ]; then \
		echo "Error: Gate-level netlist not found at $(GL_NETLIST). Run 'make impl' first."; \
		exit 1; \
	fi
	@if [ ! -d "$(PDK_ROOT)/$(PDK)" ]; then \
		echo "Error: PDK not found at $(PDK_ROOT)/$(PDK). Run 'make pdk' or 'make setup' first."; \
		exit 1; \
	fi
	@echo "[sim-gl] Copying gate-level netlist and running cocotb GL simulation..."
	cp "$(GL_NETLIST)" "$(TEST_DIR)/gate_level_netlist.v"
	$(MAKE) -C $(TEST_DIR) clean
	$(MAKE) -C $(TEST_DIR) GATES=yes PDK_ROOT="$(PDK_ROOT)"
	$(PYTHON) -m cocotb_tools.check_results $(TEST_DIR)/results.xml

test-gl: sim-gl

waves:
	@if [ ! -f "$(TEST_DIR)/tb.fst" ]; then \
		echo "Waveform $(TEST_DIR)/tb.fst not found. Running 'make sim' first..."; \
		$(MAKE) sim; \
	fi
	@if command -v surfer >/dev/null 2>&1; then \
		surfer "$(TEST_DIR)/tb.fst"; \
	elif command -v gtkwave >/dev/null 2>&1; then \
		gtkwave "$(TEST_DIR)/tb.fst"; \
	else \
		echo "Neither surfer nor gtkwave found in PATH."; \
		exit 1; \
	fi

# ------------------------------------------------------------------------------
# Synthesis & Implementation (Yosys & LibreLane)
# ------------------------------------------------------------------------------

synth:
	@echo "[synth] Running local Yosys synthesis for $(TOP_MODULE)..."
	@if [ -f "$(STDCELL_LIB)" ]; then \
		echo "[synth] Mapping to $(PDK) standard cells ($(STDCELL_LIB))..."; \
		yosys -QT -p "read_liberty -lib $(STDCELL_LIB); read_verilog -sv $(VERILOG_SRCS); synth -nordff -top $(TOP_MODULE); dfflibmap -liberty $(STDCELL_LIB); abc -liberty $(STDCELL_LIB); opt_clean -purge; check -assert; stat -liberty $(STDCELL_LIB)"; \
	else \
		echo "[synth] Standard cell liberty not found in .pdk (generic synthesis)..."; \
		yosys -QT -p "read_verilog -sv $(VERILOG_SRCS); synth -nordff -top $(TOP_MODULE); opt_clean -purge; check -assert; stat"; \
	fi

config:
	@if [ ! -f "$(TT_SCRIPT)" ]; then \
		echo "Error: $(TT_SCRIPT) not found. Run 'make setup' first."; \
		exit 1; \
	fi
	$(TT_TOOL) --create-user-config $(TT_ARGS)

impl: config
	@if ! docker info >/dev/null 2>&1; then \
		echo "Error: Docker daemon is not running. Start Docker Desktop or run 'make colima'."; \
		exit 1; \
	fi
	@echo "[impl] Running LibreLane RTL-to-GDSII flow for $(TOP_MODULE) (PDK=$(PDK))..."
	$(TT_TOOL) --harden $(TT_ARGS)
	@$(MAKE) stats

harden: impl
gds: impl

stats:
	@$(TT_TOOL) --print-warnings $(TT_ARGS)
	@$(TT_TOOL) --print-stats $(TT_ARGS)
	@$(TT_TOOL) --print-cell-category $(TT_ARGS)

submission:
	$(TT_TOOL) --create-tt-submission $(TT_ARGS)

# ------------------------------------------------------------------------------
# Visualization & Documentation
# ------------------------------------------------------------------------------

openroad:
	$(TT_TOOL) --open-in-openroad $(TT_ARGS)

klayout:
	$(TT_TOOL) --open-in-klayout $(TT_ARGS)

png:
	$(TT_TOOL) --create-png $(TT_ARGS)

svg:
	$(TT_TOOL) --create-svg $(TT_ARGS)

docs:
	$(TT_TOOL) --check-docs $(TT_ARGS)

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------

clean:
	$(MAKE) -C $(TEST_DIR) clean
	rm -rf $(TEST_DIR)/sim_build $(TEST_DIR)/results.xml $(TEST_DIR)/tb.fst $(TEST_DIR)/gate_level_netlist.v $(TEST_DIR)/__pycache__
	rm -f $(SRC_DIR)/user_config.json $(SRC_DIR)/config_merged.json ports.json

distclean: clean
	rm -rf runs tt_submission gds_render*.png gds_render*.svg $(VENV_DIR) $(PDK_ROOT) $(TT_DIR)
