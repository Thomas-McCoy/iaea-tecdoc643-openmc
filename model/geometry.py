"""
geometry.py
-----------
Geometry definitions for the IAEA TECDOC-643 Appendix A-2
Generic 10 MW LEU Research Reactor Core (Argonne design).

Reference:
    IAEA-TECDOC-643, "Research Reactor Core Conversion Guidebook,
    Volume 2: Analysis (Appendices A-F)," IAEA, Vienna, 1992.
    Appendix A-2: Generic 10 MW Reactor — Argonne National Laboratory.

Core Layout:
    - 7x6 core positions (TECDOC-643 A-2 Table 1 quotes 8x9 grid-plate
      positions, which counts the surrounding water ring)
    - 23 standard fuel elements, 5 control fuel elements, 2 flux traps,
      12 graphite reflector positions = 42 = 7x6
    - Lattice pitch: 77 mm x 81 mm
    - Active fuel meat height: 60 cm; plate height 62 cm

Axial model structure (symmetric about z=0):
    CORE_BOTTOM = -90 cm  (vacuum)
    [-90, -45]  : 45 cm light water
    [-45, -31]  : 14 cm homogenized end-box (0.25 Al / 0.75 H₂O by volume)
    [-31, -30]  :  1 cm unfueled clad extension
    [-30, +30]  : 60 cm active fuel meat
    [+30, +31]  :  1 cm unfueled clad extension
    [+31, +45]  : 14 cm homogenized end-box
    [+45, +90]  : 45 cm light water
    CORE_TOP    = +90 cm  (vacuum) — COINCIDES with the fully-withdrawn (f=1)
                  blade top; no water cap above the withdrawn blade.
    Sum check: 2 * (45 + 14 + 1 + 30) = 180 cm — tripwired below.

Lateral model structure:
    The 7x6 lattice is enclosed in an explicit water-filled pool box whose
    lateral faces sit POOL_WATER_THICK = 38.5 cm outboard of the core
    envelope. Vacuum boundary at the pool faces.
        x: 6 * 7.7 + 2 * 38.5 = 123.2 cm
        y: 7 * 8.1 + 2 * 38.5 = 133.7 cm
    Pool water is the 294 K bulk water material, NOT the 316.8 K core coolant.

Control blade model — fixed-length sliding absorber:
    BLADE_LENGTH = 60 cm (rigid; never changes)
    ROD_TRAVEL   = 60 cm (full stroke)
    withdrawn_fraction f in [0, 1]:
        z_bot = -30 + f * 60   → f=0: -30,  f=1: +30
        z_top = z_bot + 60     → f=0: +30,  f=1: +90 (= CORE_TOP at f=1)
    b4c fills the Hf-slot x/y band for z in [z_bot, z_top]. An ENDBOX_HEIGHT
    (14 cm) homogenized (end_box_homog) end-box cap rides above the blade in
    the blade's own slot footprint, with its bottom at
    max(z_top, HALF_PLATE_Z) — see the A4 note in the control-element section.
    At f=0 the cap sits at [+31,+45], COPLANAR with the surrounding end-boxes
    (2026-07-20 decision), and the 1 cm slot band [+30,+31] between the blade
    top and the cap is core coolant water. At f=1 the blade top coincides with
    CORE_TOP (z_top == +90), so the cap is pushed entirely out of the model and
    is NOT created — the blade itself fills the slot to the top.
    Plate/clad, structural and channel cells run the full plate height
    z=[-31, +31]; only the fuel meat is restricted to z=[-30, +30].
    End-box/water cells cover z outside [-31, +31].

Standard Fuel Element (LEU, U3Si2-Al, heterogeneous build):
    - Envelope:           76 x 80 mm
    - Side plates:        4.8 mm each (aluminum, in x)
    - Active stack:       66.4 mm wide between side plate inner faces
    - 23 plates:          1.27 mm inner, 1.5 mm outer (outer plates clad on
                          both faces of the meat at the outer 0.495 mm
                          thickness, not just the face away from the stack)
    - Fuel meat:          0.51 mm thick x 63 mm wide x 600 mm tall
    - Plate height:       620 mm (600 mm meat + 10 mm unfueled clad each end)
    - Inner clad:         0.38 mm  |  Outer clad: 0.495 mm

All dimensions in cm.
"""

import openmc
from materials import (fuel, clad, water, water_core, b4c, graphite, aluminum,
                       end_box_homog, N_AXIAL_ZONES, make_zoned_fuel)

# =============================================================================
# LATTICE / ELEMENT ENVELOPE
# =============================================================================

PITCH_X = 7.7    # cm  (77 mm)
PITCH_Y = 8.1    # cm  (81 mm)

ELEM_X = 7.6     # cm  (76 mm)
ELEM_Y = 8.0     # cm  (80 mm)

# --- Axial plate / meat heights ---------------------------------------------
# The reference MCNP model carries 1 cm of UNFUELED cladding above and below
# the active meat: the plates stand 62 cm tall with 60 cm of meat inside them.
# MEAT_HEIGHT and PLATE_HEIGHT are INDEPENDENT primaries; the clad extension is
# derived from the pair and is never written as a literal anywhere.
MEAT_HEIGHT  = 60.0   # cm (600 mm) — active fuel meat height  [TECDOC] (MCNP MATCH)
PLATE_HEIGHT = 62.0   # cm (620 mm) — fuel / unfueled plate height   [MCNP]
CLAD_EXT     = (PLATE_HEIGHT - MEAT_HEIGHT) / 2.0   # 1.0 cm          [DERIVED]

assert CLAD_EXT > 0, "PLATE_HEIGHT must exceed MEAT_HEIGHT (clad extension <= 0)"

# Element dimension (Z). Side plates, unfueled control plates, flux-trap blocks
# and reflector blocks all run the full plate height, not the meat height.
ELEM_Z = PLATE_HEIGHT   # 62.0 cm                                     [MCNP]

# Inter-element water gap — documentation/tripwire only. Feeds no surface or
# cell directly; every gap cell derives its width from the pitch/envelope
# XPlane/YPlane objects themselves (PITCH_X/Y, ELEM_X/Y above), not from
# these constants. Exists so a future PITCH/ELEM edit that zeroes or inverts
# the gap fails loudly here instead of emitting a zero-width sliver cell.
GAP_X = (PITCH_X - ELEM_X) / 2.0   # cm
GAP_Y = (PITCH_Y - ELEM_Y) / 2.0   # cm
assert GAP_X > 0, "PITCH_X must exceed ELEM_X (zero/negative gap)"
assert GAP_Y > 0, "PITCH_Y must exceed ELEM_Y (zero/negative gap)"

SIDE_PLATE_THICK = 0.48   # cm  (4.8 mm)
ACTIVE_STACK_X   = ELEM_X - 2 * SIDE_PLATE_THICK   # 6.64 cm

# =============================================================================
# PLATE / MEAT / CLAD DIMENSIONS
# =============================================================================

PLATE_THICK_INNER = 0.127    # cm  (1.27 mm)

CLAD_THICK_INNER = 0.038     # cm  (0.38 mm)
CLAD_THICK_OUTER = 0.0495    # cm  (0.495 mm)

MEAT_THICK = 0.051           # cm  (0.51 mm)
MEAT_WIDTH = 6.3             # cm  (63 mm)

# Outer plates (first/last in the stack) are clad at the outer thickness on
# BOTH faces of the meat, not just the face away from the stack — so their
# total thickness is meat + 2*CLAD_THICK_OUTER, not meat + inner + outer.
PLATE_THICK_OUTER = MEAT_THICK + 2 * CLAD_THICK_OUTER   # 0.15 cm  (1.5 mm)

N_PLATES_STD  = 23
N_PLATES_CTRL = 17

WATER_CHAN_THICK = 0.219     # cm  (2.19 mm)

# Standard element plate-stack height and the residual end water gap between
# the outermost plate face and the element envelope edge. [DERIVED]
STD_STACK_HEIGHT = (2 * PLATE_THICK_OUTER
                    + (N_PLATES_STD - 2) * PLATE_THICK_INNER
                    + (N_PLATES_STD - 1) * WATER_CHAN_THICK)   # 7.785 cm
STD_END_WATER = (ELEM_Y - STD_STACK_HEIGHT) / 2.0             # 0.1075 cm  [DERIVED]
assert STD_END_WATER > 0, "standard element end water gap must be positive"

# Flux trap cylindrical water hole radius.
# ASSUMED 2.5 cm (inscribed radius of the 50 mm square hole).
# Area-equivalent radius would be 5/sqrt(pi) ~2.8209 cm.
# VERIFY against Kyle's MCNP deck — if the deck uses a CYL surface
# with a different radius, update FT_HOLE_RADIUS here.
FT_HOLE_RADIUS = 2.5         # cm

# HALF_Z is the ACTIVE MEAT half-height and must track MEAT_HEIGHT, not ELEM_Z.
# Since B1 the two differ (60 vs 62): the blade travel, the meat cells and the
# depletion zone tiling all key off HALF_Z, and deriving it from ELEM_Z would
# silently move the meat to +/-31 along with the plates.
HALF_Z       = MEAT_HEIGHT / 2.0     # 30.0 cm — active meat half-height  [DERIVED]
HALF_PLATE_Z = PLATE_HEIGHT / 2.0    # 31.0 cm — plate / clad half-height [DERIVED]

assert abs(HALF_PLATE_Z - (HALF_Z + CLAD_EXT)) < 1e-12, \
    "HALF_PLATE_Z must equal HALF_Z + CLAD_EXT"

# =============================================================================
# AXIAL MODEL EXTENTS AND FIXED-LENGTH BLADE PARAMETERS
# =============================================================================

