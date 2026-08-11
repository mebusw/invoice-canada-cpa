#!/usr/bin/env python3
"""trial_run_3 — Stage 0 (manifest) + Stage 1 (multi-modal extraction).

No regex field extraction. MiniMax returns JSON; MinerU returns markdown.
Both are handed verbatim to the LLM-judge (Claude) in Stage 2.
"""
import os, re, json, hashlib, sys, subprocess, shutil
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/Users/jacky/.agents/skills/mineru")
from run_mineru import parse_with_fallback

WORK = "/Users/jacky/.claude/skills/invoice-canada-cpa/trials/trial_run_3"
SRC = os.path.join(WORK, "01_source")
EXT = os.path.join(WORK, "02_extraction")
MM_DIR = os.path.join(EXT, "minimax_outputs")
MU_DIR = os.path.join(EXT, "mineru_outputs")

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()

# ── Stage 0: manifest ────────────────────────────────────────────────────────
imgs = sorted(f for f in os.listdir(SRC) if f.lower().endswith((".jpg", ".jpeg", ".png")))
manifest = []
for i, fn in enumerate(imgs, 1):
    manifest.append({
        "doc_id": f"2026-{i:04d}",
        "source_file": fn,
        "file_hash": sha256(os.path.join(SRC, fn)),
        "page_no": 1,
        "doc_type_hint": "unknown",
    })
hashes = {}
for m in manifest:
    hashes.setdefault(m["file_hash"], []).append(m["doc_id"])
m_dupes = {h: v for h, v in hashes.items() if len(v) > 1}
with open(os.path.join(EXT, "manifest.json"), "w") as f:
    json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
               "count": len(manifest), "hash_duplicates": m_dupes,
               "docs": manifest}, f, indent=2)
print(f"[Stage 0] manifest: {len(manifest)} docs, hash-dupes: {len(m_dupes)}")

PROMPT = """You are extracting data from a Canadian receipt photo. Read the image carefully and return ONLY a JSON object (no markdown fences, no commentary) with this exact shape — populate every field you can read, use null for missing:

{
  "doc_type": "receipt | signature_slip | statement | unknown",
  "vendor": "store or restaurant name as printed",
  "vendor_cn": "Chinese name if any (preserve original characters)",
  "address": "street, city, province postal as printed",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "currency": "CAD | USD | other",
  "payment_method": "Visa | MasterCard | Debit | Cash | other",
  "line_items": [{"name": "as printed", "price": 0.00}, ...],
  "subtotal": 0.00,
  "discount": 0.00,
  "tax": 0.00,
  "tax_label": "HST | GST | PST | QST | N/A | mixed",
  "total": 0.00,
  "tip": 0.00,
  "confidence": 0.0,
  "notes": "anything that affects reconciliation or classification"
}
"""

def minimax(rec):
    fn = rec["source_file"]
    try:
        r = subprocess.run(["mmx", "vision", "describe", "--image", os.path.join(SRC, fn),
                            "--prompt", PROMPT, "--quiet", "--output", "text"],
                           capture_output=True, text=True, timeout=120)
        out = r.stdout.strip()
    except Exception as e:
        out = f"__ERROR__ {e}"
    with open(os.path.join(MM_DIR, fn + ".json.txt"), "w") as f:
        f.write(out)
    ok = bool(re.search(r"\{[\s\S]*\}", out))
    print(f"  [MiniMax] {fn}: {'ok' if ok else 'NO-JSON'} ({len(out)}b)", flush=True)
    return fn, ok

def mineru(rec):
    fn = rec["source_file"]
    outdir = os.path.join(MU_DIR, "output_" + os.path.splitext(fn)[0])
    os.makedirs(outdir, exist_ok=True)
    try:
        md = parse_with_fallback(os.path.join(SRC, fn), outdir, timeout=300)
    except Exception as e:
        md = None
        print(f"  [MinerU] {fn}: EXCEPTION {e}", flush=True)
    p = os.path.join(outdir, "full.md")
    ok = os.path.exists(p) and os.path.getsize(p) > 0
    print(f"  [MinerU] {fn}: {'ok' if ok else 'FAIL'}", flush=True)
    return fn, ok

print(f"[Stage 1] MiniMax x{len(manifest)} …")
mm_ok = 0
with ThreadPoolExecutor(max_workers=4) as ex:
    for fut in as_completed([ex.submit(minimax, r) for r in manifest]):
        mm_ok += 1 if fut.result()[1] else 0

print(f"[Stage 1] MinerU x{len(manifest)} …")
mu_ok = 0
with ThreadPoolExecutor(max_workers=3) as ex:
    for fut in as_completed([ex.submit(mineru, r) for r in manifest]):
        mu_ok += 1 if fut.result()[1] else 0

print(f"[Stage 1] DONE  MiniMax {mm_ok}/{len(manifest)}  MinerU {mu_ok}/{len(manifest)}")
if mu_ok < len(manifest):
    print("[Stage 1] WARNING: MinerU Precision Parse incomplete — explicit failure, no silent Agent fallback")
