"""Builds the A3 scratch-pad cover (front + back) as one HTML file.

Page = A3 portrait 297 x 420 mm + 3 mm bleed on every side = 303 x 426 mm.
All artwork is an SVG in mm units; trim line sits 3 mm in from each edge.
"""
import json

QR = json.load(open("qr.json"))
W, H, B = 303, 426, 3  # page with bleed, bleed

C = dict(
    green="#1E5E3B", leaf="#5FA83A", lime="#9BCB54", orange="#EE7D22",
    sun="#F8B83C", ink="#1C2B33", muted="#5B6B70", sky1="#DDF0F7", sky2="#F7FBF4",
    pink="#E9799A", blue="#3B82C4", red="#D9483B", cream="#FFF8EE",
)

FONTS = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700"
         "&family=Inter:wght@400;500;600;700&display=swap")


def emblem(x, y, s):
    """Tree emblem (placeholder for the official logo), top-left at x,y, size s mm."""
    k = s / 40
    return f'''<g transform="translate({x} {y}) scale({k})">
  <path d="M19 40 C19 30 18.5 24 17 19 M20 40 C20.5 31 21 26 23 21 M19.5 30 C16 27 13 27 10 27.5 M20.5 28 C24 25.5 27 25 30 25.5"
        stroke="{C['green']}" stroke-width="2.6" fill="none" stroke-linecap="round"/>
  <circle cx="17" cy="11" r="7.5" fill="{C['leaf']}"/>
  <circle cx="26" cy="13" r="6.5" fill="{C['lime']}"/>
  <circle cx="8.5" cy="21" r="5.5" fill="{C['lime']}"/>
  <circle cx="32" cy="22" r="5.5" fill="{C['leaf']}"/>
  <circle cx="23" cy="5" r="3.8" fill="{C['orange']}"/>
</g>'''


def logo_block(x, y):
    return f'''{emblem(x, y, 30)}
<text x="{x+35}" y="{y+12}" class="serif" font-size="11.5" fill="{C['green']}">Bodhana &amp;</text>
<text x="{x+35}" y="{y+24}" class="serif" font-size="11.5" fill="{C['green']}">Learning Tree</text>
<text x="{x+35.4}" y="{y+30.5}" class="sans" font-size="4" font-weight="600" letter-spacing="1.25" fill="{C['orange']}">MONTESSORI SCHOOL</text>'''


def wave(y0):
    """Bottom swoosh like the reference: orange ribbon over a deep green wave."""
    return f'''<path d="M0 {y0+22} C 70 {y0+42}, 150 {y0+10}, 210 {y0+4} S 290 {y0-8}, {W} {y0-14} L {W} {H} L 0 {H} Z" fill="{C['orange']}"/>
<path d="M0 {y0+30} C 75 {y0+48}, 150 {y0+20}, 215 {y0+12} S 292 {y0+2}, {W} {y0-4} L {W} {H} L 0 {H} Z" fill="{C['green']}"/>'''


