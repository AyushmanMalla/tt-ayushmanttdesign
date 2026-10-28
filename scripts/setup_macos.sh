#!/usr/bin/env bash
# Centralized macOS Toolchain & Environment Setup for Tiny Tapeout (gf180mcuD / LibreLane / cocotb)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PDK_ROOT_DIR="${PDK_ROOT:-${ROOT_DIR}/.pdk}"
TT_DIR="${ROOT_DIR}/tt"
PDK_NAME="${PDK:-gf180mcuD}"
PDK_FAMILY="gf180mcu"
LIBRELANE_VERSION="${LIBRELANE_TAG:-3.0.14}"
TT_TOOLS_REPO="https://github.com/TinyTapeout/tt-support-tools.git"
TT_TOOLS_REF="${TT_TOOLS_REF:-main}"

SKIP_BREW=0
SKIP_PDK=0
SKIP_DOCKER=0
START_COLIMA=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Sets up the open-source ASIC design & verification environment on macOS:
  - Homebrew packages (icarus-verilog, verilator, yosys, surfer, cairo/libpng/qhull/librsvg/pngquant, colima/docker)
  - Tiny Tapeout support tools in ./tt
  - Repo-local Python virtual environment in ./.venv (cocotb, pytest, librelane==${LIBRELANE_VERSION})
  - Repo-local ${PDK_NAME} PDK in ./.pdk via ciel

Options:
  --skip-brew      Skip Homebrew package checks/installations
  --skip-pdk       Skip downloading/enabling the ${PDK_NAME} PDK in ./.pdk
  --skip-docker    Skip checking/installing Docker CLI & Colima
  --start-colima   Start the Colima container runtime after installation
  -h, --help       Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-brew)    SKIP_BREW=1; shift ;;
    --skip-pdk)     SKIP_PDK=1; shift ;;
    --skip-docker)  SKIP_DOCKER=1; shift ;;
    --start-colima) START_COLIMA=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

