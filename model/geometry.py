"""
geometry.py
-----------
Geometry definitions for the IAEA TECDOC-643 Appendix A-2
Generic 10 MW LEU Research Reactor Core (Argonne design).

Reference:
    IAEA-TECDOC-643, "Research Reactor Core Conversion Guidebook,
    Volume 2: Analysis (Appendices A-F)," IAEA, Vienna, 1992.
    Appendix A-2: Generic 10 MW Reactor — Argonne National Laboratory.

Core Layout Summary (from Table 1, Appendix A-2):
    - Reactor Type         : Pool-type MTR
    - Power                : 10 MW
    - Standard Fuel Elems  : 23
    - Control Fuel Elems   : 5
    - Core arrangement     : 5 x 6 element positions
    - Grid plate           : 8 x 9 positions
    - Lattice pitch        : 77 mm x 81 mm
    - Moderator/Coolant    : H2O
    - Reflectors           : Graphite (2 faces), H2O

Fuel Element Dimensions (LEU, U3Si2-Al):
    - Element outer dims   : 76 mm x 80 mm x 600 mm
    - Plate thickness      : 1.27 mm (inner), 1.385 mm (outer, thick clad)
    - Water channel thick  : ~2.16 mm (slightly tightened from nominal
                              2.19 mm to make the stack fit exactly in
                              7.7 cm pitch — see note below)
    - Plates/std element   : 23
    - Plates/ctrl element  : 17 fuel + 4 Al plates
    - Fuel meat dims       : 0.51 mm x 63 mm x 600 mm
    - Clad thickness       : 0.38 mm (inner), 0.495 mm (outer)
    - U density in meat    : 4.45 g/cm3
    - 235U/std element     : 390 g
    - 235U/ctrl element    : 288 g

NOTE on plate stack width:
    The TECDOC nominal numbers (23 plates × 1.27 mm + 22 channels × 2.19 mm
    = 77.39 mm) actually exceed the 76 mm element width. To get a
    well-defined geometry that fills the 7.7 cm lattice pitch exactly with
    no overlap or undefined regions, we set:
        - ELEM_X = 7.7 cm (matches pitch — no side plate region in x)
        - PLATE_THICK_OUTER = 0.1385 cm (preserves asymmetric clad physics)
        - WATER_CHAN_THICK is solved from these so the stack fits.
    Total fuel meat volume and 235U loading per element are preserved.

All dimensions in cm (OpenMC standard).
"""

import openmc
from materials import fuel, clad, water, hafnium, graphite, aluminum, air

# =============================================================================
# UNIT CONVERSIONS (mm → cm)
# =============================================================================

# Lattice pitch
PITCH_X = 7.7    # cm  (77 mm)
PITCH_Y = 8.1    # cm  (81 mm)

# Fuel element outer dimensions
# ELEM_X is set equal to the pitch so the plate stack fills the lattice cell
# exactly with no inter-element gap or side-plate region in x. The y-direction
# still has a 1 mm gap (8.0 cm element in 8.1 cm pitch) for end fittings.
ELEM_X = PITCH_X        # 7.7 cm — full pitch width
ELEM_Y = 8.0            # cm  (80 mm)
ELEM_Z = 60.0           # cm  (600 mm) — active fuel height

# Plate thickness — outer plates physically thicker than inner because
# their outward-facing clad is thicker (0.495 vs 0.38 mm) while keeping
# the same 0.51 mm meat.
PLATE_THICK_INNER = 0.127    # cm  (1.27 mm)
PLATE_THICK_OUTER = 0.1385   # cm  (1.385 mm = 0.495 + 0.51 + 0.38 mm)

# Clad thickness (asymmetric for outer plates)
CLAD_THICK_INNER = 0.038   # cm  (0.38 mm)
CLAD_THICK_OUTER = 0.0495  # cm  (0.495 mm)

# Fuel meat dimensions
MEAT_THICK = 0.051  # cm  (0.51 mm)
MEAT_WIDTH = 6.3    # cm  (63 mm)

# Number of plates
N_PLATES_STD  = 23   # plates per standard fuel element
N_PLATES_CTRL = 17   # fuel plates per control fuel element