def hero(x, y, w, h):
    """Illustrated Montessori scene: sky, sun, hills, big tree, pink tower, number rods."""
    cx = x + w * 0.56
    g = []
    g.append(f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{C["sky1"]}"/><stop offset="1" stop-color="{C["sky2"]}"/></linearGradient>'
             f'<clipPath id="heroClip"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath></defs>')
    g.append(f'<g clip-path="url(#heroClip)">')
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#sky)"/>')
    # sun + rays
    sx, sy = x + w * 0.16, y + h * 0.2
    g.append(f'<circle cx="{sx}" cy="{sy}" r="15" fill="{C["sun"]}"/>')
    for i in range(12):
        g.append(f'<rect x="{sx-1}" y="{sy-27}" width="2" height="7" rx="1" fill="{C["sun"]}" '
                 f'transform="rotate({i*30} {sx} {sy})"/>')
    # clouds
    for (cx0, cy0, s) in [(x + w*0.36, y + h*0.14, 1.0), (x + w*0.84, y + h*0.22, 0.8)]:
        g.append(f'<g fill="#fff" opacity=".95" transform="translate({cx0} {cy0}) scale({s})">'
                 f'<circle cx="0" cy="0" r="8"/><circle cx="10" cy="-4" r="10"/><circle cx="21" cy="0" r="8"/>'
                 f'<rect x="0" y="0" width="21" height="8"/></g>')
    # birds
    for (bx, by) in [(x + w*0.86, y + h*0.42), (x + w*0.91, y + h*0.38), (x + w*0.82, y + h*0.36)]:
        g.append(f'<path d="M{bx-4} {by} q2 -2.5 4 0 q2 -2.5 4 0" stroke="{C["ink"]}" stroke-width=".9" fill="none"/>')
    # hills
    gy = y + h * 0.72
    g.append(f'<path d="M{x} {gy+6} C {x+w*0.25} {gy-26}, {x+w*0.5} {gy-6}, {x+w*0.62} {gy-14} S {x+w*0.9} {gy-34}, {x+w} {gy-18} L {x+w} {y+h} L {x} {y+h} Z" fill="{C["lime"]}"/>')
    g.append(f'<path d="M{x} {gy+16} C {x+w*0.3} {gy-4}, {x+w*0.55} {gy+14}, {x+w} {gy-2} L {x+w} {y+h} L {x} {y+h} Z" fill="{C["leaf"]}"/>')
    # tree trunk + branches
    ty = gy + 8
    g.append(f'<path d="M{cx-9} {ty} C {cx-6} {ty-30}, {cx-8} {ty-55}, {cx-20} {ty-78} '
             f'M{cx+9} {ty} C {cx+6} {ty-30}, {cx+10} {ty-55}, {cx+24} {ty-74} '
             f'M{cx} {ty} L {cx} {ty-90}" stroke="{C["green"]}" stroke-width="6.5" fill="none" stroke-linecap="round"/>')
    g.append(f'<path d="M{cx-12} {ty+2} C {cx-4} {ty-4}, {cx+4} {ty-4}, {cx+12} {ty+2} Z" fill="{C["green"]}"/>')
    # canopy
    canopy = [(0, -110, 34, "leaf"), (-34, -92, 28, "lime"), (34, -90, 30, "leaf"), (-18, -128, 24, "lime"),
              (22, -126, 25, "lime"), (-52, -70, 18, "leaf"), (54, -68, 19, "lime"), (0, -78, 22, "leaf")]
    for dx, dy, r, col in canopy:
        g.append(f'<circle cx="{cx+dx}" cy="{ty+dy}" r="{r}" fill="{C[col]}"/>')
    # fruit / blossoms
    for dx, dy, col in [(-24, -108, "orange"), (14, -100, "red"), (36, -118, "orange"), (-40, -80, "red"),
                        (4, -136, "orange"), (46, -84, "orange"), (-8, -88, "sun"), (24, -76, "sun")]:
        g.append(f'<circle cx="{cx+dx}" cy="{ty+dy}" r="3.2" fill="{C[col]}"/>')
    # pink tower (left)
    px, pb = x + w * 0.17, gy + 18
    yy = pb
    for i in range(7):
        s = 22 - i * 2.8
        yy -= s * 0.62
        g.append(f'<rect x="{px - s/2}" y="{yy}" width="{s}" height="{s*0.62}" fill="{C["pink"]}" '
                 f'stroke="#fff" stroke-width=".5"/>')
    # number rods (right)
    rx, ry = x + w * 0.73, gy + 22
    for i in range(5):
        L = 14 + i * 9
        for j in range(i + 2):
            seg = L / (i + 2)
            g.append(f'<rect x="{rx + j*seg}" y="{ry - i*4.6}" width="{seg}" height="3.8" '
                     f'fill="{C["red"] if j % 2 == 0 else C["blue"]}"/>')
    g.append('</g>')
    return "\n".join(g)


