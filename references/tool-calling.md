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

result = subprocess.run(
    ["mmx", "vision", "describe", "--image", path, "--prompt", prompt, "--quiet", "--output", "text"],
    capture_output=True, text=True, timeout=60
)
m = re.search(r"\{[\s\S]*\}", result.stdout)
data = json.loads(m.group(0)) if m else {}
```

Do **not** write field-level regex extraction beyond this. Trust the JSON.

### Failure modes

- Empty stdout: API key issue or rate limit. Wait 5s and retry.
- JSON with `null` for all fields: model couldn't parse the image. Re-prompt with `"Look at this image carefully and extract..."`.
- No JSON block: model output prose. Tighten the prompt or use `--output json` if available.
- Output truncated at token limit on long receipts (50+ line items): rely on MinerU markdown to fill gaps.

## MinerU Precision Parse

### Authentication
API key is in `/Users/jacky/.agents/skills/mineru/.env` as `MINERU_API_KEY`. The `run_mineru.py` script reads it automatically.

### Command

```bash
python3 /Users/jacky/.agents/skills/mineru/run_mineru.py <image_path> --timeout 300
```

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

The same script supports agent mode via `agent_parse()`. **However, in practice the agent API's CDN download returns SSL errors** (cdn-mineru.openxlab.org.cn). Do not fall back to agent mode silently — if Precision Parse fails, **explicitly record the failure** and rely on MiniMax for that image.

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