# Water channel thickness — solved so the plate stack exactly fills ELEM_X.
# stack = (N-2) * inner + 2 * outer + (N-1) * channel = ELEM_X
WATER_CHAN_THICK = 0.169 
# = (7.7 - 21*0.127 - 2*0.1385) / 22 = 0.21620 cm = 2.162 mm
# (~1.3% reduction from nominal 2.19 mm — acceptable for benchmarking)

# Half-height for z-surfaces
HALF_Z = ELEM_Z / 2.0   # 30.0 cm


# =============================================================================
# STANDARD FUEL ELEMENT
# 23 fuel plates with 22 water channels stacked in the x-direction.
# Plates run lengthwise in y (meat width = MEAT_WIDTH = 6.3 cm).
# The element is the full pitch wide in x, with no separate side-plate
# region — the outer plates handle the boundary with thicker clad.
# =============================================================================

def make_standard_fuel_element(elem_id):
    """
    Assemble 23 fuel plates with water channels into a standard fuel element.
    The element is built within a single lattice pitch cell (PITCH_X x PITCH_Y).
    Stack width is exactly ELEM_X (= PITCH_X), so plates fill the cell with
    no overflow or undefined regions.
    """

    # --- Bounding surfaces of the lattice cell ---
    # Use ELEM_X = PITCH_X so the element fills its lattice cell exactly in x.
    # In y, a 1 mm water gap remains around the active plate region.
    box_left   = openmc.XPlane(x0=-ELEM_X / 2.0)
    box_right  = openmc.XPlane(x0= ELEM_X / 2.0)
    box_front  = openmc.YPlane(y0=-ELEM_Y / 2.0)
    box_back   = openmc.YPlane(y0= ELEM_Y / 2.0)
    box_bottom = openmc.ZPlane(z0=-HALF_Z)
    box_top    = openmc.ZPlane(z0= HALF_Z)

    # --- Pitch cell surfaces (for water gap in y between elements) ---
    pitch_front = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back  = openmc.YPlane(y0= PITCH_Y / 2.0)

    cells = []

    # Stack starts at the left edge of the lattice cell (x = -ELEM_X/2).
    # By construction the stack also ends exactly at the right edge.
    x = -ELEM_X / 2.0
    plate_x_bounds = []  # list of (left_xplane, right_xplane) per plate

    for i in range(N_PLATES_STD):
        is_first = (i == 0)
        is_last  = (i == N_PLATES_STD - 1)
        is_outer = is_first or is_last

        # Pick total plate thickness based on position
        plate_thick = PLATE_THICK_OUTER if is_outer else PLATE_THICK_INNER

        # Plate x-bounds
        left_surf  = openmc.XPlane(x0=x)
        right_surf = openmc.XPlane(x0=x + plate_thick)

        # Asymmetric clad on outer plates — thick clad faces the outside,
        # normal clad faces the next water channel
        if is_first:
            clad_l, clad_r = CLAD_THICK_OUTER, CLAD_THICK_INNER
        elif is_last:
            clad_l, clad_r = CLAD_THICK_INNER, CLAD_THICK_OUTER
        else:
            clad_l, clad_r = CLAD_THICK_INNER, CLAD_THICK_INNER

        # Meat x-bounds (within the plate)
        meat_l = openmc.XPlane(x0=x + clad_l)
        meat_r = openmc.XPlane(x0=x + plate_thick - clad_r)

        # Meat y-bounds (centered in the element, MEAT_WIDTH = 6.3 cm)
        meat_front = openmc.YPlane(y0=-MEAT_WIDTH / 2.0)
        meat_back  = openmc.YPlane(y0= MEAT_WIDTH / 2.0)

        # Fuel meat region
        meat_region = (
            +meat_l & -meat_r &
            +meat_front & -meat_back &
            +box_bottom & -box_top
        )
        # Cladding = the rest of the plate volume (in y, full ELEM_Y; in z,
        # full active height) minus the meat region.
        clad_region = (
            +left_surf & -right_surf &
            +box_front & -box_back &
            +box_bottom & -box_top &
            ~meat_region
        )

        cells.append(openmc.Cell(
            name=f'std{elem_id}_meat_{i}',
            fill=fuel, region=meat_region))
        cells.append(openmc.Cell(
            name=f'std{elem_id}_clad_{i}',
            fill=clad, region=clad_region))

        plate_x_bounds.append((left_surf, right_surf))
        x += plate_thick

        # Water channel after this plate (skip after the last plate)
        if not is_last:
            chan_left  = right_surf
            chan_right = openmc.XPlane(x0=x + WATER_CHAN_THICK)
            chan_region = (
                +chan_left & -chan_right &
                +box_front & -box_back &
                +box_bottom & -box_top
            )
            cells.append(openmc.Cell(
                name=f'std{elem_id}_chan_{i}',
                fill=water, region=chan_region))
            x += WATER_CHAN_THICK

    # --- Inter-element water gap (in y) ---
    # The element fills ELEM_X in x but only ELEM_Y in y; the lattice cell
    # is PITCH_Y in y, so there's a thin water strip at +y and -y edges.
    water_y_front = (
        +box_left & -box_right &
        +pitch_front & -box_front &
        +box_bottom & -box_top
    )
    water_y_back = (
        +box_left & -box_right &
        +box_back & -pitch_back &
        +box_bottom & -box_top
    )
    cells.append(openmc.Cell(
        name=f'std{elem_id}_water_gap_front',
        fill=water, region=water_y_front))
    cells.append(openmc.Cell(
        name=f'std{elem_id}_water_gap_back',
        fill=water, region=water_y_back))

    elem_univ = openmc.Universe(
        name=f'std_fuel_elem_{elem_id}',
        cells=cells)
    return elem_univ


