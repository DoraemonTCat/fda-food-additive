# -*- coding: utf-8 -*-
"""
แปลง 'บัญชีหมายเลข 1' (ประกาศ สธ. วัตถุเจือปนอาหาร) จาก PDF -> ตาราง flat
ไม่ใช้ OCR เพราะ PDF มี text layer ครบ
"""
import re, sys, io, json
import pdfplumber
import pandas as pd

PDF = r"C:\Users\peefr\Downloads\กฏหมาย-FOOD_ADDITIVE.pdf"

# ขอบเขตแกน x ของแต่ละคอลัมน์ (วัดจากหน้าจริง, หน่วย pt)
COLS = [
    ("CODEXNUMBER",  70.0, 132.0),
    ("CODEXNM",     132.0, 315.0),
    ("FA_MAX",      315.0, 398.0),
    ("REMARK",      398.0, 486.0),
    ("REMARK_REF",  486.0, 560.0),
]
CODEX_RE = re.compile(r'^\d{1,2}(\.\d+)*$')
ROW_TOL = 4.0   # ต่างกันไม่เกินนี้ถือว่าอยู่บรรทัดเดียวกัน


def col_of(word):
    c = (word["x0"] + word["x1"]) / 2
    for name, lo, hi in COLS:
        if lo <= c < hi:
            return name
    return None


def page_lines(page):
    """จัดคำเป็นบรรทัด -> [{top, cells:{col:text}}]"""
    lines = {}
    for w in page.extract_words():
        key = round(w["top"] / ROW_TOL)
        lines.setdefault(key, []).append(w)
    out = []
    for key in sorted(lines):
        ws = sorted(lines[key], key=lambda w: w["x0"])
        cells = {}
        for w in ws:
            c = col_of(w)
            if c:
                cells[c] = (cells.get(c, "") + " " + w["text"]).strip()
        out.append({"top": min(w["top"] for w in ws), "cells": cells,
                    "raw": " ".join(w["text"] for w in ws)})
    return out


def parse_header(text):
    """ดึง INS_NO / NAME_FML / FUNCTION จากหน้าที่ขึ้นสารใหม่"""
    ins = re.search(r'INS:\s*([^\s]+(?:\s*\([iv]+\))?)', text)
    if not ins:
        return None
    ins_no = ins.group(1).strip().rstrip(',')

    # ชื่อสาร = บรรทัดภาษาอังกฤษก่อน INS:
    name = None
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("INS:"):
            break
        m = re.match(r'^([A-Z0-9][A-Za-z0-9 ,\.\-\'()/]*?)\s*\([ก-๙].*', ln)
        if m:
            name = m.group(1).strip()
        elif re.match(r'^[A-Z][A-Z0-9 ,\.\-\'()/]{3,}$', ln):
            name = ln.strip()

    # หน้าที่: อาจตัดหลายบรรทัด -> เก็บจนถึงหัวตาราง
    fn = ""
    m = re.search(r'หน้าที่:\s*(.*?)(?:รหัสของ|\Z)', text, re.S)
    if m:
        fn = re.sub(r'\s+', ' ', m.group(1)).strip()
    funcs = [x.strip() for x in fn.split(",") if x.strip()]
    return {"INS_NO": ins_no, "NAME_FML": name, "FUNCTIONS_TH": funcs}


def body_start(lines):
    """หา y ที่ตารางเริ่ม (ใต้หัวตาราง)"""
    for i, ln in enumerate(lines):
        if "รหัสของ" in ln["raw"]:
            end = ln["top"] + 30
            for ln2 in lines[i:]:
                if ln2["top"] <= end and ("กำหนด" in ln2["raw"] or "(มก./กก.)" in ln2["raw"]):
                    end = max(end, ln2["top"])
            return end + 5
    return None


def main():
    records = []
    cur = None          # สารปัจจุบัน
    last = None         # record ล่าสุด (ไว้ต่อบรรทัดที่ตัด)
    problems = []

    with pdfplumber.open(PDF) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if "รหัสของ" not in text:
                continue
            h = parse_header(text)
            if h:
                cur = h
                last = None
                if not h["NAME_FML"]:
                    problems.append(f"p.{pno}: หาชื่อสารไม่เจอ (INS {h['INS_NO']})")
                if not h["FUNCTIONS_TH"]:
                    problems.append(f"p.{pno}: หา FUNCTION ไม่เจอ (INS {h['INS_NO']})")
            if cur is None:
                problems.append(f"p.{pno}: มีตารางแต่ยังไม่เจอหัวสาร")
                continue

            lines = page_lines(page)
            ys = body_start(lines)
            if ys is None:
                continue
            for ln in lines:
                if ln["top"] < ys:
                    continue
                c = ln["cells"]
                code = c.get("CODEXNUMBER", "").strip()
                if CODEX_RE.match(code):
                    last = {
                        "INS_NO": cur["INS_NO"],
                        "NAME_FML": cur["NAME_FML"],
                        "_FUNCTIONS_TH": cur["FUNCTIONS_TH"],
                        "CODEXNUMBER": code,
                        "CODEXNM": c.get("CODEXNM", ""),
                        "FA_MAX": c.get("FA_MAX", ""),
                        "REMARK": c.get("REMARK", ""),
                        "REMARK_REF": c.get("REMARK_REF", ""),
                        "_page": pno,
                    }
                    records.append(last)
                elif last is not None and not code:
                    # บรรทัดต่อของ cell ที่ตัดขึ้นบรรทัดใหม่
                    for k in ("CODEXNM", "FA_MAX", "REMARK", "REMARK_REF"):
                        if c.get(k):
                            last[k] = (last[k] + " " + c[k]).strip()

    # ---- ขยายแถวตาม FUNCTION (1 function = 1 แถว) ----
    rows = []
    for r in records:
        fns = r["_FUNCTIONS_TH"] or [""]
        for f in fns:
            rows.append({
                "INS_NO": r["INS_NO"],
                "NAME_FML": r["NAME_FML"],
                "FUNCTION_TH": f,
                "FA_MAX": r["FA_MAX"],
                "FACTOR_CACULATE": 1,
                "REMARK_REF": r["REMARK_REF"],
                "REMARK": r["REMARK"],
                "CODEXNUMBER": r["CODEXNUMBER"],
                "CODEXNM": re.sub(r'\s+', ' ', r["CODEXNM"]).strip(),
                "_page": r["_page"],
            })

    df = pd.DataFrame(rows)
    out = "FOOD_ADDITIVE_extracted.xlsx"
    df.to_excel(out, index=False)

    print(f"records (ก่อนขยาย function): {len(records)}")
    print(f"rows    (หลังขยาย function): {len(df)}")
    print(f"สารทั้งหมด: {df['INS_NO'].nunique()} INS")
    print(f"-> {out}")
    if problems:
        print(f"\n!! ปัญหา {len(problems)} จุด (แสดง 20 แรก):")
        for p in problems[:20]:
            print("  ", p)


if __name__ == "__main__":
    main()
