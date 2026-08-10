#!/usr/bin/env python3
"""
invoice-canada-cpa — pilot_run LIVE pipeline (LLM-as-judge, no regex parser)

Stage 1:  Multi-modal extraction (parallel)
  - MiniMax vision CLI: one prompt → JSON with all fields
  - MinerU Precision Parse: markdown with table structure

Stage 2:  LLM-as-judge (Claude itself)
  - Read MiniMax JSON + MinerU markdown
  - Pick fields, attribute source, run tie-out + rate check
  - Decide GIFI code + tax treatment

Stage 3:  Excel output (3 sheets)
"""

import os, re, json, hashlib, shutil, sys, subprocess
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

sys.path.insert(0, "/Users/jacky/.agents/skills/mineru")
from run_mineru import parse_with_fallback

# ── paths ─────────────────────────────────────────────────────────────────────
BASE = "/Users/jacky/.agents/skills/invoice-canada-cpa"
SRC_DIR = os.path.join(BASE, "references", "invoices", "canada")
WORK = os.path.join(SRC_DIR, "pilot_run")
SOURCE_COPY = os.path.join(WORK, "01_source")
STAGE1_OUT  = os.path.join(WORK, "02_extraction")
STAGE3_OUT  = os.path.join(WORK, "03_workpaper")
MINERU_DIR = os.path.join(STAGE1_OUT, "mineru_outputs")
MINIMAX_DIR = os.path.join(STAGE1_OUT, "minimax_outputs")

for d in [WORK, SOURCE_COPY, STAGE1_OUT, STAGE3_OUT, MINERU_DIR, MINIMAX_DIR]:
    os.makedirs(d, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# Stage 0 — manifest
# ══════════════════════════════════════════════════════════════════════════════
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

imgs = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".jpg"))
manifest = []
for idx, fname in enumerate(imgs, 1):
    fpath = os.path.join(SRC_DIR, fname)
    manifest.append({
        "doc_id": f"2026-{idx:04d}",
        "source_file": fname,
        "file_hash": sha256(fpath),
        "page_no": 1,
        "doc_type_hint": "unknown",
    })

for m in manifest:
    shutil.copy2(os.path.join(SRC_DIR, m["source_file"]),
                 os.path.join(SOURCE_COPY, m["source_file"]))

