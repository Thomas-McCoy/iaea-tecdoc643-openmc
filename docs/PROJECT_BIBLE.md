# PROJECT BIBLE — IAEA TECDOC-643 OpenMC Model
**Generic 10 MW LEU Research Reactor (ANL A-2 design) · Mines × Argonne · ADDER-OpenMC Preparation**

Maintainer: Thomas McCoy (Colorado School of Mines, ME/Nuclear, exp. May 2027; Research Aide, Argonne National Laboratory)
Last updated: 2026-10-19 · Status: **Task 1 ONGOING.** Fresh-core re-validation on the current geometry is pending; no k-eff result on it is validated.

This document is the single source of project truth for any collaborator — human or AI. Read it fully before touching the model. **The current code governs**; this document summarizes it and cites `file:line` (paths relative to `model/` unless stated). Where the two disagree, the code wins and this document is stale.

---

## 1. Mission

Prepare for ADDER-OpenMC coupling for research and test reactor (RTR) fuel management, under a potential NNSA-scoped Argonne–Mines collaboration:

1. **Task 1 — TECDOC Core Models.** Build publicly available OpenMC and MCNP models of the IAEA TECDOC-643 Appendix A-2 Generic 10 MW LEU core (Argonne design). Cross-validate at all-fresh conditions (keff, blade worths), then extend to depletion in ADDER-MCNP and OpenMC. *Fresh-core cross-validation: ongoing (§3). OpenMC depletion runs under way (§3a).*
2. **Task 2 — Runtime Comparison.** MCNP vs. OpenMC computational efficiency, fresh and depleted, CPU and GPU OpenMC.
3. **Task 3 — MCNP → OpenMC Conversion Assessment.** Run the conversion tool on the reference MCNP model, qualitatively assess model complexity, ease of modification, and ADDER integration vs. the native model.

