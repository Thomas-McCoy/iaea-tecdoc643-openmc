#!/usr/bin/env bash
#
# sync_deliverable.sh — push the dev tree to the public deliverable repo.
#
#   dev:         ~/iaea-tecdoc643-openmc            (Thomas-McCoy/iaea-tecdoc643-openmc)
#   deliverable: ~/CSM-Open-source-Reactor-Model-Library/iaea-tecdoc-core
#                (M-PRISM-Colorado-School-of-Mines/CSM-Open-source-Reactor-Model-Library;
#                 moved from mascovale/ 2026-10-19)
#
# RUN IT FROM A CLEAN CHECKOUT (a `git worktree` or local clone of the commit
# to ship).
# rsync copies whatever is on disk, and untracked directories that no
# exclusion names (tools/, viz_out/, .claude/ ...) would ship from a working
# tree. The uncommitted-changes check below only sees tracked files.
#
# WHY THIS EXISTS
#
# Testament II T2.7 replaced the old `cp model/*.py` runbook with a whole-tree
# rsync after the 7/20 stray-file incident. A whole-tree rsync copies
# everything, and two things that must NOT ship are covered by no .gitignore
# rule: docs/ and model/run_vii_mat.py. SUPERSEDED_NOTES.md section 5 documents
# the exclusion list, but documentation does not enforce — the next manual
# rsync ships both regardless of what the notes say. This script makes the
# exclusions executable.
#
# It is also what gets run to fix Phase 1 audit BLOCKER #1 (the deliverable repo
# is serving a 2026-07-27 model: FT_HOLE_RADIUS = 2.5, 60 cm plates, 15 cm
# end-box, 8x9 lattice, no pool), so it needs to exist before that happens.
#
# DEFAULTS TO DRY RUN. Writing requires --write, explicitly.
#
#   ./scripts/sync_deliverable.sh              # dry run, shows what would change
#   ./scripts/sync_deliverable.sh --write      # actually copies
#   ./scripts/sync_deliverable.sh --dest PATH  # override the destination
#
# It does NOT commit or push in the deliverable repo. Review the diff there,
# then commit by hand. Publishing is a decision, not a side effect of syncing.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/CSM-Open-source-Reactor-Model-Library/iaea-tecdoc-core"
WRITE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --write)  WRITE=1; shift ;;
        --dry-run) WRITE=0; shift ;;
        --dest)   DEST="$2"; shift 2 ;;
        -h|--help) sed -n '2,37p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# -----------------------------------------------------------------------------
# EXCLUSIONS — SUPERSEDED_NOTES.md section 5. Keep the two lists in step.
#
# The deliverable is THE MODEL, not the engineering record.
#
# INCLUDES are passed BEFORE the exclusions (rsync: first matching rule wins).
# They carve the one file the model itself depends on out of docs/:
# reference_materials.csv is the source of record that materials.py cites and
# tests/test_reference_materials.py reads.
# -----------------------------------------------------------------------------
INCLUDES=(
    'docs/'
    'docs/reference_materials.csv'
)
EXCLUDES=(
    # --- engineering record, never ships -------------------------------------
    'docs/*'                    # PHASE1_AUDIT.md, SUPERSEDED_NOTES.md — internal
                                # audit, open questions, provenance weaknesses
                                # (everything in docs/ except the INCLUDES)
    'PROJECT_BIBLE.md'          # standing rule; confirmed absent, keep it so
    'TESTAMENT_*.md'            # same class

    # --- a second, WRONG source of truth --------------------------------------
    'model/run_vii_mat.py'      # runs clean and builds a DIFFERENT model:
                                # graphite 1.70, end-box 1.41975, no c_Al27.
                                # Publishing it is worse than publishing nothing.
                                # Remove this line once the rewrite lands.
    'model/BENCHMARK_DIMENSIONS.md'  # stale (Hf blade, 0.1075 CFE offset,
                                     # graphite 1.70, 15 cm cap); excluded until
                                     # rewritten (PROJECT_BIBLE §10)

    # --- generated output ------------------------------------------------------
    'plots/'                    # nothing tracked since 4a76220; generators ship
    'figures/_proof/'
    'figures/*.pdf'
    'figures/*.png'
    'figures/solidworks_*.txt'
    'run_results/'
    '*.xml'                     # geometry.xml, settings.xml, plots.xml, model.xml
    '*.h5'
    '*.out'

    # --- vcs / tooling ---------------------------------------------------------
    '.git'                      # NOT '.git/': in a worktree .git is a FILE,
                                # and shipping it makes the destination a
                                # worktree of the dev repo
    '.gitignore'                # the deliverable keeps its own
    '/README.md'                # same: the deliverable's README is Valerio's;
                                # the dev README is empty (leading / = top
                                # level only)
    '/analysis/'                # cluster-specific, not reviewed for the
                                # deliverable; excluded for now
    '__pycache__/'
    '*.py[cod]'
    '.pytest_cache/'
    '.ipynb_checkpoints/'
    '.DS_Store'
    'scripts/sync_deliverable.sh'   # this script is dev-side tooling
)

RSYNC_ARGS=(-av --delete)
for i in "${INCLUDES[@]}"; do RSYNC_ARGS+=(--include "$i"); done
for e in "${EXCLUDES[@]}"; do RSYNC_ARGS+=(--exclude "$e"); done

echo "=============================================================="
echo " deliverable sync"
echo "   source: $SRC"
echo "   dest:   $DEST"
echo "   mode:   $([[ $WRITE -eq 1 ]] && echo 'WRITE' || echo 'DRY RUN (use --write to apply)')"
echo "=============================================================="

if [[ ! -d "$DEST" ]]; then
    echo "ERROR: destination does not exist: $DEST" >&2
    exit 1
fi

# Refuse to publish an uncommitted tree. What ships must be reproducible from a
# commit; a dirty tree cannot be pointed at.
if ! git -C "$SRC" diff --quiet HEAD 2>/dev/null; then
    echo
    echo "ERROR: source tree has uncommitted changes." >&2
    git -C "$SRC" status --short >&2
    echo >&2
    echo "Commit or stash first — the deliverable must correspond to a commit." >&2
    exit 1
fi

SHA="$(git -C "$SRC" rev-parse --short HEAD)"
BRANCH="$(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
echo "  source commit: $SHA ($BRANCH)"

# Warn if the source branch has not been pushed. Publishing code whose history
# exists on exactly one laptop is how a deliverable becomes unreproducible.
if ! git -C "$SRC" rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
    echo "  WARNING: branch '$BRANCH' has no upstream on origin — the published"
    echo "           model would have no public history to correspond to."
elif [[ -n "$(git -C "$SRC" log "origin/$BRANCH..$BRANCH" --oneline 2>/dev/null)" ]]; then
    echo "  WARNING: branch '$BRANCH' has unpushed commits — push before publishing."
fi
echo

if [[ $WRITE -eq 1 ]]; then
    rsync "${RSYNC_ARGS[@]}" "$SRC"/ "$DEST"/
    echo
    echo "Sync complete from $SHA."
    echo "NOT committed in the deliverable repo — review and commit by hand:"
    echo "    git -C $(dirname "$DEST") status"
else
    rsync "${RSYNC_ARGS[@]}" --dry-run "$SRC"/ "$DEST"/
    echo
    echo "DRY RUN — nothing was written. Re-run with --write to apply."
fi