BLADE_LENGTH     = 60.0    # cm — rigid absorber blade (fixed length, translates in z)
ROD_TRAVEL       = 60.0    # cm — full stroke
CORE_TOP         = +90.0   # cm — vacuum boundary; COINCIDES with the fully-withdrawn
                            # (f=1) blade top (z_top = -30 + 60 + 60 = +90). No cap above.
CORE_BOTTOM      = -90.0   # cm — vacuum boundary; symmetric with CORE_TOP

# Homogenized end-box axial extent. The plates gaining 1 cm at each end and the
# end-box losing 1 cm are the same centimetre — +/-45 and +/-90 do not move.
ENDBOX_HEIGHT    = 14.0    # cm — homogenized end-box height            [MCNP]

ENDBOX_ABOVE_TOP = HALF_PLATE_Z + ENDBOX_HEIGHT    # +45.0 cm           [DERIVED]
ENDBOX_BELOW_BOT = -ENDBOX_ABOVE_TOP               # −45.0 cm           [DERIVED]
POOL_WATER_AXIAL = CORE_TOP - ENDBOX_ABOVE_TOP     # +45.0 cm           [DERIVED]

# Symmetry / height tripwires. Documentation + guard only: none of these feed a
# cell or surface directly. Tolerance-based, not ==, since every value here is
# now the end of a float derivation chain.
assert abs(CORE_TOP + CORE_BOTTOM) < 1e-12, "axial model must be symmetric about z=0"
assert abs((CORE_TOP - CORE_BOTTOM) - 180.0) < 1e-12, "total axial height must be 180 cm"
assert abs((CORE_TOP - ENDBOX_ABOVE_TOP) - POOL_WATER_AXIAL) < 1e-12, \
    "upper water region must be POOL_WATER_AXIAL"
assert abs((ENDBOX_BELOW_BOT - CORE_BOTTOM) - POOL_WATER_AXIAL) < 1e-12, \
    "lower water region must be POOL_WATER_AXIAL"
assert abs((ENDBOX_ABOVE_TOP - HALF_PLATE_Z) - ENDBOX_HEIGHT) < 1e-12, \
    "upper end-box must be ENDBOX_HEIGHT tall"
assert abs((-HALF_PLATE_Z - ENDBOX_BELOW_BOT) - ENDBOX_HEIGHT) < 1e-12, \
    "lower end-box must be ENDBOX_HEIGHT tall"

# B1 tripwire — the whole axial stack, layer by layer, must close on 180 cm:
#   2 * (45 water + 14 end-box + 1 clad extension + 30 half-meat) = 180
_AXIAL_STACK_SUM = 2.0 * (POOL_WATER_AXIAL + ENDBOX_HEIGHT + CLAD_EXT + HALF_Z)
assert abs(_AXIAL_STACK_SUM - 180.0) < 1e-12, (
    f"axial stack sums to {_AXIAL_STACK_SUM} cm, not 180 cm — layers: "
    f"water {POOL_WATER_AXIAL}, end-box {ENDBOX_HEIGHT}, clad ext {CLAD_EXT}, "
    f"half-meat {HALF_Z}")
assert abs(_AXIAL_STACK_SUM - (CORE_TOP - CORE_BOTTOM)) < 1e-12, \
    "axial layer sum disagrees with the CORE_BOTTOM..CORE_TOP model extent"

# Blade travel is unchanged by B1: the f=1 blade top must still land exactly on
# CORE_TOP, which is what makes the withdrawn case create no cap at all.
assert abs((-HALF_Z + ROD_TRAVEL + BLADE_LENGTH) - CORE_TOP) < 1e-12, \
    "f=1 blade top no longer coincides with CORE_TOP — cap logic assumes it does"

# Shared axial ZPlane surfaces — transmission (NOT vacuum boundaries).
# Defined once at module level and reused in every element universe to avoid
# creating redundant surfaces at identical z-values.
# _z_fuel_* bound the ACTIVE MEAT (+/-30); _z_plate_* bound the PLATES and every
# structural cell (+/-31). The 1 cm between them is unfueled cladding.
_z_fuel_bot     = openmc.ZPlane(z0=-HALF_Z)           # −30.0 cm
_z_fuel_top     = openmc.ZPlane(z0= HALF_Z)           # +30.0 cm
_z_plate_bot    = openmc.ZPlane(z0=-HALF_PLATE_Z)     # −31.0 cm
_z_plate_top    = openmc.ZPlane(z0= HALF_PLATE_Z)     # +31.0 cm
_z_endbox_above = openmc.ZPlane(z0=ENDBOX_ABOVE_TOP)  # +45.0 cm
_z_endbox_below = openmc.ZPlane(z0=ENDBOX_BELOW_BOT)  # −45.0 cm
_z_model_top    = openmc.ZPlane(z0=CORE_TOP)           # +90.0 cm
_z_model_bot    = openmc.ZPlane(z0=CORE_BOTTOM)        # −90.0 cm


# =============================================================================
# FUEL MEAT AXIAL DEPLETION ZONES
#
# [MCNP-VISUAL — UNCONFIRMED, pending Kyle] The zone count and the assumption
# of uniform zone height were read visually from a zx slice plot of the
# reference MCNP model — see the tagging block in materials.py, which owns
# N_AXIAL_ZONES. Nothing here is [TECDOC].
#
# The zone bounds are derived from the ACTIVE MEAT planes themselves (reading
# .z0 off the existing shared surfaces), NOT from ELEM_Z. ELEM_Z is the element
# extent, and since B1 the two HAVE diverged (62 cm element vs 60 cm meat);
# zones derived from ELEM_Z would tile 62 cm and silently mis-size every
# depletion volume. The tiling assert below tests the quantity that matters.
#
# Zoning is opt-in (build_core_geometry(depletion_zoning=True)). With it off,
# none of these surfaces are created and the model is unchanged.
# =============================================================================

MEAT_BOT_Z  = _z_fuel_bot.z0     # −30.0 cm — active meat lower bound
MEAT_TOP_Z  = _z_fuel_top.z0     # +30.0 cm — active meat upper bound

# MEAT_HEIGHT is a module-level primary (see the envelope block); it used to be
# derived here off these two planes. Since B1 the plates (62 cm) and the meat
# (60 cm) are different heights, so the derivation is inverted into a check:
# the meat planes must still bound exactly MEAT_HEIGHT, or the zone tiling
# below is sizing depletion volumes against the wrong stack.
assert abs((MEAT_TOP_Z - MEAT_BOT_Z) - MEAT_HEIGHT) < 1e-12, \
    "active meat planes do not bound MEAT_HEIGHT"

MEAT_ZONE_HEIGHT           = MEAT_HEIGHT / N_AXIAL_ZONES    # 12.0 cm for N=5
MEAT_ZONE_VOLUME_PER_PLATE = MEAT_THICK * MEAT_WIDTH * MEAT_ZONE_HEIGHT

assert abs((MEAT_BOT_Z + N_AXIAL_ZONES * MEAT_ZONE_HEIGHT) - MEAT_TOP_Z) < 1e-12, \
    "axial zones do not tile the active meat height"

# Interior zone dividers, created ONCE and reused across all 28 fueled element
# universes — never inside the per-element builder, which would put
# (N_AXIAL_ZONES-1) x 28 coincident redundant planes in the model.
#
# Created lazily rather than at import: module-level surface construction
# consumes the global auto-ID counter and would shift every subsequent surface
# ID, so the zoning-OFF model would stop being byte-for-byte identical to the
# Phase One baseline.
_FUEL_ZONE_PLANES = None


def fuel_zone_planes():
    """The N_AXIAL_ZONES-1 interior zone ZPlanes (−18, −6, +6, +18 for N=5)."""
    global _FUEL_ZONE_PLANES
    if _FUEL_ZONE_PLANES is None:
        _FUEL_ZONE_PLANES = [
            openmc.ZPlane(z0=MEAT_BOT_Z + k * MEAT_ZONE_HEIGHT)
            for k in range(1, N_AXIAL_ZONES)
        ]
    return _FUEL_ZONE_PLANES


def zone_z_bounds(k):
    """(lower, upper) ZPlane surfaces bounding axial zone k.

    zone 0 = bottom (z = MEAT_BOT_Z). The outermost bounds reuse the existing
    shared active-fuel planes, so no duplicate surface is made at ±30.
    """
    planes = fuel_zone_planes()
    return (_z_fuel_bot if k == 0 else planes[k - 1],
            _z_fuel_top if k == N_AXIAL_ZONES - 1 else planes[k])



# =============================================================================
# STANDARD FUEL ELEMENT
# 23 plates stacked in y, running in x. Plates are 62 cm tall (z) with 60 cm
# of meat inside them. All structural cells are bounded to the plate height
# z=[-31, +31]; only the meat stops at z=[-30, +30].
# End-box and water regions fill the full pitch footprint above/below.
# =============================================================================

