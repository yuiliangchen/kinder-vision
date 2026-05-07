from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if sys.platform == "darwin":
    plt.rcParams["font.sans-serif"] = [
        "PingFang TC",
        "Heiti TC",
        "STHeiti",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def save_heatmap_png(grid: list[list[float]] | np.ndarray, out_path: Path, title: str = "教室熱區 (3×3)") -> Path:
    """grid: 3×3 比例矩陣，輸出 docs/agents/macro_analytics.md 所述之熱力圖檔。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    H = np.asarray(grid, dtype=np.float64)
    if H.size != 9:
        H = np.zeros((3, 3))
    H = H.reshape(3, 3)
    fig, ax = plt.subplots(figsize=(4, 3.5))
    im = ax.imshow(H, cmap="YlOrRd", vmin=0, vmax=max(float(H.max()), 0.05))
    ax.set_xticks([0, 1, 2], labels=["左", "中", "右"])
    ax.set_yticks([0, 1, 2], labels=["上", "中", "下"])
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def save_trajectory_png(
    xy_norm: np.ndarray,
    out_path: Path,
    title: str = "髖部軌跡 (正規化座標)",
) -> Path:
    """xy_norm: (N,2) 座標約在 [0,1]×[0,1]（畫面寬高比例）。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(4, 3.5))
    if xy_norm.size and xy_norm.shape[0] >= 2:
        ax.plot(xy_norm[:, 0], 1.0 - xy_norm[:, 1], "-", color="steelblue", linewidth=1.2, alpha=0.85)
        ax.scatter(xy_norm[0, 0], 1.0 - xy_norm[0, 1], c="green", s=36, zorder=3, label="起點")
        ax.scatter(xy_norm[-1, 0], 1.0 - xy_norm[-1, 1], c="red", s=36, zorder=3, label="終點")
        ax.legend(loc="upper right", fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel("水平 (0=左, 1=右)")
    ax.set_ylabel("垂直 (0=下, 1=上)")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