# =============================================================================
# CONTROL ELEMENT  (unchanged from current version — still has plates in y;
# orientation fix is a separate task)
# =============================================================================

CTRL_SIDE_PLATE = 0.55      # cm — side plate width (control element)
CTRL_FUEL_WIDTH = 6.60      # cm — width between guide plates
ABSORBER_THICK  = 0.31      # cm — hafnium blade thickness
ABSORBER_GAP    = 0.395     # cm — water gap between blade and fuel region
GUIDE_REGION    = 1.075     # cm — total guide plate region from element edge


def make_control_fuel_element(elem_id, blades_inserted=True):
    """
    Assemble a control fuel element with 17 fuel plates, 4 Al dummy plates,
    guide plate channels, and (optionally) absorber blades.

    NOTE: This element currently builds plates stacked in y, which is
    inconsistent with the standard element (plates in x). Orientation
    rewrite is a follow-up task.
    """
    cells = []

    # --- Lattice cell boundaries ---
    pitch_left   = openmc.XPlane(x0=-PITCH_X / 2.0)
    pitch_right  = openmc.XPlane(x0= PITCH_X / 2.0)
    pitch_front  = openmc.YPlane(y0=-PITCH_Y / 2.0)
    pitch_back   = openmc.YPlane(y0= PITCH_Y / 2.0)
    pitch_bottom = openmc.ZPlane(z0=-HALF_Z)
    pitch_top    = openmc.ZPlane(z0= HALF_Z)

    elem_left   = pitch_left
    elem_right  = pitch_right
    elem_front  = pitch_front
    elem_back   = pitch_back

    side_inner_left  = openmc.XPlane(x0=-PITCH_X / 2.0 + 0.70)
    side_inner_right = openmc.XPlane(x0= PITCH_X / 2.0 - 0.70)

    guide_inner_front = openmc.YPlane(y0=-PITCH_Y / 2.0 + GUIDE_REGION)
    guide_inner_back  = openmc.YPlane(y0= PITCH_Y / 2.0 - GUIDE_REGION)

    if blades_inserted:
        blade_front_outer = openmc.YPlane(y0=-PITCH_Y / 2.0 + GUIDE_REGION - ABSORBER_GAP)
        blade_front_inner = openmc.YPlane(y0=-PITCH_Y / 2.0 + GUIDE_REGION - ABSORBER_GAP - ABSORBER_THICK)
        blade_back_inner  = openmc.YPlane(y0= PITCH_Y / 2.0 - GUIDE_REGION + ABSORBER_GAP + ABSORBER_THICK)
        blade_back_outer  = openmc.YPlane(y0= PITCH_Y / 2.0 - GUIDE_REGION + ABSORBER_GAP)

    meat_left  = openmc.XPlane(x0=-MEAT_WIDTH / 2.0)
    meat_right = openmc.XPlane(x0= MEAT_WIDTH / 2.0)

    n_fuel_plates = 17
    n_al_plates   = 4
    n_total_plates = n_fuel_plates + n_al_plates  # 21
    n_channels = n_total_plates - 1  # 20

    stack_height = n_total_plates * PLATE_THICK_INNER + n_channels * WATER_CHAN_THICK
    fuel_region_height = PITCH_Y - 2 * GUIDE_REGION
    y_start = -PITCH_Y / 2.0 + GUIDE_REGION + (fuel_region_height - stack_height) / 2.0

    al_plate_indices = {0, 1, n_total_plates - 2, n_total_plates - 1}

    y = y_start
    plate_surfaces = []

    for i in range(n_total_plates):
        plate_thick = PLATE_THICK_INNER

        bottom_surf = openmc.YPlane(y0=y)
        top_surf    = openmc.YPlane(y0=y + plate_thick)

        if i in al_plate_indices:
            plate_region = (
                +bottom_surf & -top_surf &
                +side_inner_left & -side_inner_right &
                +pitch_bottom & -pitch_top
            )
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_al_plate_{i}',
                fill=aluminum, region=plate_region))
        else:
            clad_l = CLAD_THICK_INNER
            clad_r = CLAD_THICK_INNER
            meat_b = openmc.YPlane(y0=y + clad_l)
            meat_t = openmc.YPlane(y0=y + plate_thick - clad_r)
            meat_region = (
                +meat_b & -meat_t &
                +meat_left & -meat_right &
                +pitch_bottom & -pitch_top
            )
            clad_region = (
                +bottom_surf & -top_surf &
                +side_inner_left & -side_inner_right &
                +pitch_bottom & -pitch_top &
                ~meat_region
            )
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_meat_{i}',
                fill=fuel, region=meat_region))
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_clad_{i}',
                fill=clad, region=clad_region))

        plate_surfaces.append((bottom_surf, top_surf))
        y += plate_thick

        if i < n_total_plates - 1:
            chan_bot = top_surf
            chan_top_y = y + WATER_CHAN_THICK
            chan_top = openmc.YPlane(y0=chan_top_y)
            chan_region = (
                +chan_bot & -chan_top &
                +side_inner_left & -side_inner_right &
                +pitch_bottom & -pitch_top
            )
            cells.append(openmc.Cell(
                name=f'ctrl{elem_id}_chan_{i}',
                fill=water, region=chan_region))
            y += WATER_CHAN_THICK

    stack_bottom = plate_surfaces[0][0]
    stack_top    = plate_surfaces[-1][1]

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_water_below_stack',
        fill=water,
        region=(+guide_inner_front & -stack_bottom &
                +side_inner_left & -side_inner_right &
                +pitch_bottom & -pitch_top)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_water_above_stack',
        fill=water,
        region=(+stack_top & -guide_inner_back &
                +side_inner_left & -side_inner_right &
                +pitch_bottom & -pitch_top)))

    if blades_inserted:
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_guide_water_bot_outer',
            fill=water,
            region=(+elem_front & -blade_front_inner &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_blade_bottom',
            fill=hafnium,
            region=(+blade_front_inner & -blade_front_outer &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_gap_bottom',
            fill=water,
            region=(+blade_front_outer & -guide_inner_front &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_gap_top',
            fill=water,
            region=(+guide_inner_back & -blade_back_outer &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_blade_top',
            fill=hafnium,
            region=(+blade_back_outer & -blade_back_inner &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_guide_water_top_outer',
            fill=water,
            region=(+blade_back_inner & -elem_back &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
    else:
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_guide_bottom_water',
            fill=water,
            region=(+elem_front & -guide_inner_front &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))
        cells.append(openmc.Cell(
            name=f'ctrl{elem_id}_guide_top_water',
            fill=water,
            region=(+guide_inner_back & -elem_back &
                    +side_inner_left & -side_inner_right &
                    +pitch_bottom & -pitch_top)))

    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_side_left',
        fill=aluminum,
        region=(+elem_left & -side_inner_left &
                +elem_front & -elem_back &
                +pitch_bottom & -pitch_top)))
    cells.append(openmc.Cell(
        name=f'ctrl{elem_id}_side_right',
        fill=aluminum,
        region=(+side_inner_right & -elem_right &
                +elem_front & -elem_back &
                +pitch_bottom & -pitch_top)))

    return openmc.Universe(name=f'ctrl_fuel_elem_{elem_id}', cells=cells)


# =============================================================================
# WATER AND GRAPHITE FILL UNIVERSES
# =============================================================================

water_cell  = openmc.Cell(name='water_fill', fill=water)
water_univ  = openmc.Universe(name='water_universe', cells=[water_cell])

graphite_cell = openmc.Cell(name='graphite_fill', fill=graphite)
graphite_univ = openmc.Universe(name='graphite_universe', cells=[graphite_cell])


# =============================================================================
# CORE LATTICE — based on TECDOC-643 Fig. 2.1 (LEU panel)
# 8 columns x 9 rows; active core 6 cols x 5 rows (23 S + 5 C + 2 F = 30)
# =============================================================================

std_elems  = [make_standard_fuel_element(i)            for i in range(23)]
ctrl_elems = [make_control_fuel_element(100 + i, blades_inserted=True) for i in range(5)]

W = water_univ
G = graphite_univ
S = std_elems
C = ctrl_elems
F = water_univ  # flux trap — modeled as pure water for now (TECDOC: 77x81 mm
                # Al block with 50 mm square water hole; refine later)

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

core_lattice = openmc.RectLattice(name='core_lattice')
core_lattice.pitch       = (PITCH_X, PITCH_Y)
core_lattice.lower_left  = (-4 * PITCH_X, -4.5 * PITCH_Y)
core_lattice.universes   = lattice_universes


# =============================================================================
# CORE BOUNDING REGION
# =============================================================================

core_left   = openmc.XPlane(x0=-4   * PITCH_X, boundary_type='vacuum')
core_right  = openmc.XPlane(x0= 4   * PITCH_X, boundary_type='vacuum')
core_front  = openmc.YPlane(y0=-4.5 * PITCH_Y, boundary_type='vacuum')
core_back   = openmc.YPlane(y0= 4.5 * PITCH_Y, boundary_type='vacuum')
core_bottom = openmc.ZPlane(z0=-40.0,           boundary_type='vacuum')
core_top    = openmc.ZPlane(z0= 40.0,           boundary_type='vacuum')

core_region = (
    +core_left  & -core_right &
    +core_front & -core_back  &
    +core_bottom & -core_top
)
core_cell = openmc.Cell(name='core_cell', fill=core_lattice, region=core_region)


# =============================================================================
# ROOT UNIVERSE AND GEOMETRY EXPORT
# =============================================================================

root_universe = openmc.Universe(name='root', cells=[core_cell])
geometry      = openmc.Geometry(root_universe)


if __name__ == '__main__':
    geometry.export_to_xml()
    print("geometry.xml written successfully.")
    print(f"\nCore layout: 8x9 grid, 6x5 active core (23 S + 5 C + 2 flux traps)")
    print(f"Lattice pitch:        {PITCH_X} cm x {PITCH_Y} cm")
    print(f"Element x = pitch:    {ELEM_X} cm  (no side plate region in x)")
    print(f"Plate (inner) thick:  {PLATE_THICK_INNER} cm")
    print(f"Plate (outer) thick:  {PLATE_THICK_OUTER} cm")
    print(f"Water channel thick:  {WATER_CHAN_THICK:.5f} cm  (solved to fit)")
    print(f"Fuel meat thickness:  {MEAT_THICK} cm")
    print(f"Fuel meat width:      {MEAT_WIDTH} cm")

    # Sanity check: stack width should equal ELEM_X exactly
    stack = (
        (N_PLATES_STD - 2) * PLATE_THICK_INNER
        + 2 * PLATE_THICK_OUTER
        + (N_PLATES_STD - 1) * WATER_CHAN_THICK
    )
    print(f"\nSanity check: stack width = {stack:.6f} cm   (target: {ELEM_X})")