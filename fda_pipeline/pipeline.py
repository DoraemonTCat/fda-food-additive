# -*- coding: utf-8 -*-
"""
FDA Food Additive — PDF -> ตาราง 9 คอลัมน์

    python pipeline.py                     # ใช้ text layer (แนะนำ, แม่น 100%)
    python pipeline.py --source easyocr    # ผ่าน OCR service ของบริษัท
    python pipeline.py --pages 2-10        # ทดสอบเฉพาะบางหน้า
    python pipeline.py --group-mode group  # กลุ่มสารเก็บเป็นแถวเดียว

ดู README.md ก่อนใช้ --source easyocr (ต้องเปิด tunnel)
"""
import argparse, re, sys
import pdfplumber
import pandas as pd

import config as C
from parser import page_lines, page_blocks, title_name
from function_map import to_english


def parse_pages_arg(s, total):
    if not s:
        return range(1, total + 1)
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= total]


def extract(pdf_path, pages=None, verbose=True):
    """เดินทุกหน้า แล้วคืน (records, warnings)

    เอกสารเรียงแบบนี้:
        [หัวเรื่องสาร A][ตาราง A ....หลายหน้า....][หัวเรื่องสาร B][ตาราง B]
    โดยรอยต่อ A->B อาจอยู่กลางหน้าก็ได้ จึงต้องอ่านเป็น block ตามลำดับ
    ไม่ใช่แบ่งหน้าเป็นส่วนหัว/ส่วนตาราง

    กลุ่มสาร (เช่น PHOSPHATES) = หัวเรื่องหลาย INS ติดกันก่อนถึงตาราง
    ทุกตัวใช้ตารางชุดเดียวกัน
    """
    records, warns = [], []
    pending = []          # สมาชิกที่เจอแล้วแต่ยังไม่ถึงตาราง
    pending_title = None
    active = []           # สมาชิกที่ตารางปัจจุบันเป็นของพวกเขา
    active_title = None
    active_name = None    # ชื่อสารที่ active อยู่ ใช้ดูว่าหน้าถัดไปยังเป็นสารเดิมไหม

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        todo = pages if pages is not None else range(1, total + 1)
        for pno in todo:
            for kind, payload in page_blocks(page_lines(pdf.pages[pno - 1])):
                if kind == "title":
                    pending_title = payload
                elif kind == "members":
                    pending.extend(payload)
                elif kind == "rows":
                    if pending:                       # สารชุดใหม่เริ่มใช้ตาราง
                        active = pending
                        active_title = pending_title or active_title
                        # ชื่ออาจมาจากชื่อเรื่อง หรือจากบรรทัด INS: ก็ได้
                        active_name = (title_name(pending_title) if pending_title
                                       else None) or next(
                            (m["NAME_FML"] for m in active if m["NAME_FML"]), None)
                        pending, pending_title = [], None
                    elif pending_title:               # มีชื่อสารใหม่แต่ไม่มี INS
                        name = title_name(pending_title)
                        if name != active_name:
                            active = [{"INS_NO": None, "NAME_FML": name,
                                       "FUNCTIONS": []}]
                            active_title, active_name = pending_title, name
                        pending_title = None
                    if not active:
                        warns.append(f"p.{pno}: มีตารางแต่ยังไม่พบหัวสาร")
                        continue
                    fallback = active_name or title_name(active_title)
                    for m in active:
                        if not m["NAME_FML"]:
                            m["NAME_FML"] = fallback
                        if not m["FUNCTIONS"]:
                            warns.append(f"p.{pno}: INS {m['INS_NO']} ไม่มี FUNCTION")
                        if not m["NAME_FML"]:
                            warns.append(f"p.{pno}: INS {m['INS_NO']} ไม่มีชื่อสาร")
                        for r in payload:
                            records.append({**r, "_member": m, "_page": pno})
            if verbose and pno % 200 == 0:
                print(f"  ... หน้า {pno} ({len(records):,} records)", file=sys.stderr)
    return records, warns


