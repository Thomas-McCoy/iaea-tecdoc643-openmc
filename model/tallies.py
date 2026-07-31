"""
tallies.py
----------
Tally definitions for the IAEA TECDOC-643 Appendix A-2
Generic 10 MW LEU Research Reactor Core (Argonne design).

Reference:
    IAEA-TECDOC-643, "Research Reactor Core Conversion Guidebook,
    Volume 2: Analysis (Appendices A-F)," IAEA, Vienna, 1992.
    Appendix A-2: Generic 10 MW Reactor — Argonne National Laboratory.

Exposes build_tallies() -> openmc.Tallies so drivers (core.build_model) can
attach the tallies to an openmc.Model. Nothing is written to disk at import
time; run this file directly only if you want a standalone tallies.xml.

Tallies:
    flux_map — 2D neutron flux map over the core footprint, z spanning the
        active fuel meat. rank_rods.py reads it from the statepoint to find
        which control rod sits in the highest flux (= highest-worth rod).
        Every bound is derived from geometry.py constants — see the note in
        build_tallies() about why this must never be hardcoded again.
"""
import openmc
from geometry import (CORE_HALF_X, CORE_HALF_Y, HALF_Z,
                      N_LAT_X, N_LAT_Y, PITCH_X, PITCH_Y)

# Flux-map resolution, held at the value the old hardcoded mesh used: it was
# 160 cells over 8 pitches in x and 180 over 9 in y, i.e. 20 per lattice pitch
# both ways. Expressing it per-pitch keeps the physical cell size fixed if the
# core ever gains or loses positions.
MESH_CELLS_PER_PITCH = 20


def build_tallies():
    """Return the openmc.Tallies for a production run (flux map).

    The mesh bounds are DERIVED from the core envelope, never written as
    literals. They were previously hardcoded to +/-4.0*PITCH_X, +/-4.5*PITCH_Y —
    the extent of the old 8x9 lattice including its water ring. After B4 reduced
    the lattice to the 6x7 core positions and moved the surrounding water into
    an explicit pool box, those numbers silently became wrong: they overhang the
    core by a full pitch cell on every side, so the outer mesh columns would tally
    pool water while the whole map shifted relative to the element positions
    rank_rods.py maps them back onto.
    """
    mesh = openmc.RegularMesh()
    mesh.dimension   = [N_LAT_X * MESH_CELLS_PER_PITCH,
                        N_LAT_Y * MESH_CELLS_PER_PITCH, 1]
    mesh.lower_left  = [-CORE_HALF_X, -CORE_HALF_Y, -HALF_Z]
    mesh.upper_right = [ CORE_HALF_X,  CORE_HALF_Y,  HALF_Z]

    # The mesh must tile the core envelope exactly — a mesh that overhangs the
    # core is how the stale bounds went unnoticed.
    assert abs((mesh.upper_right[0] - mesh.lower_left[0])
               - N_LAT_X * PITCH_X) < 1e-9, "flux mesh does not span the core in x"
    assert abs((mesh.upper_right[1] - mesh.lower_left[1])
               - N_LAT_Y * PITCH_Y) < 1e-9, "flux mesh does not span the core in y"

    flux_tally = openmc.Tally(name='flux_map')
    flux_tally.filters = [openmc.MeshFilter(mesh)]
    flux_tally.scores  = ['flux']

    return openmc.Tallies([flux_tally])


if __name__ == '__main__':
    build_tallies().export_to_xml()
    print("tallies.xml written (flux map).")