def make_standard_fuel_element(elem_id, element_id=None, zoned=False):
    """
    Standard ANL/TECDOC A-2 fuel element.

    X = plate meat width direction (side plates bound this)
    Y = plate/channel stack direction (plates stacked here)
    Z = axial (plates -31 to +31 cm; active fuel meat -30 to +30 cm)

    elem_id     integer index, unchanged — drives every cell name.
    element_id  core-map position label ('B4', ...) — depletion zoning only.
    zoned       when True, each plate's meat is split into N_AXIAL_ZONES
                stacked cells sharing one material per zone across all plates
                of this element. When False the element is built exactly as it
                always has been.
    """
    if zoned and element_id is None:
        raise ValueError("zoned=True requires a core-map element_id label")

    # One material per axial zone, shared by all 23 plates of this element.
    zone_mats = ([make_zoned_fuel(element_id, k,
                                  N_PLATES_STD * MEAT_ZONE_VOLUME_PER_PLATE)
                  for k in range(N_AXIAL_ZONES)] if zoned else None)

    # Pitch cell boundaries
    pitch_left  = openmc.XPlane(x0=-PITCH_X / 2.0)
    pitch_right = openmc.XPlane(x0= PITCH_X / 2.0)
    pitch_front = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back  = openmc.YPlane(y0= PITCH_Y / 2.0)

    # Element envelope
    box_left  = openmc.XPlane(x0=-ELEM_X / 2.0)
    box_right = openmc.XPlane(x0= ELEM_X / 2.0)
    box_front = openmc.YPlane(y0=-ELEM_Y / 2.0)
    box_back  = openmc.YPlane(y0= ELEM_Y / 2.0)

    # Side plate inner faces
    side_inner_left  = openmc.XPlane(x0=-ELEM_X / 2.0 + SIDE_PLATE_THICK)
    side_inner_right = openmc.XPlane(x0= ELEM_X / 2.0 - SIDE_PLATE_THICK)

    # Fuel meat X boundaries
    meat_left  = openmc.XPlane(x0=-MEAT_WIDTH / 2.0)
    meat_right = openmc.XPlane(x0= MEAT_WIDTH / 2.0)

    # Axial bounds — reuse module-level surfaces (avoids redundant surface IDs).
    # meat_z* bound the fuel meat only (+/-30); plate_z bounds the plates and
    # every structural cell (+/-31). The clad cells subtract the full meat
    # region, so the 1 cm bands [+/-30, +/-31] inside the meat footprint come
    # out as unfueled cladding with no extra cell.
    meat_zbot = _z_fuel_bot   # −30 cm
    meat_ztop = _z_fuel_top   # +30 cm
    plate_z   = +_z_plate_bot & -_z_plate_top   # [−31, +31]

    cells = []

    plate_thicks = (
        [PLATE_THICK_OUTER]
        + [PLATE_THICK_INNER] * (N_PLATES_STD - 2)
        + [PLATE_THICK_OUTER]
    )

    stack_height_y = sum(plate_thicks) + (N_PLATES_STD - 1) * WATER_CHAN_THICK
    # Tie the built stack to the module-level derived end-water gap.
    assert abs((ELEM_Y - stack_height_y) / 2.0 - STD_END_WATER) < 1e-9, \
        "standard stack end water gap disagrees with STD_END_WATER"
    y = -stack_height_y / 2.0
    stack_bottom_surf = openmc.YPlane(y0=y)

    for i, plate_thick in enumerate(plate_thicks):
        is_first = (i == 0)
        is_last  = (i == N_PLATES_STD - 1)

        plate_bottom = openmc.YPlane(y0=y)
        plate_top    = openmc.YPlane(y0=y + plate_thick)

        if is_first or is_last:
            # Outer plates: clad at the outer thickness on BOTH faces of the
            # meat (not just the face away from the stack).
            clad_bottom = CLAD_THICK_OUTER
            clad_top    = CLAD_THICK_OUTER
        else:
            clad_bottom = CLAD_THICK_INNER 
            clad_top    = CLAD_THICK_INNER

        meat_bottom = openmc.YPlane(y0=y + clad_bottom)
        meat_top    = openmc.YPlane(y0=y + plate_thick - clad_top)

        # Meat: bounded in x, y, AND z (active zone only)
        meat_xy = +meat_left & -meat_right & +meat_bottom & -meat_top
        meat_region = meat_xy & +meat_zbot & -meat_ztop

        # Plate region bounded to active zone
        plate_region = (
            +side_inner_left & -side_inner_right &
            +plate_bottom & -plate_top &
            plate_z
        )

        if zoned:
            # One cell per axial zone. The clad cell below still subtracts the
            # FULL meat_region, so the zone cells tile the same volume the
            # single meat cell occupied — no gap, no overlap.
            for k in range(N_AXIAL_ZONES):
                z_lo, z_hi = zone_z_bounds(k)
                cells.append(openmc.Cell(
                    name=f'std{elem_id}_meat_{i}_z{k}',
                    fill=zone_mats[k],
                    region=meat_xy & +z_lo & -z_hi
                ))
        else:
            cells.append(openmc.Cell(
                name=f'std{elem_id}_meat_{i}',
                fill=fuel,
                region=meat_region
            ))
        cells.append(openmc.Cell(
            name=f'std{elem_id}_clad_{i}',
            fill=clad,
            region=plate_region & ~meat_region
        ))

        y += plate_thick

        if not is_last:
            chan_bottom = plate_top
            chan_top    = openmc.YPlane(y0=y + WATER_CHAN_THICK)
            cells.append(openmc.Cell(
                name=f'std{elem_id}_chan_{i}',
                fill=water_core,
                region=(
                    +side_inner_left & -side_inner_right &
                    +chan_bottom & -chan_top &
                    plate_z
                )
            ))
            y += WATER_CHAN_THICK

    stack_top_surf = openmc.YPlane(y0=y)

    # Water below and above the plate stack — active zone only
    cells.append(openmc.Cell(
        name=f'std{elem_id}_water_below_stack',
        fill=water_core,
        region=(
            +box_front & -stack_bottom_surf &
            +side_inner_left & -side_inner_right &
            plate_z
        )
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_water_above_stack',
        fill=water_core,
        region=(
            +stack_top_surf & -box_back &
            +side_inner_left & -side_inner_right &
            plate_z
        )
    ))

    # Side plates — active zone only
    cells.append(openmc.Cell(
        name=f'std{elem_id}_side_left',
        fill=aluminum,
        region=(
            +box_left & -side_inner_left &
            +box_front & -box_back &
            plate_z
        )
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_side_right',
        fill=aluminum,
        region=(
            +side_inner_right & -box_right &
            +box_front & -box_back &
            plate_z
        )
    ))

    # Inter-element water gaps — active zone only
    cells.append(openmc.Cell(
        name=f'std{elem_id}_gap_xleft',
        fill=water_core,
        region=(
            +pitch_left & -box_left &
            +pitch_front & -pitch_back &
            plate_z
        )
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_gap_xright',
        fill=water_core,
        region=(
            +box_right & -pitch_right &
            +pitch_front & -pitch_back &
            plate_z
        )
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_gap_yfront',
        fill=water_core,
        region=(
            +box_left & -box_right &
            +pitch_front & -box_front &
            plate_z
        )
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_gap_yback',
        fill=water_core,
        region=(
            +box_left & -box_right &
            +box_back & -pitch_back &
            plate_z
        )
    ))

    # ── Axial regions above/below the active fuel ──────────────────────────
    # End-box is one solid full-pitch homogenized block — no inter-element
    # water gap subdivision (the end-box material is already a homogenized
    # Al/water mixture, so a physical gap slice within it is not meaningful).
    full_pitch = +pitch_left & -pitch_right & +pitch_front & -pitch_back

    cells.append(openmc.Cell(
        name=f'std{elem_id}_upper_endbox',
        fill=end_box_homog,
        region=full_pitch & +_z_plate_top & -_z_endbox_above   # +31 → +45 cm
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_upper_water',
        fill=water,
        region=full_pitch & +_z_endbox_above & -_z_model_top
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_lower_endbox',
        fill=end_box_homog,
        region=full_pitch & +_z_endbox_below & -_z_plate_bot   # −45 → −31 cm
    ))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_lower_water',
        fill=water,
        region=full_pitch & +_z_model_bot & -_z_endbox_below
    ))

    return openmc.Universe(name=f'std_fuel_elem_{elem_id}', cells=cells)


# =============================================================================
# CONTROL ELEMENT
# Architecture: two end blocks + central 17-plate fuel follower stack, built
# on the SAME standard 0.127 cm plate / 0.219 cm channel pitch as the standard
# fuel element (TECDOC A-2 Table 1: "17 + 4 Al plates").
#
#   Follower fuel stack (17 plates + 16 channels), centered on the element:
#     half-width = (17*PLATE_THICK_INNER + 16*WATER_CHAN_THICK) / 2 = 2.8315 cm
#
#   Each end, from the fuel stack outward to the element wall:
#     [feeder channel 0.219 | Al inner guide 0.150 | blade water g |
#      B4C blade slot 0.310 | blade water g | Al outer guide 0.150 |
#      outer offset water OUTER_OFFSET]
#   The feeder channel is a standard fuel-to-fuel water channel (matches the
#   follower's own plate pitch). The two blade-flanking water gaps are EQUAL
#   (even spacing) and are the residual after every other layer is fixed:
#     g = (END_BLOCK - 2*CTRL_AL_PLATE_THICK - ABSORBER_THICK - CTRL_OUTER_OFFSET
#          - CTRL_FEEDER_CHANNEL) / 2
#   where END_BLOCK = ELEM_Y/2 - CTRL_FUEL_STACK_HALF (1.1685 cm, fixed by the
#   element envelope and the fuel stack half-width above).
#
# Fixed-length sliding blade:
#   The B4C absorber blade is BLADE_LENGTH=60 cm long and translates in z.
#   At fraction f, the blade occupies z=[z_bot, z_top] = [-30+f*60, +30+f*60].
#   b4c fills the Hf-slot x/y band for z in [z_bot, z_top] across the full
#   model height. Below z_bot, water fills the slot down to the plate bottom
#   (-31) — the blade never dips below z=-30, so the lower end-box/water are
#   uniform material with no reserved slot at all. Above z_top, the slot's own
#   material is region-appropriate (coolant up to +31 if the blade is below
#   it, then the 14 cm cap, then water to CORE_TOP); at f=1, z_top == CORE_TOP
#   so that complement is zero-measure (no cap).
#   All guide/slider/fuel/channel cells are bounded to the PLATE height
#   z=[-31, +31]; only the fuel meat stops at z=[-30, +30]; end-box/water cells
#   fill z outside [-31, +31].
# =============================================================================

ABSORBER_THICK  = 0.31