Deliverable destination: `mascovale/CSM-Open-source-Reactor-Model-Library/tree/main/IAEA-Tecdoc-Core` (Valerio's public repo). Development repo: `Thomas-McCoy/iaea-tecdoc643-openmc`.

---

## 2. Hierarchy of Authority (memorize this)

1. **Kyle Anderson's reference MCNP model** — the governing reference for ALL material and geometry specifications. When the reference MCNP model and TECDOC-643 disagree, the reference MCNP model wins. **Exception:** the rows Kyle has stated are being corrected on the MCNP side (§3, three open items) — there OpenMC governs.
2. **TECDOC-643 Appendix A-2** (te_643v2_prn.pdf) — geometry/spec source where the reference MCNP model is silent. Kyle's March 9, 2026 email designates A-2 as the core of interest.
3. **TECDOC-643 Chapter 7 / Appendix G benchmark values** — context only. They use a *different flux-trap treatment* than A-2 Table 1 and are NOT validation targets.

**MCNP-model-vs-document discrepancies already caught and resolved (do not re-litigate):**
- Absorber is **B₄C, not Hf** (early model error, corrected) — materials.py:112–133.
- Control-element unfueled Al plates: **1.27 mm** [TECDOC A-2 Table 1] (`CTRL_AL_PLATE_THICK = 0.127`, geometry.py:989–994). The reference MCNP model's 1.50 mm is being corrected on the MCNP side. Do not change ours to match.
- Blade worth: the reference is the MCNP model's **18,540 pcm**. The TECDOC-643 comparison row is Table 7.7 LEU **B₄C**, ANL Monte Carlo, **14.95 ± 0.40 %Δk/k** (20.55 ± 0.55 $) — given in %Δk/k, so no β conversion is involved. It is **context only** (natural B₄C, different flux-trap treatment). **Never** adjust geometry toward the TECDOC value.

---

## 3. Cross-Validation Status — Task 1 ONGOING

**No k-eff result on the current geometry is to be presented as validated.** Fresh-core re-validation on the current geometry is pending.

**Quantity comparison** (`model_cross_validation (6).xlsx`, not in the repo): 78 quantities (51 geometry + 27 material) — **73 MATCH, 5 DIFF**. The 5 DIFF rows were 4 open items, all being resolved on the MCNP side; OpenMC governs. The outer-pool water pair is now **resolved** (2026-10-19), leaving 3 DIFF rows / 3 open items:

| Quantity | OpenMC (live) | Reference MCNP model |
|---|---|---|
| CFE unfueled plate thickness | 0.127 (geometry.py:993) | 0.150 |
| End-box region X | 7.7, full pitch (geometry.py:117, 163) | 7.6 |
| End-box region Y | 8.1, full pitch (geometry.py:118, 163) | 8.0 |
| ~~Outer-pool water H-1 / O-16~~ RESOLVED | 6.669090e-2 / 3.334550e-2 (materials.py:100–101) | 6.669090e-2 / 3.334550e-2 (`docs/reference_materials.csv`). OpenMC's O-16 was H1/2 = 3.334545e-2, 1.5e-6 low; now the reference value |

**All 8 base materials now match `docs/reference_materials.csv` (from the reference MCNP model)** nuclide-by-nuclide to 1e-6, with matching thermal-scattering presence — `python tests/test_reference_materials.py` (§6).

**Spec checks vs TECDOC A-2 Table 1** (`python model/check_u235_mass.py`, all pass): enrichment 19.7501 w/o · U density 4.4500 g/cm³ · U-235 389.69 g/SFE, 288.03 g/CFE · U/Si 1.50001 · meat density 6.2598 g/cm³ (materials.py:62–70).

**Model envelope:** 123.2 × 133.7 × 180 cm — 38.5 cm of pool water beyond the lattice in x and y (geometry.py:42–43, 1748, 1756–1761).

**k-eff on the current geometry — exists, NOT validated.** ENDF/B-VIII.0 against VII.0-based reference targets:
- rtrhpc1, 2026-08-04, 500,000 × 250 (50 inactive), OpenMC 0.15.3: rods in (f = 0) **0.98027 ± 0.00011**; rods out (f = 1) **1.19620 ± 0.00010**; blade worth 18,458 ± 13 pcm (TESTAMENT_III §8.1; statepoints not in the repo).
- Local, 2026-08-03, 50,000 × 200 (50 inactive), conda env `openmc-env` (OpenMC 0.15.0): rods in (f = 0) **0.98010 ± 0.00037** (`run_results/core_run/`, gitignored).

Reference targets: keff = 0.979959 rods in, 1.19753 rods out; blade worth 18,540 pcm.

**Do not compare the depletion BOL k-eff (§3a, ENDF/B-VIII.1) with the fresh-core k-eff above (ENDF/B-VIII.0).** They are on different libraries.

### 3a. Depletion (OpenMC) — in progress

Source: `tecdoc643_depletion_stepsize_comparison.xlsx`. Common to all jobs: OpenMC 0.15.3 · ENDF/B-VIII.1 + `endfb81_chain.pwr.xml` · CE/CM + CRAM48 (core.py:120, 127) · 12,280 per-plate materials (core.py:63–66) · 10 MW (core.py:113) · `--insertion 0` · 50,000 × 200 (50 inactive). All runs on rtrhpc1.

| Job | Schedule | Step lengths | Steps | End | k-eff BOL → end | Crossing |
|---|---|---|---|---|---|---|
| 15117 | kyle-400d, 1×, ADDER-matched (Kyle 2026-08-31) | 1, 1, 2, 3, 5, 8, 13, 21 d, then 17 × 21 d | 25 | 411 d | 1.19767 → 0.92700 | 297.74 d (285–306 bracket) |
| 15196 | valerio-318d, 2×, not ADDER-matched (Valerio 2026-09-01) | 2, 2, 4, 6, 10, 16, 26, 42 d, then 5 × 42 d | 13 | 318 d | 1.19767 → 0.98822 | 297.57 d (276–318 bracket) |
| 15348 | valerio-300d, 4× | 4, 4, 8, 12, 20, 32, 52, 84, 84 d | 9 | 300 d | TODO | TODO |

Crossings agree to 0.17 d (0.06 %). The schedules share only days 0, 2 and 4, and day 0 is bit-identical. Pu-239/240/241 run 0.28–0.50 % high on the 2× grid while U-235/U-238 agree to ~1e-5 %; the Np-239 mechanism is a **HYPOTHESIS**. **k-eff agreement alone does not validate step size for fuel management.**

These schedules cannot be reproduced from main: its CLI builds uniform steps only (core.py:491). See §10. ADDER's 4 substeps are not applied — `substeps` does not exist for CECM on OpenMC 0.15.3 (core.py:129–148).

---

## 4. Codebase Architecture

Five-file modular model. **All runs go through one code path:** `core.build_model()` (core.py:169).

| File | Role |
|---|---|
| `core.py` | Central driver. `CoreConfig` dataclass = single control surface. Defaults: insertion 100 % (all in), 50,000 × 200 (50 inactive) (core.py:55–60). CLI: `--insertion`, `--particles`, `--batches`, `--inactive`, `--seed`, `--output-dir`, `--overwrite-output`, `--depletion-zoning`, `--deplete`, `--chain-file`, `--power`, `--timesteps`, `--step-days` (core.py:436–464). Output dir is absolute (`<repo>/run_results/core_run`) and a directory holding previous run output is refused without `--overwrite-output` (core.py:86, 258–283). `run_depletion()` is live: `CoupledOperator` + `CECMIntegrator`, solver `cram48`, chain default `endfb81_chain.pwr.xml` in `/beegfs2/data/EP/openmc/data/depletion`; `simplified_*` and fast chains are refused; there is no default step schedule, and the CLI builds uniform steps only (core.py:311–426, 491). `substeps = 4` is recorded but not passed (core.py:129–148). |
| `materials.py` | 8 base materials (materials.py:453), atom densities from `docs/reference_materials.csv` (from the reference MCNP model), plus 12,280 per-plate zoned fuel clones (2 × 10 zones per plate, materials.py:380–381) when `--depletion-zoning` is on. |
| `geometry.py` | Full geometry. `build_core_geometry(withdrawn_fraction, depletion_zoning=False)` is the single construction path (core.py:199). Running `python geometry.py` directly performs self-checks + `geometry_debug` overlap runs at f = 0, 0.5, 0.99 and 1.0 (geometry.py:2272–2400). |
| `settings.py` | Eigenvalue settings, source box with `constraints={'fissionable': True}`, temperature interpolation (settings.py:182–192, 216). Run statistics come from `CoreConfig`, which overrides settings.py's own values. |
| `tallies.py` | `build_tallies()` attached by `build_model()`: `flux_map` mesh over the 6 × 7 lattice, 20 cells per pitch, z over the active meat (tallies.py:32–64). |

Support: `check_u235_mass.py`, `Analyze_rod_sweep.py`, `run/run_rod_sweep.py` (goes through `core`), `tests/`, `figures/`. **`run_vii_mat.py` is a stale independent copy of an old `materials.py` — do not run it** (Phase 1 audit Finding 3).

**⚠️ THE BLADE DIRECTION CONVENTION — the #1 way to silently ruin a run:**
- `CoreConfig.blade_insertion_percent` (CLI `--insertion`): **0 = fully WITHDRAWN, 100 = fully INSERTED** (control-room sense).
- `geometry.build_core_geometry(withdrawn_fraction=f)`: **f = 0.0 fully INSERTED, f = 1.0 fully WITHDRAWN** (opposite sense).
- `build_model()` converts: `f = 1.0 − insertion_percent/100`. Never call geometry functions with an insertion percent, and never report results without stating which convention the number uses. Results in this document use **f (withdrawal fraction)**.

---

## 5. Geometry Reference (all cm)

**Lattice:** 6 (x) × 7 (y) = 42 positions, pitch 7.7 × 8.1 (geometry.py:117–118, 1741–1742). Active 5×6 core: 23 standard fuel elements, 5 control elements, 2 flux traps, plus graphite reflector rows top/bottom (each block 7.6 × 8.0 with thin water gaps to the pitch boundary, aligned to the fuel lattice) (geometry.py:13–19, 164–167, 1811–1819). TECDOC's 8 × 9 is the grid-plate row only (geometry.py:20). There is no water ring in the lattice: an explicit pool box of 294 K water extends 38.5 cm beyond the lattice on all four sides (geometry.py:39–44, 1748). `lattice.outer = water_univ` guards boundary roundoff (geometry.py:1960). Vacuum boundaries at the pool faces (x ±61.6, y ±66.85) and z = ±90 (geometry.py:340–343, 1970–1976). Model envelope 123.2 × 133.7 × 180.

**Axial stack (every element footprint, symmetric about z = 0; geometry.py:25–36):**
- [−90, −45] water (294 K) · [−45, −31] homogenized end box · [−31, −30] unfueled clad extension · [−30, +30] active fuel meat · [+30, +31] clad extension · [+31, +45] end box · [+45, +90] water (294 K).
- End box: **14 cm** (`ENDBOX_HEIGHT`, geometry.py:347), **full pitch 7.7 × 8.1** (geometry.py:163, 842–857). TECDOC A-2 gives 15 cm and a 600 mm element; the reference MCNP model governs (geometry.py:141–146).

**Standard fuel element (76 × 80 mm envelope):** 23 plates stacked in y; inner plates 0.127 cm / outer **0.150** cm [DERIVED: meat + 2 × outer clad]; inner clad 0.038 / outer 0.0495; meat 0.051 thick × 6.3 wide × 60 tall; water channels 0.219; exterior channel 0.1075 [DERIVED]; side plates 0.48 (in x); plate / side plate / element Z 62 [MCNP] (geometry.py:122–123, 130–134, 146, 183, 196–202, 221, 258, 263, 272).

**Control element (17 fuel plates + blade structure):**
- Follower fuel stack centered, standard pitch: half-width = (17×0.127 + 16×0.219)/2 = **2.8315 cm** (geometry.py:1011–1012). Channels are the standard 0.219 — the compressed-channel (0.217) defect is fixed; do not reintroduce it.
- End block each side: `ELEM_Y/2 − 2.8315 = 1.1685 cm` (geometry.py:1032), built fuel→wall as: feeder channel 0.219 | Al guide 0.127 | blade water g | **B₄C slot 0.310** | blade water g | Al guide 0.127 | outer offset water `CTRL_OUTER_OFFSET`.
- `g = CTRL_BLADE_WATER` is the residual, **0.1275**, pinned by assert (geometry.py:1037–1060). Guide coolant channel (span between the guides) = 0.310 + 2 × 0.1275 = **0.565** (geometry.py:1068–1072). Asserts enforce the budget closes to the wall exactly.
- **`CTRL_OUTER_OFFSET = 0.1305` [MCNP]** — CFE exterior channel, supplied by Kyle 2026-07-31; it may postdate the reference MCNP model (geometry.py:1019–1029).

**Blade model — fixed-length sliding absorber:** BLADE_LENGTH = 60, ROD_TRAVEL = 60 (geometry.py:314, 325). Blade **0.31 × 6.63 × 60** (geometry.py:906, 930). At fraction f: blade z = [−30 + 60f, +30 + 60f]. B₄C fills the slot x/y band in that z-range; a 1 cm Al top clad (`BLADE_TOP_CLAD`, geometry.py:335) rides on the B₄C and a 14 cm end-box cap rides on the clad; at f = 1 the B₄C top is at +90 and the clad and cap are clipped out (geometry.py:46–62). Plate/clad, structural and channel cells run the plate height z = [−31, +31]; only the fuel meat is z = [−30, +30] (geometry.py:63–65).

**Flux trap:** 7.6 × 8.0 aluminum block with a central ZCylinder water hole, **`FT_HOLE_RADIUS = 2.820` [MCNP]**, area-equivalent to the 50 mm square hole (geometry.py:284–288). Hole and pitch-gap water is the 316.8 K core water; the axial water beyond the end boxes is 294 K pool water (geometry.py:1556–1606). Note: A-2 Table 1 vs. Chapter 7/Appendix G treat flux traps differently — confirm with Kyle which configuration is the benchmark reference.

---

## 6. Materials Reference

**Source: `docs/reference_materials.csv` (from the reference MCNP model)** — one row per nuclide, with each material's temperature and thermal scattering. `tests/test_reference_materials.py` checks every base material against it: each nuclide atom density to 1e-6 relative ("C (natural)" against C12 + C13), no extra nuclides, and thermal-scattering presence (none / Al-27 / H in H2O / graphite).

Every base material is `add_nuclide()` at the reference atom density (atom/b-cm) + `set_density('atom/b-cm', N)`, with N = the **sum** of its nuclide densities, so each nuclide is reproduced exactly. There is **no air** in the model (the July 2026 status slides' materials table listing air is stale).

| Material | Composition (atom/b-cm) | Notes |
|---|---|---|
| `fuel` — LEU U₃Si₂-Al | U235 2.251800e-03, U238 9.034100e-03, Al27 3.256300e-02, Si28/29/30 6.938766e-03 / 3.524947e-04 / 2.326390e-04; N = 5.137280e-02 | 332.1 K. **No S(α,β).** → 6.2598 g/cm³. materials.py:62–70 |
| `clad` — Al cladding | Al27 6.026260e-02 (pure Al stands in for 6061-T6, as in the reference MCNP model) | 330.7 K. `c_Al27`. Was 2.70 g/cm³ → 6.026261e-02 (2.2e-7 off); now the reference value. materials.py:79–84 |
| `aluminum` — structural Al | Al27 6.026260e-02 | **330.7 K — still to confirm with Kyle** (§10). `c_Al27`. Side plates, CFE guide plates, flux-trap blocks, blade top clad. materials.py:158–163 |
| `water` — outer pool | H1 6.669090e-02, O16 3.334550e-02 (the reference value, not H1/2) | 294.0 K, H-1 + O-16 ONLY, `c_H_in_H2O`. Lateral pool box, axial water beyond \|z\| = 45, absorber slot above the blade cap. → 0.99727 g/cm³. materials.py:98–103 |
| `water_core` — core coolant | H1 6.625423e-02, O16 3.312711e-02 | **316.8 K**, H-1 + O-16 ONLY, `c_H_in_H2O`. All in-core coolant (plate channels, inter-element gaps, flux-trap hole, graphite gaps, slot below the blade). → 0.99074 g/cm³. materials.py:105–110 |
| `b4c` — B₄C absorber | B10 **1.914973e-02**, B11 **7.010412e-02**, C (natural) 2.005592e-02; N = 1.0930977e-01 | 294.0 K; → 2.000 g/cm³; **no S(α,β)**. B:C = 4.450, B-10 = 21.46 at% of boron, both as given by the reference. Carbon via `add_element('C')`: OpenMC's 0.988922 / 0.011078 split, the SAME as graphite (the old hard-coded 0.9893 / 0.0107 is gone). The reference model's stated N, 1.093098e-01, is the nuclide sum rounded 2.7e-7 high. materials.py:112–133 |
| `graphite` — reflector | C (natural) **8.724000e-02** | 294.0 K, `c_Graphite` (graphite thermal scattering is in the reference MCNP model). → 1.7400 g/cm³. TECDOC gives no graphite density. materials.py:135–149 |
| `end_box_homog` — end box | Al27 1.506565e-02, H1 4.969068e-02, O16 2.484534e-02 | 316.8 K; → 1.41806 g/cm³; exactly 25 v/o Al / 75 v/o core water. **`c_H_in_H2O` ONLY** — `c_Al27` removed 2026-10-19 to match the reference. Also fills the moving cap above each blade. materials.py:165–184 |

Carbon: `USE_NATURAL_CARBON = False` (materials.py:47) expands natural carbon to C12/C13 because ENDF/B-VIII.0 has no C0; `True` switches b4c and graphite to C0 together (never exercised). `USE_AL_SAB = True` (materials.py:54) puts `c_Al27` on `clad` and `aluminum` only.

**What sits above each blade** (geometry.py:1357–1395): B₄C → 1 cm `aluminum` top clad → 14 cm `end_box_homog` cap → 294 K `water` to +90, each clipped at CORE_TOP. No side or bottom clad on the blade.

**Not a matched comparison yet:** the thermal-scattering check is presence only. MCNP evaluates each table at its own fixed library temperature; OpenMC interpolates to the material temperature.

Byte-identity after the 2026-10-19 change: `geometry.xml` is unchanged (f = 0 `9081962e…`, f = 1 `79a73a91…`); `materials.xml` moves deliberately `49cde120…` (2,066 B) → `89677292…` (2,204 B).

Temperature treatment: `settings.temperature = {'method': 'interpolation', 'default': 294.0}` (settings.py:216; core.py:95–96). Every material sets its own temperature explicitly; the default (the reference MCNP model's 294 K, not OpenMC's 293.6 K) is a backstop.

**Nuclear data — per path:**

| Path | Library |
|---|---|
| Fresh core | ENDF/B-VIII.0 HDF5. Local: `/home/tmccoy/nuclear-data/endfb-viii.0-hdf5/cross_sections.xml` (core.py:40) |
| Depletion | ENDF/B-VIII.1 + `endfb81_chain.pwr.xml` on rtrhpc1. The chain default is in core.py:316; the cross-section library is not pinned in code |

Precedence: `OPENMC_CROSS_SECTIONS` env var → `CoreConfig.cross_sections` → local fallback (core.py:151–162). On the cluster, set the env var in the submission script (core.py:38–39).

---

## 7. Hard Constraints (non-negotiable)

1. **Never modify absorber geometry — or any geometry — to chase keff or blade-worth targets.** Discrepancies get reconciled with the owner of the reference MCNP model (Kyle), never absorbed by tuning.
2. **The reference MCNP model governs**, except the rows Kyle has stated are being corrected on the MCNP side (§3). Matching the reference MCNP model while disagreeing with TECDOC is success, not a bug.
3. **Plan-then-approve gates for geometry edits.** Present the plan; get explicit approval before touching files. Surgical, localized changes only.
4. **No magic numbers.** Every dimension is a named, parameterized constant that traces to the reference MCNP model or a TECDOC table, tagged `[MCNP]`, `[TECDOC]`, `[DERIVED]` or `[ASSUMED]`. Unconfirmed values are tagged `[ASSUMED]` in comments (e.g. `MIN_RESIDUAL_GAP`, geometry.py:108).
5. **All production runs go through `core.build_model()`** — never hand-assemble a model that bypasses the single code path.
6. **Report exact numerical values.** keff to 5 decimals with uncertainty; differences in pcm; state the blade convention used.

---

## 8. Verification Workflow (pre-flight, before every rtrhpc1 submission)

1. `python geometry.py` self-checks (layer-sum asserts, blade z-range asserts, `geometry_debug` overlap runs at f = 0, 0.5, 0.99, 1.0) — geometry errors are silent in MCNP but loud in OpenMC; use that.
2. Cross-section geometry plots (`tests/plot_core.py`, `tests/make_phase1_xs_plots.py`) — inspect visually; arithmetic verification alone is not enough (this caught the control-element sprawl).
3. Coordinate assertions / material dump review; `python model/check_u235_mass.py` (TECDOC spec checks), `python tests/test_reference_materials.py` (materials vs the reference MCNP model) and `python tests/check_depletion_zoning.py`.
4. Short keff tripwire run locally (small particles/batches) — sanity-check magnitude before burning cluster hours.
5. Full production run on rtrhpc1.

Production statistics baseline: 50,000 particles/batch, 200 batches, 50 inactive (≈ ±37 pcm at f = 0) (core.py:58–60). Local WSL 12-core for dev/short runs. No Shannon entropy mesh is defined, so source convergence is unmonitored (§10).

---

## 9. Compute & Environment

- **Local:** WSL Ubuntu, VS Code. Conda envs present (`conda env list`, 2026-09-23) — they are distinct; do not collapse them:

  | Env | OpenMC | Notes |
  |---|---|---|
  | `openmc-016` | 0.15.3 | local working env |
  | `openmc` | 0.15.3 | also present locally; `which openmc` resolves here in the default shell |
  | `openmc-adder` | 0.15.3 | |
  | `openmc-env` | 0.15.0 | old; used by the 2026-08-03 local run |

- **Cluster:** rtrhpc1 (Argonne RTR HPC), PBS/Torque, 128 OpenMP threads per node, conda env `openmc`, OpenMC 0.15.3. Libraries: ENDF/B-VII.1, VIII.0, VIII.1, and VII.0 HDF5 as `mcnp_endfb70` (`c_Al27` on it unverified). Depletion chains in `/beegfs2/data/EP/openmc/data/depletion` (core.py:311).

---

## 10. Open Items

| Item | Owner/Path |
|---|---|
| Matched-library comparison: VII.0 is available on rtrhpc1 as `mcnp_endfb70` but `c_Al27` on it is unverified; otherwise both sides move to one library | Kyle / Thomas |
| Three MCNP-side DIFF rows (CFE unfueled plate, end-box region X/Y) — Kyle's edit; ours must not change to match. (Outer-pool water H-1/O-16: CLOSED 2026-10-19, §3) | Kyle |
| Confirm `CTRL_OUTER_OFFSET = 0.1305` is in the MCNP surface cards, not only the report figure | Kyle |
| ~~Graphite and Al thermal scattering on the MCNP side~~ CLOSED 2026-10-19: the reference MCNP model carries graphite and Al-27 thermal scattering, on graphite and on the two pure-Al materials only (not the end box) (§6) | — |
| `Downloads/iaeac000` is an older reference MCNP model version (no Al thermal scattering, different thermal-scattering temperatures, 100 fuel cells/plate) — confirm with Kyle; structural Al temperature still to confirm | Kyle / Thomas |
| Confirm which flux-trap configuration is the benchmark reference (A-2 Table 1 vs. Ch. 7/App. G) | Kyle |
| Shannon entropy mesh — none defined; needed before results are published | Thomas |
| Fresh-core re-validation on the current geometry | Thomas |
| 15348 k-eff and crossing (§3a) | Thomas |
| Commit rtrhpc1 `core.py` `_SCHEDULES` and `openmc_submit.pbs` to main; main's CLI (uniform steps only, core.py:491) cannot reproduce these runs | Thomas |
| OpenMC 0.16.0 upgrade for `substeps` (CECM); equivalence to ADDER's substep unconfirmed (core.py:129–148) | Thomas / Kyle |
| ~~Align b4c C12/C13 split to OpenMC's 0.988922 / 0.011078~~ CLOSED 2026-10-19: b4c and graphite both use `add_element('C')` (materials.py:132, 147) | — |
| `run_vii_mat.py` rewrite: import from `materials.py`, override only the library switch | Thomas |
| `Analyze_rod_sweep.py:16–41` compares against TECDOC LEU Hf 15.22 $; the TECDOC context row is B₄C 14.95 %Δk/k (§2) | Thomas |
| Stale code comments: core.py:39 (Slurm), core.py:11 (`openmc-env`), core.py:94 and settings.py:213 ("flux-trap water"), core.py:105–107 and materials.py:52–53 (library basis — depletion uses VIII.1). (materials.py pool-water placement: fixed 2026-10-19) | Thomas |
| Publish model to `mascovale/CSM-Open-source-Reactor-Model-Library` — `scripts/sync_deliverable.sh` (dry run by default) | Thomas |
| Tasks 2 & 3 (CPU/GPU runtime; conversion-tool assessment) | Downstream |

---

## 11. People

- **Kyle Anderson** (kanderson@anl.gov) — ANL. Day-to-day technical authority; owns the reference MCNP model.
- **Erik Wilson** (erikwilson@anl.gov) — Principal Nuclear Engineer, Manager, RTR group, ANL; PRO-X program authority.
- **Christian Castagna** — ANL; co-author.
- **Mohamed Elsawi** — ANL; co-author.
- **Valerio Mascolino** (valerio.mascolino@mines.edu) — Mines advisor. Owns the public deliverable repo; performed the independent material-scan review.
- **Lindsey Morphey** (lmorphey@anl.gov) — ANL HR contact.

---

## 12. How to Work on This Project (for AI assistants)

- **Lead with the answer.** Exact numbers first, then reasoning. Preserve every significant digit; convert differences to pcm.
- **Flag open items plainly** — never bury an unconfirmed assumption. Placeholder values must be labeled as such in code and in prose.
- **Don't over-scaffold.** Thomas is technically precise; skip hedging, skip re-explaining basics, skip decorative structure.
- **Geometry edits:** propose a plan, wait for approval, then apply the minimal diff. Never batch a geometry change with unrelated cleanup.
- **When a result looks wrong, suspect the model before the physics, and the convention (Section 4 blade direction) before the model.**
- **Never suggest tuning toward a target.** If OpenMC and the reference MCNP model disagree, the next step is diagnosis and an email to Kyle — not a parameter tweak.
- Email drafts: short, professional; Thomas will ask about CC'ing and next steps — anticipate those.
- Superseded sources: the July 2026 status slides and TESTAMENT_II. See `docs/SUPERSEDED_NOTES.md` and `docs/TESTAMENT_III_2026-08-04.md` §9. Trust the code; cite `file:line` rather than restating.
