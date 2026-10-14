#!/usr/bin/env python3
"""index -> (element, plate, x, z) from materials.xml, asserted against
the creation-order arithmetic in build_core_geometry()."""
import sys, re, json
import xml.etree.ElementTree as ET
from collections import Counter

STD = ['A2','B2','D2','E2','F2','A3','B3','C3','D3','F3',
       'A4','C4','E4','F4','A5','B5','C5','D5','F5',
       'B6','D6','E6','F6']
CTRL = ['C2','E3','B4','E5','C6']
FT   = ['D4','A6']
N_STD_PLATES, N_CTRL_PLATES, N_X, N_Z = 23, 17, 2, 10

NAME = re.compile(r'^fuel_([A-F]\d)_p(\d+)_x(\d+)_z(\d+)$')

xml_path, out_path = sys.argv[1], sys.argv[2]

found = {}
for m in ET.parse(xml_path).getroot().iter('material'):
    mo = NAME.match(m.get('name') or '')
    if mo:
        found[int(m.get('id'))] = (mo.group(1), int(mo.group(2)),
                                   int(mo.group(3)), int(mo.group(4)))
print(f"named zoned fuel materials: {len(found)}")
assert len(found) == 12280, "expected 12,280 zoned fuel materials"

ids = sorted(found)
assert ids == list(range(ids[0], ids[0] + 12280)), "material ids not contiguous"
print(f"id range {ids[0]}..{ids[-1]}, contiguous")

expected = []
for elem, npl in ([(e, N_STD_PLATES) for e in STD] +
                  [(e, N_CTRL_PLATES) for e in CTRL]):
    for p in range(npl):
        for j in range(N_X):
            for k in range(N_Z):
                expected.append((elem, p, j, k))
assert len(expected) == 12280, len(expected)

mismatch = [(i, found[ids[i]], expected[i])
            for i in range(12280) if found[ids[i]] != expected[i]]
if mismatch:
    print(f"ARITHMETIC ORDER DISAGREES WITH materials.xml: "
          f"{len(mismatch)} rows, first {mismatch[0]}")
    print("  -> xml wins; downstream must use the xml map, not the formula")
else:
    print("creation-order arithmetic matches materials.xml exactly")

def ring(lbl):
    col, row = lbl[0], int(lbl[1])
    return "perimeter" if row in (2, 6) or col in ("A", "F") else "interior"

FT_ADJ = {"D4": ["C4", "E4", "D3", "D5"], "A6": ["B6", "A5"]}
adj_centre = set(FT_ADJ["D4"])
adj_edge   = set(FT_ADJ["A6"])

rows = []
for i, mid in enumerate(ids):
    elem, p, j, k = found[mid]
    is_std = elem in STD
    rows.append({
        "index": i, "id": mid, "element": elem, "plate": p, "x": j, "z": k,
        "type": "SFE" if is_std else "CFE",
        "ring": ring(elem),
        "ft_adjacent": ("centre" if elem in adj_centre
                        else "edge" if elem in adj_edge else None),
        "outer_plate": bool(is_std and p in (0, N_STD_PLATES - 1)),
    })

with open(out_path, "w") as fh:
    json.dump({"decoder": rows, "std": STD, "ctrl": CTRL, "flux_traps": FT},
              fh)

print("ring:       ", Counter(r["ring"] for r in rows))
print("type:       ", Counter(r["type"] for r in rows))
print("ft_adjacent:", Counter(r["ft_adjacent"] for r in rows))
print(f"wrote {out_path}")
