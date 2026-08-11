# invoice-canada-cpa — Skill Maturity Assessment

**Basis**: trial_run_3, a full end-to-end run over 12 Canadian receipts (`references/invoices/canada/`)
on 2026-08-11. Live MiniMax vision + live MinerU Precision Parse + Claude as LLM-judge.
No cached results, no hand-fed values.

> **Status: D1–D8 fixed; workpaper rebuilt at line-item granularity.** See §6 for what changed
> after this assessment was first written, including a defect that only surfaced *because* of the fix.

---

## 1. Run result

| Metric | Result |
|---|---|
| Extraction success | MiniMax 12/12 (1 retry), MinerU Precision Parse 12/12 |
| **Ground truth (total + tax, from filenames)** | **12/12 exact** |
| Tie-out gate | 12/12 PASS |
| Tax-rate gate | 7 PASS at statutory/zero, 5 mixed-basket NOTE, **0 ERROR** |
| All 10 quality gates | PASS, 0 exceptions |
| Line items extracted | 96 across 12 receipts |
| `review_required` | 5/12 flagged for CPA |

**The cross-validation design earned its keep.** Four numeric/date fields would have been wrong
had either tool been trusted alone:

| doc | field | MiniMax | MinerU | adopted | how resolved |
|---|---|---|---|---|---|
| 0001 | tax / discount | 9.41 / 11.48 | (totals block missing) | **11.02 / 9.41** | visual re-read — MiniMax swapped the two lines |
| 0009 | date | 2021-03-26 | 03/21/26 | **2026-03-21** | MinerU + visual |
| 0005 | date | 2026-02-28 | 02/26/2026 | **2026-02-26** | MinerU + visual |
| 0007 / 0009 / 0010 | item prices | correct | 9.98 / 3.03 / 2.88 | **MiniMax** | line-item sum reconciles to printed subtotal |

Doc 0001 is the headline case: MiniMax's tie-out was off by $3.68 and the gate caught it, but the
gate alone only says "something is wrong". Recovering the true 11.02/9.41 split required a judge
that could go back to the image. That is the skill's core thesis, and it held.

---

## 2. Defects found in the skill

### D1 — Documented MinerU command contradicts the skill's own rule (HIGH)

SKILL.md §1.2 prescribes `python3 run_mineru.py <image> --timeout 300`, and two lines later:
> 生产环境只用 Precision Parse；如果 Precision Parse 不可用，**显式报错**，不要静默退到 Agent。

But `run_mineru.py`'s CLI entrypoint calls `parse_with_fallback()`, which tries the **Agent API
first** and only falls back to Precision. Following the documented command does the exact thing the
rule forbids. I had to bypass it and call `precision_parse()` directly to comply.

**Fix**: document `from run_mineru import precision_parse; precision_parse(path, timeout=300)`,
or add a `--precision-only` flag. Also document that `precision_parse` writes to `./output_<stem>/`
relative to **cwd** — it takes no output-dir argument, which forces per-call cwd isolation when
parallelising.

### D2 — Date field priority is backwards (HIGH)

§2.1 assigns `date` → MiniMax primary. In this batch MiniMax got **2 of 12 dates wrong** and MinerU
was right both times. Doc 0009 is the dangerous one: MiniMax returned `2021-03-26` and wrote in its
own notes *"2021-03-26 is more plausible than a future date in 2026"* — a knowledge-cutoff
hallucination in which the model **overrode what was printed** because it disbelieved the year.
Wrong by 5 years and 5 days; would have failed the period gate and dropped the expense from the
filing year. MiniMax flagged "future-dated" on 6 of 12 receipts.

**Fix**: make `date` MinerU-primary (register/auth timestamps OCR cleanly and repeat 2–3× per
receipt), and add an explicit instruction: *never adjust a printed date because it appears to be in
the future; the filing year is supplied by the caller, not inferred by the model.*

### D3 — The best validator in this run isn't in the skill (HIGH)

**Σ line_items == subtotal** deterministically resolved 3 of the 4 numeric conflicts, with no
image re-read and no judgement call. It is strictly stronger than the tie-out for catching
single-item OCR slips, because the tie-out only sees three aggregate numbers.

The skill's Gate 10 only checks that `line_items` is *non-empty*. This should be a real gate.
It also gives the judge a principled tie-breaker instead of falling back on the §2.1 priority table.

### D4 — No defence against MinerU hallucination (MEDIUM)

`hmart_5.5_0`'s `full.md` contains ~600 characters of fabricated Chinese text about a 2017 Shanghai
Pudong Development Bank guarantee contract, appearing nowhere on a $5.50 rice receipt. The skill
treats MinerU markdown as trustworthy judge input and lists only "rotated images → layout confusion"
under known limitations. A judge that trusts MinerU could import invented content into `notes`,
`vendor`, or line items.

**Fix**: add to §1.2 and the limitations table — *MinerU may emit whole fabricated paragraphs;
any MinerU content not corroborated by the image or MiniMax is discarded, not merged.*

### D5 — Timeout / throughput guidance is absent and the documented snippet is unsafe (MEDIUM)