CTRL_FUEL_WIDTH_X   = ACTIVE_STACK_X
CTRL_SIDE_PLATE_X   = SIDE_PLATE_THICK
CTRL_AL_PLATE_THICK = 0.127   # cm (1.27 mm) [TECDOC] — was 0.15 (an Argonne
                              # TH-analysis convenience); reverted 2026-07-20.
CTRL_HF_THICK       = ABSORBER_THICK

N_CTRL_FUEL_PLATES  = 17
CTRL_PLATE_PITCH    = PLATE_THICK_INNER + WATER_CHAN_THICK   # 0.346 cm

# N_PLATES_CTRL (module top) and N_CTRL_FUEL_PLATES are two names for the same
# 17-plate follower stack — pre-existing duplication. The follower loop and the
# zoned-material volumes both key off N_CTRL_FUEL_PLATES; this tripwire stops
# the two from drifting apart and silently mis-sizing a depletion volume.
assert N_CTRL_FUEL_PLATES == N_PLATES_CTRL, \
    "N_CTRL_FUEL_PLATES and N_PLATES_CTRL disagree on the follower plate count"

# Follower fuel stack half-width (standard 0.127/0.219 pitch, symmetric)
CTRL_FUEL_STACK_HALF = (N_CTRL_FUEL_PLATES * PLATE_THICK_INNER
                        + (N_CTRL_FUEL_PLATES - 1) * WATER_CHAN_THICK) / 2.0  # 2.8315 cm

# Feeder channel: the follower's outermost fuel plate to the inner guide
# plate is a standard fuel-to-fuel water channel, same width as every
# plate-to-plate channel in the stack above it.
CTRL_FEEDER_CHANNEL = WATER_CHAN_THICK   # 0.219 cm [DERIVED — standard channel]

# Gap between the outer guide plate and the element wall, likewise set to the
# standard-element end gap.
CTRL_OUTER_OFFSET = STD_END_WATER   # 0.1075 cm [DERIVED, 2026-07-20 meeting]

# End-block budget: everything between the fuel stack edge and the wall.
CTRL_END_BLOCK = ELEM_Y / 2.0 - CTRL_FUEL_STACK_HALF   # 1.1685 cm

# Blade-flanking water gap — residual, split equally on both sides of the
# blade. Recomputes automatically if CTRL_OUTER_OFFSET (or any layer above)
# changes.
CTRL_BLADE_WATER = (CTRL_END_BLOCK - CTRL_FEEDER_CHANNEL
                    - 2.0 * CTRL_AL_PLATE_THICK - ABSORBER_THICK
                    - CTRL_OUTER_OFFSET) / 2.0
# With the 2026-07-20 values this evaluates to exactly:
#   (1.1685 - 0.219 - 2*0.127 - 0.31 - 0.1075) / 2 = 0.139 cm

assert CTRL_BLADE_WATER >= 0.05, (
    f"CTRL_BLADE_WATER={CTRL_BLADE_WATER:.5f} cm is degenerate for "
    f"CTRL_AL_PLATE_THICK={CTRL_AL_PLATE_THICK}, "
    f"CTRL_OUTER_OFFSET={CTRL_OUTER_OFFSET} — check end-block budget")


