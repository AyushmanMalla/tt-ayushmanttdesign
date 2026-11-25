#!/usr/bin/env python3
"""
AETHER-16 — 3D Acoustic Field & Gor'kov Potential Simulator

Computes the physical 40 kHz Huygens-Fresnel acoustic pressure field p(x, y, z)
and Gor'kov acoustic radiation potential U(x, y, z) for a 2 mm EPS sphere
suspended inside the AETHER-16 dual-opposing 2x8 concave ring geometry.

Supports:
  1. Direct phase-vector input (e.g., exported from cocotb RTL simulation)
  2. Built-in visualization of Standing-Wave Traps, Z-Elevator, 3D Halo Orbit,
     and Acoustic Vortex signature modes.

Outputs high-resolution PNG figures (and optional animated GIF) suitable for
docs/info.md and engineering verification reports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

# Physical constants (Singapore ambient air @ ~27 C)
C_AIR = 347.0           # Speed of sound in air (m/s)
RHO_AIR = 1.18          # Air density (kg/m^3)
F_ULTRA = 40_000.0      # Nominal ultrasonic frequency (Hz)
LAMBDA = C_AIR / F_ULTRA  # ~8.675 mm
K_WAVE = 2.0 * np.pi / LAMBDA

# 2 mm EPS foam bead parameters
BEAD_RADIUS = 1.0e-3    # 1.0 mm radius (2.0 mm diameter)
RHO_BEAD = 25.0         # EPS density (kg/m^3)
C_BEAD = 900.0          # Approx speed of sound in EPS (m/s)
F1 = 1.0 - (RHO_AIR * C_AIR**2) / (RHO_BEAD * C_BEAD**2)
F2 = 2.0 * (RHO_BEAD - RHO_AIR) / (2.0 * RHO_BEAD + RHO_AIR)

# Transducer parameters (10 mm 40 kHz MA40S4S / TCT40-10T @ 24 Vpp diff drive)
TRANS_RADIUS = 5.0e-3   # 5 mm piston radius
P0_REF = 12.0           # Effective pressure scaling per transducer at 1 m (Pa*m)


def build_dual_ring_geometry(
    ring_radius: float = 18.0e-3,
    dish_sep: float = 72.0e-3,
    focal_radius: float = 55.0e-3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build the symmetric 2x8 dual-opposing concave ring transducer array.

    Channels 0..7  : Bottom ring (45 deg spacing, open ~16 mm central aperture)
    Channels 8..15 : Top ring (mirror image at z = +dish_sep/2)

    Returns:
      positions : (16, 3) transducer center coordinates in meters
      normals   : (16, 3) unit normal vectors aimed toward the central focus
    """
    angles = np.arange(8) * (np.pi / 4.0)  # 0, 45, ..., 315 deg
    z_half = dish_sep / 2.0

    # Slight concave tilt aiming transducers toward the origin (0, 0, 0)
    tilt = np.arcsin(np.clip(ring_radius / focal_radius, 0.0, 0.7))

    positions = np.zeros((16, 3))
    normals = np.zeros((16, 3))

    for k, ang in enumerate(angles):
        ca, sa = np.cos(ang), np.sin(ang)
        # Bottom ring (Ch 0..7)
        positions[k] = [ring_radius * ca, ring_radius * sa, -z_half]
        normals[k] = [-np.sin(tilt) * ca, -np.sin(tilt) * sa, np.cos(tilt)]
        # Top ring (Ch 8..15)
        positions[k + 8] = [ring_radius * ca, ring_radius * sa, +z_half]
        normals[k + 8] = [-np.sin(tilt) * ca, -np.sin(tilt) * sa, -np.cos(tilt)]

    return positions, normals


def piston_directivity(sin_theta: np.ndarray) -> np.ndarray:
    """Far-field circular piston directivity 2*J1(k*a*sin(theta))/(k*a*sin(theta))."""
    x = K_WAVE * TRANS_RADIUS * sin_theta
    # Accurate rational/series approximation for 2*J1(x)/x without scipy dependency
    # Using Bessel J1 via integral or Taylor + Hankel — use numpy trapezoid for exact J1!
    # For x <= 4 (covers 0..90 deg since k*a = 3.62), 8-term Taylor series is exact to <1e-10!
    x2 = x * x
    val = np.ones_like(x)
    term = np.ones_like(x)
    for m in range(1, 12):
        term = term * (-x2) / (4.0 * m * (m + 1))
        val = val + term
    return val


