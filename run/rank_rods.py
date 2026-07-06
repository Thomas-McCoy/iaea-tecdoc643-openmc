"""
rank_rods.py — read the flux map and rank the five control rods.
Run AFTER the OpenMC run finishes, from the run's output directory
(the one containing statepoint.*.h5, e.g. run_results/core_run).
Highest flux = your Max-Worth-Rod-Out candidate.
"""
import glob
import sys
import pathlib
import numpy as np
import openmc

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'model'))
from geometry import PITCH_X, PITCH_Y

sp_files = sorted(glob.glob('statepoint.*.h5'))
if not sp_files:
    raise SystemExit("No statepoint.*.h5 here — did the run finish in this folder?")
sp = openmc.StatePoint(sp_files[-1])
print(f"Reading {sp_files[-1]}")

nx, ny = 160, 180
flux = sp.get_tally(name='flux_map').mean.ravel().reshape(ny, nx)  # [y, x]

xc = 0.5 * (np.linspace(-4.0*PITCH_X, 4.0*PITCH_X, nx+1)[:-1]
            + np.linspace(-4.0*PITCH_X, 4.0*PITCH_X, nx+1)[1:])
yc = 0.5 * (np.linspace(-4.5*PITCH_Y, 4.5*PITCH_Y, ny+1)[:-1]
            + np.linspace(-4.5*PITCH_Y, 4.5*PITCH_Y, ny+1)[1:])

centers = {
    "C0": (-0.5*PITCH_X,  2.0*PITCH_Y),
    "C1": ( 1.5*PITCH_X,  1.0*PITCH_Y),
    "C2": (-1.5*PITCH_X,  0.0),
    "C3": ( 1.5*PITCH_X, -1.0*PITCH_Y),
    "C4": (-0.5*PITCH_X, -2.0*PITCH_Y),
}

results = {}
for name, (cx, cy) in centers.items():
    in_x = np.abs(xc - cx) <= PITCH_X / 2.0
    in_y = np.abs(yc - cy) <= PITCH_Y / 2.0
    results[name] = flux[np.ix_(in_y, in_x)].sum()

ranked = sorted(results.items(), key=lambda kv: kv[1], reverse=True)
top = ranked[0][1]
print("\nControl rod ranking (local flux, all rods out):")
for name, val in ranked:
    print(f"  {name}  {val/top:6.3f}")
print(f"\nMax-worth candidate: {ranked[0][0]}")