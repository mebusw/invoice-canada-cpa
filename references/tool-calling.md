# Tool calling reference

Exact commands, parameters, and authentication for each tool in the pipeline.

**Pipeline mode detection**（在抽取前先跑）：

```bash
test -f ~/.agents/skills/mineru/run_mineru.py && echo "minerU_AVAILABLE" || echo "minerU_MISSING"
command -v mmx >/dev/null && echo "MMX_AVAILABLE" || echo "MMX_MISSING"
echo "OPENAI_API_KEY set: ${OPENAI_API_KEY:+yes}${OPENAI_API_KEY:-no}"
```

按以下优先级决定 `pipeline_mode` 与 `vision_llm`：

1. 用户在请求里显式说 "用 GPT / Codex / gpt-5" → `vision_llm=gpt-5`（若不可用直接报错）
2. `mmx` 在 PATH 上 → `vision_llm=minimax`
3. 否则退到 `vision_llm=gpt-5`

然后 `pipeline_mode = dual-vision`（若 `minerU_AVAILABLE`）否则 `single-vision`。结果写入 `manifest.json`：

```json
{
  "pipeline_mode": "dual-vision",
  "vision_llm": "minimax",
  "second_source": "mineru"
}
```

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


### Failure modes

- **Timeout / API_ERROR**：重试一次，仍失败记显式提取失败，不要写空结果。
- **400 / context_length_exceeded**：图太大（>20 MB），预处理时压到长边 2048 px，再重新上传。
- **insufficient_quota / rate_limit**：等 30s 后重试一次，仍失败标 review_required，不写空结果。
- **BAD_JSON**：模型无视 `response_format` 返回 prose。重新 prompt 时显式加 "Return ONLY valid JSON, no prose."；仍失败则 record 失败。
- **Date shifted by years**（与 MiniMax 同）：GPT-5 也有 knowledge cutoff 幻觉。处理方式与 MiniMax 一致（见上面 Failure modes 与 SKILL.md §2.1）。

### 推荐 prompt 写法

与 MiniMax 完全共享 schema。**唯一建议差异**：在 prompt 末尾加一句

```
Return ONLY the JSON object. No prose before or after.
```

可以降低 GPT-5 输出 markdown fence 的概率（虽然 `response_format=json_object` 已能消除大部分情况）。

## MinerU Precision Parse（仅 dual-vision 模式）

> 如果 `~/.agents/skills/mineru/run_mineru.py` 不存在，整个章节跳过 —— single-vision 模式不调用 MinerU。

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

Use Tesseract only as a sanity check or when both vision LLM and MinerU are unavailable.

## Cost comparison (informal)

| Tool | Per-image cost | Per-image time |
|---|---|---|
| MiniMax (`mmx vision describe`) | $$ (vision API) | 5–15s |
| GPT-5 (`chat.completions`) | $$ (vision API) | 8–20s |
| MinerU Precision Parse | $ (PDF parse API) | 20–40s |
| Tesseract | Free | 1–3s |
| LLM cross-validation | $ (Claude tokens) | 5–15s |

For a 12-receipt batch（仅作数量级参考）：
- **dual-vision + MiniMax**：~$0.50–1 (MiniMax) + ~$0.10–0.30 (MinerU) + ~$0.20 (LLM-judge) = ~$1–2
- **dual-vision + GPT-5**：~$1.50–3 (GPT-5) + ~$0.10–0.30 (MinerU) + ~$0.20 (LLM-judge) = ~$2–3.5
- **single-vision + MiniMax**：~$0.50–1 (MiniMax) + ~$0.20 (LLM-judge) = ~$0.7–1.2
- **single-vision + GPT-5**：~$1.50–3 (GPT-5) + ~$0.20 (LLM-judge) = ~$1.7–3.2

精确价格以各供应商当期账单为准；这里仅供 batch 大小预算做量级判断。

## Running tools in parallel（按模式）

### dual-vision 模式

vision LLM 与 MinerU 用线程池并发跑；MinerU 是瓶颈（~30s/图），3–4 个 worker 把吞吐维持在 ~10–15s/图：

```python
from concurrent.futures import ThreadPoolExecutor

def process_one(image_path):
    llm_json  = run_vision_llm(image_path)   # MiniMax 或 GPT-5
    mineru_md = run_mineru(image_path)
    return llm_json, mineru_md

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(process_one, image_paths))
```

### single-vision 模式

无需并发 —— 只有一个工具。串行或单 worker 即可：

```python
def process_one(image_path):
    return run_vision_llm(image_path), None   # 第二源固定为 None

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(process_one, image_paths))
```

`pool.map` 在 single-vision 下意义不大但保留统一接口；调用方按 `pipeline_mode` 决定 worker 数即可。