def write_lines(x, y, w):
    out = []
    for i, label in enumerate(["Name", "Class / Section", "Subject"]):
        yy = y + i * 13
        out.append(f'<text x="{x}" y="{yy}" class="sans" font-size="5" font-weight="600" fill="{C["muted"]}">{label}</text>')
        lx = x + (38 if i == 1 else 26)
        out.append(f'<line x1="{lx}" y1="{yy+0.8}" x2="{x+w}" y2="{yy+0.8}" stroke="{C["muted"]}" stroke-width=".35"/>')
    return "\n".join(out)


def front():
    m = B + 15  # inner margin from bleed edge
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm">
<rect width="{W}" height="{H}" fill="#fff"/>
{logo_block(m, B+16)}
<text x="{W-m}" y="{B+26}" text-anchor="end" class="sans" font-size="4.6" font-weight="600" fill="{C['ink']}">Toddler · Primary · Elementary · Adolescent</text>
<text x="{W-m}" y="{B+33}" text-anchor="end" class="sans" font-size="4.2" fill="{C['muted']}">Chennai · OMR · Velachery · Adyar</text>
{hero(B+10, B+60, W-2*B-20, 205)}
<text x="{m}" y="{B+300}" class="serif" font-size="30" fill="{C['green']}">Scratch Pad</text>
<text x="{m+1}" y="{B+314}" class="sans" font-size="6.2" font-weight="500" letter-spacing=".6" fill="{C['orange']}">Think · Sketch · Explore</text>
{write_lines(m, B+336, W-2*m-90)}
{wave(B+366)}
<text x="{m}" y="{H-B-12}" class="sans" font-size="4.6" font-weight="600" fill="#fff">Montessori Education · Cambridge International School</text>
</svg>'''


def qr_tile(x, y, key, label, size=40):
    q = QR[key]
    k = size / q["n"]
    return f'''<rect x="{x-2}" y="{y-2}" width="{size+4}" height="{size+4}" rx="2" fill="#fff"/>
