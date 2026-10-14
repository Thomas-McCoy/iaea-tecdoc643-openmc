#!/usr/bin/env python3
"""Recon only. Reads structure and attrs; loads no bulk arrays."""
import sys
import h5py

path = sys.argv[1]
probe = ["U235", "U238", "Pu239", "Pu240", "Pu241",
         "Xe135", "Sm149", "Sm151", "Gd155", "Nd148"]

with h5py.File(path, "r") as f:
    print("TOP-LEVEL")
    for k in f:
        o = f[k]
        if isinstance(o, h5py.Dataset):
            gb = o.size * o.dtype.itemsize / 1e9
            print(f"  DATASET {k:18s} shape={o.shape} dtype={o.dtype} {gb:.2f} GB")
        else:
            sub = list(o.keys())
            print(f"  GROUP   {k:18s} n={len(sub)} first5={sub[:5]}")

    if "nuclides" in f:
        print(f"\nNUCLIDES in chain: {len(f['nuclides'])}")
        for n in probe:
            if n in f["nuclides"]:
                print(f"  {n:6s} {dict(f['nuclides'][n].attrs)}")
            else:
                print(f"  {n:6s} NOT IN CHAIN")

    if "materials" in f:
        mids = list(f["materials"].keys())
        print(f"\nMATERIALS: {len(mids)}")
        print(f"  id range: {mids[0]} .. {mids[-1]}")
        for m in mids[:3]:
            print(f"  {m}: {dict(f['materials'][m].attrs)}")

    if "time" in f:
        print(f"\nTIME shape={f['time'].shape}")
        print(f"  first 3 rows: {f['time'][:3]}")
