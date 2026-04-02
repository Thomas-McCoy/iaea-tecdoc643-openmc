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
    - Plate thickness      : 1.27 mm
    - Water channel thick  : 2.19 mm
    - Plates/std element   : 23
    - Plates/ctrl element  : 17 fuel + 4 Al plates
    - Fuel meat dims       : 0.51 mm x 63 mm x 600 mm
    - Clad thickness       : 0.38 mm (inner), 0.495 mm (outer)
    - U density in meat    : 4.45 g/cm3
    - 235U/std element     : 390 g
    - 235U/ctrl element    : 288 g

All dimensions in cm (OpenMC standard).
"""

import openmc
from materials import fuel, clad, water, hafnium, beryllium, aluminum, air

# =============================================================================
# UNIT CONVERSIONS (mm → cm)
# =============================================================================

# Lattice pitch
PITCH_X = 7.7    # cm  (77 mm)
PITCH_Y = 8.1    # cm  (81 mm)

# Fuel element outer dimensions
ELEM_X = 7.6     # cm  (76 mm)
ELEM_Y = 8.0     # cm  (80 mm)
ELEM_Z = 60.0    # cm  (600 mm) — active fuel height

# Fuel plate dimensions
PLATE_THICK_INNER = 0.127   # cm  (1.27 mm)
PLATE_THICK_OUTER = 0.1385  # cm  (1.385 mm)
WATER_CHAN_THICK = 0.219   # cm  (2.19 mm)
CLAD_THICK_INNER = 0.038   # cm  (0.38 mm)
CLAD_THICK_OUTER = 0.0495  # cm  (0.495 mm)
MEAT_THICK       = 0.051   # cm  (0.51 mm)
MEAT_WIDTH       = 6.3     # cm  (63 mm)

# Number of plates
N_PLATES_STD  = 23   # plates per standard fuel element
N_PLATES_CTRL = 17   # fuel plates per control fuel element

# Half-height for z-surfaces
HALF_Z = ELEM_Z / 2.0   # 30.0 cm

# =============================================================================
# HELPER: BUILD A SINGLE FUEL PLATE
# Returns an openmc.Universe representing one fuel plate cross-section
# inner=True uses inner clad thickness, inner=False uses outer
# =============================================================================


def make_standard_fuel_element(elem_id):
    """
    Assemble 23 fuel plates with water channels into a standard fuel element.
    The element sits in a water-filled lattice cell (PITCH_X x PITCH_Y).
    """

    # --- Bounding surfaces of the fuel element box ---
    box_left   = openmc.XPlane(x0=-ELEM_X / 2.0)
    box_right  = openmc.XPlane(x0= ELEM_X / 2.0)
    box_front  = openmc.YPlane(y0=-ELEM_Y / 2.0)
    box_back   = openmc.YPlane(y0= ELEM_Y / 2.0)
    box_bottom = openmc.ZPlane(z0=-HALF_Z)
    box_top    = openmc.ZPlane(z0= HALF_Z)

    box_region = (
        +box_left & -box_right &
        +box_front & -box_back &
        +box_bottom & -box_top
    )

    cells = []

    # Place 23 plates side by side in the x-direction
    # Total width used by plates + water channels:
    #   23 plates * 0.127 cm + 22 channels * 0.219 cm + 2 side plates
    # We center the stack at x=0

    total_plates_width = (N_PLATES_STD - 2) * PLATE_THICK_INNER + 2 * PLATE_THICK_OUTER
    total_water_width  = (N_PLATES_STD - 1) * WATER_CHAN_THICK
    stack_width = total_plates_width + total_water_width
    x_start = -stack_width / 2.0   # left edge of first plate

    plate_surfaces = []   # store x-plane positions for all plate/channel bounds

    x = x_start
    for i in range(N_PLATES_STD):
        plate_thick = PLATE_THICK_OUTER if (i == 0 or i == N_PLATES_STD - 1) else PLATE_THICK_INNER

        left_surf  = openmc.XPlane(x0=x)
        right_surf = openmc.XPlane(x0=x + plate_thick)

        # Fuel meat surfaces within this plate
        # Determine cladding thickness based on plate position
        if i == 0:
            # leftmost plate — thick clad on left face, normal on right
            clad_l = CLAD_THICK_OUTER
            clad_r = CLAD_THICK_INNER
        elif i == N_PLATES_STD - 1:
            # rightmost plate — normal clad on left face, thick on right
            clad_l = CLAD_THICK_INNER
            clad_r = CLAD_THICK_OUTER
        else:
            # all inner plates — normal clad on both faces
            clad_l = CLAD_THICK_INNER
            clad_r = CLAD_THICK_INNER

        meat_l = openmc.XPlane(x0=x + clad_l)
        meat_r = openmc.XPlane(x0=x + plate_thick - clad_r)


        meat_front = openmc.YPlane(y0=-MEAT_WIDTH / 2.0)
        meat_back  = openmc.YPlane(y0= MEAT_WIDTH / 2.0)

        # Fuel meat cell
        meat_region = (
            +meat_l & -meat_r &
            +meat_front & -meat_back &
            +box_bottom & -box_top
        )
        clad_region = (
            +left_surf & -right_surf &
            +box_bottom & -box_top &
            ~meat_region
        )

        cells.append(openmc.Cell(
            name=f'elem{elem_id}_meat_{i}',
            fill=fuel, region=meat_region))
        cells.append(openmc.Cell(
            name=f'elem{elem_id}_clad_{i}',
            fill=clad, region=clad_region))

        plate_surfaces.append((left_surf, right_surf))
        x += plate_thick

        # Water channel between plates (not after last plate)
        if i < N_PLATES_STD - 1:
            chan_left  = right_surf
            chan_right = openmc.XPlane(x0=x + WATER_CHAN_THICK)
            chan_region = (
                +chan_left & -chan_right &
                +box_bottom & -box_top
            )
            cells.append(openmc.Cell(
                name=f'elem{elem_id}_chan_{i}',
                fill=water, region=chan_region))
            x += WATER_CHAN_THICK

    # Fill the rest of the element box with aluminum (side plates, end fittings)
    # This covers anything inside the box that isn't a plate or water channel
    all_plate_regions = []
    for ls, rs in plate_surfaces:
        all_plate_regions.append(+ls & -rs & +box_bottom & -box_top)

    al_region = box_region.clone()
    for ls, rs in plate_surfaces:
        al_region = al_region & ~(+ls & -rs & +box_bottom & -box_top)

    cells.append(openmc.Cell(
        name=f'elem{elem_id}_Al_structure',
        fill=aluminum, region=al_region))

    elem_univ = openmc.Universe(
        name=f'std_fuel_elem_{elem_id}',
        cells=cells)
    return elem_univ


# =============================================================================
# WATER UNIVERSE (fills empty lattice positions)
# =============================================================================

water_cell  = openmc.Cell(name='water_fill', fill=water)
water_univ  = openmc.Universe(name='water_universe', cells=[water_cell])

# =============================================================================
# GRAPHITE REFLECTOR UNIVERSE
# =============================================================================

graphite = openmc.Material(name='graphite')
graphite.set_density('g/cm3', 1.7)
graphite.add_element('C', 1.0, 'ao')
graphite.add_s_alpha_beta('c_Graphite')

graphite_cell  = openmc.Cell(name='graphite_fill', fill=graphite)
graphite_univ  = openmc.Universe(name='graphite_universe',
                                  cells=[graphite_cell])

# =============================================================================
# BUILD CORE LATTICE
# 8x9 grid plate; 5x6 active core (23 std fuel + 5 ctrl fuel elements)
# Core is centered at origin; graphite reflectors on +Y and -Y faces
#
# Lattice map (8 columns x 9 rows):
#   W = water (empty position)
#   S = standard fuel element
#   C = control fuel element (simplified as standard for now)
#   G = graphite reflector
#
# Based on TECDOC-643 Fig. 2.1 — 5x6 core centered in 8x9 grid
# =============================================================================

# Create fuel element universes
std_elems = [make_standard_fuel_element(i) for i in range(23)]
ctrl_elems = [make_standard_fuel_element(100 + i) for i in range(5)]

# Assign universes to a flat list matching the lattice map
# Row order: top to bottom (y), left to right (x)
# 9 rows x 8 columns

W = water_univ
G = graphite_univ
S = std_elems    # list of 23
C = ctrl_elems   # list of 5

# Simple 5x6 core layout inside 8x9 grid (approximate from TECDOC Fig 2.1)
# Rows 0,1,8 = all water (top/bottom buffer)
# Rows 2-7 = active core rows (6 rows of 5 core + buffer water/graphite)

lattice_universes = [
    # Row 0 (top buffer)
    [W, W, W, W, W, W, W, W],
    # Row 1
    [W, W, G, G, G, G, W, W],
    # Row 2 — core row 1
    [W, G, S[0],  S[1],  C[0],  S[2],  G, W],
    # Row 3 — core row 2
    [W, G, S[3],  S[4],  S[5],  S[6],  G, W],
    # Row 4 — core row 3 (center)
    [W, G, C[1],  S[7],  S[8],  C[2],  G, W],
    # Row 5 — core row 4
    [W, G, S[9],  S[10], S[11], S[12], G, W],
    # Row 6 — core row 5
    [W, G, S[13], C[3],  S[14], S[15], G, W],
    # Row 7 — core row 6
    [W, G, S[16], S[17], C[4],  S[18], G, W],
    # Row 8
    [W, W, G, G, G, G, W, W],
]

# Note: remaining std elements S[19]-S[22] not placed yet — 
# layout will be refined against the actual TECDOC figure.

core_lattice = openmc.RectLattice(name='core_lattice')
core_lattice.pitch = (PITCH_X, PITCH_Y)
core_lattice.lower_left = (-4 * PITCH_X, -4.5 * PITCH_Y)
core_lattice.universes = lattice_universes

# =============================================================================
# CORE BOUNDING REGION
# =============================================================================

core_left   = openmc.XPlane(x0=-4 * PITCH_X, boundary_type='vacuum')
core_right  = openmc.XPlane(x0= 4 * PITCH_X, boundary_type='vacuum')
core_front  = openmc.YPlane(y0=-4.5 * PITCH_Y, boundary_type='vacuum')
core_back   = openmc.YPlane(y0= 4.5 * PITCH_Y, boundary_type='vacuum')
core_bottom = openmc.ZPlane(z0=-40.0, boundary_type='vacuum')
core_top    = openmc.ZPlane(z0= 40.0, boundary_type='vacuum')

core_region = (
    +core_left & -core_right &
    +core_front & -core_back &
    +core_bottom & -core_top
)

core_cell = openmc.Cell(name='core_cell',
                        fill=core_lattice,
                        region=core_region)

# =============================================================================
# ROOT UNIVERSE AND GEOMETRY EXPORT
# =============================================================================

root_universe = openmc.Universe(name='root', cells=[core_cell])
geometry = openmc.Geometry(root_universe)

if __name__ == '__main__':
    geometry.export_to_xml()
    print("geometry.xml written successfully.")
    print(f"\nCore layout: 8x9 grid, 5x6 active core")
    print(f"Lattice pitch: {PITCH_X} cm x {PITCH_Y} cm")
    print(f"Fuel element: {ELEM_X} cm x {ELEM_Y} cm x {ELEM_Z} cm")
    print(f"Plates per standard element: {N_PLATES_STD}")
    print(f"Fuel meat thickness: {MEAT_THICK} cm")
    print(f"Water channel thickness: {WATER_CHAN_THICK} cm")
