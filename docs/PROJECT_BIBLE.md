# PROJECT BIBLE — IAEA TECDOC-643 OpenMC Model
**Generic 10 MW LEU Research Reactor (ANL A-2 design) · Mines × Argonne · ADDER-OpenMC Preparation**

Maintainer: Thomas McCoy (Colorado School of Mines, ME/Nuclear, exp. May 2027; Research Aide, Argonne National Laboratory)
Last updated: July 6, 2026 · Status: **Task 1 fresh-core cross-validation COMPLETE**

This document is the single source of project truth for any collaborator — human or AI. Read it fully before touching the model. If anything here conflicts with an older chat, slide deck, or note, **this document and the current code govern.**

---

## 1. Mission

Prepare for ADDER-OpenMC coupling for research and test reactor (RTR) fuel management, under a potential NNSA-scoped Argonne–Mines collaboration:

1. **Task 1 — TECDOC Core Models.** Build publicly available OpenMC and MCNP models of the IAEA TECDOC-643 Appendix A-2 Generic 10 MW LEU core (Argonne design). Cross-validate at all-fresh conditions (keff, blade worths), then extend to depletion in ADDER-MCNP and OpenMC. *Fresh-core validation: done.*
2. **Task 2 — Runtime Comparison.** MCNP vs. OpenMC computational efficiency, fresh and depleted, CPU and GPU OpenMC.
3. **Task 3 — MCNP → OpenMC Conversion Assessment.** Run the conversion tool on the MCNP deck, qualitatively assess model complexity, ease of modification, and ADDER integration vs. the native model.

