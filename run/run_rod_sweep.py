"""
run_rod_sweep.py
----------------
Fixed-length sliding blade rod-worth sweep for the IAEA TECDOC-643 core.

The B4C absorber blade is 60 cm long and rigid.  At withdrawn fraction f:
    z_bot = -30 + f * 60   (blade bottom, cm)
    z_top =  z_bot + 60    (blade top,    cm)

Sweep runs OpenMC for fractions in [0.0, 0.1, ..., 1.0].  For each:
  - keff is computed from 100 active batches of 50 000 particles.
  - Reactivity ρ = (keff − 1) / keff  [Δk/k].
  - Differential worth ≡ cumulative ρ(f) − ρ(0) in dollars  (β_eff = 0.0075).

Model construction goes through core.build_model() (single code path,
tallies attached); this script converts each withdrawal fraction f to the
CoreConfig insertion percent: insertion% = 100·(1 − f).

Outputs:
  run_results/rod_sweep_results.json  — all keff / rho values
  run_results/rod_worth_curve.png     — reactivity and dollar-worth curves

Validation checkpoints printed to stdout:
  - Blade z-span at each fraction with bounds check vs [CORE_BOTTOM, CORE_TOP].
  - ~68% critical-position estimate (rod position where keff ≈ 1.0).
  - f=0 keff comparison vs prior all-in result.
"""

import sys
import json
import pathlib
import numpy as np

MODEL_DIR = pathlib.Path(__file__).parent.parent / 'model'
sys.path.insert(0, str(MODEL_DIR))

from core import CoreConfig, run_eigenvalue
from geometry import HALF_Z, BLADE_LENGTH, ROD_TRAVEL, CORE_BOTTOM, CORE_TOP

# =============================================================================
# SWEEP CONFIGURATION
# =============================================================================

FRACTIONS = np.round(np.linspace(0.0, 1.0, 11), 3).tolist()  # 0.0, 0.1, ..., 1.0

# Particles per batch and batch counts for the sweep
PARTICLES  = 50_000
BATCHES    = 150
INACTIVE   = 50

# β_eff for 235U LEU core; TECDOC benchmark total worth ≈ 15.22 $
BETA_EFF       = 0.0075
TECDOC_DOLLARS = 15.22

RESULTS_DIR = pathlib.Path(__file__).parent.parent / 'run_results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# SWEEP LOOP
# =============================================================================

results = []

print(f"\n{'='*65}")
print(f"  Rod Worth Sweep — {len(FRACTIONS)} fractions, {PARTICLES} p/batch, "
      f"{BATCHES - INACTIVE} active batches")
print(f"  Core z: [{CORE_BOTTOM}, {CORE_TOP}] cm  |  Blade length: {BLADE_LENGTH} cm")
print(f"{'='*65}\n")

for f in FRACTIONS:
    z_bot = -HALF_Z + f * ROD_TRAVEL
    z_top = z_bot + BLADE_LENGTH
    in_bounds = (z_bot >= CORE_BOTTOM) and (z_top <= CORE_TOP)
    print(f"\n--- f={f:.2f}: blade z=[{z_bot:.1f}, {z_top:.1f}] cm  "
          f"within [{CORE_BOTTOM}, {CORE_TOP}]: {in_bounds} ---")
    assert in_bounds, "blade outside core bounds — check CORE_TOP / CORE_BOTTOM"

    cfg = CoreConfig(
        blade_insertion_percent=100.0 * (1.0 - f),   # f is a WITHDRAWAL fraction
        particles=PARTICLES,
        batches=BATCHES,
        inactive=INACTIVE,
        output_dir=str(RESULTS_DIR / f'rod_sweep_f{f:.3f}'),
    )
    keff = run_eigenvalue(cfg)

    k    = keff.nominal_value
    k_uc = keff.std_dev
    rho  = (k - 1.0) / k          # Δk/k

    print(f"  keff = {k:.5f} ± {k_uc:.5f}    ρ = {rho*100:.4f}% Δk/k")

    results.append({
        'fraction': f,
        'z_bot':    z_bot,
        'z_top':    z_top,
        'keff':     k,
        'keff_unc': k_uc,
        'rho':      rho,
    })

# =============================================================================
# RESULTS TABLE
# =============================================================================

rho0 = results[0]['rho']   # all-in reactivity (f=0)

print(f"\n\n{'='*72}")
print("ROD WORTH SWEEP RESULTS")
print(f"{'='*72}")
hdr = (f"{'f':>5}  {'z_bot':>6}  {'z_top':>6}  "
       f"{'keff':>9}  {'±':>7}  {'ρ (%)':>9}  {'Δρ (%)':>9}  {'worth ($)':>10}")
print(hdr)
print("-" * 72)

for r in results:
    delta_rho     = r['rho'] - rho0
    worth_dollars = delta_rho / BETA_EFF
    print(f"{r['fraction']:>5.2f}  {r['z_bot']:>6.1f}  {r['z_top']:>6.1f}  "
          f"{r['keff']:>9.5f}  {r['keff_unc']:>7.5f}  "
          f"{r['rho']*100:>9.4f}  {delta_rho*100:>9.4f}  {worth_dollars:>10.3f}")