def make_control_fuel_element(elem_id, withdrawn_fraction=0.0,
                              element_id=None, zoned=False):
    """
    Control fuel element with a fixed-length (60 cm) B4C absorber blade that
    translates in z.

    withdrawn_fraction f in [0, 1]:
        f=0 → blade at z=[-30, +30] (all-in, blade spans the active meat)
        f=1 → blade at z=[+30, +90] (all-out, blade entirely above active fuel)

    The blade always exists; only its z-position changes.

    elem_id     integer index, unchanged — drives every cell name.
    element_id  core-map position label ('C2', ...) — depletion zoning only.
    zoned       when True, each follower plate's meat is split into
                N_AXIAL_ZONES stacked cells sharing one material per zone
                across all 17 plates. The absorber slot lives in a different
                y-band than the meat (see the slot/meat disjointness note in
                the follower section below), so the axial cut never touches
                the blade, its slot, or the sliding-cap logic.
    """
    if zoned and element_id is None:
        raise ValueError("zoned=True requires a core-map element_id label")

    # One material per axial zone, shared by all 17 follower plates.
    zone_mats = ([make_zoned_fuel(element_id, k,
                                  N_CTRL_FUEL_PLATES * MEAT_ZONE_VOLUME_PER_PLATE)
                  for k in range(N_AXIAL_ZONES)] if zoned else None)

    f = withdrawn_fraction
    z_bot = -HALF_Z + f * ROD_TRAVEL   # blade bottom
    z_top = z_bot + BLADE_LENGTH        # blade top

    assert z_bot >= CORE_BOTTOM, (
        f"ctrl{elem_id}: blade bottom {z_bot:.2f} < CORE_BOTTOM {CORE_BOTTOM}")
    assert z_top <= CORE_TOP, (
        f"ctrl{elem_id}: blade top {z_top:.2f} > CORE_TOP {CORE_TOP}")
    # These two are the sole justification for (a) merging the lower end-box/
    # water into uniform material with no Hf-slot exclusion, and (b) never
    # needing an "above-active" water-gap cell (the blade always reaches at
    # least the top of the active zone). If travel or geometry parameters
    # ever change so these fail, both simplifications below become wrong.
    assert z_bot >= -HALF_Z, (
        f"ctrl{elem_id}: blade_z_bot={z_bot:.2f} < -HALF_Z ({-HALF_Z}) — "
        "blade would enter the lower end-box/water; lower-side merge is invalid")
    assert z_top >= HALF_Z, (
        f"ctrl{elem_id}: blade_z_top={z_top:.2f} < HALF_Z ({HALF_Z}) — "
        "blade would leave a water gap above it inside the active zone")
    print(f"ctrl{elem_id}: f={f:.3f}  blade z=[{z_bot:.2f}, {z_top:.2f}] cm"
          f"  (within [{CORE_BOTTOM}, {CORE_TOP}] ✓)")

    # Axial surfaces for this blade position
    blade_z_bot = openmc.ZPlane(z0=z_bot)
    blade_z_top = openmc.ZPlane(z0=z_top)
    plate_z    = +_z_plate_bot & -_z_plate_top   # [−31, +31]

    cells = []

    # Pitch cell boundaries
    pitch_left  = openmc.XPlane(x0=-PITCH_X / 2.0)
    pitch_right = openmc.XPlane(x0= PITCH_X / 2.0)
    pitch_front = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back  = openmc.YPlane(y0= PITCH_Y / 2.0)

    # Element envelope
    elem_left  = openmc.XPlane(x0=-ELEM_X / 2.0)
    elem_right = openmc.XPlane(x0= ELEM_X / 2.0)
    elem_front = openmc.YPlane(y0=-ELEM_Y / 2.0)
    elem_back  = openmc.YPlane(y0= ELEM_Y / 2.0)

    # X-band for the interior stack (between side plates)
    side_inner_left  = openmc.XPlane(x0=-CTRL_FUEL_WIDTH_X / 2.0)
    side_inner_right = openmc.XPlane(x0= CTRL_FUEL_WIDTH_X / 2.0)

    # Fuel meat x/z bounds
    meat_zbot  = _z_fuel_bot
    meat_ztop  = _z_fuel_top
    meat_left  = openmc.XPlane(x0=-MEAT_WIDTH / 2.0)
    meat_right = openmc.XPlane(x0= MEAT_WIDTH / 2.0)

    # Y-layout — fuel stack is centered, half-width fixed by the standard
    # 0.127/0.219 pitch (CTRL_FUEL_STACK_HALF, module level).
    y_fuel_start = -CTRL_FUEL_STACK_HALF   # −2.8315 cm
    y_fuel_end   =  CTRL_FUEL_STACK_HALF   # +2.8315 cm

    # Bottom end block, built outward from the fuel stack to the wall:
    #   feeder channel (0.219) | inner guide (Al) | blade water (g) |
    #   B4C blade slot | blade water (g) | outer guide (Al) | outer offset water
    bot_slider_top = openmc.YPlane(y0=y_fuel_start - CTRL_FEEDER_CHANNEL)
    bot_slider_bot = openmc.YPlane(y0=bot_slider_top.y0 - CTRL_AL_PLATE_THICK)
    bot_hf_top     = openmc.YPlane(y0=bot_slider_bot.y0 - CTRL_BLADE_WATER)
    bot_hf_bot     = openmc.YPlane(y0=bot_hf_top.y0 - ABSORBER_THICK)
    bot_guide_top  = openmc.YPlane(y0=bot_hf_bot.y0 - CTRL_BLADE_WATER)
    bot_offset_top = openmc.YPlane(y0=bot_guide_top.y0 - CTRL_AL_PLATE_THICK)
    # bot_offset_top should coincide with elem_front + CTRL_OUTER_OFFSET
    assert abs(bot_offset_top.y0 - (-ELEM_Y / 2.0 + CTRL_OUTER_OFFSET)) < 1e-9, \
        "control end-block budget does not reach the element wall (bottom)"

    # Top end block — mirror image, built outward from the fuel stack to the wall.
    top_slider_bot = openmc.YPlane(y0=y_fuel_end + CTRL_FEEDER_CHANNEL)
    top_slider_top = openmc.YPlane(y0=top_slider_bot.y0 + CTRL_AL_PLATE_THICK)
    top_hf_bot     = openmc.YPlane(y0=top_slider_top.y0 + CTRL_BLADE_WATER)
    top_hf_top     = openmc.YPlane(y0=top_hf_bot.y0 + ABSORBER_THICK)
    top_guide_bot  = openmc.YPlane(y0=top_hf_top.y0 + CTRL_BLADE_WATER)
    top_guide_top  = openmc.YPlane(y0=top_guide_bot.y0 + CTRL_AL_PLATE_THICK)
    assert abs(top_guide_top.y0 - (ELEM_Y / 2.0 - CTRL_OUTER_OFFSET)) < 1e-9, \
        "control end-block budget does not reach the element wall (top)"

    # Hf slot x/y footprints (unbounded in z — blade cells own their z-range)
    hf_slot_b = +bot_hf_bot & -bot_hf_top & +side_inner_left & -side_inner_right
    hf_slot_t = +top_hf_bot & -top_hf_top & +side_inner_left & -side_inner_right

    # ── Bottom sandwich structural cells (active zone only) ─────────────────
    # Wall -> fuel: offset water | outer guide | blade water | [blade] |
    #               blade water | inner guide | feeder channel | fuel

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_offset_water_bottom', fill=water_core,
        region=(+elem_front & -bot_offset_top &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_guide_bottom', fill=aluminum,
        region=(+bot_offset_top & -bot_guide_top &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_blade_water_outer_bottom', fill=water_core,
        region=(+bot_guide_top & -bot_hf_bot &
                +side_inner_left & -side_inner_right & plate_z)))

    # (Hf slot cells are handled separately below — not bounded to plate_z)
    #  they own their own z-ranges, driven by the blade position.

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_blade_water_inner_bottom', fill=water_core,
        region=(+bot_hf_top & -bot_slider_bot &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_slider_bottom', fill=aluminum,
        region=(+bot_slider_bot & -bot_slider_top &
                +side_inner_left & -side_inner_right & plate_z)))

    # ── Top sandwich structural cells (active zone only) ────────────────────
    # Fuel -> wall: feeder channel | inner guide | blade water | [blade] |
    #               blade water | outer guide | offset water

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_slider_top', fill=aluminum,
        region=(+top_slider_bot & -top_slider_top &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_blade_water_inner_top', fill=water_core,
        region=(+top_slider_top & -top_hf_bot &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_blade_water_outer_top', fill=water_core,
        region=(+top_hf_top & -top_guide_bot &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_guide_top', fill=aluminum,
        region=(+top_guide_bot & -top_guide_top &
                +side_inner_left & -side_inner_right & plate_z)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_offset_water_top', fill=water_core,
        region=(+top_guide_top & -elem_back &
                +side_inner_left & -side_inner_right & plate_z)))

    # ── Fixed-length B4C blade ───────────────────────────────────────────────
    # B4C occupies [z_bot, z_top] in the Hf-slot band, unbounded by axial
    # region (spans across active/end-box/water boundaries as one piece).
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_absorber_bottom', fill=b4c,
        region=hf_slot_b & +blade_z_bot & -blade_z_top))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_absorber_top', fill=b4c,
        region=hf_slot_t & +blade_z_bot & -blade_z_top))

    # Water below the blade, down to the BOTTOM OF THE PLATES (−31), not the
    # bottom of the meat. The lower end-box now stops at −31 and carries no
    # slot exclusion, so if this stopped at −30 the slot band [−31, −30] would
    # be undefined space: it passes an overlap check and leaks particles.
    # The blade never dips below −30 (asserted above), so this band is always
    # water regardless of f.
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_slot_b_water_below', fill=water_core,
        region=hf_slot_b & +_z_plate_bot & -blade_z_bot))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_slot_t_water_below', fill=water_core,
        region=hf_slot_t & +_z_plate_bot & -blade_z_bot))

    # ── Moving homogenized end-box cap (A4, resolved 2026-07-31: Option B) ──
    # An ENDBOX_HEIGHT (14 cm) end_box_homog cap rides above the blade in the
    # Hf-slot x/y band, clipped at CORE_TOP; above the cap the slot is water
    # (294 K) up to CORE_TOP.
    #
    # The cap bottom is max(z_top, HALF_PLATE_Z), NOT z_top. B1 shortened the
    # cap from 15 cm to 14 cm while the plates grew to +/-31, so a cap bolted
    # rigidly to the blade top would sit at [+30,+44] at f=0 — 1 cm low, and no
    # longer coplanar with the surrounding end-boxes at [+31,+45]. The
    # 2026-07-20 decision is that the cap IS coplanar at full insertion, so the
    # cap is anchored to the fixed end-box floor instead and the 1 cm slot band
    # [z_top, +31] is core coolant water.
    #
    # This only bites for z_top < HALF_PLATE_Z, i.e. f < CLAD_EXT/ROD_TRAVEL
    # (1/60 ~ 0.0167). At and above that the cap sits on the blade top exactly
    # as it always did, and the water band is zero-measure.
    #
    # No lower-side counterpart is needed: blade_z_bot is always >= -HALF_Z
    # (asserted above), so the blade never reaches the lower end-box/water.
    if z_top < CORE_TOP:
        cap_bot_z = max(z_top, HALF_PLATE_Z)
        # Cap top is always >= ENDBOX_ABOVE_TOP, so the water above the cap
        # never encroaches on the end-box band [+31,+45].
        assert cap_bot_z + ENDBOX_HEIGHT >= ENDBOX_ABOVE_TOP, (
            f"ctrl{elem_id}: cap top {cap_bot_z + ENDBOX_HEIGHT:.2f} < "
            f"ENDBOX_ABOVE_TOP {ENDBOX_ABOVE_TOP} — cap would not clear the "
            f"end-box band")
        blade_cap_bot = openmc.ZPlane(z0=cap_bot_z)
        blade_cap_top = openmc.ZPlane(z0=min(cap_bot_z + ENDBOX_HEIGHT, CORE_TOP))

        # Coolant in the slot between the blade top and the cap floor. Empty
        # (zero-measure) whenever the blade has been withdrawn past +31.
        if cap_bot_z > z_top:
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_slot_b_water_under_cap', fill=water_core,
                region=hf_slot_b & +blade_z_top & -blade_cap_bot))
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_slot_t_water_under_cap', fill=water_core,
                region=hf_slot_t & +blade_z_top & -blade_cap_bot))

        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_blade_cap_slot_b', fill=end_box_homog,
            region=hf_slot_b & +blade_cap_bot & -blade_cap_top))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_blade_cap_slot_t', fill=end_box_homog,
            region=hf_slot_t & +blade_cap_bot & -blade_cap_top))
        if blade_cap_top.z0 < CORE_TOP:
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_water_above_cap_slot_b', fill=water,
                region=hf_slot_b & +blade_cap_top & -_z_model_top))
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_water_above_cap_slot_t', fill=water,
                region=hf_slot_t & +blade_cap_top & -_z_model_top))

    # ── 17-plate fuel follower (active zone only) ───────────────────────────

    plate_bot_surfs = []
    plate_top_surfs = []

    for i in range(N_CTRL_FUEL_PLATES):
        # Standard 0.127/0.219 pitch, same as the standard fuel element.
        plate_bot = y_fuel_start + i * CTRL_PLATE_PITCH
        plate_top = plate_bot + PLATE_THICK_INNER

        plate_bot_s = openmc.YPlane(y0=plate_bot)
        plate_top_s = openmc.YPlane(y0=plate_top)
        plate_bot_surfs.append(plate_bot_s)
        plate_top_surfs.append(plate_top_s)

        meat_b = openmc.YPlane(y0=plate_bot + CLAD_THICK_INNER)
        meat_t = openmc.YPlane(y0=plate_top - CLAD_THICK_INNER)
        # The meat y-band lies inside the follower stack [-2.8315, +2.8315];
        # the Hf slots sit at |y| in [3.3165, 3.6265], outside it. Meat and
        # absorber slot are disjoint in y, so the axial zone cut below cannot
        # interact with the blade cells or the not_hf_slots complement.
        meat_xy = +meat_b & -meat_t & +meat_left & -meat_right
        meat_region = meat_xy & +meat_zbot & -meat_ztop
        clad_region = (
            +plate_bot_s & -plate_top_s &
            +side_inner_left & -side_inner_right &
            plate_z &
            ~meat_region
        )
        if zoned:
            # One cell per axial zone; clad_region still subtracts the FULL
            # meat_region, so the zone cells tile exactly what the single meat
            # cell occupied.
            for k in range(N_AXIAL_ZONES):
                z_lo, z_hi = zone_z_bounds(k)
                cells.append(openmc.Cell(
                    name=f'ctrl{elem_id}_meat_{i}_z{k}',
                    fill=zone_mats[k],
                    region=meat_xy & +z_lo & -z_hi))
        else:
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_meat_{i}', fill=fuel, region=meat_region))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_clad_{i}', fill=clad, region=clad_region))

    # Water channels (active zone only)
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_chan_bot_half', fill=water_core,
        region=(+bot_slider_top & -plate_bot_surfs[0] &
                +side_inner_left & -side_inner_right & plate_z)))
    for i in range(N_CTRL_FUEL_PLATES - 1):
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_chan_{i}', fill=water_core,
            region=(+plate_top_surfs[i] & -plate_bot_surfs[i + 1] &
                    +side_inner_left & -side_inner_right & plate_z)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_chan_top_half', fill=water_core,
        region=(+plate_top_surfs[-1] & -top_slider_bot &
                +side_inner_left & -side_inner_right & plate_z)))

    # Side plates (active zone only)
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_side_left', fill=aluminum,
        region=(+elem_left & -side_inner_left &
                +elem_front & -elem_back & plate_z)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_side_right', fill=aluminum,
        region=(+side_inner_right & -elem_right &
                +elem_front & -elem_back & plate_z)))

    # Inter-element water gaps (active zone only)
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_gap_xleft', fill=water_core,
        region=(+pitch_left & -elem_left &
                +pitch_front & -pitch_back & plate_z)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_gap_xright', fill=water_core,
        region=(+elem_right & -pitch_right &
                +pitch_front & -pitch_back & plate_z)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_gap_yfront', fill=water_core,
        region=(+elem_left & -elem_right &
                +pitch_front & -elem_front & plate_z)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_gap_yback', fill=water_core,
        region=(+elem_left & -elem_right &
                +elem_back & -pitch_back & plate_z)))

    # ── Axial regions above/below active fuel ───────────────────────────────
    # Upper end-box/water still exclude the Hf-slot footprint (handled above,
    # since the blade can reach into them). Lower end-box/water need NO such
    # exclusion: the blade never enters z<-HALF_Z (asserted above), so that
    # band is uniform material straight through — no reserved gap. End-box is
    # one solid full-pitch homogenized block — no inter-element water gap
    # subdivision (the end-box material is already a homogenized Al/water
    # mixture, so a physical gap slice within it is not meaningful).
    full_pitch   = +pitch_left & -pitch_right & +pitch_front & -pitch_back
    not_hf_slots = ~hf_slot_b & ~hf_slot_t   # complement of both Hf slot footprints

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_upper_endbox', fill=end_box_homog,
        region=full_pitch & +_z_plate_top & -_z_endbox_above & not_hf_slots))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_upper_water', fill=water,
        region=full_pitch & +_z_endbox_above & -_z_model_top & not_hf_slots))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_lower_endbox', fill=end_box_homog,
        region=full_pitch & +_z_endbox_below & -_z_plate_bot))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_lower_water', fill=water,
        region=full_pitch & +_z_model_bot & -_z_endbox_below))

    return openmc.Universe(name=f'ctrl_fuel_elem_{elem_id}', cells=cells)