def to_dataframe(records, group_mode="expand"):
    """แตกเป็นแถว: 1 แถว = (สาร x หน้าที่ x หมวดอาหาร)"""
    rows = []
    for r in records:
        m = r["_member"]
        funcs = m["FUNCTIONS"] or [""]
        for f in funcs:
            rows.append({
                "INS_NO": m["INS_NO"],
                "NAME_FML": m["NAME_FML"],
                "FUNCTION": to_english(f),
                "FUNCTION_TH": f,
                "FA_MAX": r["FA_MAX"].strip(),
                "FACTOR_CACULATE": C.DEFAULT_FACTOR_CACULATE,
                "REMARK_REF": r["REMARK_REF"].strip(),
                "REMARK": r["REMARK"].strip(),
                "CODEXNUMBER": r["CODEXNUMBER"].strip(),
                "CODEXNM": re.sub(r'\s+', ' ', r["CODEXNM"]).strip(),
                "_page": r["_page"],
            })
    df = pd.DataFrame(rows)
    if group_mode == "group" and not df.empty:
        # ยุบกลุ่มสาร: เก็บแถวเดียวต่อ (ชื่อสาร, หน้าที่, หมวดอาหาร)
        df = df.drop_duplicates(
            subset=["NAME_FML", "FUNCTION", "CODEXNUMBER", "FA_MAX", "REMARK"])
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="pdftext",
                    choices=["pdftext", "easyocr", "aigen", "other"],
                    help="pdftext = อ่าน text layer (แม่น 100%%); อื่นๆ = ผ่าน OCR service")
    ap.add_argument("--pdf", help="path ของ PDF (ว่าง = ใช้ PDF_PATH ใน config.py)")
    ap.add_argument("--pages", help="เช่น 2-10 หรือ 2,5,9 (ว่าง = ทุกหน้า)")
    ap.add_argument("--group-mode", default="expand", choices=["expand", "group"],
                    help="expand = กลุ่มสารแตกเป็นราย INS (ค่าเริ่มต้น)")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    if args.pdf:                       # ระบุไฟล์จากบรรทัดคำสั่งได้ ไม่ต้องแก้ config
        from pathlib import Path
        C.PDF_PATH = Path(args.pdf)
    if not C.PDF_PATH.exists():
        sys.exit(f"ไม่พบไฟล์ PDF: {C.PDF_PATH}")

    if args.source != "pdftext":
        from ocr_source import run_ocr_mode
        return run_ocr_mode(args)

    with pdfplumber.open(C.PDF_PATH) as pdf:
        total = len(pdf.pages)
    pages = parse_pages_arg(args.pages, total)

    print(f"อ่าน {C.PDF_PATH.name} ({total} หน้า) ด้วย text layer ...")
    records, warns = extract(C.PDF_PATH, pages)
    df = to_dataframe(records, args.group_mode)

    if df.empty:
        # เอกสารไม่ใช่รูปแบบบัญชีหมายเลข 1 -> ใช้ตัวอ่านแบบทั่วไปแทน
        # หลักการเดียวกัน: เจอช่องไหนใส่ช่องนั้น ไม่เจอปล่อยว่าง
        print("ไม่พบรูปแบบบัญชีหมายเลข 1 -> ใช้ตัวอ่านแบบทั่วไป ...")
        from generic import extract_generic
        # ใช้ pymupdf ไม่ใช่ pdfplumber:
        # ฟอนต์ไทยในเอกสารบางฉบับไม่มีตาราง map เป็น Unicode
        # pdfplumber จะคืนค่าเป็น (cid:1143) และสลับลำดับสระ
        # pymupdf ถอดออกมาถูกต้อง และเร็วกว่ามาก
        import pymupdf
        doc = pymupdf.open(C.PDF_PATH)
        pt = [(p, doc[p - 1].get_text() or "") for p in pages]
        grows = extract_generic(pt)
        for g in grows:
            g["FACTOR_CACULATE"] = C.DEFAULT_FACTOR_CACULATE
        df = pd.DataFrame(grows, columns=C.OUTPUT_COLUMNS + ["_PAGE", "_RAW"])

    if df.empty:
        import pymupdf
        doc = pymupdf.open(C.PDF_PATH)
        chars = sum(len(doc[i].get_text().strip())
                    for i in range(min(doc.page_count, 20)))
        print()
        print("ไม่พบข้อมูลที่อ่านได้เลยในเอกสารนี้ (0 แถว)")
        if chars == 0:
            print("สาเหตุ: PDF นี้ไม่มี text layer (เป็นไฟล์สแกน/ภาพ)")
            print("ลองโหมด OCR:  python pipeline.py --source easyocr --pdf <ไฟล์>")
        sys.exit(1)
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = args.out or (C.OUTPUT_DIR / "FOOD_ADDITIVE_extracted.xlsx")
    # ไฟล์ผลลัพธ์มี 9 คอลัมน์ตามสเปกเท่านั้น ห้ามเพิ่มคอลัมน์อื่น
    df[C.OUTPUT_COLUMNS].to_excel(out, index=False)

    print(f"\nแถวทั้งหมด : {len(df):,}")
    print(f"จำนวนสาร   : {df['INS_NO'].nunique()} INS")
    print(f"หมวดอาหาร  : {df['CODEXNUMBER'].nunique()} รหัส")
    print(f"FUNCTION   : {df['FUNCTION'].nunique()} ค่า")
    print()
    print("ช่องที่มีข้อมูล:")
    for c in C.OUTPUT_COLUMNS:
        n = (df[c].notna() & (df[c].astype(str).str.strip() != "")).sum()
        print("   %-16s %6d / %d" % (c, n, len(df)))
    print(f"-> {out}")
    if warns:
        print(f"\nคำเตือน {len(warns)} รายการ (10 แรก):")
        for w in warns[:10]:
            print("  ", w)


if __name__ == "__main__":
    main()
