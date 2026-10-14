#!/usr/bin/env python3
"""One streaming pass over /number. Peak RSS ~400 MB."""
import sys, json, argparse
import numpy as np
import h5py

NUCS = ["U235", "U238", "Pu239", "Pu240", "Pu241",
        "Xe135", "Sm149", "Sm151", "Gd155", "Nd148"]

p = argparse.ArgumentParser()
p.add_argument("path")
p.add_argument("tag")
p.add_argument("--steps", type=int, default=0, help="tripwire: only first N steps")
a = p.parse_args()

with h5py.File(a.path, "r") as f:
    num = f["number"]
    n_step, n_mat, n_nuc_all = num.shape

    # --- nuclide columns -------------------------------------------------
    cols = [int(f["nuclides"][n].attrs["atom number index"]) for n in NUCS]

    # --- material index map, asserted not assumed ------------------------
    ids = np.empty(n_mat, dtype=np.int64)
    vols = np.empty(n_mat, dtype=np.float64)
    seen = np.zeros(n_mat, dtype=bool)
    for mid, grp in f["materials"].items():
        i = int(grp.attrs["index"])
        assert 0 <= i < n_mat, f"index {i} out of range for material {mid}"
        assert not seen[i], f"duplicate index {i}"
        seen[i] = True
        ids[i] = int(mid)
        vols[i] = float(grp.attrs["volume"])
    assert seen.all(), f"{(~seen).sum()} material indices never filled"
    print(f"index map OK: 0..{n_mat-1}, id {ids.min()}..{ids.max()}")
    print(f"id - index constant? {np.unique(ids - np.arange(n_mat))}")

    uv = np.unique(vols)
    print(f"distinct volumes: {len(uv)} -> {uv[:5]}")
    if len(uv) != 1:
        print("  WARNING: volumes NOT uniform; zone aggregation must volume-weight")

    # --- metadata --------------------------------------------------------
    times = f["time"][:]           # (n_step, 2) seconds [start, end]
    eig   = f["eigenvalues"][:]    # (n_step, 2) k-eff, sigma
    srate = f["source_rate"][:]

    steps = a.steps if a.steps else n_step
    out = np.empty((steps, n_mat, len(NUCS)), dtype=np.float64)

    # --- stream one step slab at a time ----------------------------------
    for i in range(steps):
        slab = num[i]                  # (12280, 3820) = 375 MB
        out[i] = slab[:, cols]
        del slab
        print(f"  step {i:3d}  day {times[i,0]/86400:8.2f}  "
              f"k={eig[i,0]:.5f}  U235_sum={out[i,:,0].sum():.6e}", flush=True)

np.save(f"inventory_{a.tag}.npy", out)

meta = {
    "tag": a.tag, "source": a.path,
    "nuclides": NUCS, "n_steps_written": steps, "n_materials": n_mat,
    "material_ids_by_index": ids.tolist(),
    "volumes_by_index": vols.tolist(),
    "time_start_s": times[:steps, 0].tolist(),
    "time_end_s": times[:steps, 1].tolist(),
    "day": (times[:steps, 0] / 86400).tolist(),
    "keff": eig[:steps, 0].tolist(), "keff_sigma": eig[:steps, 1].tolist(),
    "source_rate_W": srate[:steps].tolist(),
    "units": "atoms per material (total, not density)",
}
with open(f"inventory_{a.tag}_meta.json", "w") as fh:
    json.dump(meta, fh, indent=1)

# core totals CSV
with open(f"core_totals_{a.tag}.csv", "w") as fh:
    fh.write("day,keff,keff_sigma," + ",".join(NUCS) + "\n")
    for i in range(steps):
        tot = out[i].sum(axis=0)
        fh.write(f"{times[i,0]/86400:.6f},{eig[i,0]:.6f},{eig[i,1]:.6f},"
                 + ",".join(f"{v:.8e}" for v in tot) + "\n")

print(f"\nwrote inventory_{a.tag}.npy  {out.nbytes/1e6:.1f} MB")