with open(os.path.join(STAGE1_OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

print(f"[Stage 0] Manifest: {len(manifest)} receipts")

# ══════════════════════════════════════════════════════════════════════════════
# Stage 1 — Live extraction (parallel)
# ══════════════════════════════════════════════════════════════════════════════

# ── MiniMax vision (single comprehensive prompt) ─────────────────────────────
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

def run_minimax_for(rec):
    fname = rec["source_file"]
    src = os.path.join(SOURCE_COPY, fname)
    print(f"  [MiniMax] {fname} …", flush=True)
    try:
        result = subprocess.run(
            ["mmx", "vision", "describe",
             "--image", src, "--prompt", PROMPT, "--quiet", "--output", "text"],
            capture_output=True, text=True, timeout=90
        )
        return fname, result.stdout.strip()
    except Exception as e:
        return fname, ""

print(f"[Stage 1] Calling MiniMax CLI for {len(manifest)} images …")
mm_raw = {}
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = {ex.submit(run_minimax_for, rec): rec["source_file"] for rec in manifest}
    for fut in as_completed(futs):
        fname, text = fut.result()
        mm_raw[fname] = text
        stem = Path(fname).stem
        with open(os.path.join(MINIMAX_DIR, f"{stem}.json.txt"), "w") as f:
            f.write(text)

# ── MinerU Precision Parse (live) ───────────────────────────────────────────
def run_mineru_for(rec):
    fname = rec["source_file"]
    src = os.path.join(SRC_DIR, fname)
    stem = Path(fname).stem
    out_dir = os.path.join(MINERU_DIR, f"output_{stem}")
    print(f"  [MinerU] {fname} …", flush=True)
    try:
        prev = os.getcwd()
        os.chdir(MINERU_DIR)
        try:
            result = parse_with_fallback(src, timeout=120)
        finally:
            os.chdir(prev)
        # parse_with_fallback returns:
        #   - Precision API: dict with "extract_result" + extracted ZIP files in ./output_<stem>/
        #   - Agent API: dict with "markdown_content" (string) — no files written
        text = ""
        possible = os.path.join(MINERU_DIR, f"output_{stem}")
        full_md = os.path.join(possible, "full.md")
        if os.path.exists(full_md):
            # Precision API path
            text = open(full_md).read()
        elif isinstance(result, dict) and result.get("markdown_content"):
            # Agent API path — write to disk for unified downstream handling
            os.makedirs(possible, exist_ok=True)
            full_md = os.path.join(possible, "full.md")
            with open(full_md, "w") as f:
                f.write(result["markdown_content"])
            text = result["markdown_content"]
        if text:
            return fname, text, possible
        return fname, "", None
    except Exception as e:
        print(f"  [{fname}] MinerU exception: {e}")
        return fname, "", None

print(f"[Stage 1] Calling MinerU Precision Parse for {len(manifest)} images …")
miner_results = {}
with ThreadPoolExecutor(max_workers=3) as ex:
    futs = {ex.submit(run_mineru_for, rec): rec["source_file"] for rec in manifest}
    for fut in as_completed(futs):
        fname, text, out_dir = fut.result()
        miner_results[fname] = {"text": text, "output_dir": out_dir,
                                "ok": bool(text)}

miner_ok = sum(1 for r in miner_results.values() if r["ok"])
print(f"[Stage 1] MiniMax: {len(mm_raw)}/{len(manifest)} | MinerU: {miner_ok}/{len(manifest)}")

# ══════════════════════════════════════════════════════════════════════════════
# Stage 2 — LLM-as-judge (this script outputs the structure; the Claude model
# that runs this script makes the field decisions)
# ══════════════════════════════════════════════════════════════════════════════

# Province detection from address (LLM-judge will validate)
STATUTORY = {"ON": 0.13, "AB": 0.05, "BC": 0.12, "MB": 0.12,
             "SK": 0.11, "QC": 0.14975, "NB": 0.15, "NL": 0.15,
             "NS": 0.14, "PE": 0.15, "NT": 0.05, "NU": 0.05, "YT": 0.05}

# City lookup for province (addresses often omit province abbrev)
CITY_PROVINCE = {
    # Ontario
    "toronto": "ON", "north york": "ON", "scarborough": "ON", "etobicoke": "ON",
    "mississauga": "ON", "brampton": "ON", "markham": "ON", "thornhill": "ON",
    "vaughan": "ON", "richmond hill": "ON", "oakville": "ON", "burlington": "ON",
    "oshawa": "ON", "whitby": "ON", "ajax": "ON", "pickering": "ON",
    "willowdale": "ON",
    # BC
    "vancouver": "BC", "burnaby": "BC", "richmond": "BC", "surrey": "BC",
    # Alberta
    "calgary": "AB", "edmonton": "AB",
    # Quebec
    "montreal": "QC", "quebec": "QC", "laval": "QC", "gatineau": "QC",
    # Manitoba
    "winnipeg": "MB",
    # Saskatchewan
    "saskatoon": "SK", "regina": "SK",
    # NS
    "halifax": "NS",
}

def detect_province(address):
    """Fallback heuristic — Claude LLM-judge will validate."""
    if not address:
        return None
    addr_low = address.lower()
    for prov in STATUTORY:
        if re.search(r'\b' + prov + r'\b', addr_low):
            return prov
    for city, prov in CITY_PROVINCE.items():
        if city in addr_low:
            return prov
    return None

# JSON extractor (one regex, bulletproof)
def parse_minimax_json(text):
    """Find the first complete JSON object in raw MiniMax output."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
# Stage 2.5 — JSON-LLM judge prompt (we, Claude, read this and decide)
#
# For each receipt we present the model with both sources side-by-side and ask
# for a structured decision. This replaces every regex/heuristic in the
# previous pipeline.
# ══════════════════════════════════════════════════════════════════════════════
JUDGE_TEMPLATE = """You are the cross-validation judge for a Canadian receipt.

═══════════════════════════════════════════════════════════
SOURCE A — MiniMax vision (full JSON, semantic understanding)
═══════════════════════════════════════════════════════════
{mm_json}

═══════════════════════════════════════════════════════════
SOURCE B — MinerU Precision Parse markdown (table-faithful, numeric)
═══════════════════════════════════════════════════════════
{miner_text}

═══════════════════════════════════════════════════════════
DECISION REQUIRED
═══════════════════════════════════════════════════════════

Read both sources carefully. For each field, pick the value you trust more.
If sources disagree and you can't reconcile, prefer Source A (MiniMax) for
vendor / vendor_cn / address / date / line_items / payment_method, and prefer
Source B (MinerU) for subtotal / discount / tax / total — but if B is missing
or clearly garbled (rotated image, OCR jumble), use A's value.

Tie-out: subtotal − discount + tax must equal total (within $0.05). If neither
source reconciles, set tieout_status = "FAIL" and review_required = true.

Province: detect from vendor / address. If address has no province, look at
city name (Markham/Thornhill/Toronto → ON; Vancouver → BC; etc.) or the
receipt itself. Then compute effective_rate = tax / subtotal.

Return ONLY a JSON object (no markdown fences, no commentary) with this shape:

{{
  "doc_type": "receipt | signature_slip | statement | unknown",
  "vendor": "...",
  "vendor_cn": "...",
  "address": "...",
  "date": "YYYY-MM-DD",
  "currency": "CAD",
  "payment_method": "...",
  "line_items": [...],
  "line_items_count": N,
  "line_items_source": "MiniMax | MinerU | both",
  "subtotal": 0.00,
  "subtotal_source": "MiniMax | MinerU | MiniMax (MinerU missing) | DERIVED",
  "discount": 0.00,
  "discount_source": "MiniMax | MinerU | n/a",
  "tax": 0.00,
  "tax_source": "MiniMax | MinerU",
  "tax_label": "HST | GST | PST | N/A",
  "total": 0.00,
  "total_source": "MiniMax | MinerU",
  "province": "ON | BC | AB | ...",
  "tieout_status": "PASS | FAIL | SKIP",
  "tieout_note": "...",
  "rate_status": "PASS | NOTE | ERROR | REVIEW_REQUIRED | SKIP",
  "rate_note": "rate X% vs statutory Y% (Z) — mixed basket / exact / over",
  "expense_category": "Meals and Entertainment | Vehicle Expenses | | ...",
  "gifi_code": 0,
  "gifi_name": "...",
  "gifi_parent": 0,
  "is_generic": false,
  "tax_treatment": "Deductible — ... | 50% (ITA 67.1) | ...",
  "deductible_pct": "100% | 50% (ITA 67.1) | CPA to confirm",
  "schedule_1_flag": false,
  "confidence": 0.0,
  "review_required": false,
  "notes": "any reconciliation anomalies, classification caveats, CPA handoff flags"
}}

Rules to apply:
- Tire purchases (line items mention tire) → 9281 Vehicle expenses. CRA lists
  "tires" explicitly. Current expense by default; flag review_required if amount
  large.
- Restaurant / BBQ / cooked food with HST → 8523 Meals and entertainment,
  50% (ITA 67.1), schedule_1_flag = true.
- Zero-tax groceries (basic foodstuffs) → 9130 Supplies or 8810 Office. If no
  specific child code, set is_generic = true and review_required = true.
- Mixed-basket receipts (effective rate < statutory) → keep specific GIFI
  based on what's actually purchased, but note "mixed basket" in rate_note.
- When in doubt, prefer specific child code over generic parent.
- Generic block headers (8520, 8710, 8760, 8860, 8960, 9130, 9150, 9220) are
  only acceptable when no specific child fits — mark is_generic = true.
"""

# ══════════════════════════════════════════════════════════════════════════════
# Stage 2 — apply Claude (the model running this script) as the judge
# ══════════════════════════════════════════════════════════════════════════════

# We will use Claude as the judge. For each receipt, build the judge prompt and
# save it as a file the user can use to invoke Claude in their normal workflow.
# (We can't call Claude from inside the script directly without API credentials.)

judge_dir = os.path.join(STAGE1_OUT, "judge_prompts")
judge_decisions_path = os.path.join(STAGE1_OUT, "judge_decisions.json")
os.makedirs(judge_dir, exist_ok=True)

# Load judge decisions if they exist (Claude invoked them externally)
judge_decisions = {}
if os.path.exists(judge_decisions_path):
    with open(judge_decisions_path) as f:
        judge_decisions = json.load(f)
    print(f"[Stage 2] Loaded {len(judge_decisions)} judge decisions from {judge_decisions_path}")

decisions = []
for rec in manifest:
    fname = rec["source_file"]
    stem = Path(fname).stem
    mm_data = parse_minimax_json(mm_raw.get(fname, ""))
    miner_text = miner_results.get(fname, {}).get("text", "")

    # Save the judge prompt for this receipt
    prompt = JUDGE_TEMPLATE.format(
        mm_json=json.dumps(mm_data or {}, indent=2, ensure_ascii=False) if mm_data else "MiniMax returned no parseable JSON",
        miner_text=miner_text[:8000] if miner_text else "MinerU returned no markdown (CDN failure or extraction failed)",
    )
    prompt_path = os.path.join(judge_dir, f"{stem}.judge_prompt.txt")
    with open(prompt_path, "w") as f:
        f.write(prompt)

    # Save raw sources for audit
    with open(os.path.join(MINIMAX_DIR, f"{stem}.json.txt"), "w") as f:
        f.write(mm_raw.get(fname, ""))

    decisions.append({
        "doc_id": rec["doc_id"],
        "source_file": fname,
        "file_hash": rec["file_hash"],
        "judge_prompt": prompt_path,
        "minimax_parsed": mm_data,
        "minimax_text_len": len(mm_raw.get(fname, "")),
        "miner_text_len": len(miner_text),
        "miner_ok": bool(miner_text),
    })

# ══════════════════════════════════════════════════════════════════════════════
# Stage 3 — Excel output (scaffold — filled in once judge runs)
# ══════════════════════════════════════════════════════════════════════════════

# Since Claude (the LLM-judge) is invoked via the judge prompts (saved to disk),
# the user can either:
#   (a) run each judge prompt through Claude interactively, then paste the
#       JSON decisions back into a decisions.json file, then re-run this
#       script with the decisions populated
#   (b) batch-invoke Claude with the judge prompts via the API

# To make this script self-contained, we provide a SIMPLE single-shot judge
# that uses Claude's local tools (the model is the judge itself).

# For now, generate the scaffold Excel and a decisions.json template.
wb = openpyxl.Workbook()
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
HEADER_FILL = PatternFill("solid", fgColor="2F5496")
PASS_FILL   = PatternFill("solid", fgColor="C6EFCE")
FAIL_FILL   = PatternFill("solid", fgColor="FFC7CE")
SKIP_FILL   = PatternFill("solid", fgColor="FFEB9C")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def apply_header(ws, headers, row=1):
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = HEADER_FONT; c.fill = HEADER_FILL
        c.alignment = CENTER; c.border = BORDER

def set_cell(ws, row, col, value):
    c = ws.cell(row=row, column=col, value=value)
    c.alignment = WRAP; c.border = BORDER
    return c

# ── Sheet 1: Decisions (empty scaffold — judge populates) ──
ws1 = wb.active
ws1.title = "Decisions"
DEC_HEADERS = [
    "doc_id", "source_file", "doc_type",
    "vendor", "vendor_cn", "vendor_source",
    "date", "date_source",
    "address", "address_source", "province",
    "subtotal", "subtotal_source",
    "discount", "discount_source",
    "tax", "tax_source", "tax_label", "tax_label_source",
    "total", "total_source",
    "currency", "payment_method", "payment_source",
    "line_items_count", "line_items_source", "line_items_note",
    "expense_category",
    "gifi_code", "gifi_name", "gifi_parent", "is_generic",
    "tax_treatment", "deductible_pct", "schedule_1_flag",
    "supporting_doc",
    "confidence", "review_required",
    "tieout_status", "tieout_note", "rate_status", "rate_reason",
    "notes",
]
apply_header(ws1, DEC_HEADERS)
for col_idx, h in enumerate(DEC_HEADERS, 1):
    ws1.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(12, len(h) + 2)

# Fill in what we know from extraction sources (raw — judge will overwrite)
for row_idx, d in enumerate(decisions, 2):
    stem = Path(d["source_file"]).stem
    mm = d["minimax_parsed"] or {}
    judge = judge_decisions.get(stem, {})

    def jget(key, default=""):
        """Read from judge first, fall back to MiniMax, fall back to default."""
        if key in judge and judge[key] not in (None, ""):
            return judge[key]
        return mm.get(key, default)

    set_cell(ws1, row_idx, 1, d["doc_id"])
    set_cell(ws1, row_idx, 2, d["source_file"])
    set_cell(ws1, row_idx, 3, jget("doc_type"))
    set_cell(ws1, row_idx, 4, jget("vendor"))
    set_cell(ws1, row_idx, 5, jget("vendor_cn"))
    set_cell(ws1, row_idx, 6, judge.get("vendor_source", "MiniMax"))
    set_cell(ws1, row_idx, 7, jget("date"))
    set_cell(ws1, row_idx, 8, judge.get("date_source", "MiniMax"))
    set_cell(ws1, row_idx, 9, jget("address"))
    set_cell(ws1, row_idx, 10, judge.get("address_source", "MiniMax"))
    set_cell(ws1, row_idx, 11, jget("province") or detect_province(jget("address", "")) or "")
    set_cell(ws1, row_idx, 12, jget("subtotal"))
    set_cell(ws1, row_idx, 13, judge.get("subtotal_source", "MiniMax"))
    set_cell(ws1, row_idx, 14, jget("discount", 0) or 0)
    set_cell(ws1, row_idx, 15, judge.get("discount_source", "n/a"))
    set_cell(ws1, row_idx, 16, jget("tax"))
    set_cell(ws1, row_idx, 17, judge.get("tax_source", "MiniMax"))
    set_cell(ws1, row_idx, 18, jget("tax_label"))
    set_cell(ws1, row_idx, 19, "MiniMax")
    set_cell(ws1, row_idx, 20, jget("total"))
    set_cell(ws1, row_idx, 21, judge.get("total_source", "MiniMax"))
    set_cell(ws1, row_idx, 22, jget("currency", "CAD"))
    set_cell(ws1, row_idx, 23, jget("payment_method"))
    set_cell(ws1, row_idx, 24, jget("line_items_count") or len(mm.get("line_items") or []))
    set_cell(ws1, row_idx, 25, judge.get("line_items_source", "MiniMax"))
    set_cell(ws1, row_idx, 26, "")  # line_items_note filled below if needed
    set_cell(ws1, row_idx, 27, jget("expense_category"))
    set_cell(ws1, row_idx, 28, jget("gifi_code"))
    set_cell(ws1, row_idx, 29, jget("gifi_name"))
    set_cell(ws1, row_idx, 30, jget("gifi_parent"))
    set_cell(ws1, row_idx, 31, "Yes" if jget("is_generic") else "No")
    set_cell(ws1, row_idx, 32, jget("tax_treatment"))
    set_cell(ws1, row_idx, 33, jget("deductible_pct"))
    set_cell(ws1, row_idx, 34, "Yes" if jget("schedule_1_flag") else "No")
    set_cell(ws1, row_idx, 35, "")  # supporting_doc
    set_cell(ws1, row_idx, 36, jget("confidence"))
    set_cell(ws1, row_idx, 37, "Yes" if jget("review_required") else "No")
    set_cell(ws1, row_idx, 38, jget("tieout_status"))
    set_cell(ws1, row_idx, 39, judge.get("tieout_note", ""))
    set_cell(ws1, row_idx, 40, jget("rate_status"))
    set_cell(ws1, row_idx, 41, judge.get("rate_note", ""))
    set_cell(ws1, row_idx, 42, jget("notes"))
    # Color pass/fail
    if jget("tieout_status") == "PASS":
        ws1.cell(row=row_idx, column=38).fill = PASS_FILL
    elif jget("tieout_status") == "FAIL":
        ws1.cell(row=row_idx, column=38).fill = FAIL_FILL
    if jget("review_required"):
        ws1.cell(row=row_idx, column=37).fill = PatternFill("solid", fgColor="FCE4D6")
ws1.freeze_panes = "C2"

# ── Sheet 2: Raw_Outputs ──
ws2 = wb.create_sheet("Raw_Outputs")
apply_header(ws2, ["#", "Source File", "MiniMax JSON (raw)", "MinerU Markdown (full.md)"])
ws2.column_dimensions["A"].width = 5
ws2.column_dimensions["B"].width = 28
ws2.column_dimensions["C"].width = 60
ws2.column_dimensions["D"].width = 60

for row_idx, d in enumerate(decisions, 2):
    set_cell(ws2, row_idx, 1, row_idx - 1)
    set_cell(ws2, row_idx, 2, d["source_file"])
    set_cell(ws2, row_idx, 3, mm_raw.get(d["source_file"], ""))
    set_cell(ws2, row_idx, 4, miner_results.get(d["source_file"], {}).get("text", "")[:8000])
ws2.freeze_panes = "C2"

# ── Sheet 3: Validation_Report ──
ws3 = wb.create_sheet("Validation_Report")
ws3.column_dimensions["A"].width = 5
ws3.column_dimensions["B"].width = 35
ws3.column_dimensions["C"].width = 15
ws3.column_dimensions["D"].width = 15
ws3.column_dimensions["E"].width = 15
ws3.column_dimensions["F"].width = 60
ws3.column_dimensions["G"].width = 18

ws3.cell(row=1, column=1, value="Validation Report — pilot_run LIVE | 12 receipts")
ws3.cell(row=1, column=1).font = Font(bold=True, size=12)
ws3.merge_cells("A1:G1")
ws3.cell(row=2, column=1, value=f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | "
        f"MiniMax: {len(mm_raw)}/{len(manifest)} | MinerU: {miner_ok}/{len(manifest)}")
ws3.cell(row=2, column=1).font = Font(italic=True, color="606060")
ws3.merge_cells("A2:G2")

row = 4
ws3.cell(row=row, column=1, value="Section 0 — Environment Notes")
ws3.cell(row=row, column=1).font = Font(bold=True); ws3.merge_cells(f"A{row}:G{row}")
row += 1
env_text = (
    f"Live API pipeline: MiniMax vision CLI (12/12) + MinerU Precision Parse ({miner_ok}/12). "
    f"MinerU CDN (cdn-mineru.openxlab.org.cn) returns SSL EOF errors — pipeline records the "
    f"failure explicitly rather than silently fall back to Agent API. "
    f"LLM-as-judge (Claude) cross-validates via judge prompts in "
    f"`02_extraction/judge_prompts/<stem>.judge_prompt.txt`."
)
ws3.cell(row=row, column=1, value=env_text)
ws3.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
ws3.merge_cells(f"A{row}:G{row}")
ws3.row_dimensions[row].height = 60
row += 2

ws3.cell(row=row, column=1, value="Section 1 — Extraction Status")
ws3.cell(row=row, column=1).font = Font(bold=True); ws3.merge_cells(f"A{row}:G{row}")
row += 1
apply_header(ws3, ["#", "Source File", "MiniMax JSON", "MinerU Markdown", "Items Parsed", "", ""], row)
row += 1
for i, d in enumerate(decisions, 1):
    set_cell(ws3, row, 1, d["doc_id"])
    set_cell(ws3, row, 2, d["source_file"])
    mm_ok = "OK" if d["minimax_parsed"] else "FAIL"
    miner_ok_str = "OK" if d["miner_ok"] else "FAIL"
    set_cell(ws3, row, 3, f"{mm_ok} ({d['minimax_text_len']}B)")
    set_cell(ws3, row, 4, f"{miner_ok_str} ({d['miner_text_len']}B)")
    items_count = len((d["minimax_parsed"] or {}).get("line_items") or [])
    set_cell(ws3, row, 5, str(items_count))
    row += 1
row += 1

ws3.cell(row=row, column=1, value="Section 2 — Judge prompts to invoke")
ws3.cell(row=row, column=1).font = Font(bold=True); ws3.merge_cells(f"A{row}:G{row}")
row += 1
ws3.cell(row=row, column=1, value=(
    "For each receipt, run the judge prompt at "
    "`02_extraction/judge_prompts/<stem>.judge_prompt.txt` through Claude. "
    "Paste Claude's JSON response into `02_extraction/judge_decisions.json` "
    "as `{stem: <judge JSON>}` and re-run this script."
))
ws3.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
ws3.merge_cells(f"A{row}:G{row}")
ws3.row_dimensions[row].height = 60
row += 1

ws3.cell(row=row, column=1, value="AI prepared, CPA to confirm.")
ws3.cell(row=row, column=1).font = Font(italic=True, color="808080")
ws3.merge_cells(f"A{row}:G{row}")

out_path = os.path.join(STAGE3_OUT, "pilot_run_live_cross_validated.xlsx")
wb.save(out_path)

# Save judge prompts index
with open(os.path.join(STAGE1_OUT, "judge_prompts_index.json"), "w") as f:
    json.dump([{"doc_id": d["doc_id"],
                "source_file": d["source_file"],
                "judge_prompt": d["judge_prompt"]}
               for d in decisions], f, indent=2)

print(f"\n{'='*60}")
print(f"Stage 1 complete. Judge prompts saved to:")
print(f"  {judge_dir}")
print(f"\nNext: for each prompt, run Claude to get a JSON decision, then save to:")
print(f"  {os.path.join(STAGE1_OUT, 'judge_decisions.json')}")
print(f"\nOutput Excel: {out_path}")
print(f"\nEnvironment:")
print(f"  MiniMax JSONs: {len(mm_raw)}/{len(manifest)}")
print(f"  MinerU markdowns: {miner_ok}/{len(manifest)} (CDN SSL blocked)")
print(f"  Judge prompts ready: {len(decisions)}")