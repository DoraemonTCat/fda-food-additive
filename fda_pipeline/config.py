# -*- coding: utf-8 -*-
"""ค่าคงที่ทั้งหมดของ pipeline — แก้ที่นี่ที่เดียว"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = Path(r"C:\Users\peefr\Downloads\กฏหมาย-FOOD_ADDITIVE.pdf")
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = OUTPUT_DIR / "ocr_cache"       # เก็บผล OCR ราย page ไว้รันต่อได้

# ---- OCR service (ต้องเปิด ssh tunnel + kubectl port-forward ก่อน ดู README) ----
OCR_BASE_URL = "http://localhost:8003"
OCR_ENDPOINT = "/ocr-service/ocr"
OCR_ENGINE   = "easyocr"      # easyocr | aigen | other
OCR_DOC_TYPE = "general"
OCR_TIMEOUT  = 600            # วินาที
OCR_DPI      = 200            # ความละเอียดตอน render หน้า PDF เป็นภาพ

# ---- ขอบเขตแกน x ของแต่ละคอลัมน์ในตาราง (หน่วย pt, วัดจากหน้าจริง) ----
TABLE_COLS = [
    ("CODEXNUMBER",  70.0, 132.0),
    ("CODEXNM",     132.0, 315.0),
    ("FA_MAX",      315.0, 398.0),
    ("REMARK",      398.0, 486.0),
    ("REMARK_REF",  486.0, 560.0),
]
# หัวเรื่องเป็น 2 คอลัมน์: ซ้าย = ชื่อ/INS/ชื่ออื่น, ขวา = หน้าที่
HEADER_SPLIT_X = 315.0

ROW_TOL = 4.0                 # ต่าง y ไม่เกินนี้ = บรรทัดเดียวกัน

# ลำดับคอลัมน์ในไฟล์ผลลัพธ์
OUTPUT_COLUMNS = [
    "INS_NO", "NAME_FML", "FUNCTION", "FA_MAX", "FACTOR_CACULATE",
    "REMARK_REF", "REMARK", "CODEXNUMBER", "CODEXNM",
]
DEFAULT_FACTOR_CACULATE = 1   # TODO: ยังไม่ทราบนิยาม รอยืนยันจากผู้กำหนดสเปก
