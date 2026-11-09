#!/usr/bin/env python3
"""Render a labeled report illustration from demo metrics (not a screenshot).

Optional development dependency: Pillow. The public HTML is generated separately.
"""
from pathlib import Path
import html
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
report = json.loads((ROOT / "examples" / "report.json").read_text())
metrics, csat = report["metrics"], report["satisfaction"]["csat"]
assert report["run"].get("synthetic_fixture")
width, height = 1200, 680
paper, ink, carmine, muted, dark, rose = "#FFF4E6", "#272C26", "#CF1747", "#68665B", "#252A25", "#FF8EAE"
scale = 2
canvas = Image.new("RGB", (width * scale, height * scale), paper)
draw = ImageDraw.Draw(canvas)
font_paths = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
bold_paths = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")]
font_path = next((p for p in font_paths if p.exists()), None)
bold_path = next((p for p in bold_paths if p.exists()), font_path)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
       '<title id="title">Audience — report illustration</title>',
       '<desc id="desc">Clearly labeled fictional Seatly demo: six AI personas, eight visits, six reached visit goals, four of six satisfied personas and two release priorities. This image is an illustration, not a screenshot or real study.</desc>',
       f'<rect width="{width}" height="{height}" fill="{paper}"/>']


def rect(x, y, w, h, fill, radius=0, stroke=None):
    attrs = f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill or "none"}"'
    if stroke: attrs += f' stroke="{stroke}"'
    svg.append('<rect ' + attrs + '/>')
    draw.rounded_rectangle((x*scale,y*scale,(x+w)*scale,(y+h)*scale), radius=radius*scale, fill=fill, outline=stroke, width=scale)


def line(x1, y1, x2, y2, color):
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"/>')
    draw.line((x1*scale,y1*scale,x2*scale,y2*scale),fill=color,width=scale)


def text(x, y, value, size=16, color=ink, bold=False):
    font = ImageFont.truetype(str(bold_path if bold else font_path),size*scale) if font_path else ImageFont.load_default(size=size*scale)
    svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{600 if bold else 400}">{html.escape(str(value))}</text>')
    draw.text((x*scale,y*scale),str(value),font=font,fill=color,anchor="ls")


def person(x, y, color):
    svg.append(f'<circle cx="{x+6}" cy="{y+5}" r="4" fill="{color}"/>')
    draw.ellipse(((x+2)*scale,(y+1)*scale,(x+10)*scale,(y+9)*scale),fill=color)
    rect(x,y+11,12,14,color,4)


text(56,77,"Audience",48)
text(283,77,".",48,carmine)
text(58,112,"AI product testing, with evidence you can inspect.",17,muted)
text(906,46,"REPORT ILLUSTRATION",11,muted)
rect(884,62,260,34,None,17,carmine)
text(903,84,"DEMO · SYNTHETIC DATA",12,carmine)

rect(56,155,1088,352,dark,22)
text(88,193,"SEATLY / FICTIONAL TICKET SERVICE",11,"#B9BAAF")
text(88,252,"Show the full price.",42,paper)
text(88,307,"Make the next step clear.",42,paper)
for i in range(6):
    person(914 + i * 29,229,rose if i < 2 else paper)
text(929,291,"6 AI personas",14,"#B9BAAF")
line(88,339,1112,339,"#51564C")
text(88,422,f'{metrics["task_success"]} / {metrics["eligible"]}',65,rose)
text(88,457,"Visit goals reached",16,paper)
text(88,483,"6 first visits + 2 continuations",11,"#B9BAAF")
text(450,422,f'{csat["satisfied"]} / {csat["n"]}',65,paper)
text(450,457,"Satisfied AI personas",16,paper)
text(450,483,"Illustrative ratings, not human feedback",11,"#B9BAAF")
text(864,422,str(len(report["priorities"])),65,paper)
text(864,457,"Release priorities",16,paper)
text(864,483,"Linked to example events",11,"#B9BAAF")

text(56,553,"01",15,carmine)
text(101,553,"Show the total before seat selection.",21)
text(101,582,"Price + fees, in the same place.",14,muted)
text(646,553,"02",15,carmine)
text(691,553,"Confirm what was selected.",21)
text(691,582,"Keep the result and next action visible.",14,muted)
line(56,614,1144,614,"#E5D7C4")
text(56,648,"6 personas  →  8 visits  →  2 priorities  →  full dialogue appendix",13,muted)
text(929,648,"No live test. No API calls.",11,muted)

svg.append('</svg>')
(OUT / "report-preview.svg").write_text('\n'.join(svg)+'\n',encoding='utf-8')
canvas.resize((width,height),Image.Resampling.LANCZOS).save(OUT / "report-preview.png",optimize=True)
print(OUT / "report-preview.png")
