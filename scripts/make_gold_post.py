#!/usr/bin/env python3
"""Build the daily Mumbai vs Dubai gold price image (1080x1080 JPEG) and caption.

Usage: python3 make_gold_post.py rates.json OUTPUT_DIR

rates.json example:
{
  "date_label": "20 Nov 2026",
  "file_date": "2026-11-20",
  "mumbai_per_gram": {"24K": 12557, "22K": 11510, "18K": 9418},
  "dubai_aed_per_gram": {"24K": 423.25, "22K": 392.00, "21K": 375.75, "18K": 322.00},
  "aed_inr": 25.59,
  "sources": {"mumbai": "...", "dubai": "...", "fx": "..."}
}
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG = (18, 18, 22)
GOLD = (212, 175, 55)
GOLD_SOFT = (240, 214, 140)
WHITE = (240, 240, 240)
MUTED = (160, 160, 168)
ROW_A = (30, 30, 36)
ROW_B = (24, 24, 29)
GREEN = (120, 200, 140)
RED = (235, 120, 110)


def inr(x):
    """Indian digit grouping, no decimals."""
    n = int(round(x))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def compute(r):
    fx = r["aed_inr"]
    rows = []
    for grade in ["24K", "22K", "21K", "18K"]:
        m = r["mumbai_per_gram"].get(grade)
        d = r["dubai_aed_per_gram"].get(grade)
        m10 = m * 10 if m is not None else None
        d10_inr = d * 10 * fx if d is not None else None
        diff = pct = None
        if m10 is not None and d10_inr is not None:
            diff = m10 - d10_inr
            pct = diff / d10_inr * 100
        rows.append(dict(grade=grade, m10=m10, d_aed=d, d10_inr=d10_inr, diff=diff, pct=pct))
    return rows


def draw_image(r, rows, out_path):
    W = H = 1080
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f = lambda size, bold=False: ImageFont.truetype(FONT_B if bold else FONT, size)

    def center(text, y, font, fill):
        w = dr.textlength(text, font=font)
        dr.text(((W - w) / 2, y), text, font=font, fill=fill)

    # Header
    dr.rectangle([0, 0, W, 8], fill=GOLD)
    center("GOLD RATE TODAY", 60, f(64, True), GOLD)
    center("Mumbai  vs  Dubai", 145, f(40), WHITE)
    center(r["date_label"], 205, f(34, True), GOLD_SOFT)

    # Table
    cols = [("Grade", 60), ("Mumbai\n₹/10g", 210), ("Dubai\nAED/g", 425), ("Dubai\n₹/10g", 590), ("Difference\n(India − Dubai)", 790)]
    top = 290
    dr.rectangle([40, top, W - 40, top + 100], fill=GOLD)
    for label, x in cols:
        dr.multiline_text((x, top + 14), label, font=f(26, True), fill=BG, spacing=6)

    y = top + 100
    rh = 125
    for i, row in enumerate(rows):
        dr.rectangle([40, y, W - 40, y + rh], fill=ROW_A if i % 2 == 0 else ROW_B)
        cy = y + 40
        dr.text((60, cy), row["grade"], font=f(38, True), fill=GOLD)
        dr.text((210, cy), inr(row["m10"]) if row["m10"] else "—", font=f(32), fill=WHITE)
        dr.text((425, cy), f"{row['d_aed']:.2f}" if row["d_aed"] else "—", font=f(32), fill=WHITE)
        dr.text((590, cy), inr(row["d10_inr"]) if row["d10_inr"] else "—", font=f(32), fill=WHITE)
        if row["diff"] is not None:
            col = RED if row["diff"] > 0 else GREEN
            sign = "+" if row["diff"] > 0 else ""
            dr.text((790, y + 22), sign + inr(row["diff"]), font=f(32, True), fill=col)
            dr.text((790, y + 68), f"{sign}{row['pct']:.1f}%", font=f(28), fill=col)
        else:
            dr.text((790, cy), "Dubai only", font=f(28), fill=MUTED)
        y += rh

    # Footer
    y += 30
    cheaper = [r_ for r_ in rows if r_["diff"] is not None]
    if cheaper:
        avg = sum(x["pct"] for x in cheaper) / len(cheaper)
        where = "Dubai" if avg > 0 else "Mumbai"
        center(f"{where} is cheaper by about {abs(avg):.1f}% today", y, f(32, True), GOLD_SOFT)
    center(f"1 AED = ₹{r['aed_inr']:.2f}", y + 55, f(26), MUTED)
    center("Indicative rates, excluding taxes and making charges", y + 95, f(24), MUTED)
    dr.rectangle([0, H - 8, W, H], fill=GOLD)

    img.save(out_path, "JPEG", quality=92)


def caption(r, rows):
    lines = [f"🪙 Gold Rate Today – Mumbai vs Dubai ({r['date_label']})", ""]
    for row in rows:
        if row["diff"] is not None:
            where = "Dubai" if row["diff"] > 0 else "Mumbai"
            lines.append(
                f"{row['grade']}: Mumbai {inr(row['m10'])} | Dubai {inr(row['d10_inr'])} (AED {row['d_aed']:.2f}/g) per 10g "
                f"→ {where} cheaper by {inr(abs(row['diff']))} ({abs(row['pct']):.1f}%)"
            )
        elif row["d_aed"]:
            lines.append(f"{row['grade']}: Dubai AED {row['d_aed']:.2f}/g ({inr(row['d10_inr'])} per 10g)")
    lines += [
        "",
        f"Exchange rate used: 1 AED = ₹{r['aed_inr']:.2f}",
        "Indicative rates, excluding GST/VAT and making charges. Check with your jeweller before buying.",
        "",
        "#GoldRate #GoldPriceToday #DubaiGold #MumbaiGold #GoldRateIndia #22KGold #24KGold #GoldPrice",
    ]
    return "\n".join(lines)


def main():
    r = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = compute(r)
    img_path = out / f"{r['file_date']}.jpg"
    draw_image(r, rows, img_path)
    cap = caption(r, rows)
    (out / f"{r['file_date']}.txt").write_text(cap)
    print(img_path)
    print(cap)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
