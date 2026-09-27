# -*- coding: utf-8 -*-
"""
แยกข้อความจาก OCR ให้เป็น 9 คอลัมน์เดียวกับโหมด pdftext

ต่างจาก parser.py ตรงที่ OCR ไม่ให้พิกัด x/y มาด้วย ได้มาเป็นข้อความก้อนเดียว
จึงต้องเดาขอบเขตแถวจากรูปแบบข้อความแทน

หลักการ: ใช้ "ปีที่รับค่ากำหนด" (25xx) เป็นตัวจบแถว เพราะเป็นค่าที่ OCR
อ่านถูกบ่อยที่สุด (~70%) แล้วไล่แกะย้อนกลับ

ช่องไหนแกะไม่ได้ปล่อยว่าง ไม่เดา
"""
import re

YEAR_RE = re.compile(r'25\d{2}')
CODE_RE = re.compile(r'^\d{1,2}(?:[.,]\d+)*\.?$')
NUM_RE = re.compile(r'^\d+$')
# รหัสเงื่อนไข: ตัวเลขคั่นจุลภาค อาจมี XS / TH ปน
COND_RE = re.compile(r'^[\d,]+$|XS|TH', re.I)
INS_RE = re.compile(r'INS\s*[:：]?\s*([0-9A-Za-z()]+)')
NAME_RE = re.compile(r'([A-Za-z][A-Za-z0-9 \-]{4,})')
FUNC_RE = re.compile(r'หน้าที่\s*[:：]?\s*([^0-9]{0,120})')


def parse_ocr_text(content: str) -> dict:
    """แกะข้อความ OCR หนึ่งหน้า -> {'header': {...}, 'rows': [...]}"""
    text = re.sub(r'\s+', ' ', content or '').strip()
    header = {"INS_NO": "", "NAME_FML": "", "FUNCTION": ""}

    m = INS_RE.search(text)
    if m:
        header["INS_NO"] = m.group(1).strip()
    # ชื่อสารมักเป็นคำอังกฤษยาวสุดในช่วงต้นหน้า
    head_zone = text[:m.start()] if m else text[:400]
    cands = NAME_RE.findall(head_zone)
    if cands:
        header["NAME_FML"] = max(cands, key=len).strip()
    m = FUNC_RE.search(text)
    if m:
        header["FUNCTION"] = m.group(1).strip(' ,')

    # ใช้ปีเป็นตัวจบแถว
    rows, prev = [], None
    for ym in YEAR_RE.finditer(text):
        seg = text[(prev.end() if prev else 0):ym.start()].strip()
        prev = ym
        if not seg:
            continue
        row = _parse_segment(seg)
        row["REMARK_REF"] = ym.group(0)
        if row["CODEXNUMBER"] or row["FA_MAX"] or row["CODEXNM"]:
            rows.append(row)
    return {"header": header, "rows": rows}


def _parse_segment(seg: str) -> dict:
    """แกะหนึ่งช่วงข้อความ (หนึ่งแถว) -> คอลัมน์ย่อย"""
    out = {"CODEXNUMBER": "", "CODEXNM": "", "FA_MAX": "",
           "REMARK": "", "REMARK_REF": "", "RAW": seg}
    toks = seg.split()
    if not toks:
        return out

    if CODE_RE.match(toks[0]):
        out["CODEXNUMBER"] = toks[0].rstrip('.')
        toks = toks[1:]

    # ไล่จากท้าย: เงื่อนไข แล้วค่อยปริมาณ
    while toks and COND_RE.search(toks[-1]) and not NUM_RE.match(toks[-1]):
        out["REMARK"] = (toks[-1] + ' ' + out["REMARK"]).strip()
        toks = toks[:-1]
    if toks and COND_RE.search(toks[-1]) and ',' in toks[-1]:
        out["REMARK"] = (toks[-1] + ' ' + out["REMARK"]).strip()
        toks = toks[:-1]
    if toks and NUM_RE.match(toks[-1]):
        out["FA_MAX"] = toks[-1]
        toks = toks[:-1]
    elif 'ปริมาณที่เหมาะสม' in seg:
        out["FA_MAX"] = 'ปริมาณที่เหมาะสม'

    out["CODEXNM"] = ' '.join(toks).strip()
    return out
