# Tool calling reference

Exact commands, parameters, and authentication for each tool in the pipeline.

## MiniMax (mmx vision)

### Authentication
The `mmx` CLI is already configured on the user's system with their API key. No setup needed.

### Command

```bash
mmx vision describe \
  --image <path> \
  --prompt "<JSON-extraction prompt>" \
  --quiet \
  --output text
```

### Recommended prompt for receipts

```
Extract from this Canadian receipt. Return ONLY valid JSON (no markdown fences, no commentary).
Use this exact schema:
{
  "vendor": "store or restaurant name",
  "vendor_cn": "Chinese name if present, else empty string",
  "address": "full street address with city and province",
  "date": "YYYY-MM-DD format",
  "time": "HH:MM or HH:MM:SS",
  "subtotal": float (pre-tax amount, or null if not shown),
  "discount": float (converted from percentage),
  "tax": float (HST/GST/PST amount, or 0 if zero-rated basic groceries),
  "tax_label": "HST" or "GST" or "PST" or "QST" or "N/A",
  "total": float (grand total amount paid),
  "currency": "CAD" or "USD",
  "payment_method": "Visa" or "MasterCard" or "Debit" or "Cash" or "Unknown",
  "payment_account": "card number or account number",
  "line_items": [{"name": "...", "price": float}, ...]
}
If any field cannot be determined, use null. Output ONLY the JSON object.
```

### Extracting JSON from output

```python
import re, json, subprocess

result = subprocess.run(
    ["mmx", "vision", "describe", "--image", path, "--prompt", prompt, "--quiet", "--output", "text"],
    capture_output=True, text=True, timeout=60
)
m = re.search(r"\{[\s\S]*\}", result.stdout)
data = json.loads(m.group(0)) if m else {}
```

### Failure modes

- Empty stdout: API key issue or rate limit. Wait 5s and retry.
- JSON with `null` for all fields: model couldn't parse the image. Try with `--prompt "Look at this image carefully and extract..."` to force attention.
- No JSON block: the model output prose instead. Tighten the prompt or use `--output json` instead of `text` if available.

## MinerU Precision Parse

### Authentication
API key is in `/Users/jacky/.agents/skills/mineru/.env` as `MINERU_API_KEY`. The `run_mineru.py` script reads it automatically.

### Command

```bash
python3 /Users/jacky/.agents/skills/mineru/run_mineru.py <image_path> --timeout 300
```

### Output structure

For an image `bbq_95.68_11.02.jpg`, output is:

```
output_bbq_95.68_11.02/
├── full.md                    ← main output (use this)
├── layout.json                ← block-level layout (debugging)
├── *.content_list.json        ← structured content
├── *.content_list_v2.json     ← v2 content
├── *.model.json               ← model metadata
├── *.origin.pdf               ← original as PDF
└── images/                    ← extracted image fragments
```

The `full.md` file is what you use for amount extraction.

### Searching for known values in full.md

```python
def value_in_mineru_text(value, text, tol=0.01):
    """Check if `value` appears anywhere as a money amount in `text`."""
    if value is None or not text:
        return False
    for m in re.finditer(r"\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})", text):
        try:
            n = float(m.group(1).replace(",", ""))
            if abs(n - value) < tol:
                return True
        except ValueError:
            pass
    return False
```

### Searching is more reliable than parsing

The markdown often has multiple amounts on a single line (because of the HTML table extraction: `<td>SUBTOTAL</td><td>$9.99</td><td>13% HST</td><td>$1.30</td>...`). Regex-based parsing of the markdown is fragile. The robust approach is to know the expected value (from filename or ground truth) and search for it.

### Agent lightweight mode

The same script supports agent mode via the `agent_parse()` function. The lightweight mode returns only markdown, no ZIP. **However, in practice the agent API often returns SSL errors on the CDN download.** Use Precision Parse as the default and only fall back to agent mode if Precision Parse fails.

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
| MiniMax | $$ (vision API) | 5-10s |
| MinerU Precision Parse | $ (PDF parse API) | 20-30s |
| Tesseract | Free | 1-3s |
| LLM cross-validation | $ (Claude tokens) | 5-15s |

For a 12-receipt batch: total cost is dominated by MiniMax (~$0.50-$1) and MinerU (~$0.10-$0.30). LLM cross-validation adds ~$0.20 in tokens. Total per batch: roughly $1-2.

## Running tools in parallel

To minimize wall-clock time, run MiniMax and MinerU in parallel using a thread pool:

```python
from concurrent.futures import ThreadPoolExecutor
import os

def process_one(image_path):
    minimax = run_minimax(image_path)
    mineru = run_mineru(image_path)
    return minimax, mineru

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(process_one, image_paths))
```

MinerU is the slowest, so 4 workers typically keeps the throughput at ~1 image per 8-10 seconds.
