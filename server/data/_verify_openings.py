#!/usr/bin/env python3
"""Verify door/window openings are actually cut into shapes_case6.stl.

Method (evidence-based, same as door verification in prior round):
Axis-aligned walls -> opening "tunnels" produce interior side faces whose
normals are +/-X or +/-Z located at INTERIOR z (not 0/roof) or interior x/y.
For a wall whose broad face normal is +Y, a window/door hole adds 4 tunnel
faces:
  - top of hole: normal -Z at z = holeTop
  - bottom of hole: normal +Z at z = holeBottom
  - left of hole: normal +/-X at x = holeLeft
  - right of hole: normal +/-X at x = holeRight
We scan for +/-Z faces at interior z-levels (exclude 0 and 3500) and report
their (x,y) extents -> reveals each opening's width/position and height.
"""
import re, math, json

STL = "D:/sourcecodes/building.wiki/server/data/shapes_case6.stl"

txt = open(STL, encoding="utf-8", errors="ignore").read()
# ASCII STL
tris = []
for m in re.finditer(
    r"facet normal\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*"
    r"outer loop\s*"
    r"vertex\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*"
    r"vertex\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*"
    r"vertex\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*"
    r"endloop\s*endfacet", txt):
    nx,ny,nz = float(m.group(1)),float(m.group(2)),float(m.group(3))
    vs = [(float(m.group(4+i*3)),float(m.group(5+i*3)),float(m.group(6+i*3))) for i in range(3)]
    cx = sum(v[0] for v in vs)/3; cy=sum(v[1] for v in vs)/3; cz=sum(v[2] for v in vs)/3
    tris.append((nx,ny,nz,cx,cy,cz,vs))

print(f"total facets parsed: {len(tris)}")

# bucket by dominant normal axis
def axis(n):
    ax = max(abs(n[0]),abs(n[1]),abs(n[2]))
    if ax==abs(n[0]): return 'X'
    if ax==abs(n[1]): return 'Y'
    return 'Z'

def sign(n):
    if n>0.5: return '+'
    if n<-0.5: return '-'
    return '0'

zfaces = [(t) for t in tris if axis((t[0],t[1],t[2]))=='Z']
xfac = [(t) for t in tris if axis((t[0],t[1],t[2]))=='X']
print(f"faces with normal Z: {len(zfaces)} ; with normal X: {len(xfac)}")

# interior z levels (exclude 0 and 3500 +- tol)
TOL=200
levels={}
for t in zfaces:
    z=round(t[5])
    if abs(z)<TOL or abs(z-3500)<TOL:
        continue
    levels.setdefault(z,[]).append(t)
print(f"\ninterior Z levels (opening top/bottom candidates): {sorted(levels.keys())}")

openings=[]
for z in sorted(levels.keys()):
    grp=levels[z]
    xs=[v[0] for t in grp for v in t[6]]
    ys=[v[1] for t in grp for v in t[6]]
    ns=set(sign(t[2]) for t in grp)
    openings.append((z, min(xs),max(xs), min(ys),max(ys), len(grp), ns))
    print(f"  z={z:>6}  x=[{min(xs):.0f},{max(xs):.0f}]  y=[{min(ys):.0f},{max(ys):.0f}]  "
          f"faces={len(grp):>3}  normal={ns}")

# interior X levels for tunnel sides (exclude extreme building x)
xlevels={}
for t in xfac:
    x=round(t[3])
    # skip if at building extreme handled separately; we look for clustered interior x
    xlevels.setdefault(x,[]).append(t)
# report x levels that have many faces (potential tunnel sides) excluding extremes
print(f"\ninterior X levels (count>2):")
for x in sorted(xlevels.keys()):
    if len(xlevels[x])>2:
        grp=xlevels[x]
        ys=[v[1] for t in grp for v in t[6]]
        zs=[v[2] for t in grp for v in t[6]]
        ns=set(sign(t[0]) for t in grp)
        print(f"  x={x:>6}  y=[{min(ys):.0f},{max(ys):.0f}]  z=[{min(zs):.0f},{max(zs):.0f}]  "
              f"faces={len(grp):>3}  normal={ns}")