<g transform="translate({x} {y}) scale({k})"><path d="{q['d']}" fill="{C['ink']}" shape-rendering="crispEdges"/></g>
<text x="{x+size/2}" y="{y+size+9}" text-anchor="middle" class="sans" font-size="5" font-weight="600" fill="{C['green']}">{label}</text>'''


def icon(kind, x, y):
    s = f'stroke="{C["orange"]}" stroke-width=".9" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    p = {
        "phone": f'<path d="M{x+1} {y-3.6} c0 4 3 7 7 7 l1 -1.6 -2.2 -1.4 -1.1 1 c-1.4 -.6 -2.4 -1.6 -3 -3 l1 -1.1 -1.4 -2.2 z" {s}/>',
        "mail": f'<rect x="{x}" y="{y-3.6}" width="8" height="5.6" rx=".6" {s}/><path d="M{x} {y-3.4} l4 3 4 -3" {s}/>',
        "web": f'<circle cx="{x+4}" cy="{y-0.8}" r="3.6" {s}/><path d="M{x+0.4} {y-0.8} h7.2 M{x+4} {y-4.4} c-2 2.4 -2 4.8 0 7.2 c2 -2.4 2 -4.8 0 -7.2" {s}/>',
        "pin": f'<path d="M{x+4} {y+3} c-2.6 -3 -3.8 -4.8 -3.8 -6.4 a3.8 3.8 0 0 1 7.6 0 c0 1.6 -1.2 3.4 -3.8 6.4z" {s}/><circle cx="{x+4}" cy="{y-3.4}" r="1.2" {s}/>',
    }[kind]
    return p


def back():
    m = B + 15
    qx, qy = W - m - 98, 196
    rows = [
        ("phone", "+91 80562 98968  /  +91 89031 74902"),
        ("mail", "contact@bodhana-learningtree.co.in"),
        ("web", "www.bodhana-learningtree.co.in"),
        ("pin", "5/381, Ambedkar Main Road, Elango Nagar,"),
        (None, "Perungudi, OMR, Chennai – 600041"),
    ]
    cy0 = 316
    contact = []
    for i, (ic, t) in enumerate(rows):
        yy = cy0 + i * 7.5
        if ic:
            contact.append(f'<g transform="translate({qx} {yy}) scale(.62) translate({-qx} {-yy})">{icon(ic, qx - 1, yy)}</g>')
        contact.append(f'<text x="{qx+9}" y="{yy}" class="sans" font-size="4.5" fill="{C["ink"]}">{t}</text>')
    campuses = [
        ("OMR · Main Campus", "Toddler to Adolescent", "Perungudi"),
        ("Bodhana House of Children", "Toddler & Primary", "Velachery"),
        ("Learning Tree Montessori", "Toddler & Primary", "Adyar"),
    ]
    camp = []
    for i, (n, p, a) in enumerate(campuses):
        yy = 222 + i * 22
        camp.append(f'<rect x="{m}" y="{yy-7}" width="2.2" height="16" rx="1" fill="{C["orange"] if i==0 else C["leaf"]}"/>')
        camp.append(f'<text x="{m+6}" y="{yy}" class="sans" font-size="5" font-weight="700" fill="{C["green"]}">{n}</text>')
        camp.append(f'<text x="{m+6}" y="{yy+7}" class="sans" font-size="4.2" fill="{C["muted"]}">{p} · {a}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}mm" height="{H}mm">
<rect width="{W}" height="{H}" fill="#fff"/>
{logo_block(m, B+16)}
<g opacity=".06">{emblem(W/2-60, 62, 120)}</g>
<text x="{m}" y="{B+197}" class="sans" font-size="5.2" font-weight="700" letter-spacing="1.2" fill="{C['orange']}">OUR CAMPUSES</text>
{"".join(camp)}
<rect x="{qx-2}" y="{qy-26}" width="54" height="13" rx="6.5" fill="{C['green']}"/>
<text x="{qx+25}" y="{qy-17.2}" text-anchor="middle" class="sans" font-size="5.6" font-weight="700" letter-spacing="1.2" fill="#fff">FOLLOW US</text>
{qr_tile(qx, qy, "instagram", "Instagram")}
{qr_tile(qx+56, qy, "facebook", "Facebook")}
{qr_tile(qx, qy+56, "website", "Website")}
{qr_tile(qx+56, qy+56, "campuses", "Our Campuses")}
<line x1="{qx-10}" y1="{cy0-6}" x2="{qx-10}" y2="{cy0+33}" stroke="{C['green']}" stroke-width=".6"/>
{"".join(contact)}
<text x="{m}" y="{cy0}" class="serif" font-size="9" fill="{C['green']}">Follow the child.</text>
<text x="{m}" y="{cy0+9}" class="sans" font-size="4.2" fill="{C['muted']}">Montessori education from</text>
<text x="{m}" y="{cy0+15.5}" class="sans" font-size="4.2" fill="{C['muted']}">18 months to adolescence.</text>
{wave(B+366)}
<text x="{m}" y="{H-B-12}" class="sans" font-size="4.6" font-weight="600" fill="#fff">Bodhana &amp; Learning Tree Montessori School · Chennai</text>
</svg>'''


html = f'''<!doctype html><html><head><meta charset="utf-8"><title>Scratch Pad Cover</title>
<link rel="stylesheet" href="{FONTS}">
<style>
@page {{ size: {W}mm {H}mm; margin: 0; }}
html, body {{ margin: 0; padding: 0; background: #fff; }}
.page {{ width: {W}mm; height: {H}mm; page-break-after: always; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.page svg {{ display: block; }}
.serif {{ font-family: 'Fraunces', Georgia, serif; font-weight: 700; }}
.sans {{ font-family: 'Inter', Arial, sans-serif; }}
</style></head><body>
<div class="page">{front()}</div>
<div class="page">{back()}</div>
</body></html>'''
open("cover.html", "w").write(html)
print("cover.html written")