log()  { printf "\033[1;34m[setup]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m[  ok ]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn ]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; }

if [[ "$(uname -s)" != "Darwin" ]]; then
  warn "This script is tailored for macOS (Darwin), detected $(uname -s). Proceeding with compatible steps..."
fi

# 1. Homebrew & Native Toolchain Packages
if [[ "${SKIP_BREW}" -eq 0 ]] && [[ "$(uname -s)" == "Darwin" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    err "Homebrew is not installed. Install it from https://brew.sh and re-run."
    exit 1
  fi

  BREW_PACKAGES=(
    icarus-verilog
    verilator
    yosys
    surfer
    libpng
    qhull
    cairo
    librsvg
    pngquant
  )

  if [[ "${SKIP_DOCKER}" -eq 0 ]]; then
    if ! command -v docker >/dev/null 2>&1; then
      BREW_PACKAGES+=(docker colima)
    fi
  fi

  MISSING_BREW=()
  for pkg in "${BREW_PACKAGES[@]}"; do
    if ! brew list --versions "${pkg}" >/dev/null 2>&1; then
      MISSING_BREW+=("${pkg}")
    fi
  done

  if [[ ${#MISSING_BREW[@]} -gt 0 ]]; then
    log "Installing missing Homebrew packages: ${MISSING_BREW[*]}"
    brew install "${MISSING_BREW[@]}"
  else
    ok "All required Homebrew packages are installed"
  fi

  if [[ "${SKIP_DOCKER}" -eq 0 ]] && [[ "${START_COLIMA}" -eq 1 ]]; then
    if command -v colima >/dev/null 2>&1; then
      if ! colima status >/dev/null 2>&1; then
        log "Starting Colima VM (4 CPUs, 8 GiB RAM)..."
        colima start --cpu 4 --memory 8
      else
        ok "Colima VM is already running"
      fi
    fi
  fi
fi

# 2. Clone or update TinyTapeout/tt-support-tools in ./tt
if [[ ! -d "${TT_DIR}/.git" ]]; then
  log "Cloning TinyTapeout/tt-support-tools (${TT_TOOLS_REF}) into ${TT_DIR}..."
  rm -rf "${TT_DIR}"
  git clone --depth 1 --branch "${TT_TOOLS_REF}" "${TT_TOOLS_REPO}" "${TT_DIR}"
  ok "Cloned tt-support-tools into ./tt"
else
  ok "tt-support-tools already present in ./tt"
fi

# 3. Create Repo-Local Python Virtual Environment (./.venv)
if [[ ! -d "${VENV_DIR}" ]]; then
  log "Creating Python virtual environment at ${VENV_DIR}..."
  if command -v uv >/dev/null 2>&1; then
    uv venv "${VENV_DIR}" --python 3.12 --seed
  else
    python3 -m venv "${VENV_DIR}"
  fi
fi

# Activate venv for installation steps
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"

log "Installing Python dependencies (cocotb, tt-support-tools, librelane==${LIBRELANE_VERSION})..."
if command -v uv >/dev/null 2>&1; then
  uv pip install --upgrade pip
  uv pip install -r "${ROOT_DIR}/test/requirements.txt" -r "${TT_DIR}/requirements.txt" "librelane==${LIBRELANE_VERSION}"
else
  pip install --upgrade pip
  pip install -r "${ROOT_DIR}/test/requirements.txt" -r "${TT_DIR}/requirements.txt" "librelane==${LIBRELANE_VERSION}"
fi
ok "Python packages installed in ./.venv"

# 4. Install / Enable Repo-Local GF180MCU PDK in ./.pdk
mkdir -p "${PDK_ROOT_DIR}"
if [[ "${SKIP_PDK}" -eq 0 ]]; then
  if [[ -f "${PDK_ROOT_DIR}/${PDK_NAME}/SOURCES" ]]; then
    ok "PDK ${PDK_NAME} already enabled at ${PDK_ROOT_DIR}/${PDK_NAME}"
  else
    log "Resolving open_pdks revision for LibreLane ${LIBRELANE_VERSION}..."
    OPDKS_REV="$(python -c "from librelane.common import get_pdk_hash; print(get_pdk_hash('${PDK_NAME}'))")"
    log "Enabling ${PDK_FAMILY} (${PDK_NAME}, rev ${OPDKS_REV}) in ${PDK_ROOT_DIR} via ciel..."
    ciel enable --pdk-family "${PDK_FAMILY}" --pdk-root "${PDK_ROOT_DIR}" "${OPDKS_REV}"
    ok "Enabled ${PDK_NAME} at ${PDK_ROOT_DIR}/${PDK_NAME}"
  fi
else
  warn "Skipped PDK download (--skip-pdk). Run 'make pdk' or re-run without --skip-pdk before hardening or GL sim."
fi

# 5. Summary
echo ""
ok "Environment setup complete!"
cat <<EOF
  Project Root : ${ROOT_DIR}
  Python Venv  : ${VENV_DIR}
  PDK Root     : ${PDK_ROOT_DIR} (PDK=${PDK_NAME})
  TT Tools     : ${TT_DIR}
  LibreLane    : $(python -m librelane --version 2>/dev/null | head -n 1 || echo "${LIBRELANE_VERSION}")
  Icarus       : $(iverilog -V 2>/dev/null | head -n 1 || echo "not found")
  Verilator    : $(verilator --version 2>/dev/null | head -n 1 || echo "not found")
  Yosys        : $(yosys -V 2>/dev/null | head -n 1 || echo "not found")

Next steps:
  1. Optional shell activation : source env.sh
  2. Run RTL lint & checks     : make lint
  3. Run cocotb RTL tests      : make sim
  4. Run local Yosys synthesis : make synth
  5. Run full LibreLane GDSII  : make impl   (requires Docker/Colima running)
  6. Run Gate-Level cocotb sim : make sim-gl
EOF