# =============================================================================
# FLUX TRAP
# =============================================================================

def make_flux_trap():
    """
    Flux trap: aluminum block with a central cylindrical water hole (water_core
    at 316.8 K, the same core coolant water used throughout the core), matching
    the MCNP deck which models the hole as a ZCylinder rather than the
    originally-commented square.

    The aluminum block itself fills the FULL lattice pitch (PITCH_X x
    PITCH_Y = 7.7 x 8.1 cm) — there is no inter-element water gap around the
    active-zone block. The axial end-box (homogenized water/Al) region above
    and below is likewise one solid full-pitch block — no gap subdivision.

    Cylinder: radius FT_HOLE_RADIUS = 2.5 cm, centered at element origin (x=0, y=0).
    The cylinder is axially unbounded within the plate height (plate_z clips it).
    Aluminum fills the annular region between the cylinder and the pitch envelope.
    """
    pitch_left  = openmc.XPlane(x0=-PITCH_X / 2.0)
    pitch_right = openmc.XPlane(x0= PITCH_X / 2.0)
    pitch_front = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back  = openmc.YPlane(y0= PITCH_Y / 2.0)

    elem_left  = openmc.XPlane(x0=-ELEM_X / 2.0)
    elem_right = openmc.XPlane(x0= ELEM_X / 2.0)
    elem_front = openmc.YPlane(y0=-ELEM_Y / 2.0)
    elem_back  = openmc.YPlane(y0= ELEM_Y / 2.0)

    hole_cyl = openmc.ZCylinder(x0=0.0, y0=0.0, r=FT_HOLE_RADIUS)

    plate_z = +_z_plate_bot & -_z_plate_top   # [−31, +31]

    cells = []

    # Cylindrical water hole — core coolant water at 316.8 K
    cells.append(openmc.Cell(
        name='flux_trap_water_hole',
        fill=water_core,
        region=-hole_cyl & plate_z
    ))
    # Aluminum block: full pitch envelope minus the cylinder, active zone only
    cells.append(openmc.Cell(
        name='flux_trap_aluminum_block',
        fill=aluminum,
        region=(+pitch_left & -pitch_right & +pitch_front & -pitch_back & +hole_cyl & plate_z)
    ))

    # Axial regions above/below active fuel. End-box is one solid full-pitch
    # homogenized block — no inter-element water gap subdivision (the
    # end-box material is already a homogenized Al/water mixture, so a
    # physical gap slice within it is not meaningful); water-beyond stays
    # full pitch.
    full_pitch = +pitch_left & -pitch_right & +pitch_front & -pitch_back

    cells.append(openmc.Cell(
        name='flux_trap_upper_endbox',
        fill=end_box_homog,
        region=full_pitch & +_z_plate_top & -_z_endbox_above
    ))
    cells.append(openmc.Cell(
        name='flux_trap_upper_water',
        fill=water,
        region=full_pitch & +_z_endbox_above & -_z_model_top
    ))
    cells.append(openmc.Cell(
        name='flux_trap_lower_endbox',
        fill=end_box_homog,
        region=full_pitch & +_z_endbox_below & -_z_plate_bot
    ))
    cells.append(openmc.Cell(
        name='flux_trap_lower_water',
        fill=water,
        region=full_pitch & +_z_model_bot & -_z_endbox_below
    ))

    return openmc.Universe(name='flux_trap_universe', cells=cells)


# =============================================================================
# WATER AND GRAPHITE FILL UNIVERSES
# =============================================================================

# Water universe: fully unbounded — bulk water fills whatever space the parent
# lattice boundary provides (used for the outer ring and top/bottom water rows).
water_cell = openmc.Cell(name='water_fill', fill=water)
water_univ = openmc.Universe(name='water_universe', cells=[water_cell])

# Graphite reflector universe.
#
# In-plane: the graphite block itself IS a solid block — each reflector
# element fills its full lattice pitch cell in the active-graphite z-range
# (no inter-element water gaps), so adjacent reflector positions form one
# continuous graphite wall.
#
# Axially: graphite occupies the full block z-range [-31, +31]. Above
# and below, the end-box (homogenized water/Al) region is one solid
# full-pitch block, same as the fuel elements — no gap subdivision.
# Water-beyond stays full pitch, mirroring the fuel element end-box + water
# stack so the reflector height matches the core height.
def make_graphite_element():
    """Graphite reflector element: continuous wall in-plane, solid end-box axially."""
    # TODO (2026-07-20 meeting): add small water channels BETWEEN graphite
    # blocks. Dimension is pending — it must come FROM THE MCNP MODEL; do not
    # invent a channel width. Until then the reflector remains a continuous
    # in-plane wall (no inter-block gap).
    pitch_left  = openmc.XPlane(x0=-PITCH_X / 2.0)
    pitch_right = openmc.XPlane(x0= PITCH_X / 2.0)
    pitch_front = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back  = openmc.YPlane(y0= PITCH_Y / 2.0)

    plate_z    = +_z_plate_bot & -_z_plate_top   # [−31, +31]
    full_pitch = +pitch_left & -pitch_right & +pitch_front & -pitch_back

    # End-box is one solid full-pitch homogenized block — no inter-element
    # water gap subdivision (the end-box material is already a homogenized
    # Al/water mixture, so a physical gap slice within it is not meaningful).
    cells = [
        openmc.Cell(
            name='graphite_block',
            fill=graphite,
            region=plate_z,
        ),
        openmc.Cell(
            name='graphite_upper_endbox',
            fill=end_box_homog,
            region=full_pitch & +_z_plate_top & -_z_endbox_above,  # +31 → +45 cm
        ),
        openmc.Cell(
            name='graphite_upper_water',
            fill=water,
            region=full_pitch & +_z_endbox_above & -_z_model_top,  # +45 → +90 cm
        ),
        openmc.Cell(
            name='graphite_lower_endbox',
            fill=end_box_homog,
            region=full_pitch & +_z_endbox_below & -_z_plate_bot,  # −45 → −31 cm
        ),
        openmc.Cell(
            name='graphite_lower_water',
            fill=water,
            region=full_pitch & +_z_model_bot & -_z_endbox_below,  # −90 → −45 cm
        ),
    ]

    return openmc.Universe(name='graphite_universe', cells=cells)


graphite_univ = make_graphite_element()


# =============================================================================
# CORE MAP — position labels for the 8x9 grid plate
#
# Token grid mirroring lattice_universes below, one token per grid position:
#   'S' standard fuel   'C' control fuel   'F' flux trap
#   'G' graphite        'W' water
# A token-for-token assert in build_core_geometry() ties this grid to the
# lattice literal, so the two can never drift apart by hand.
#
# TECDOC-643 A-2 Table 1: "Grid Plate 8x9 Positions", "Active Core Geometry
# 5x6 Positions", 23 standard + 5 control elements, and two irradiation
# channels — "1 at Core Center" and "1 at Core Edge" (A-2 §1: one water-filled
# flux trap near the center of the core, another near an edge). The literal
# below places them at D4 (center) and A6 (edge), which is the benchmark
# configuration.
#
# LABELS cover the inner 6x7 region only (the fuelled/reflector positions);
# the surrounding water ring is unlabelled. Columns A-F run left to right in
# +x; rows 1-7 run top to bottom, so ROW 1 IS THE +y EDGE — matching the array
# order of CORE_MAP and lattice_universes, so a reader comparing the two never
# has to mentally flip anything.
#
# The letter/number convention is THIS PROJECT'S OWN — TECDOC-643 A-2 specifies
# no element labeling scheme, so the convention itself carries no [TECDOC] tag.
# Labels feed no dimension, surface, or cell region; they name depletion
# materials and nothing else.
# =============================================================================

CORE_MAP_COLS = 'ABCDEF'
CORE_MAP = [
    ['W', 'W', 'W', 'W', 'W', 'W', 'W', 'W'],
    ['W', 'G', 'G', 'G', 'G', 'G', 'G', 'W'],
    ['W', 'S', 'S', 'C', 'S', 'S', 'S', 'W'],
    ['W', 'S', 'S', 'S', 'S', 'C', 'S', 'W'],
    ['W', 'S', 'C', 'S', 'F', 'S', 'S', 'W'],
    ['W', 'S', 'S', 'S', 'S', 'C', 'S', 'W'],
    ['W', 'F', 'S', 'C', 'S', 'S', 'S', 'W'],
    ['W', 'G', 'G', 'G', 'G', 'G', 'G', 'W'],
    ['W', 'W', 'W', 'W', 'W', 'W', 'W', 'W'],
]


