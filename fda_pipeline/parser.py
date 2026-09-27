# -*- coding: utf-8 -*-
"""
แยกโครงสร้าง 'บัญชีหมายเลข 1' จากหน้า PDF -> records

โครงสร้างเอกสารที่ต้องรับมือ:
  1. หนึ่งสาร = หัวเรื่อง (ชื่อ/INS/หน้าที่) + ตารางหมวดอาหาร ซึ่งกินได้หลายหน้า
  2. หัวเรื่องเป็น 2 คอลัมน์: ซ้าย=ชื่อ/INS/ชื่ออื่น  ขวา=หน้าที่
     -> ถ้าอ่านเป็น text ล้วนจะสลับกันมั่ว ต้องแยกด้วยพิกัด x
  3. 'กลุ่มสาร' เช่น PHOSPHATES: INS หลายสิบตัวใช้ตารางร่วมกันชุดเดียว
  4. ตารางไม่มีเส้นขอบ -> extract_tables() ใช้ไม่ได้ ต้องแบ่งคอลัมน์จากพิกัด x
"""
import re
from config import TABLE_COLS, HEADER_SPLIT_X, ROW_TOL

CODEX_RE = re.compile(r'^\d{1,2}(\.\d+)*$')
# ข้อความหัวประกาศที่โผล่เฉพาะหน้าแรกของบัญชี ไม่ใช่ชื่อสาร
BOILERPLATE_RE = re.compile(
    r'ประกาศกระทรวง|พระราชบัญญัติ|หลักเกณฑ์|แนบท้าย|ราชกิจจา')
# เอกสารเขียน 'INS: -' สำหรับสารที่ไม่มีเลข INS -> ต้องจับด้วย
# ไม่งั้นทั้ง block รวมถึง 'หน้าที่:' จะถูกทิ้ง
INS_RE = re.compile(r'INS:\s*(-|[0-9]+[a-z]?(?:\([ivx]+\))?)')
# ชื่อสารภาษาอังกฤษ: ตัวพิมพ์ใหญ่ขึ้นต้น ตามด้วยวงเล็บภาษาไทย
NAME_RE = re.compile(r'([A-Z][A-Za-z0-9 ,\.\-\'/&()]*?)\s*\([\u0E00-\u0E7F]')
THAI = r'\u0E00-\u0E7F'


# สระ/วรรณยุกต์ไทยที่ต้องเกาะตัวอักษรข้างหน้า
COMBINING = 'ัิ-ฺ็-๎'
# ในไฟล์นี้บางฟอนต์เรียงวรรณยุกต์ไว้ "หลัง" เครื่องหมายวรรคตอน
# เช่น 'อิมัลซิไฟเออร,์' ที่ควรเป็น 'อิมัลซิไฟเออร์,'
STRAY_MARK_RE = re.compile(r'([,\s]+)([' + COMBINING + r']+)')


def fix_thai_marks(s: str) -> str:
    """ย้ายสระ/วรรณยุกต์ที่หลุดไปอยู่หลังเครื่องหมายวรรคตอน กลับมาเกาะตัวอักษร"""
    prev = None
    while prev != s:
        prev = s
        s = STRAY_MARK_RE.sub(lambda m: m.group(2) + m.group(1), s)
    return s


def join_frag(a: str, b: str) -> str:
    """ต่อข้อความที่ถูกตัดขึ้นบรรทัดใหม่

    ภาษาไทยไม่เว้นวรรคระหว่างคำ การขึ้นบรรทัดใหม่จึงไม่ได้แปลว่ามีช่องว่าง
    เช่น 'เกลือ' + 'อิมัลซิไฟอิ้งค์' ต้องได้ 'เกลืออิมัลซิไฟอิ้งค์'
    แต่ '...หลัก' + '(ปรุงแต่ง)' ควรมีช่องว่างคั่น
    """
    if not a:
        return b
    if not b:
        return a
    if b[0] in '(' or (b[0].isascii() and b[0].isalnum() and a[-1] not in ',-'):
        return a + ' ' + b
    return a + b


