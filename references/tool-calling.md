# Tool calling reference

Exact commands, parameters, and authentication for each tool in the pipeline.

## MiniMax vision CLI

### Authentication
`mmx` CLI is already configured on the user's system with API key. No setup needed.

###### Command

```bash
mmx vision describe \
  --image <path> \
  --prompt "<JSON-extraction prompt>" \
  --quiet \
  --output text
```

### Recommended prompt for receipts

The prompt should request a single JSON object with **all** the fields the pipeline needs (vendor, line_items, amounts, etc.). See `SKILL.md` §1.1 for the schema. **Do not use multiple short prompts** — the model performs better with one comprehensive schema prompt than several split prompts.

Key prompt design rules:
- Provide the JSON schema as the prompt itself, not as prose
- Include `line_items` explicitly — models omit it unless asked
- Include `discount` and `tip` separately — they often pollute subtotal otherwise
- Include `confidence` so the model self-reports reliability
- Ask for the `notes` field for any reconciliation anomalies

### Extracting JSON from output

```python
import re, json, subprocess

def call_minimax(path, prompt, timeout=300):
    try:
        result = subprocess.run(
            ["mmx", "vision", "describe", "--image", path,
             "--prompt", prompt, "--quiet", "--output", "text"],
            capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"          # explicit failure — never a silent empty dict

    m = re.search(r"\{[\s\S]*\}", result.stdout)
    if not m:
        return None, "NO_JSON"
    try:
        return json.loads(m.group(0)), "OK"   # json.loads is the success test
    except json.JSONDecodeError:
        return None, "BAD_JSON"
```

Do **not** write field-level regex extraction beyond this. Trust the JSON.

> ⚠️ **Never use `re.search(r"\{[\s\S]*\}", ...)` as the success test.** A `subprocess` timeout raises an exception whose string **echoes the full command including the prompt** — and the prompt *is* a JSON schema, full of braces. The regex matches, and a call that completely failed gets recorded as a success with garbage data. This is not hypothetical: the largest receipt in the test corpus (66 line items) blew a 120 s timeout and passed this check. **Success = `json.loads` did not raise.**

**Timeout**: default `timeout=300`. Receipts with 50+ line items exceed 120 s; the previously documented `timeout=60` fails on any non-trivial receipt. Retry once on timeout; on a second failure record an explicit extraction failure rather than writing an empty result.

### Failure modes

- Timeout: retry once at the same timeout, then record explicit failure. Do **not** fall back to an empty dict.
- Empty stdout: API key issue or rate limit. Wait 5s and retry.
- JSON with `null` for all fields: model couldn't parse the image. Re-prompt with `"Look at this image carefully and extract..."`.
- No JSON block: model output prose. Tighten the prompt or use `--output json` if available.
- Output truncated at token limit on long receipts (50+ line items): rely on MinerU markdown to fill gaps.
- **Date shifted by years**: the model may "correct" a printed date it believes is in the future (knowledge-cutoff artifact). Take dates from MinerU. See SKILL.md §2.1.

## MinerU Precision Parse

### Authentication
API key is in `/Users/jacky/.agents/skills/mineru/.env` as `MINERU_API_KEY`. `precision_parse` reads it automatically via `load_env()`.

### Command

**Call `precision_parse` directly. Do NOT use the `run_mineru.py` CLI.**

```python
import sys
sys.path.insert(0, "/Users/jacky/.agents/skills/mineru")
from run_mineru import precision_parse

precision_parse(image_path, timeout=300)
```

> ⚠️ **The CLI violates this skill's own rule.** `run_mineru.py`'s `main()` calls `parse_with_fallback()`, whose docstring reads *"解析文件，优先使用 Agent API，失败时降级到 Precision API"* — **Agent is the primary path**, Precision only the fallback. SKILL.md requires Precision Parse only. The Agent failure prints one log line and is then swallowed by a successful fallback, so the output looks entirely normal and the violation is invisible. Verified in trial_run_2's `run.log`: repeated `cdn-mineru.openxlab.org.cn` SSL failures, results still produced.

**`precision_parse` takes no output-directory argument** — it writes `./output_<stem>/` relative to the **current working directory**. When parallelising, give each call its own cwd (`subprocess.run(..., cwd=...)`), or concurrent calls will collide.

Signature is `precision_parse(file_path, timeout=120)`. Note `parse_with_fallback(file_path, timeout)` takes **no** output-dir parameter either — passing one positionally raises `got multiple values for argument 'timeout'`.


### Output structure

```
output_<image>/
├── full.md                    ← main output (use this)
├── layout.json                ← block-level layout (debugging)
├── *.content_list.json        ← structured content
├── *.content_list_v2.json     ← v2 content
├── *.model.json                ← model metadata
├── *.origin.pdf               ← original as PDF
└── images/                    ← extracted image fragments
```

The `full.md` is given to the LLM-judge for cross-validation, **not** parsed by regex.

### Agent lightweight mode caveat

The same script supports agent mode via `agent_parse()`. **However, in practice the agent API's CDN download returns SSL errors** (cdn-mineru.openxlab.org.cn). 

## Tesseract OCR

### Setup
Requires `tesseract` and `magick` on the system. On macOS: `brew install tesseract imagemagick`. Chinese language packs optional (`tessdata`).

### Command

```bash
bash /Users/jacky/.agents/skills/ocr-image-text-extract/scripts/preprocess_ocr.sh <image> [lang]
```

Default language: `chi_sim+chi_tra+eng`. Use `eng` only for English receipts.

### Limitations to remember

- **Chinese garbled**: even with `chi_sim`, results are unreliable
- **Rotated images fail completely**
- **Long receipts lose lines** (vertical scrolling needed)
- **Structure lost**: just text, no field labels

Use Tesseract only as a sanity check or when both MiniMax and MinerU are unavailable.

## Cost comparison (informal)

| Tool | Per-image cost | Per-image time |
|---|---|---|
| MiniMax | $$ (vision API) | 5–15s |
| MinerU Precision Parse | $ (PDF parse API) | 20–40s |
| Tesseract | Free | 1–3s |
| LLM cross-validation | $ (Claude tokens) | 5–15s |

For a 12-receipt batch: total cost dominated by MiniMax (~$0.50–1) and MinerU (~$0.10–0.30). LLM cross-validation adds ~$0.20 in tokens. Total per batch: roughly $1–2.

## Running tools in parallel

To minimize wall-clock time, run MiniMax and MinerU in parallel using a thread pool:

```python
from concurrent.futures import ThreadPoolExecutor

def process_one(image_path):
    minimax = run_minimax(image_path)
    mineru = run_mineru(image_path)
    return minimax, mineru

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(process_one, image_paths))
```

MinerU is the slowest (~30s per image), so 3–4 workers keeps throughput at ~1 image per 10–15 seconds.