def core_map_label(row, col):
    """Position label for grid index (row, col), or None outside the inner 6x7."""
    if 1 <= row <= 7 and 1 <= col <= 6:
        return f'{CORE_MAP_COLS[col - 1]}{row}'
    return None


def core_map_labels(token):
    """Row-major list of position labels for a CORE_MAP token ('S', 'C', ...).

    Row-major order matches the order the lattice literal assigns std_elems[i]
    and ctrl_elems[i], so labels line up with those indices element for element.
    """
    return [core_map_label(i, j)
            for i, row in enumerate(CORE_MAP)
            for j, t in enumerate(row) if t == token]


STD_ELEMENT_IDS  = core_map_labels('S')   # 23 standard element positions
CTRL_ELEMENT_IDS = core_map_labels('C')   # 5 control element positions

assert len(STD_ELEMENT_IDS) == 23, \
    f"CORE_MAP has {len(STD_ELEMENT_IDS)} 'S' positions, expected 23"
assert len(CTRL_ELEMENT_IDS) == 5, \
    f"CORE_MAP has {len(CTRL_ELEMENT_IDS)} 'C' positions, expected 5"
assert sum(r.count('F') for r in CORE_MAP) == 2, \
    "CORE_MAP must have exactly 2 flux traps (A-2 Table 1: 1 center, 1 edge)"
assert None not in STD_ELEMENT_IDS + CTRL_ELEMENT_IDS, \
    "a fuelled position fell outside the labelled inner 6x7 region"
assert len(set(STD_ELEMENT_IDS + CTRL_ELEMENT_IDS)) == 28, \
    "duplicate core-map labels"


# =============================================================================
# CORE LATTICE — TECDOC-643 Fig. 2.1 (LEU panel)
# =============================================================================

def build_core_geometry(withdrawn_fraction=1.0, depletion_zoning=False):
    """Build the full-core openmc.Geometry for a blade WITHDRAWAL fraction f.

    f = 0.0 → blades fully INSERTED  (absorber spans z=[-30, +30])
    f = 1.0 → blades fully WITHDRAWN (absorber spans z=[+30, +90])

    depletion_zoning=True splits every fuel meat cell into N_AXIAL_ZONES axial
    cells, one depletable material per element per zone (28 x N materials, all
    starting from the identical base fuel composition). Structural scaffolding
    for a later depletion study — it configures nothing about depletion itself.
    Default False: the Phase One fresh-core cross-validation baseline must not
    move. With it off the model is byte-for-byte what it has always been.

    This is the single construction path used by core.build_model() and all
    run/ drivers. Vacuum boundaries at the lattice edge and at
    CORE_BOTTOM=-90 / CORE_TOP=+90 accommodate the full axial stack
    (water/end-box/fuel/end-box/water); the withdrawn (f=1) blade top
    coincides exactly with CORE_TOP, so there is no water cap above it.
    """
    std_elems  = [make_standard_fuel_element(
                      i, element_id=STD_ELEMENT_IDS[i], zoned=depletion_zoning)
                  for i in range(23)]
    ctrl_elems = [make_control_fuel_element(
                      100 + i, withdrawn_fraction=withdrawn_fraction,
                      element_id=CTRL_ELEMENT_IDS[i], zoned=depletion_zoning)
                  for i in range(5)]

    W = water_univ
    G = graphite_univ
    S = std_elems
    C = ctrl_elems
    F = make_flux_trap()

    lattice_universes = [
        [W, W, W, W, W, W, W, W],
        [W, G, G, G, G, G, G, W],
        [W, S[0],  S[1],  C[0],  S[2],  S[3],  S[4],  W],
        [W, S[5],  S[6],  S[7],  S[8],  C[1],  S[9],  W],
        [W, S[10], C[2],  S[11], F,     S[12], S[13], W],
        [W, S[14], S[15], S[16], S[17], C[3],  S[18], W],
        [W, F,     S[19], C[4],  S[20], S[21], S[22], W],
        [W, G, G, G, G, G, G, W],
        [W, W, W, W, W, W, W, W],
    ]

    # CORE_MAP must mirror the lattice literal token for token. This is the
    # guard that stops the two from being reconciled by hand: the labels that
    # name depletion materials are only meaningful if the map matches what is
    # actually built.
    _token_of = {W: 'W', G: 'G', F: 'F'}
    _token_of.update({u: 'S' for u in S})
    _token_of.update({u: 'C' for u in C})
    for _i, (_map_row, _lat_row) in enumerate(zip(CORE_MAP, lattice_universes)):
        _built = [_token_of[u] for u in _lat_row]
        assert _built == _map_row, (
            f"CORE_MAP row {_i} {_map_row} disagrees with the lattice "
            f"literal {_built}")
    assert len(CORE_MAP) == len(lattice_universes), \
        "CORE_MAP and lattice_universes have different row counts"

    core_lattice = openmc.RectLattice(name='core_lattice')
    core_lattice.pitch      = (PITCH_X, PITCH_Y)
    core_lattice.lower_left = (-4 * PITCH_X, -4.5 * PITCH_Y)
    core_lattice.universes  = lattice_universes
    # Guard against edge-case lattice lookups just outside the universe array
    # (floating-point roundoff at the boundary planes) — fill with bulk water
    # instead of losing the particle.
    core_lattice.outer      = water_univ

    core_left   = openmc.XPlane(x0=-4   * PITCH_X, boundary_type='vacuum')
    core_right  = openmc.XPlane(x0= 4   * PITCH_X, boundary_type='vacuum')
    core_front  = openmc.YPlane(y0=-4.5 * PITCH_Y, boundary_type='vacuum')
    core_back   = openmc.YPlane(y0= 4.5 * PITCH_Y, boundary_type='vacuum')
    core_bottom = openmc.ZPlane(z0=CORE_BOTTOM,     boundary_type='vacuum')
    core_top    = openmc.ZPlane(z0=CORE_TOP,        boundary_type='vacuum')

    core_region = (
        +core_left  & -core_right  &
        +core_front & -core_back   &
        +core_bottom & -core_top
    )
    core_cell = openmc.Cell(name='core_cell', fill=core_lattice,
                            region=core_region)

    root_universe = openmc.Universe(name='root', cells=[core_cell])
    return openmc.Geometry(root_universe)


# Module-level default geometry (blades fully inserted) — kept for direct
# `python geometry.py` debug use; drivers should call build_core_geometry().
geometry = build_core_geometry(withdrawn_fraction=0.0)


def _lattice_center(row, col):
    """Global (x, y) of the centre of CORE_MAP cell (row, col).

    Mirrors the lattice lower_left used in build_core_geometry(); row 0 is the
    +y edge, matching CORE_MAP's array order.
    """
    n_rows = len(CORE_MAP)
    ll_x, ll_y = -4 * PITCH_X, -4.5 * PITCH_Y
    return (ll_x + (col + 0.5) * PITCH_X,
            ll_y + (n_rows - 1 - row + 0.5) * PITCH_Y)


def _material_at(geom, x, y, z):
    """Name of the material filling the innermost cell containing (x, y, z)."""
    for obj in reversed(geom.find((x, y, z))):
        if isinstance(obj, openmc.Cell):
            if obj.fill is None:
                return None
            return getattr(obj.fill, 'name', None)
    return None


def _run_point_checks(geom, f):
    """Point-containment assertions for the B1 axial stack.

    Probes a standard element's first-plate meat centreline up the axial stack:
    meat -> unfueled clad extension -> end-box -> water. Any of these coming
    back as the wrong material (or None) means a band is mis-clipped or has
    been left as undefined space.
    """
    row, col = 2, 1                          # CORE_MAP 'S' position A2
    assert CORE_MAP[row][col] == 'S', "point-check anchor is not a standard element"
    ex, ey = _lattice_center(row, col)

    # Centreline of plate 0's meat, derived exactly as the builder lays it out.
    meat0_y = -(STD_STACK_HEIGHT / 2.0) + CLAD_THICK_OUTER + MEAT_THICK / 2.0
    px, py = ex, ey + meat0_y

    z_mid_clad_ext = HALF_Z + CLAD_EXT / 2.0            # +30.5
    z_mid_endbox   = HALF_PLATE_Z + ENDBOX_HEIGHT / 2.0  # +38.0
    z_mid_water    = ENDBOX_ABOVE_TOP + POOL_WATER_AXIAL / 2.0  # +67.5

    # Exact material identity, not substrings: the clad extension band must be
    # cladding and nothing else, which is the entire point of B1.
    expected = [
        (( px,  py,            0.0), fuel,          'active meat'),
        (( px,  py,  z_mid_clad_ext), clad,         'upper clad extension'),
        (( px,  py, -z_mid_clad_ext), clad,         'lower clad extension'),
        (( px,  py,  z_mid_endbox), end_box_homog,  'upper end-box'),
        (( px,  py, -z_mid_endbox), end_box_homog,  'lower end-box'),
        (( px,  py,  z_mid_water),  water,          'upper water'),
        (( px,  py, -z_mid_water),  water,          'lower water'),
    ]
    for point, want, label in expected:
        got = _material_at(geom, *point)
        assert got is not None, \
            f"f={f}: {label} at {point} is UNDEFINED SPACE (no material)"
        assert got == want.name, \
            f"f={f}: {label} at {point} is '{got}', expected '{want.name}'"

    print(f"  point checks (f={f}): axial stack "
          f"meat/clad-ext/end-box/water all resolve correctly")