The 66-line Costco receipt **blew a 120 s MiniMax timeout** and needed a retry; `tool-calling.md`'s
example uses `timeout=60`, which would have failed harder. No retry policy is specified beyond
"wait 5s and retry" for empty stdout.

Worse, the documented success check is `re.search(r"\{[\s\S]*\}", stdout)`. My run reproduced its
failure mode: the *timeout error string itself contains braces* (the prompt is echoed in the
exception), so the regex matched and the failure was silently recorded as a success. I only caught
it by eyeballing the dump.

**Fix**: `timeout=300` for receipts with many lines; validate with `json.loads`, not a brace regex;
scale the timeout with image size or line count.

### D6 — `discount` semantics are ambiguous and 3 of 12 receipts hit it (MEDIUM)

Costco prints `TOTAL DISCOUNT(S) $49.50` and Walmart prints `WAS … YOU SAVED …`, but both are
**already netted into the printed subtotal**. Feeding them into `discount` breaks the tie-out
(1170.84 − 49.50 + 144.62 ≠ 1315.46). Meanwhile the BBQ receipt's `10% DISCOUNT $9.41` sits
genuinely between subtotal and tax and **must** be used. The skill notes the Costco case in one
example's `notes` field but never states the rule.

**Fix**: state it as a rule — *use `discount` only when the receipt applies it between SUBTOTAL and
TAX. Item-level and "you saved" totals are already netted; record them in `notes`, not `discount`.*

### D7 — GIFI guidance is thin for the most common real basket (MEDIUM)

8 of 12 receipts landed on **8810 Office expenses**, which is a poor semantic fit for groceries.
The skill routes 超市杂货 → "8810 / 9130", but 9130 is on its own generic blacklist, so 8810 is
effectively forced by elimination. The honest answer for most of these baskets is *"this is not a
deductible business expense at all"* — a personal/shareholder benefit — and **the skill has no way
to express that.** Every row must receive a GIFI code (Gate 7), so non-business spend gets laundered
into a plausible-looking operating expense with `review_required=true` as the only signal.

**Fix**: add a `business_purpose` / `is_deductible` axis distinct from the GIFI axis, and a
documented route for shareholder-benefit and personal items (typically 9270 with
`deductible_pct=0`, or exclusion from the workpaper with a reason).

### D8 — Gate list is malformed (LOW)

The §质量闸门 list numbers two gates **10** and has no gate **9**; gate 8's text reads
"非非 total项" (double negative typo). This checklist is a CPA-facing deliverable.

### D9 — Most production defences are untested (LOW, but it caps the maturity rating)

The corpus is 12 receipts, **all Ontario, all CAD, all clean single-receipt images, all `doc_type=receipt`**.
Of the 10 rows in §生产环境必须防御, **6 have zero coverage here**: signature slips, statements,
multi-receipt images, refunds/negatives, non-CAD + FX, multi-page PDFs. Likewise `supporting_doc`
is null in all 12 rows and the pairing/dedup logic never fired. 12/12 on this corpus should not be
read as production accuracy.

---

## 3. Process maturity

**There is no end-to-end harness.** Stage 2 is "Claude reads everything and decides", which produced
excellent results but is not reproducible or automatable — trial_run_2 literally stops with
*"Next: for each prompt, run Claude to get a JSON decision"* and its Excel was never populated from
live judge output. In trial_run_3 I hand-authored the 12 decisions into a Python literal. That is
honest to the skill's design, but it means:

- No regression suite. Nothing detects that MiniMax's date behaviour changed between runs.
- Judge quality is unmeasured — the ground truth in the filenames is never used by the skill itself.
  I had to add the check.
- Cost/latency unmeasured.

The filename-encoded ground truth is sitting right there and the skill doesn't exploit it. A
`--eval` mode scoring extracted total/tax against it would turn this into a measurable system.

---

## 4. Verdict

### Maturity: **Level 3 / 5 — "Validated prototype"**

| | |
|---|---|
| L1 Sketch | — |
| L2 Works on an example | — |
| **L3 Validated prototype** | **← here.** Correct on a real batch; validation design is genuinely sound; documentation has contradictions; edge cases untested; no automated harness. |
| L4 Production-hardened | needs D1–D6 fixed, edge cases covered, end-to-end harness with eval mode |
| L5 Audit-grade | needs regression suite, versioned GIFI master data, CPA sign-off loop |

**Strongest aspect** — the validation architecture. Separating *extraction* (models) from
*evaluation* (rules) is the right call, and the two-anchor design works: the tie-out catches
internal inconsistency, the statutory-rate ceiling catches the case where both tools misread the
same number. The GIFI generic-parent trap is correctly and specifically documented — that is real
domain knowledge, not filler, and the run used it (0 generic codes emitted).

**Weakest aspect** — the gap between the prose and what the tools actually do. D1 is the clearest
symptom: the skill states a safety rule and then documents the command that breaks it. D2 and D5 are
the same shape — field-priority and timeout guidance written from intuition rather than measurement.
These are exactly the defects an eval harness would have caught, which is why D9/§3 is the
highest-leverage thing to fix: not more prose, but a scored regression run.

