# -*- coding: utf-8 -*-
"""ตรวจความถูกต้องของผลแปลง นมโค.pdf

สร้าง 'เฉลย' จากพิกัด x ของคอลัมน์ในเอกสาร (ซึ่งคงที่)
แล้วเทียบกับผลที่ตัวอ่านแบบทั่วไปแกะได้
"""
import sys
import pdfplumber
import pandas as pd
from parser import page_lines

PDF = r"C:/Users/peefr/Downloads/นมโค.pdf"
SAMPLE = list(range(2, 42))          # สุ่มตรวจ 40 หน้าแรกของ layout A
COLS = [("INS_NO", 165, 210), ("NAME_FML", 210, 400)]


def truth_rows(pages):
    rows = []
    with pdfplumber.open(PDF) as pdf:
        for pno in pages:
            for ln in page_lines(pdf.pages[pno - 1]):
                cell = {}
                for name, lo, hi in COLS:
                    txt = " ".join(w["text"] for w in ln["words"]
                                   if lo <= (w["x0"] + w["x1"]) / 2 < hi)
                    cell[name] = txt.strip()
                if cell.get("NAME_FML") in ("", "NAME_FML"):
                    continue
                cell["_PAGE"] = pno
                rows.append(cell)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output/นมโค.xlsx"
    truth = truth_rows(SAMPLE)
    got = pd.read_excel(out)
    if "_PAGE" in got.columns:
        got = got[got["_PAGE"].isin(SAMPLE)]
    else:
        print("(ไฟล์ผลลัพธ์ไม่มีคอลัมน์ _PAGE -> เทียบกับทั้งไฟล์ ซึ่งนับแบบใจกว้างกว่าความจริง)")
        print()

    print("เฉลย (จากพิกัดคอลัมน์) : %d แถว จาก %d หน้า" % (len(truth), len(SAMPLE)))
    print("ผลที่สคริปต์แกะได้      : %d แถว" % len(got))
    print()

    for col in ("INS_NO", "NAME_FML"):
        t = [x for x in truth[col].astype(str) if x and x != "-"]
        g = set(str(x).strip() for x in got[col].dropna())
        hit = sum(1 for x in set(t) if x in g)
        uniq = len(set(t))
        print("%-10s ค่าที่ควรมี %3d แบบ | สคริปต์เจอ %3d แบบ (%.0f%%)"
              % (col, uniq, hit, 100 * hit / uniq if uniq else 0))

    print()
    print("ตัวอย่างเฉลย 5 แถวแรก:")
    print(truth.head(5).to_string(index=False))