def page_lines(page):
    """รวมคำที่อยู่ระดับ y เดียวกันเป็นบรรทัด

    ใช้การไล่จัดกลุ่มตามลำดับ ไม่ใช่ round(top / TOL)
    เพราะการปัดเศษจะตัดคำที่ห่างกันแค่เศษ pt ไปคนละบรรทัด
    (เช่น 'INS:' ที่ y=473.38 กับค่า '160c(ii)' ที่ y=474.10)
    """
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    lines, cur, base = [], [], None
    for w in words:
        if base is None or w["top"] - base <= ROW_TOL:
            if base is None:
                base = w["top"]
            cur.append(w)
        else:
            lines.append({"top": base, "words": sorted(cur, key=lambda x: x["x0"])})
            cur, base = [w], w["top"]
    if cur:
        lines.append({"top": base, "words": sorted(cur, key=lambda x: x["x0"])})
    return lines


def _cells(words):
    """แบ่งคำในบรรทัดเข้าคอลัมน์ตามพิกัด x"""
    out = {}
    for w in words:
        c = (w["x0"] + w["x1"]) / 2
        for name, lo, hi in TABLE_COLS:
            if lo <= c < hi:
                out[name] = (out[name] + " " + w["text"]).strip() if name in out else w["text"]
                out[name] = fix_thai_marks(out[name])
                break
    return out


def _side_text(words, left: bool, split_x=HEADER_SPLIT_X):
    """ข้อความฝั่งซ้าย (ชื่อ/INS) หรือฝั่งขวา (หน้าที่) ของหัวเรื่อง

    split_x ไม่คงที่ทั้งเอกสาร — บางหน้า 'หน้าที่:' เริ่มที่ x=303 บางหน้า x=319
    ผู้เรียกจึงต้องหาเส้นแบ่งจากตำแหน่งคำว่า 'หน้าที่:' ในบรรทัดนั้นเอง
    """
    sel = [w["text"] for w in words
           if (w["x0"] < split_x) == left]
    return fix_thai_marks(" ".join(sel).strip())


# ชื่อสารบรรทัดแรกอาจยังไม่มีวงเล็บไทย (ชื่อยาวจนตัดบรรทัด)
# จึงต้องมีตัวจับ "ขึ้นต้นด้วยตัวพิมพ์ใหญ่ล้วน" แยกอีกตัว
# ต้องรัดกุม ไม่งั้นจะไปโดนรหัสเงื่อนไขอย่าง 'XS252' ในตาราง
TITLE_START_RE = re.compile("^[A-Z][A-Z0-9 ,\-'/&.]{3,}$")
TITLE_LEFT_X = 140.0        # ชื่อสารต้องเริ่มชิดขอบซ้ายของหน้า


def looks_like_title(left, words):
    """เป็นบรรทัดแรกของชื่อสารหรือไม่

    เงื่อนไข: เริ่มชิดขอบซ้าย + เป็นตัวพิมพ์ใหญ่ล้วน + มีมากกว่าหนึ่งคำ
    (กันไม่ให้รหัสเช่น 'XS252' ที่อยู่กลางตารางถูกเข้าใจผิดว่าเป็นชื่อสาร)
    """
    t = left.strip()
    return (bool(words) and words[0]["x0"] < TITLE_LEFT_X
            and " " in t and bool(TITLE_START_RE.match(t)))
TITLE_RE = re.compile("^[A-Z][A-Za-z0-9 ,.\-/&()']{3,}\s*\([฀-๿]")


def _member_from(left, right):
    """สร้าง member จากข้อความหัวเรื่องที่สะสมไว้"""
    ins = INS_RE.search(left)
    if not ins:
        return None
    # ตัด 'ชื่ออื่น:' ทิ้ง เพราะมีชื่ออังกฤษปนทำให้จับชื่อสารผิด
    body = INS_RE.sub("", left).split("ชื่ออื่น")[0].strip()
    m = NAME_RE.search(body)
    fm = re.search(r'หน้าที่:\s*(.*)$', right, re.S)
    funcs = [x.strip() for x in fm.group(1).split(",") if x.strip()] if fm else []
    ins_no = ins.group(1)
    return {"INS_NO": None if ins_no == "-" else ins_no,
            "NAME_FML": m.group(1).strip() if m else None,
            "FUNCTIONS": funcs}


