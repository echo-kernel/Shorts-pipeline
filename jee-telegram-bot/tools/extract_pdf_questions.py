#!/usr/bin/env python3
"""Download NTA/coaching JEE paper PDF and OCR question-page images.

Outputs review candidates only. It never invents answer keys or marks OCR as verified.
"""
import argparse, json, re, subprocess, sys, urllib.request
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES = 50 * 1024 * 1024
ALLOWED_HOSTS = {"jeemain.nta.nic.in","nta.ac.in","www.nta.ac.in","cdnbbsr.s3waas.gov.in","image-static.collegedunia.com","www.pw.live","pw.live","class-sit.aakash.ac.in","news.allen.in","allen.in","prepwiser.in","www.prepwiser.in"}

def download(url, dest):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JEE-PYQ-Extractor"})
    with urllib.request.urlopen(req,timeout=90) as r:
        if urlparse(r.geturl()).hostname not in ALLOWED_HOSTS: raise ValueError("Redirected to unapproved host")
        data=r.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES: raise ValueError("PDF exceeds 50 MB")
        if not data.startswith(b"%PDF-"): raise ValueError("URL did not return a PDF")
        dest.write_bytes(data)

def main():
    ap=argparse.ArgumentParser()
    for k in ("url","year","date","shift"): ap.add_argument("--"+k,required=True)
    ap.add_argument("--source-label",default="NTA")
    a=ap.parse_args()
    u=urlparse(a.url)
    if u.scheme!="https" or u.hostname not in ALLOWED_HOSTS: raise ValueError("Use an approved HTTPS PDF host")
    out=Path("pdf-extraction-output"); out.mkdir(exist_ok=True)
    pdf=out/"source-paper.pdf"; download(a.url,pdf)
    import fitz
    doc=fitz.open(pdf)
    page_text=[]
    for n,page in enumerate(doc,1):
        native=page.get_text("text",sort=True).strip()
        if len(native)<180 or "Question Number" in native and len(native)<800:
            pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
            img=out/f"page-{n:03}.png"; pix.save(img)
            proc=subprocess.run(["tesseract",str(img),"stdout","-l","eng","--psm","6"],capture_output=True,text=True)
            if proc.returncode: raise RuntimeError("Tesseract OCR failed: "+proc.stderr[-500:])
            text=proc.stdout.strip()
        else: text=native
        page_text.append(f"\n\n===== PDF PAGE {n} =====\n{text}")
    raw="".join(page_text).strip()
    (out/"extracted-text.txt").write_text(raw,encoding="utf-8")
    matches=list(re.finditer(r"(?i)Question\s*Number\s*[:：]?\s*(\d{1,3})",raw))
    questions=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(raw)
        chunk=raw[m.start():end].strip()
        if len(chunk)<45: continue
        qnum=int(m.group(1))
        questions.append({
          "id":f"{a.year}-{a.date}-{a.shift.replace(' ','-').lower()}-q{qnum}",
          "question_number":qnum,"year":a.year,"exam_date":a.date,"shift":a.shift,
          "subject":"unknown","question":chunk,"options":[],
          "answer":None,"explanation":"",
          "verified":False,"verification_status":"needs_manual_review",
          "source_url":a.url,"source_label":a.source_label,
          "note":"OCR candidate. Check question, options, diagrams and NTA final answer key before adding to live bank."
        })
    meta={"year":a.year,"date":a.date,"shift":a.shift,"source_label":a.source_label,"pdf_url":a.url,"pages":len(doc)}
    (out/"question-candidates.json").write_text(json.dumps({"metadata":meta,"candidate_count":len(questions),"questions":questions},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Processed {len(doc)} pages; OCR question candidates: {len(questions)}")
    print("Review question-candidates.json and extracted-text.txt. Nothing was auto-verified or added to live bot.")

if __name__=="__main__":
    try: main()
    except Exception as e: print("ERROR:",e,file=sys.stderr); sys.exit(1)
