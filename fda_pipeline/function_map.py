# -*- coding: utf-8 -*-
"""
ตารางแปลง FUNCTION ภาษาไทย -> ชื่อ functional class ภาษาอังกฤษ (Codex)

!! ต้องให้ผู้กำหนดสเปกตรวจสอบก่อนใช้งานจริง !!
อ้างอิง: Codex Alimentarius GSFA - Table 3 Functional Classes

คำที่ยังไม่แน่ใจถูกทำเครื่องหมาย NEEDS_REVIEW ไว้ด้านล่าง
to_english() จะคืนค่าภาษาไทยเดิมถ้าแปลไม่ได้ (ไม่เดามั่ว)
"""

FUNCTION_MAP = {
    # --- ยืนยันแล้วจากไฟล์ตัวอย่างที่ได้รับ ---
    "สารเพิ่มรสชาติ":                 "Flavour enhancer",
    "สารให้ความหวาน":                 "Sweetener",

    # --- ตรงกับ Codex functional class โดยตรง ---
    "สารควบคุมความเป็นกรด":           "Acidity regulator",
    "สารป้องกันการจับเป็นก้อน":        "Anticaking agent",
    "สารป้องกันการเกิดฟอง":           "Antifoaming agent",
    "สารป้องกันการเกิดออกซิเดชั่น":    "Antioxidant",
    "สารฟอกสี":                       "Bleaching agent",
    "สารเพิ่มปริมาณ":                 "Bulking agent",
    "สารให้ก๊าซคาร์บอนไดออกไซด์":      "Carbonating agent",
    "สารช่วยทำละลาย หรือช่วยพา":       "Carrier",
    "ก๊าซที่ใช้ขับดัน":                "Propellant",
    "สี":                             "Colour",
    "สารคงสภาพของสี":                 "Colour retention agent",
    "อิมัลซิไฟเออร์":                  "Emulsifier",
    "เกลืออิมัลซิไฟอิ้งค์":            "Emulsifying salt",
    "สารทำให้แน่น":                   "Firming agent",
    "วัตถุแต่งกลิ่นรส":                "Flavouring agent",
    "สารปรับปรุงคุณภาพแป้ง":           "Flour treatment agent",
    "สารทำให้เกิดฟอง":                "Foaming agent",
    "สารทำให้เกิดเจล":                "Gelling agent",
    "สารเคลือบผิว":                   "Glazing agent",
    "สารทำให้เกิดความชุ่มชื้น":        "Humectant",
    "ก๊าซที่ช่วยในการเก็บรักษาอาหาร":   "Packaging gas",
    "สารกันเสีย":                     "Preservative",
    "สารช่วยให้ฟู":                   "Raising agent",
    "สารช่วยจับอนุมูลโลหะ":            "Sequestrant",
    "สารทำให้คงตัว":                  "Stabilizer",
    "สารให้ความข้นเหนียว":            "Thickener",

    # --- NEEDS_REVIEW: ไม่ตรง Codex class ตรงๆ ผมเทียบให้ตามความหมาย ---
    "สารให้ความข้น":                  "Thickener",                    # NEEDS_REVIEW
    "สารปรับปรุงเนื้อสัมผัส":          "Texturizer",                   # NEEDS_REVIEW
    "ช่วยให้โครงสร้างผลึกน้ำแข็งมีความคงตัว": "Ice structuring agent",  # NEEDS_REVIEW
    "สารช่วยทำละลาย":                 "Carrier solvent",              # NEEDS_REVIEW
}

# คำที่ยังไม่ยืนยัน — ให้ผู้กำหนดสเปกตรวจก่อนใช้จริง
NEEDS_REVIEW = {
    "สารให้ความข้น", "สารปรับปรุงเนื้อสัมผัส",
    "ช่วยให้โครงสร้างผลึกน้ำแข็งมีความคงตัว", "สารช่วยทำละลาย",
}

_unmapped = set()

# ฟอนต์ในเอกสารทำให้สระ/วรรณยุกต์เพี้ยนได้ เช่น
#   'สารทำให้คงตัว'      -> 'สารทําให้คงตัว'     (ํ + า แทน ำ)
#   'วัตถุแต่งกลิ่นรส'    -> 'วัตถแุ ต่งกลิ่นรส'   (สระสลับตำแหน่ง)
# การเทียบจึงตัดสระ/วรรณยุกต์และช่องว่างออกก่อน แล้วค่อยจับคู่
_MARKS = set("ัิีึืฺุู"
             "็่้๊๋์ํ๎")


def _key(s: str) -> str:
    s = (s or "").replace("ำ", "า")        # ำ -> า
    return "".join(c for c in s if c not in _MARKS and not c.isspace())


_FUZZY = {_key(k): v for k, v in FUNCTION_MAP.items()}


def to_english(th: str) -> str:
    """แปลงเป็นอังกฤษ; ถ้าไม่รู้จักคืนค่าเดิมและจดไว้ (ไม่เดา)"""
    th = (th or "").strip()
    if not th:
        return ""
    if th in FUNCTION_MAP:
        return FUNCTION_MAP[th]
    hit = _FUZZY.get(_key(th))
    if hit:
        return hit
    _unmapped.add(th)
    return th


def unmapped_terms():
    """คำที่ยังแปลไม่ได้ — ใช้ตรวจว่าตารางแปลงครบหรือยัง"""
    return sorted(_unmapped)
