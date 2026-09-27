# -*- coding: utf-8 -*-
"""
โหมด OCR — ส่งแต่ละหน้าเข้า OCR service ของบริษัท

ต้องเปิด tunnel ก่อน (ดู README หัวข้อ "เชื่อมต่อ OCR service")

!! ข้อจำกัดสำคัญ !!
OCR คืนค่าเป็น "ข้อความก้อนเดียว" ไม่มีขึ้นบรรทัด ไม่มีพิกัด
จึงยังแปลงกลับเป็น 9 คอลัมน์ไม่ได้ โหมดนี้ทำได้แค่ดึงข้อความดิบออกมาเก็บไว้
ถ้าต้องการตาราง ให้ใช้ --source pdftext
เหตุผลและตัวเลขวัดผล ดูใน README หัวข้อ "ทำไมค่าเริ่มต้นไม่ใช่ OCR"
"""
import json
import re
import sys
import time

import pandas as pd
import pymupdf
import requests

import config as C
from ocr_parse import parse_ocr_text

NEWLINE = chr(10)


def ocr_page(png_bytes: bytes, engine: str) -> dict:
    """ส่งภาพหนึ่งหน้าเข้า OCR service"""
    url = C.OCR_BASE_URL + C.OCR_ENDPOINT
    r = requests.post(
        url,
        params={"ocr_name": engine, "doc_type": C.OCR_DOC_TYPE},
        files={"file": ("page.png", png_bytes, "image/png")},
        timeout=C.OCR_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def run_ocr_mode(args):
    """ดึงข้อความทุกหน้าผ่าน OCR แล้วเก็บ cache ไว้ราย page

    เก็บ cache เพราะ OCR ใช้เวลา ~40 วินาที/หน้า
    ทั้งเล่ม 839 หน้าใช้เวลาเป็นสิบชั่วโมง ถ้าหลุดกลางทางต้องรันต่อได้
    """
    engine = args.source
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # cache key ต้องมีชื่อเอกสาร ไม่งั้นเอกสารคนละไฟล์จะใช้ cache ปนกัน
    slug = re.sub(r"[^0-9A-Za-z_.-]", "_", C.PDF_PATH.stem)[:40]

    doc = pymupdf.open(C.PDF_PATH)
    total = doc.page_count
    if args.pages:
        from pipeline import parse_pages_arg
        pages = parse_pages_arg(args.pages, total)
    else:
        pages = range(1, total + 1)
    pages = list(pages)

    print(f"OCR engine = {engine} | {len(pages)} หน้า | cache: {C.CACHE_DIR}")
    print(f"ประมาณการ: ~{len(pages) * 40 / 3600:.1f} ชั่วโมง (40 วินาที/หน้า)")

    done = failed = skipped = 0
    t0 = time.time()
    for pno in pages:
        cache = C.CACHE_DIR / f"{slug}__{engine}_p{pno:04d}.json"
        if cache.exists():                      # รันซ้ำ -> ข้ามหน้าที่ทำแล้ว
            skipped += 1
            continue
        png = doc[pno - 1].get_pixmap(dpi=C.OCR_DPI).tobytes("png")
        try:
            res = ocr_page(png, engine)
        except Exception as e:                  # หน้าเดียวพังไม่ควรล้มทั้งงาน
            failed += 1
            print(f"  p.{pno} ล้มเหลว: {e}", file=sys.stderr)
            cache.with_suffix(".error.txt").write_text(str(e), encoding="utf-8")
            continue
        cache.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        done += 1
        rate = (time.time() - t0) / max(done, 1)
        print(f"  p.{pno} ok ({rate:.0f} วิ/หน้า, สำเร็จ {done} ล้มเหลว {failed})")

    # ---- รวมผลเป็นไฟล์เดียว ----
    # ไม่พยายามจัดเป็น 9 คอลัมน์ เพราะเอกสารสแกนแต่ละแบบมีข้อมูลไม่เหมือนกัน
    # ดึงข้อความที่อ่านได้ออกมาให้ครบ ส่วนการคัดแยกลงคอลัมน์เป็นขั้นถัดไป
    rows = []
    txt_out = C.OUTPUT_DIR / ("ocr_" + engine + "_raw.txt")
    with txt_out.open("w", encoding="utf-8") as f:
        for pno in pages:
            cache = C.CACHE_DIR / (slug + "__" + engine + "_p" + str(pno).zfill(4) + ".json")
            if not cache.exists():
                continue
            data = json.loads(cache.read_text(encoding="utf-8"))
            content = (data.get("data") or {}).get("content", "")
            f.write(NEWLINE + "===== PAGE " + str(pno) + " =====" + NEWLINE)
            f.write(content + NEWLINE)

            parsed = parse_ocr_text(content)
            h = parsed["header"]
            for r in parsed["rows"]:
                rows.append({
                    "INS_NO": h["INS_NO"],
                    "NAME_FML": h["NAME_FML"],
                    "FUNCTION": h["FUNCTION"],
                    "FA_MAX": r["FA_MAX"],
                    "FACTOR_CACULATE": C.DEFAULT_FACTOR_CACULATE,
                    "REMARK_REF": r["REMARK_REF"],
                    "REMARK": r["REMARK"],
                    "CODEXNUMBER": r["CODEXNUMBER"],
                    "CODEXNM": r["CODEXNM"],
                    "_SOURCE_FILE": C.PDF_PATH.name,
                    "_PAGE": pno,
                    "_RAW": r["RAW"],
                })
    xlsx_out = C.OUTPUT_DIR / ("ocr_" + engine + "_" + C.PDF_PATH.stem + ".xlsx")
    # 9 คอลัมน์ตามสเปกเท่านั้น
    cols = C.OUTPUT_COLUMNS
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    df.to_excel(xlsx_out, index=False)

    print()
    print("สำเร็จ %d | ข้าม(ทำแล้ว) %d | ล้มเหลว %d" % (done, skipped, failed))
    print("-> " + str(xlsx_out) + "   (Excel)")
    print("-> " + str(txt_out) + "   (ข้อความล้วน)")
    print()
    print("แถวที่แกะได้: %d" % len(rows))
    if rows:
        filled = {c: sum(1 for r in rows if str(r.get(c, "")).strip()) for c in C.OUTPUT_COLUMNS}
        print("ช่องที่มีข้อมูล (จาก %d แถว):" % len(rows))
        for c in C.OUTPUT_COLUMNS:
            print("   %-16s %4d" % (c, filled[c]))