Deliverable destination: `mascovale/CSM-Open-source-Reactor-Model-Library/tree/main/IAEA-Tecdoc-Core` (Valerio's public repo). Development repo: `Thomas-McCoy/iaea-tecdoc643-openmc`.

---

## 2. Hierarchy of Authority (memorize this)

1. **Kyle Anderson's MCNP deck** — the governing reference for ALL material and geometry specifications. When the deck and TECDOC-643 disagree, the deck wins. Full stop.
2. **TECDOC-643 Appendix A-2** (te_643v2_prn.pdf) — geometry/spec source where the deck is silent. Kyle's March 9, 2026 email designates A-2 as the core of interest.
3. **TECDOC-643 Chapter 7 / Appendix G benchmark values** — context only. They use a *different flux-trap treatment* than A-2 Table 1 and are NOT validation targets.

**Deck-vs-document discrepancies already caught and resolved (do not re-litigate):**
- Absorber is **B₄C, not Hf** (early model error, corrected)
- Control-element end plates: **1.50 mm** (Kyle's TH-modified deck), not 1.27 mm
- Blade worth ~24.7–24.8 $ vs. TECDOC's 15.22 $ — a known deck-vs-TECDOC difference. OpenMC matches the deck. Reconcile with Kyle if needed; **never** adjust geometry to move toward the TECDOC value.

---

## 3. Validated State (July 6, 2026 — ENDF/B-VIII.0, current geometry)

| Case | OpenMC (combined) | MCNP reference | Δ |
|---|---|---|---|
| All blades in (f = 0.0) | 0.98004 ± 0.00039 | 0.979959 | **+8 pcm** (within 1σ) |
| All blades out (f = 1.0) | 1.19590 ± 0.00039 | 1.19753 | −163 pcm (library difference) |
| Total blade worth | **18,418 pcm** | 18,540 pcm | 122 pcm (0.66%, within <1% target) |

Leakage fractions: 0.09377 ± 0.00011 (f=0.0), 0.08656 ± 0.00010 (f=1.0).

Notes:
- These results **supersede** the July 1 numbers in the July 2026 status deck (rods-in −23 pcm / rods-out −207 pcm). The improvement came from the control-element geometry rework — the compressed 0.217 cm follower channels were restored to the standard 0.219 cm pitch with the blade/guide structure confined to the end blocks.
- The −163 pcm rods-out offset is attributed to ENDF/B-VII.0 (MCNP) vs. VIII.0 (OpenMC). Rodded cases are less library-sensitive than unrodded. Resolution path: Kyle re-runs his deck on VIII.0 (VII.0 HDF5 does not exist on Triforce — only VII.1, VIII.0, VIII.1).
- MCNP reference targets: **keff = 0.979959 rods-in, 1.19753 rods-out; blade worth 18,540 pcm (~24.7 $).**

---

## 4. Codebase Architecture

Five-file modular model. **All runs go through one code path:** `core.build_model()`.

| File | Role |
|---|---|
| `core.py` | Central driver. `CoreConfig` dataclass = single control surface. CLI: `--insertion`, `--particles`, `--batches`, `--inactive`, `--seed`, `--output-dir`. Depletion scaffold stubbed (NotImplementedError) for future ADDER coupling. |
| `materials.py` | 8 materials, atom-fraction / atom-density basis, deck-authoritative values. |
| `geometry.py` | Full geometry. `build_core_geometry(withdrawn_fraction)` is the single construction path. Running `python geometry.py` directly performs self-checks + a `geometry_debug` overlap run. |
| `settings.py` | Eigenvalue settings, source box with `constraints={'fissionable': True}`, temperature interpolation. |
| `tallies.py` | `build_tallies()` attached by `build_model()`. |

**⚠️ THE BLADE DIRECTION CONVENTION — the #1 way to silently ruin a run:**
- `CoreConfig.blade_insertion_percent` (CLI `--insertion`): **0 = fully WITHDRAWN, 100 = fully INSERTED** (control-room sense).
- `geometry.build_core_geometry(withdrawn_fraction=f)`: **f = 0.0 fully INSERTED, f = 1.0 fully WITHDRAWN** (opposite sense).
- `build_model()` converts: `f = 1.0 − insertion_percent/100`. Never call geometry functions with an insertion percent, and never report results without stating which convention the number uses. Results in this document use **f (withdrawal fraction)**.

---

## 5. Geometry Reference (all cm)

**Lattice:** 8×9 rectangular lattice, pitch 7.7 × 8.1. Active 5×6 core: 23 standard fuel elements, 5 control elements, 2 flux traps, graphite reflector rows top/bottom (each block 7.6 × 8.0 with thin water gaps to the pitch boundary, aligned to the fuel lattice), water ring outside. `lattice.outer = water_univ` guards boundary roundoff. Vacuum boundaries at lattice edge and z = −65 / +95.

**Axial stack (every element footprint):**
- [−65, −45] water · [−45, −30] homogenized end-box (25 v/o Al / 75 v/o H₂O) · [−30, +30] active fuel · [+30, +45] end-box · [+45, +95] water.

**Standard fuel element (76 × 80 mm envelope):** 23 plates stacked in y; inner plates 0.127 cm / outer 0.1385 cm; inner clad 0.038 / outer 0.0495; meat 0.051 thick × 6.3 wide × 60 tall; water channels 0.219; side plates 0.48 (in x).

**Control element (17 fuel plates + blade structure):**
- Follower fuel stack centered, standard pitch: half-width = (17×0.127 + 16×0.219)/2 = **2.8315 cm**. Channels are the standard 0.219 — the compressed-channel (0.217) defect is fixed; do not reintroduce it.
- End block each side: `ELEM_Y/2 − 2.8315 = 1.1685 cm`, built fuel→wall as: feeder channel 0.219 | Al guide 0.150 | blade water g | **B₄C slot 0.310** | blade water g | Al guide 0.150 | outer offset water `CTRL_OUTER_OFFSET`.
- `g = CTRL_BLADE_WATER` auto-computes as the residual (currently 0.14475 with offset 0.05). Asserts enforce the budget closes to the wall exactly.
- **`CTRL_OUTER_OFFSET = 0.05` is a PLACEHOLDER — pending confirmation against Kyle's deck.** It is parameterized; change it in one place only and let g recompute.

**Blade model — fixed-length sliding absorber:** BLADE_LENGTH = 60, ROD_TRAVEL = 60. At fraction f: blade z = [−30 + 60f, +30 + 60f]. B₄C fills the slot x/y band in that z-range; water fills the slot outside it. All structural/fuel cells are clipped to the active zone z = [−30, +30].

**Flux trap:** aluminum block with a central ZCylinder water hole, `FT_HOLE_RADIUS = 2.5` (**ASSUMED** — inscribed radius of the 50 mm square; verify against the deck's CYL surface). Hole water is the hot 316.8 K material; gaps and axial regions use bulk 294 K water. Note: A-2 Table 1 vs. Chapter 7/Appendix G treat flux traps differently — confirm with Kyle which configuration is the benchmark reference.

---

## 6. Materials Reference (deck-authoritative)

All compositions in **atom fractions / atom densities (atom/b-cm)**. There is **no air** in the model (the July slide deck's materials table listing air is stale).

| Material | Composition | Notes |
|---|---|---|
| LEU U₃Si₂-Al fuel | U235 2.251800e-03, U238 9.034100e-03, Al27 3.256300e-02, Si28/29/30 6.938766e-03 / 3.524947e-04 / 2.326390e-04 | **No S(α,β)** (deck has no mt card) |
| B₄C absorber | B10 **1.914973e-02**, B11 **7.010412e-02**, C split by natural abundance (C12 = 2.005592e-02 × 0.9893, C13 × 0.0107) | VIII.0 has no C0 card; if a VII.0-compatible run is ever needed, revert to Kyle's `C0 2.005592e-02`. No S(α,β). |
| Bulk water | H1 6.66909e-02, O16 = H1/2 | 294 K, 0.9975 g/cm³ basis, H-1 + O-16 ONLY, `c_H_in_H2O` |
| Flux-trap water | H1 6.625423e-02, O16 = H1/2 | **316.8 K**, 0.9909 g/cm³ basis, separate material |
| Cladding / structure | Pure Al 2.70 g/cm³ | 6061 alloying elements omitted; **no S(α,β) on Al anywhere** |
| Graphite | 1.70 g/cm³ | `c_Graphite` S(α,β) |
| End-box homog | 25 v/o Al / 75 v/o H₂O (0.993 g/cm³), H-1 + O-16 only | `c_H_in_H2O` on the water component |

Temperature treatment: `settings.temperature = {'method': 'interpolation', 'default': 294.0}` (materials without explicit T evaluate at the deck's 294 K, not OpenMC's 293.6 K default).

Nuclear data: ENDF/B-VIII.0 HDF5. Local: `/home/tmccoy/nuclear-data/endfb-viii.0-hdf5/cross_sections.xml`. `OPENMC_CROSS_SECTIONS` env var takes precedence (set in the Slurm script on Triforce).

---

## 7. Hard Constraints (non-negotiable)

1. **Never modify absorber geometry — or any geometry — to chase keff or blade-worth targets.** Discrepancies get reconciled with the deck owner (Kyle), never absorbed by tuning.
2. **Kyle's deck governs.** Matching the deck while disagreeing with TECDOC is success, not a bug.
3. **Plan-then-approve gates for geometry edits.** Present the plan; get explicit approval before touching files. Surgical, localized changes only.
4. **No magic numbers.** Every dimension is a named, parameterized constant that traces to a deck line or TECDOC table. Unconfirmed values (e.g., `CTRL_OUTER_OFFSET`) are marked as placeholders in comments.
5. **All production runs go through `core.build_model()`** — never hand-assemble a model that bypasses the single code path.
6. **Report exact numerical values.** keff to 5 decimals with uncertainty; differences in pcm; state the blade convention used.

---

## 8. Verification Workflow (pre-flight, before every Triforce submission)

1. `python geometry.py` self-checks (layer-sum asserts, blade z-range asserts, `find_overlaps`/geometry_debug run) — geometry errors are silent in MCNP but loud in OpenMC; use that.
2. Cross-section geometry plots — inspect visually; arithmetic verification alone is not enough (this caught the control-element sprawl).
3. Coordinate assertions / material dump review.
4. Short keff tripwire run locally (small particles/batches) — sanity-check magnitude before burning cluster hours.
5. Full production run on Triforce.

Production statistics baseline: 50,000 particles/batch, 200 batches, 50 inactive (≈±40–45 pcm). Local WSL 12-core for dev/short runs.

---

## 9. Compute & Environment

- **Local:** WSL Ubuntu, conda env `openmc-env`, OpenMC 0.15.0, VS Code.
- **Cluster:** Triforce (Valerio's workstation, remote Slurm), `work` partition, 32 cores. Available libraries: ENDF/B-VII.1, VIII.0, VIII.1 (**no VII.0 HDF5 exists**).
- **Known blockers:** GitHub push to Valerio's repo blocked from the Argonne network (TLS proxy); push from Triforce instead. `settings.only_fissionable` deprecation warning is harmless (already migrated to `constraints={'fissionable': True}`); on the cleanup list.

---

## 10. Open Items

| Item | Owner/Path |
|---|---|
| Matched-library run: ask Kyle to re-run MCNP on ENDF/B-VIII.0 → isolate the −163 pcm rods-out offset | Kyle |
| Confirm `CTRL_OUTER_OFFSET` (~0.05, placeholder) against the deck | Kyle's deck |
| Confirm `FT_HOLE_RADIUS` (2.5 assumed) against the deck's CYL surface | Kyle's deck |
| Confirm which flux-trap configuration is the benchmark reference (A-2 Table 1 vs. Ch. 7/App. G) | Kyle |
| Reconcile blade worth in $ (deck ~24.7 vs. TECDOC 15.22) — documentation item, not a code change | Kyle |
| Publish model to `mascovale/CSM-Open-source-Reactor-Model-Library` (push from Triforce) | Thomas |
| ADDER-OpenMC depletion: chain file, power basis (10 MW), timesteps, integrator, operator type | Task 1 phase 2 |
| Tasks 2 & 3 (CPU/GPU runtime; conversion-tool assessment) | Downstream |
| Update the July 2026 status deck with the +8 pcm / −163 pcm / 18,418 pcm results | Thomas |

---

## 11. People

- **Kyle Anderson** (kanderson@anl.gov) — ANL Principal Nuclear Engineer. Day-to-day technical authority; owns the reference MCNP deck. Erik Wilson (erikwilson@anl.gov) is on the thread at ANL.
- **Valerio Mascolino** (valerio.mascolino@mines.edu) — Mines advisor. Owns Triforce and the public repo; performed the independent material-scan review.
- **Lindsey Morphey** (lmorphey@anl.gov) — ANL HR contact.

---

## 12. How to Work on This Project (for AI assistants)

- **Lead with the answer.** Exact numbers first, then reasoning. Preserve every significant digit; convert differences to pcm.
- **Flag open items plainly** — never bury an unconfirmed assumption. Placeholder values must be labeled as such in code and in prose.
- **Don't over-scaffold.** Thomas is technically precise; skip hedging, skip re-explaining basics, skip decorative structure.
- **Geometry edits:** propose a plan, wait for approval, then apply the minimal diff. Never batch a geometry change with unrelated cleanup.
- **When a result looks wrong, suspect the model before the physics, and the convention (Section 4 blade direction) before the model.**
- **Never suggest tuning toward a target.** If OpenMC and the deck disagree, the next step is diagnosis and an email to Kyle — not a parameter tweak.
- Email drafts: short, professional; Thomas will ask about CC'ing and next steps — anticipate those.
- Stale-source warning: the July 2026 status deck predates the geometry fix (results in §3 supersede it) and its materials slide lists air (removed). Trust the code and this document.
