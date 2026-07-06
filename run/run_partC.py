"""
run_partC.py
------------
Part C: pcm attribution — all-out vs all-in keff against the recorded
baselines and the TECDOC-643 benchmark values.

Baseline keff (prior geometry, before the guide-plate / end-box fixes):
  all-out : 1.18420 ± ~20 pcm
  all-in  : 1.01944 ± ~20 pcm

TECDOC-643 benchmark (Table 4, Appendix A-2, LEU BOL):
  all-out : 1.1922
  all-in  : 1.0296

Model construction goes through core.build_model() (single code path,
tallies attached); this script only sets blade insertion per case and
does the bookkeeping.
"""

import sys
import json
import pathlib

MODEL_DIR = pathlib.Path(__file__).parent.parent / 'model'
sys.path.insert(0, str(MODEL_DIR))

from core import CoreConfig, run_eigenvalue

RESULTS_DIR = pathlib.Path(__file__).parent.parent / 'run_results'
RESULTS_DIR.mkdir(exist_ok=True)

TECDOC   = {'all_out': 1.1922, 'all_in': 1.0296}
BASELINE = {'all_out': 1.18420, 'all_in': 1.01944}

results = {}

# insertion percent: 0 = fully withdrawn (all-out), 100 = fully inserted (all-in)
for case, insertion in [('all_out', 0.0), ('all_in', 100.0)]:
    print(f"\n{'='*60}")
    print(f"  Running: {case}  (blade insertion = {insertion:.0f}%)")
    print(f"{'='*60}")

    cfg = CoreConfig(
        blade_insertion_percent=insertion,
        particles=70_000,
        batches=150,
        inactive=50,
        output_dir=str(RESULTS_DIR / f'partC_{case}'),
    )
    keff = run_eigenvalue(cfg)

    delta_tecdoc   = (keff.nominal_value - TECDOC[case]) * 1e5
    delta_baseline = (keff.nominal_value - BASELINE[case]) * 1e5

    results[case] = {
        'keff':  keff.nominal_value,
        'sigma': keff.std_dev,
        'delta_TECDOC_pcm':   delta_tecdoc,
        'delta_baseline_pcm': delta_baseline,
    }
    print(f"  keff = {keff.nominal_value:.5f} ± {keff.std_dev:.5f}")
    print(f"  vs TECDOC  : {delta_tecdoc:+.0f} pcm")
    print(f"  vs baseline: {delta_baseline:+.0f} pcm  (regression recovered if +)")

# Summary table
print("\n" + "="*70)
print("PART C — PCM ATTRIBUTION SUMMARY")
print("="*70)
print(f"{'Case':<12} {'keff':>8} {'±σ':>7} {'vs TECDOC':>12} {'vs baseline':>13} {'δ-recovery':>12}")
print("-"*70)
for case in ['all_out', 'all_in']:
    r = results[case]
    # regression was: baseline - TECDOC (how far under)
    regression_before = (BASELINE[case] - TECDOC[case]) * 1e5
    recovery = r['delta_TECDOC_pcm'] - regression_before  # how much closer to TECDOC
    print(f"{case:<12} {r['keff']:>8.5f} {r['sigma']:>7.5f} "
          f"{r['delta_TECDOC_pcm']:>+12.0f} {r['delta_baseline_pcm']:>+13.0f} "
          f"{recovery:>+12.0f}")

# Control rod worth
worth_fixed   = (results['all_out']['keff'] - results['all_in']['keff']) / \
                (results['all_out']['keff'] * results['all_in']['keff'])
worth_tecdoc  = (TECDOC['all_out'] - TECDOC['all_in']) / \
                (TECDOC['all_out'] * TECDOC['all_in'])
worth_baseline = (BASELINE['all_out'] - BASELINE['all_in']) / \
                 (BASELINE['all_out'] * BASELINE['all_in'])

print(f"\nControl rod worth (Δk/kk'):")
print(f"  Fixed geometry: {worth_fixed:.4f}  ({worth_fixed*1e5:.0f} pcm)")
print(f"  Baseline:       {worth_baseline:.4f}  ({worth_baseline*1e5:.0f} pcm)")
print(f"  TECDOC:         {worth_tecdoc:.4f}  ({worth_tecdoc*1e5:.0f} pcm)")

(RESULTS_DIR / 'partC_results.json').write_text(
    json.dumps({'fixed': results,
                'baseline': BASELINE,
                'tecdoc': TECDOC,
                'worth': {'fixed': worth_fixed, 'tecdoc': worth_tecdoc, 'baseline': worth_baseline}},
               indent=2))
print(f"\nResults saved to {RESULTS_DIR}/partC_results.json")