def compute_pressure_and_gorkov(
    positions: np.ndarray,
    normals: np.ndarray,
    phases_rad: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_z: np.ndarray,
    amplitudes: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute complex acoustic pressure p(r) and Gor'kov potential U(r) on a 2D slice grid.
    """
    if amplitudes is None:
        amplitudes = np.ones(len(positions))

    # Evaluate pressure and finite-difference gradient for velocity term
    eps = 0.25e-3  # 0.25 mm finite difference step

    def eval_p(gx: np.ndarray, gy: np.ndarray, gz: np.ndarray) -> np.ndarray:
        p = np.zeros_like(gx, dtype=np.complex128)
        for i in range(len(positions)):
            if amplitudes[i] <= 0.0:
                continue
            dx = gx - positions[i, 0]
            dy = gy - positions[i, 1]
            dz = gz - positions[i, 2]
            r = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-9
            cos_th = np.clip(
                (dx * normals[i, 0] + dy * normals[i, 1] + dz * normals[i, 2]) / r,
                0.0,
                1.0,
            )
            sin_th = np.sqrt(np.maximum(0.0, 1.0 - cos_th * cos_th))
            direct = piston_directivity(sin_th)
            p += (amplitudes[i] * P0_REF * direct / r) * np.exp(
                1j * (K_WAVE * r + phases_rad[i])
            )
        return p

    p0 = eval_p(grid_x, grid_y, grid_z)
    dp_dx = (eval_p(grid_x + eps, grid_y, grid_z) - eval_p(grid_x - eps, grid_y, grid_z)) / (2 * eps)
    dp_dy = (eval_p(grid_x, grid_y + eps, grid_z) - eval_p(grid_x, grid_y - eps, grid_z)) / (2 * eps)
    dp_dz = (eval_p(grid_x, grid_y, grid_z + eps) - eval_p(grid_x, grid_y, grid_z - eps)) / (2 * eps)

    omega = 2.0 * np.pi * F_ULTRA
    p_rms2 = 0.5 * np.abs(p0) ** 2
    v_rms2 = 0.5 * (np.abs(dp_dx) ** 2 + np.abs(dp_dy) ** 2 + np.abs(dp_dz) ** 2) / (
        (RHO_AIR * omega) ** 2
    )

    vol = (4.0 / 3.0) * np.pi * BEAD_RADIUS**3
    u_gorkov = vol * (
        F1 * p_rms2 / (2.0 * RHO_AIR * C_AIR**2)
        - F2 * (3.0 / 4.0) * RHO_AIR * v_rms2
    )
    return p0, u_gorkov


def phases_from_aether_regs(
    phase_bits: int = 6,
    z_off: int = 0,
    grad_x: int = 0,
    grad_y: int = 0,
    top_invert: int = 0,
    vortex: int = 0,
    base_phases: list[int] | None = None,
) -> np.ndarray:
    """Exact bit-accurate model of AETHER-16's 3D ring phase combiner."""
    n_steps = 1 << phase_bits
    half = n_steps >> 1
    sx = [1, 1, 0, -1, -1, -1, 0, 1]
    sy = [0, 1, 1, 1, 0, -1, -1, -1]
    if base_phases is None:
        base_phases = [0] * 16

    eff = np.zeros(16, dtype=int)
    for i in range(16):
        k = i % 8
        ph = base_phases[i]
        if i >= 8:
            ph += z_off + (half if top_invert else 0)
        ph += sx[k] * grad_x + sy[k] * grad_y
        if vortex:
            ph += k * (n_steps // 8)
        eff[i] = ph % n_steps

    return 2.0 * np.pi * eff / n_steps


def render_static_overview(out_path: Path, phase_bits: int = 6) -> None:
    """Render a publication-grade 3-panel acoustic verification figure."""
    positions, normals = build_dual_ring_geometry()

    xs = np.linspace(-22e-3, 22e-3, 121)
    zs = np.linspace(-26e-3, 26e-3, 141)
    gx, gz = np.meshgrid(xs, zs)
    gy = np.zeros_like(gx)

    configs = [
        ("Standing-Wave Lock\n(Z_off = 0, Gx = 0)", phases_from_aether_regs(phase_bits, z_off=0)),
        ("Vertical Elevator Shift\n(Z_off = 90 deg -> +1.08 mm)", phases_from_aether_regs(phase_bits, z_off=1 << (phase_bits - 2))),
        ("3D Halo Tilt Steering\n(Gx = +6 steps)", phases_from_aether_regs(phase_bits, z_off=0, grad_x=6)),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=160, constrained_layout=True)
    fig.patch.set_facecolor("#0d1117")

    for ax, (title, phases) in zip(axes, configs):
        p0, u_gorkov = compute_pressure_and_gorkov(positions, normals, phases, gx, gy, gz)
        u_uj = u_gorkov * 1e6  # microjoules

        vmax = np.percentile(np.abs(u_uj), 96)
        im = ax.pcolormesh(
            xs * 1e3,
            zs * 1e3,
            u_uj,
            cmap="inferno_r",
            shading="auto",
            vmin=-vmax * 0.6,
            vmax=vmax,
        )
        # Overlay local minima (levitation pockets) near the central axis
        center_idx = np.argmin(np.abs(xs))
        u_axis = u_uj[:, center_idx]
        minima = [
            j
            for j in range(2, len(zs) - 2)
            if u_axis[j] < u_axis[j - 1]
            and u_axis[j] < u_axis[j + 1]
            and u_axis[j] < np.percentile(u_axis, 35)
        ]
        # Refine X minimum at each Z pocket
        for j in minima:
            x_best = xs[np.argmin(u_uj[j, 40:81]) + 40] * 1e3
            ax.scatter(
                [x_best],
                [zs[j] * 1e3],
                s=42,
                facecolor="#ffffff",
                edgecolor="#00e5ff",
                linewidth=1.3,
                zorder=5,
            )

        ax.set_title(title, color="#f0f6fc", fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel("X Position (mm)", color="#c9d1d9", fontsize=9.5)
        ax.set_ylabel("Z Position (mm)", color="#c9d1d9", fontsize=9.5)
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="#8b949e", labelsize=8.5)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_aspect("equal")

        cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
        cbar.set_label("Gor'kov Potential U (µJ)", color="#c9d1d9", fontsize=8.5)
        cbar.ax.yaxis.set_tick_params(color="#8b949e", labelsize=8)
        plt.setp(cbar.ax.get_yticklabels(), color="#8b949e")

    fig.suptitle(
        "AETHER-16 — Simulated 40 kHz Dual-Ring Gor'kov Acoustic Levitation Traps (2 mm EPS Spheres)",
        color="#ffffff",
        fontsize=12.5,
        fontweight="bold",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[acoustic-sim] Saved static overview: {out_path}")


def render_from_phase_json(json_path: Path, out_path: Path) -> None:
    """Render acoustic field directly from RTL-simulated phase vectors exported by cocotb."""
    data = json.loads(json_path.read_text())
    phase_bits = int(data.get("phase_bits", 6))
    frames = data["frames"]
    positions, normals = build_dual_ring_geometry()

    xs = np.linspace(-20e-3, 20e-3, 91)
    zs = np.linspace(-24e-3, 24e-3, 105)
    gx, gz = np.meshgrid(xs, zs)
    gy = np.zeros_like(gx)

    n_steps = 1 << phase_bits
    fig, ax = plt.subplots(figsize=(5.6, 5.4), dpi=130)
    fig.patch.set_facecolor("#0d1117")

    u_frames = []
    for fr in frames:
        phases_rad = 2.0 * np.pi * np.array(fr["phases"], dtype=float) / n_steps
        amps = np.array(fr.get("amplitudes", [1.0] * 16), dtype=float)
        _, u_g = compute_pressure_and_gorkov(positions, normals, phases_rad, gx, gy, gz, amps)
        u_frames.append((fr.get("label", ""), u_g * 1e6))

    vmax = max(np.percentile(np.abs(u), 96) for _, u in u_frames)

    def draw_frame(idx: int):
        ax.clear()
        label, u_uj = u_frames[idx]
        ax.pcolormesh(
            xs * 1e3,
            zs * 1e3,
            u_uj,
            cmap="inferno_r",
            shading="auto",
            vmin=-vmax * 0.6,
            vmax=vmax,
        )
        # Mark levitation traps along central column
        c_slice = u_uj[:, 30:61]
        for j in range(2, len(zs) - 2):
            x_min_local = int(np.argmin(c_slice[j]))
            val = c_slice[j, x_min_local]
            if (
                val < c_slice[j - 1, x_min_local]
                and val < c_slice[j + 1, x_min_local]
                and val < np.percentile(u_uj, 25)
            ):
                ax.scatter(
                    [xs[30 + x_min_local] * 1e3],
                    [zs[j] * 1e3],
                    s=52,
                    facecolor="#ffffff",
                    edgecolor="#00e5ff",
                    linewidth=1.4,
                    zorder=5,
                )
        ax.set_title(f"AETHER-16 RTL Output → {label}", color="#f0f6fc", fontsize=10.5, fontweight="bold")
        ax.set_xlabel("X Position (mm)", color="#c9d1d9")
        ax.set_ylabel("Z Position (mm)", color="#c9d1d9")
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="#8b949e")
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_aspect("equal")

    anim = FuncAnimation(fig, draw_frame, frames=len(u_frames), interval=180)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(out_path, writer=PillowWriter(fps=6))
    plt.close(fig)
    print(f"[acoustic-sim] Saved RTL-driven animation: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AETHER-16 Gor'kov Acoustic Field Simulator")
    parser.add_argument("--phase-bits", type=int, default=6, help="Phase resolution bits (6 or 7)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/images/acoustic_trap_xz.png"),
        help="Output PNG path for static 3-panel trap visualization",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="Optional cocotb-exported phase JSON to render animated GIF",
    )
    parser.add_argument(
        "--gif-out",
        type=Path,
        default=Path("docs/images/acoustic_motion.gif"),
        help="Output GIF path when --from-json is provided",
    )
    args = parser.parse_args()

    render_static_overview(args.out, phase_bits=args.phase_bits)
    if args.from_json is not None:
        render_from_phase_json(args.from_json, args.gif_out)


if __name__ == "__main__":
    main()