total_rho     = results[-1]['rho'] - rho0
total_dollars = total_rho / BETA_EFF
print(f"\nTotal rod worth:  Δρ = {total_rho*100:.4f}%  =  {total_dollars:.2f} $"
      f"  (β_eff = {BETA_EFF})")
print(f"TECDOC benchmark: {TECDOC_DOLLARS} $  |  deviation: "
      f"{total_dollars - TECDOC_DOLLARS:+.2f} $")

# f=0 validation vs prior all-in baseline
print(f"\nf=0 (all-in) keff = {results[0]['keff']:.5f} ± {results[0]['keff_unc']:.5f}")
print(f"  vs prior baseline  1.01944 : "
      f"{(results[0]['keff'] - 1.01944)*1e5:+.0f} pcm  "
      f"(shift from taller model + end-box regions)")
print(f"  vs TECDOC 1.0296           : "
      f"{(results[0]['keff'] - 1.0296)*1e5:+.0f} pcm")

# Critical-position estimate (~68% withdrawal expected)
print("\nCritical-position search (keff ≈ 1.0):")
f_crit = None
for i in range(len(results) - 1):
    r1, r2 = results[i], results[i + 1]
    if r1['rho'] <= 0 <= r2['rho'] or r1['rho'] >= 0 >= r2['rho']:
        f_crit = (r1['fraction']
                  + (0.0 - r1['rho']) / (r2['rho'] - r1['rho'])
                  * (r2['fraction'] - r1['fraction']))
        z_b_c = -HALF_Z + f_crit * ROD_TRAVEL
        z_t_c = z_b_c + BLADE_LENGTH
        print(f"  f_crit ≈ {f_crit:.3f} ({f_crit*100:.1f}% withdrawn)"
              f"  →  blade z=[{z_b_c:.1f}, {z_t_c:.1f}] cm")
        break
if f_crit is None:
    print("  keff did not cross 1.0 in sweep range — check reactivity sign.")

# =============================================================================
# SAVE RESULTS
# =============================================================================

results_file = RESULTS_DIR / 'rod_sweep_results.json'
with open(results_file, 'w') as fp:
    json.dump(
        {
            'fractions':       FRACTIONS,
            'beta_eff':        BETA_EFF,
            'tecdoc_dollars':  TECDOC_DOLLARS,
            'f_critical':      f_crit,
            'total_dollars':   total_dollars,
            'results':         results,
        },
        fp,
        indent=2,
    )
print(f"\nResults saved to {results_file}")

# =============================================================================
# PLOT
# =============================================================================

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fracs  = [r['fraction']   for r in results]
    rho_pc = [r['rho'] * 100  for r in results]          # % Δk/k
    worth  = [(r['rho'] - rho0) / BETA_EFF for r in results]  # $ (0 at f=0)
    unc_pc = [r['keff_unc'] / r['keff']**2 * 100 for r in results]  # σ in %

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle('TECDOC-643 Control Rod Worth — Fixed-Length Sliding Blade\n'
                 f'(BLADE_LENGTH={BLADE_LENGTH} cm, β_eff={BETA_EFF})', fontsize=11)

    ax1.errorbar(fracs, rho_pc, yerr=unc_pc, fmt='bo-', capsize=3,
                 label='ρ (%  Δk/k)')
    ax1.axhline(0, color='k', lw=0.8, ls='--')
    if f_crit is not None:
        ax1.axvline(f_crit, color='r', lw=1.0, ls='--',
                    label=f'f_crit ≈ {f_crit:.3f}')
    ax1.set_xlabel('Withdrawn fraction  f', fontsize=11)
    ax1.set_ylabel('Reactivity  ρ  (%  Δk/k)', fontsize=11)
    ax1.set_title('Reactivity vs Rod Position')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(fracs, worth, 'rs-', label='Rod worth ($)')
    ax2.axhline(0, color='k', lw=0.8, ls='--')
    ax2.axhline(total_dollars, color='purple', lw=0.8, ls=':',
                label=f'Total = {total_dollars:.2f} $')
    ax2.axhline(TECDOC_DOLLARS, color='green', lw=0.8, ls=':',
                label=f'TECDOC = {TECDOC_DOLLARS} $')
    if f_crit is not None:
        ax2.axvline(f_crit, color='r', lw=1.0, ls='--',
                    label=f'f_crit ≈ {f_crit:.3f}')
    ax2.set_xlabel('Withdrawn fraction  f', fontsize=11)
    ax2.set_ylabel('Cumulative rod worth  ($)', fontsize=11)
    ax2.set_title(f'Rod Worth Curve  (β_eff = {BETA_EFF})')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    plot_path = RESULTS_DIR / 'rod_worth_curve.png'
    fig.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Plot saved to {plot_path}")

except ImportError:
    print("matplotlib not available — skipping plot.")