def page_blocks(lines):
    """อ่านหน้าแบบไล่จากบนลงล่าง คืน block ตามลำดับที่ปรากฏจริง

    จำเป็นเพราะหนึ่งหน้าอาจเป็น
        [ตารางท้ายของสาร A] -> [หัวเรื่องสาร B] -> [ตารางของสาร B]
    การแบ่งหน้าเป็น "ส่วนหัว" กับ "ส่วนตาราง" อย่างเดียวจึงใช้ไม่ได้

    block: ("title", str) | ("members", [member]) | ("rows", [row])
    """
    blocks = []
    members, rows = [], []
    cur_left = cur_right = ""
    title_buf = None
    in_table = False
    skip_until = -1
    func_x = None

    def flush_member():
        nonlocal cur_left, cur_right
        m = _member_from(cur_left, cur_right)
        if m:
            members.append(m)
        cur_left = cur_right = ""

    def flush_members():
        flush_member()
        if members:
            blocks.append(("members", list(members)))
            members.clear()

    def flush_rows():
        if rows:
            blocks.append(("rows", list(rows)))
            rows.clear()

    def flush_title():
        nonlocal title_buf
        if title_buf:
            blocks.append(("title", title_buf))
            title_buf = None

    for idx, ln in enumerate(lines):
        if idx < skip_until:
            continue
        fx = next((w["x0"] for w in ln["words"]
                   if w["text"].startswith("หน้าที่")), None)
        raw = " ".join(w["text"] for w in ln["words"])
        if "INS:" in raw:
            func_x = fx                     # ขึ้นสารใหม่ -> รีเซ็ตเส้นแบ่ง
        elif fx is not None:
            func_x = fx
        split_x = (func_x - 2) if func_x else HEADER_SPLIT_X
        left = _side_text(ln["words"], True, split_x)
        right = _side_text(ln["words"], False, split_x)
        whole = left + " " + right

        if "บัญชีหมายเลข" in left or BOILERPLATE_RE.search(left):
            continue                                   # หัวกระดาษ ข้าม

        if "รหัสของ" in whole:                          # หัวตาราง
            flush_title()
            flush_members()
            end = ln["top"] + 30
            skip_until = idx + 1
            for j in range(idx, len(lines)):
                t2 = " ".join(w["text"] for w in lines[j]["words"])
                if lines[j]["top"] <= end and ("กำหนด" in t2 or "(มก./กก.)" in t2):
                    skip_until = j + 1
            in_table = True
            continue

        if INS_RE.search(left):                        # สารตัวใหม่เริ่มตรงนี้
            if in_table:
                flush_rows()
                in_table = False
            flush_title()
            flush_member()
            cur_left, cur_right = left, right
            continue

        if in_table:
            c = _cells(ln["words"])
            code = c.get("CODEXNUMBER", "").strip()
            if CODEX_RE.match(code):
                rows.append({"CODEXNUMBER": code,
                             "CODEXNM": c.get("CODEXNM", ""),
                             "FA_MAX": c.get("FA_MAX", ""),
                             "REMARK": c.get("REMARK", ""),
                             "REMARK_REF": c.get("REMARK_REF", "")})
            elif TITLE_RE.match(left) or looks_like_title(left, ln["words"]):
                flush_rows()                           # ชื่อสารตัวใหม่ใต้ตาราง
                in_table = False
                title_buf = whole.strip()
            elif rows:                                 # cell ที่ตัดขึ้นบรรทัดใหม่
                for k in ("CODEXNM", "FA_MAX", "REMARK", "REMARK_REF"):
                    if c.get(k):
                        rows[-1][k] = join_frag(rows[-1][k], c[k])
            continue

        # ยังไม่เข้าตาราง
        if cur_left or cur_right:                      # บรรทัดต่อของ member
            cur_left = join_frag(cur_left, left)
            cur_right = join_frag(cur_right, right)
        elif title_buf is not None:                    # ชื่อสารที่ตัดหลายบรรทัด
            title_buf = join_frag(title_buf, whole.strip())
        elif TITLE_RE.match(left) or looks_like_title(left, ln["words"]):
            title_buf = whole.strip()
        elif right:
            cur_right = join_frag(cur_right, right)

    flush_title()
    flush_members()
    flush_rows()
    return blocks


def title_name(title):
    """ดึงชื่ออังกฤษจากชื่อเรื่อง"""
    if not title:
        return None
    m = NAME_RE.search(title)
    if m:
        return m.group(1).strip()
    m = re.match("^([A-Z][A-Za-z0-9 ,.\-/&()']+)", title)
    return m.group(1).strip() if m else None
