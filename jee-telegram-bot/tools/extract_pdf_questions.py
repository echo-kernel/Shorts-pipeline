#!/usr/bin/env python3
"""Download a JEE paper PDF URL and extract reviewable question candidates."""
import argparse, json, re, sys, urllib.request
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES = 50 * 1024 * 1024
ALLOWED_HOSTS = {"jeemain.nta.nic.in","nta.ac.in","www.nta.ac.in","image-static.collegedunia.com","www.pw.live","pw.live","class-sit.aakash.ac.in","news.allen.in","allen.in","prepwiser.in","www.prepwiser.in"}

def download(url, destination):
    req = urllib.request.Request(url, headers={"User-Agent":"JEE-PYQ-PDF-Extractor/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        if urlparse(response.geturl()).hostname not in ALLOWED_HOSTS:
            raise ValueError("Redirected to an unapproved host")
        content_type = response.headers.get("Content-Type","").lower()
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES: raise ValueError("PDF exceeds 50 MB")
        if not data.startswith(b"%PDF-") and "pdf" not in content_type:
            raise ValueError("URL did not return a PDF")
        destination.write_bytes(data)

def extract(pdf_path, meta):
    import fitz
    doc = fitz.open(pdf_path)
    raw = re.sub(r"\n{3,}", "\n\n", "\n\n".join(p.get_text("text", sort=True) for p in doc)).strip()
    starts = list(re.finditer(r"(?im)^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})\s*[.)]\s+", raw))
    rows = []
    for i, m in enumerate(starts):
        block = raw[m.start():starts[i+1].start() if i+1 < len(starts) else len(raw)].strip()
        if len(block) < 35: continue
        opts = list(re.finditer(r"(?im)(?:^|\n)\s*(?:\(([A-D1-4])\)|([A-D])[).])\s+", block))
        stem = block[:opts[0].start()].strip() if opts else block
        choices = []
        for j, om in enumerate(opts):
            end = opts[j+1].start() if j+1 < len(opts) else len(block)
            value = block[om.end():end].strip()
            if value: choices.append({"label":om.group(1) or om.group(2),"text":value})
        rows.append({"question_number":int(m.group(1)),"year":meta["year"],"exam_date":meta["date"],"shift":meta["shift"],"subject":"unknown","question_text":stem,"options":choices,"answer":None,"verification_status":"needs_review","source_pdf_url":meta["pdf_url"],"note":"OCR/layout and official answer-key verification required."})
    return rows, raw

def main():
    p=argparse.ArgumentParser()
    for name in ("url","year","date","shift"): p.add_argument("--"+name,required=True)
    p.add_argument("--source-label",default="NTA")
    a=p.parse_args()
    u=urlparse(a.url)
    if u.scheme!="https" or u.hostname not in ALLOWED_HOSTS:
        raise ValueError("Use an HTTPS PDF URL hosted on NTA, Aakash, ALLEN, PW, Collegedunia or PrepWiser.")
    out=Path("pdf-extraction-output"); out.mkdir(exist_ok=True)
    pdf=out/"source-paper.pdf"; download(a.url,pdf)
    meta={"year":a.year,"date":a.date,"shift":a.shift,"pdf_url":a.url,"source_label":a.source_label}
    rows,raw=extract(pdf,meta)
    (out/"extracted-text.txt").write_text(raw,encoding="utf-8")
    (out/"question-candidates.json").write_text(json.dumps({"metadata":meta,"candidate_count":len(rows),"verification_required":True,"questions":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Candidate questions extracted:",len(rows))
    print("No question is marked verified or automatically added to the live bank.")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("ERROR:",e,file=sys.stderr); sys.exit(1)
