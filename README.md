![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# AyushmanTTDesign — Tiny Tapeout Verilog Project (GF180MCU)

- [Read the documentation for project](docs/info.md)

## Open-Source ASIC Workflow (macOS & Make)

This project uses a full open-source RTL-to-GDSII flow targeting the GlobalFoundries 180nm (`gf180mcuD`) PDK:
- **RTL Design**: Verilog-2005 (`src/project.v`, top module `tt_um_ayushmanmalla_top`)
- **Verification**: [cocotb](https://www.cocotb.org/) + Icarus Verilog (`test/tb.v`, `test/test.py`) + [Surfer](https://surfer-project.org/)
- **Lint & Synthesis**: Verilator & Yosys
- **ASIC Implementation (RTL-to-GDSII)**: [LibreLane](https://librelane.readthedocs.io/) (OpenROAD, Yosys, Magic, Netgen, KLayout)

### 1. Environment Setup (macOS)

Run the centralized setup script via Make to install Homebrew dependencies, clone `tt-support-tools` into `./tt`, create the repo-local Python environment in `./.venv`, and enable the `gf180mcuD` PDK in `./.pdk`:

```sh
make setup
```

*(Optional)* Activate the repo-local environment directly in your shell:

```sh
source env.sh
```

### 2. Make Targets

| Command | Description |
| :--- | :--- |
| `make help` | Show all available targets |
| `make setup` | Install macOS toolchain, `./tt`, `./.venv`, and `./.pdk` |
| `make lint` | Run Verilator lint and Tiny Tapeout port/configuration checks |
| `make sim` | Run cocotb RTL verification (`test/test.py`) |
| `make waves` | View simulation waveforms (`test/tb.fst`) in Surfer |
| `make synth` | Run fast local Yosys synthesis and cell count check |
| `make config` | Generate LibreLane configuration (`src/config_merged.json`) |
| `make impl` | Run full LibreLane RTL-to-GDSII flow (`./tt/tt_tool.py --harden --gf`) |
| `make sim-gl` | Run Gate-Level cocotb verification against the hardened netlist |
| `make stats` | Print synthesis warnings, routing utilization, and cell summary |
| `make openroad` | Open hardened design in OpenROAD GUI |
| `make klayout` | Open hardened design in KLayout |
| `make png` | Render GDSII layout to `gds_render.png` |
| `make docs` | Validate `info.yaml` and `docs/info.md` |
| `make clean` | Clean simulation and temporary build files |

## Enable GitHub actions to build the results page

- [Enabling GitHub Pages](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part)

## Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)
- [Build your design locally](https://www.tinytapeout.com/guides/local-hardening/)

## What next?

- [Submit your design to the next shuttle](https://app.tinytapeout.com/).
- Edit [this README](README.md) and explain your design, how it works, and how to test it.
- Share your project on your social network of choice:
  - LinkedIn [#tinytapeout](https://www.linkedin.com/search/results/content/?keywords=%23tinytapeout) [@TinyTapeout](https://www.linkedin.com/company/100708654/)
  - Mastodon [#tinytapeout](https://chaos.social/tags/tinytapeout) [@matthewvenn](https://chaos.social/@matthewvenn)
  - X (formerly Twitter) [#tinytapeout](https://twitter.com/hashtag/tinytapeout) [@tinytapeout](https://twitter.com/tinytapeout)
  - Bluesky [@tinytapeout.com](https://bsky.app/profile/tinytapeout.com)
