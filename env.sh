#!/usr/bin/env bash
# Source this file ("source env.sh") to activate the repo-local ASIC toolchain in your current shell.

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _TT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  _TT_ROOT="$(cd "$(dirname "${(%):-%x}")" && pwd)"
else
  _TT_ROOT="$(pwd)"
fi

export PDK_ROOT="${_TT_ROOT}/.pdk"
export PDK="gf180mcuD"
export LIBRELANE_TAG="3.0.14"
export TT_ARGS="--gf"
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"

if [[ -f "${_TT_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${_TT_ROOT}/.venv/bin/activate"
  echo "[env] Activated .venv | PDK=${PDK} | PDK_ROOT=${PDK_ROOT}"
else
  echo "[env] Warning: ${_TT_ROOT}/.venv not found. Run 'make setup' first."
fi

unset _TT_ROOT