def _run_blade_slot_checks(geom, f):
    """Point-containment assertions down a control element's absorber slot.

    This is the A4 (Option B) check. At full insertion the blade top is at +30
    but the end-box floor is at +31, so the slot must read:
        blade -> 1 cm coolant -> 14 cm cap (coplanar at [+31,+45]) -> water.
    Once the blade is withdrawn past +31 the coolant band closes up and the cap
    sits directly on the blade top again.
    """
    row, col = 2, 3                          # CORE_MAP 'C' position D2
    assert CORE_MAP[row][col] == 'C', "slot-check anchor is not a control element"
    ex, ey = _lattice_center(row, col)

    # Centreline of the lower absorber slot, built outward exactly as the
    # element builder lays the end block out.
    slot_c = -(CTRL_FUEL_STACK_HALF + CTRL_FEEDER_CHANNEL + CTRL_AL_PLATE_THICK
               + CTRL_BLADE_WATER + ABSORBER_THICK / 2.0)
    px, py = ex, ey + slot_c

    z_bot = -HALF_Z + f * ROD_TRAVEL
    z_top = z_bot + BLADE_LENGTH

    def want_at(z):
        """Material the slot should carry at height z, per the A4 resolution."""
        if z < z_bot:
            return water_core          # slot below the blade, down to −31
        if z < z_top:
            return b4c                 # the blade itself
        if z >= CORE_TOP:
            return None
        cap_bot = max(z_top, HALF_PLATE_Z)
        if z < cap_bot:
            return water_core          # A4: coolant between blade top and cap
        if z < min(cap_bot + ENDBOX_HEIGHT, CORE_TOP):
            return end_box_homog       # the 14 cm cap
        return water                   # bulk water above the cap

    probes = [-31.0 + CLAD_EXT / 2.0, -HALF_Z / 2.0, 0.0, HALF_Z / 2.0,
              HALF_Z + CLAD_EXT / 2.0, HALF_PLATE_Z + ENDBOX_HEIGHT / 2.0,
              ENDBOX_ABOVE_TOP - 0.5, ENDBOX_ABOVE_TOP + 0.5, 67.5, 89.5]
    for z in probes:
        want = want_at(z)
        if want is None:
            continue
        got = _material_at(geom, px, py, z)
        assert got is not None, \
            f"f={f}: absorber slot at z={z} is UNDEFINED SPACE (no material)"
        assert got == want.name, \
            f"f={f}: absorber slot at z={z} is '{got}', expected '{want.name}'"

    # A4 explicitly: at full insertion the cap must be coplanar with the
    # surrounding end-boxes, and the 1 cm band below it must be coolant.
    if f == 0.0:
        assert _material_at(geom, px, py, HALF_Z + CLAD_EXT / 2.0) == water_core.name, \
            "A4: slot band [+30,+31] at f=0 must be core coolant water"
        assert _material_at(geom, px, py, ENDBOX_ABOVE_TOP - 0.5) == end_box_homog.name, \
            "A4: cap must reach ENDBOX_ABOVE_TOP at f=0 (coplanar with end-boxes)"
        assert _material_at(geom, px, py, ENDBOX_ABOVE_TOP + 0.5) == water.name, \
            "A4: cap must stop at ENDBOX_ABOVE_TOP at f=0, water above"

    print(f"  slot checks  (f={f}): absorber slot stack resolves correctly "
          f"(blade z=[{z_bot:.1f}, {z_top:.1f}])")


if __name__ == '__main__':
    geometry.export_to_xml()
    print("geometry.xml written successfully.\n")
    print(f"Lattice pitch:        {PITCH_X} x {PITCH_Y} cm")
    print(f"Element envelope:     {ELEM_X} x {ELEM_Y} x {ELEM_Z} cm")
    print(f"Active fuel meat z:   [{-HALF_Z}, {+HALF_Z}] cm ({MEAT_HEIGHT} cm)")
    print(f"Plate / clad z:       [{-HALF_PLATE_Z}, {+HALF_PLATE_Z}] cm "
          f"({PLATE_HEIGHT} cm, {CLAD_EXT} cm unfueled clad each end)")
    print(f"End-box above:        [{+HALF_PLATE_Z}, {ENDBOX_ABOVE_TOP}] cm "
          f"({ENDBOX_HEIGHT} cm)")
    print(f"End-box below:        [{ENDBOX_BELOW_BOT}, {-HALF_PLATE_Z}] cm "
          f"({ENDBOX_HEIGHT} cm)")
    print(f"Core z-bounds:        [{CORE_BOTTOM}, {CORE_TOP}] cm (vacuum)")
    print(f"Axial stack sum:      2 x ({POOL_WATER_AXIAL} + {ENDBOX_HEIGHT} + "
          f"{CLAD_EXT} + {HALF_Z}) = {_AXIAL_STACK_SUM} cm")
    print(f"Active-zone gap width: GAP_X={GAP_X:.4f} cm, GAP_Y={GAP_Y:.4f} cm "
          f"(end-box regions are solid full-pitch homogenized blocks — no "
          f"gap subdivision there)")
    print(f"\nBlade model:")
    print(f"  BLADE_LENGTH = {BLADE_LENGTH} cm (fixed)")
    print(f"  ROD_TRAVEL   = {ROD_TRAVEL} cm")
    for f_chk in [0.0, 0.5, 1.0]:
        z_b = -HALF_Z + f_chk * ROD_TRAVEL
        z_t = z_b + BLADE_LENGTH
        ok = z_b >= CORE_BOTTOM and z_t <= CORE_TOP
        print(f"  f={f_chk:.1f}: blade z=[{z_b:.1f}, {z_t:.1f}]  "
              f"within [{CORE_BOTTOM},{CORE_TOP}]: {ok}")

    print(f"\nControl element layout:")
    print(f"  Fuel stack half-width (CTRL_FUEL_STACK_HALF): "
          f"{CTRL_FUEL_STACK_HALF:.6f} cm")
    print(f"  Fuel stack:       [{-CTRL_FUEL_STACK_HALF:.6f}, "
          f"{CTRL_FUEL_STACK_HALF:.6f}] cm "
          f"({2*CTRL_FUEL_STACK_HALF:.6f} cm, 17 plates @ pitch "
          f"{CTRL_PLATE_PITCH:.6f} cm)")
    print(f"  End block (each): {CTRL_END_BLOCK:.6f} cm "
          f"(feeder {CTRL_FEEDER_CHANNEL:.5f} + guide {CTRL_AL_PLATE_THICK:.5f} "
          f"+ blade-water {CTRL_BLADE_WATER:.5f} + blade {ABSORBER_THICK:.5f} "
          f"+ blade-water {CTRL_BLADE_WATER:.5f} + guide {CTRL_AL_PLATE_THICK:.5f} "
          f"+ offset {CTRL_OUTER_OFFSET:.5f})")

    end_block_layer_sum = (CTRL_FEEDER_CHANNEL + CTRL_AL_PLATE_THICK
                           + CTRL_BLADE_WATER + ABSORBER_THICK
                           + CTRL_BLADE_WATER + CTRL_AL_PLATE_THICK
                           + CTRL_OUTER_OFFSET)
    print(f"  End-block layer sum: {end_block_layer_sum:.6f} cm "
          f"(should be {CTRL_END_BLOCK:.6f})")
    print(f"  Total (2 ends + fuel stack): "
          f"{2*end_block_layer_sum + 2*CTRL_FUEL_STACK_HALF:.6f} cm (should be {ELEM_Y})")

    assert abs(end_block_layer_sum - CTRL_END_BLOCK) < 1e-9, \
        "control end-block layers do not sum to CTRL_END_BLOCK"
    assert abs(2*end_block_layer_sum + 2*CTRL_FUEL_STACK_HALF - ELEM_Y) < 1e-9, \
        "control element total height != ELEM_Y"

    # Geometry overlap check
    import tempfile
    from materials import materials as _materials
    from settings import settings as _settings

    _settings.particles = 200
    _settings.batches   = 2
    _settings.inactive  = 1

    debug_model = openmc.Model(
        geometry=geometry, materials=_materials, settings=_settings
    )
    with tempfile.TemporaryDirectory() as _debug_dir:
        debug_model.run(geometry_debug=True, cwd=_debug_dir)
    print("\nOverlap check (f=0.0) passed: no cell overlaps detected.")
    _run_point_checks(geometry, 0.0)
    _run_blade_slot_checks(geometry, 0.0)

    # f=0.5 is the ordinary mid-travel case: blade at [0,+60], cap riding
    # directly on the blade top, no A4 coolant band.
    geometry_f05 = build_core_geometry(withdrawn_fraction=0.5)
    debug_model_f05 = openmc.Model(
        geometry=geometry_f05, materials=_materials, settings=_settings
    )
    with tempfile.TemporaryDirectory() as _debug_dir_f05:
        debug_model_f05.run(geometry_debug=True, cwd=_debug_dir_f05)
    print("Overlap check (f=0.5) passed: no cell overlaps detected.")
    _run_point_checks(geometry_f05, 0.5)
    _run_blade_slot_checks(geometry_f05, 0.5)

    # f=1.0 exercises the degenerate case introduced by the axial resize:
    # blade_z_top == CORE_TOP exactly (three coincident ZPlane objects at the
    # withdrawn blade top / upper_water boundary / global vacuum boundary).
    geometry_f1 = build_core_geometry(withdrawn_fraction=1.0)
    debug_model_f1 = openmc.Model(
        geometry=geometry_f1, materials=_materials, settings=_settings
    )
    with tempfile.TemporaryDirectory() as _debug_dir_f1:
        debug_model_f1.run(geometry_debug=True, cwd=_debug_dir_f1)
    print("Overlap check (f=1.0) passed: no cell overlaps detected "
          "(blade top coincident with CORE_TOP vacuum boundary).")
    _run_point_checks(geometry_f1, 1.0)
    _run_blade_slot_checks(geometry_f1, 1.0)
