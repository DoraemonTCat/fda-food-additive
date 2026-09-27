# -*- coding: utf-8 -*-
"""
ตัวอ่านแบบทั่วไป — ใช้กับ PDF ที่ไม่ใช่รูปแบบ 'บัญชีหมายเลข 1'

หลักการ: กวาดทุกบรรทัด มองหาอะไรก็ตามที่พอจะระบุได้ว่าเป็นคอลัมน์ไหน
เจอก็ใส่ ไม่เจอก็ปล่อยว่าง ไม่เดา ไม่บังคับว่าต้องครบถึงจะเอา
แถวไหนไม่เจออะไรเลยสักช่องถึงจะข้าม

ตัวนี้แม่นน้อยกว่า parser.py (ที่ใช้พิกัดคอลัมน์จริง) แต่ใช้ได้กับทุกเอกสาร
"""
import re
from function_map import FUNCTION_MAP, to_english

THAI = '\u0E00-\u0E7F'
CODEX_RE = re.compile(r'^\d{1,2}(?:\.\d+){1,4}$')
YEAR_RE = re.compile(r'^25\d{2}$')
NUM_RE = re.compile(r'^\d{1,7}$')
COND_RE = re.compile(r'^(?:\d{1,4},)+\d{1,4}$|^(?:XS|TH)\w*$|,XS|,TH', re.I)
INS_LINE_RE = re.compile(r'INS[_\s]*(?:NO)?\s*[:：]?\s*([0-9]+[a-z]?(?:\([ivx]+\))?)', re.I)
NAME_RE = re.compile(r'\b([A-Z][A-Z0-9 ,\.\-\'/&]{4,})\b')
GMP_TH = 'ปริมาณที่เหมาะสม'

# ชื่อหน้าที่ที่รู้จัก ทั้งไทยและอังกฤษ (เรียงยาวไปสั้น กันการจับซ้อน)
_TH_FUNCS = sorted(FUNCTION_MAP.keys(), key=len, reverse=True)
_EN_FUNCS = sorted(set(FUNCTION_MAP.values()), key=len, reverse=True)


def _find_function(text):
    for en in _EN_FUNCS:
        if en.lower() in text.lower():
            return en
    for th in _TH_FUNCS:
        if th in text:
            return to_english(th)
    return ""


def extract_generic(pages_text):
    """pages_text: [(page_no, text)] -> [row dict]

    เก็บค่าระดับ 'หัวเรื่อง' (INS_NO / NAME_FML / FUNCTION) ไว้ใช้กับบรรทัดถัดๆ ไป
    เพราะเอกสารส่วนใหญ่เขียนชื่อสารครั้งเดียวแล้วตามด้วยรายการยาว
    """
    rows = []
    cur = {"INS_NO": "", "NAME_FML": "", "FUNCTION": ""}

    for pno, text in pages_text:
        for raw in (text or "").split("\n"):
            line = raw.strip()
            if not line or line in ("NULL", "-"):
                continue

            m = INS_LINE_RE.search(line)
            if m:
                cur["INS_NO"] = m.group(1)

            fn = _find_function(line)
            if fn:
                cur["FUNCTION"] = fn

            nm = NAME_RE.search(line)
            if nm and len(nm.group(1).strip()) > 5 and not CODEX_RE.match(line):
                cand = nm.group(1).strip()
                if cand.upper() not in ("NULL", "NAME_FML", "INS_NO"):
                    cur["NAME_FML"] = cand

            row = {k: "" for k in ("INS_NO", "NAME_FML", "FUNCTION", "FA_MAX",
                                   "REMARK_REF", "REMARK", "CODEXNUMBER", "CODEXNM")}
            toks = line.split()
            thai_parts = []
            for t in toks:
                if CODEX_RE.match(t) and not row["CODEXNUMBER"]:
                    row["CODEXNUMBER"] = t
                elif YEAR_RE.match(t) and not row["REMARK_REF"]:
                    row["REMARK_REF"] = t
                elif COND_RE.search(t) and not row["REMARK"]:
                    row["REMARK"] = t
                elif NUM_RE.match(t) and not row["FA_MAX"]:
                    row["FA_MAX"] = t
                elif re.search('[' + THAI + ']', t):
                    thai_parts.append(t)
            if GMP_TH in line:
                row["FA_MAX"] = GMP_TH
            th_text = " ".join(thai_parts).strip()
            if th_text and th_text != GMP_TH:
                row["CODEXNM"] = th_text

            # บรรทัดนี้มีข้อมูลระดับแถวอะไรบ้างไหม
            if not any(row[k] for k in ("FA_MAX", "REMARK_REF", "REMARK",
                                        "CODEXNUMBER", "CODEXNM")):
                continue

            row["INS_NO"] = row["INS_NO"] or cur["INS_NO"]
            row["NAME_FML"] = cur["NAME_FML"]
            row["FUNCTION"] = cur["FUNCTION"]
            row["_PAGE"] = pno
            row["_RAW"] = line
            rows.append(row)
    return rows
