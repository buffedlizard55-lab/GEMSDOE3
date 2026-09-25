"""Fault-trace geometry: skeleton endpoints, along-strike tip extension and truncation self-tests.

Motivation (official DrivenData staff answers, retrieved 2026-09-25):
  * https://community.drivendata.org/raw/11536 - "new fault" means any fault pixel not already
    captured by USGS/INGENIOUS and "can include newly mapped geometry of an existing fault system",
    e.g. a continuation beyond a mapped endpoint.
  * https://community.drivendata.org/raw/11516 - the known-fault scoring mask is pixel-exact and
    identical to the provided training labels.

Everything here is label-geometry only. No hidden label, proxy catalogue or submission value is used
to *construct* an extension; catalogues are used only to *measure* extensions.
"""
from __future__ import annotations

from collections import deque

import numpy as np
from scipy.ndimage import convolve, label
from skimage.morphology import skeletonize

_EIGHT = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype="int16")
_STEPS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def skeleton(mask: np.ndarray) -> np.ndarray:
    """One-pixel 8-connected centre lines of a binary raster."""
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2:
        raise ValueError("Need a 2-D mask")
    return skeletonize(m)


def endpoints(skel: np.ndarray) -> np.ndarray:
    """Skeleton pixels with exactly one 8-neighbour (line tips); returns (n, 2) row/col."""
    s = np.asarray(skel, dtype=bool)
    n = convolve(s.astype("int16"), _EIGHT, mode="constant")
    return np.argwhere(s & (n == 1))


def walk_back(skel: np.ndarray, start: tuple[int, int], steps: int) -> list[tuple[int, int]]:
    """Geodesic path from a tip inward, at most `steps` pixels (stops at junction/other tip)."""
    h, w = skel.shape
    path, seen = [tuple(start)], {tuple(start)}
    current = tuple(start)
    for _ in range(steps):
        nxt = [(current[0] + dy, current[1] + dx) for dy, dx in _STEPS
               if 0 <= current[0] + dy < h and 0 <= current[1] + dx < w
               and skel[current[0] + dy, current[1] + dx] and (current[0] + dy, current[1] + dx) not in seen]
        if len(nxt) != 1:  # junction or end: direction is no longer defined by a single strand
            break
        current = nxt[0]
        seen.add(current)
        path.append(current)
    return path


def tip_directions(skel: np.ndarray, lookback: int = 8, min_path: int = 5):
    """Unit outward direction per tip, estimated from the last `lookback` skeleton pixels."""
    tips, dirs = [], []
    for r, c in endpoints(skel):
        path = walk_back(skel, (int(r), int(c)), lookback)
        if len(path) < min_path:
            continue
        pts = np.asarray(path, dtype="float64")
        # Principal axis of the tip strand, signed to point outward (from interior to tip).
        centred = pts - pts.mean(axis=0)
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
        axis = vt[0]
        outward = pts[0] - pts[-1]
        if np.dot(axis, outward) < 0:
            axis = -axis
        tips.append((int(r), int(c)))
        dirs.append(axis / np.linalg.norm(axis))
    return np.asarray(tips, dtype="int64").reshape(-1, 2), np.asarray(dirs, dtype="float64").reshape(-1, 2)


def extend_tips(tips: np.ndarray, dirs: np.ndarray, length: int, shape: tuple[int, int],
                start: int = 1) -> np.ndarray:
    """Straight along-strike rays of `length` pixels beyond each tip (the tip itself excluded)."""
    out = np.zeros(shape, dtype=bool)
    if length <= 0 or not len(tips):
        return out
    t = np.arange(start, length + 1, dtype="float64")
    for (r, c), (dy, dx) in zip(tips, dirs):
        rr = np.rint(r + dy * t).astype(int)
        cc = np.rint(c + dx * t).astype(int)
        good = (rr >= 0) & (rr < shape[0]) & (cc >= 0) & (cc < shape[1])
        out[rr[good], cc[good]] = True
    return out


def truncate_tips(skel: np.ndarray, cut: int):
    """Remove the outermost `cut` pixels of every free strand end. Returns (kept, removed)."""
    s = np.asarray(skel, dtype=bool).copy()
    removed = np.zeros_like(s)
    for r, c in endpoints(s):
        path = walk_back(s, (int(r), int(c)), cut - 1)
        # Only cut strands long enough that something remains to define direction afterwards.
        if len(path) < cut:
            continue
        for pr, pc in path:
            removed[pr, pc] = True
    return s & ~removed, removed


def component_lengths(mask: np.ndarray) -> np.ndarray:
    lab, n = label(mask, structure=np.ones((3, 3)))
    return np.bincount(lab.ravel())[1:] if n else np.zeros(0, int)


def random_directions(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.uniform(0, 2 * np.pi, n)
    return np.stack([np.sin(a), np.cos(a)], axis=1)


def bfs_distance_ok(mask: np.ndarray) -> bool:  # small helper kept for tests of connectivity
    pts = np.argwhere(mask)
    if not len(pts):
        return True
    seen = {tuple(pts[0])}
    q = deque([tuple(pts[0])])
    while q:
        r, c = q.popleft()
        for dy, dx in _STEPS:
            p = (r + dy, c + dx)
            if 0 <= p[0] < mask.shape[0] and 0 <= p[1] < mask.shape[1] and mask[p] and p not in seen:
                seen.add(p)
                q.append(p)
    return len(seen) == len(pts)