**Recommended next three actions**
1. Fix D1 (one-line doc change, but it's a live correctness bug).
2. Add Σ line_items == subtotal as a hard gate (D3) — biggest accuracy gain per unit of effort.
3. Add `--eval` scoring against the filename ground truth, then re-derive the §2.1 priority table
   from measurements instead of intuition (fixes D2 and prevents its recurrence).

---

## 6. Post-assessment: fixes applied (2026-08-11)

### Skill changes

| Defect | Change |
|---|---|
| D1 | SKILL.md §1.2 + tool-calling.md now mandate `precision_parse()` directly and document *why* the CLI is forbidden (`parse_with_fallback` makes Agent the primary path). Also documents the cwd-relative output dir and the `got multiple values for 'timeout'` trap. |
| D2 | §2.1 priority table: `date`/`time` moved to **MinerU-primary**, with an explicit prohibition on "correcting" a printed date that looks future-dated. |
| D3 | New **Gate 4 — 明细加总** (`Σ line_items == subtotal`), documented in new §2.2b as the strongest deterministic check, explicitly ranked *above* the §2.1 priority table as a tie-breaker. |
| D4 | MinerU hallucination warning added to §1.2 and the limitations table, with the H Mart example. |
| D5 | `json.loads` (not a brace regex) is now the documented success test, with the timeout-echo failure mode spelled out; `timeout=300` default. |
| D6 | `discount` semantics promoted from a buried example note to a rule + decision table. |
| D7 | New **§3.5b**: `is_deductible` as a third axis orthogonal to GIFI and tax treatment. Positioning fixed as **"record every voucher"** — nothing is excluded; non-business spend is recorded and flagged `N`. |
| D8 | Gate list renumbered and rewritten as a table: 10 → **13 gates** (+ line-item sum, tax allocation, deductibility decided), plus a documented `--eval` mode. |

### Workpaper restructured to line-item granularity

Main body is now **one row per line item** (145 rows across 12 receipts), with document
headers repeated on every row and alternating per-document banding. 4 sheets:
`Line_Items` / `Documents` / `Raw_Outputs` / `Validation_Report`.

This immediately resolved two of the `review_required` flags from the first pass, because
GIFI is now decided **per line** rather than per document:

- T&T $36.17 — hot food + rice + cold noodle ($27.58) → **8523** @ 50%; strawberries ($5.00) → **8810** @ 100%
- Costco $1,315 — chicken/eggs/lamb → **8810**; $1,000+ of supplements → **9270**, `is_deductible = N`

Deductibility split across 145 lines: **Y** 3 lines / $869.95 · **REVIEW** 98 lines / $806.66 ·
**N** 44 lines / $1,016.54. That last number is the point of D7: **$1,016 of the $2,693 batch is
personal spend that the old document-level design was quietly booking as "Office expenses."**

### The new gate caught a defect on its first run

Gate 4 failed on the Costco receipt: `Σ lines 1169.84 vs subtotal 1170.84`, off by exactly $1.00.
Visual re-read located it at a single line — `1840053 SALTED DUCK`:

| | value |
|---|---|
| MiniMax | 6.99 |
| MinerU | 14.99 |
| **Printed on receipt** | **7.99** |

**Both tools were wrong on the same line**, in different directions — precisely the failure mode
the tie-out cannot see (it only inspects three aggregate numbers, and the error was inside the
line detail). The sum reconciliation not only detected it but *localized* it to one row out of 66.
Corrected to 7.99, after which `Σ lines == 1170.84` and the independent taxable-base cross-check
lands on `1112.49 × 13% = 144.62` — exactly the printed tax.

This is the strongest available evidence for D3: the gate paid for itself on the run that
introduced it, on a receipt that had already passed every gate in the previous design.

### Also found: a bug in the new gate itself

The taxable-base cross-check initially failed the BBQ receipt (`94.07 × 13% = 12.23` vs printed
`11.02`). That was a defect in the *check*, not the data — the taxable base must be net of the
receipt-level 10% discount. Fixed to pro-rate the discount over taxable lines:
`84.66 × 13% = 11.01` ✓. Worth recording because it is the same class of error as D6: forgetting
that a receipt-level discount changes the tax base.

### Result after fixes

**14/14 gates PASS · 0 exceptions · ground truth still 12/12 exact.**

### Maturity: still **Level 3 / 5**, but for a different reason

The documentation-vs-reality gap that defined the L3 ceiling is now largely closed (D1–D8).
What still caps it at L3 is **§5 coverage and §3 process**, both unchanged:

- 6 of 10 documented production defences remain untested (signature slips, statements,
  multi-receipt images, refunds, FX, multi-page PDFs)
- Stage 2 is still Claude-in-the-loop with no harness; the 145 line classifications were
  hand-authored, so there is still no regression suite
- `--eval` is now *specified* in SKILL.md but not *implemented*

**Next three actions are unchanged in substance**: implement `--eval`, then build an edge-case
corpus, then re-derive the §2.1 priority table from measurement. The difference is that the
skill's prose is now trustworthy enough that an implementer following it will not be actively
misled — which is the actual precondition for L4.
