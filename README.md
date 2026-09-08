# invoice-canada-cpa

[English](README.md) · [中文](README.zh-CN.md)

An Agent Skill that turns a pile of Canadian receipt and invoice photos into an auditable, line-item-level expense workpaper — with every line mapped to a CRA GIFI code for T2 filing.

## What it does

You hand it a folder of receipt images (JPG, PNG, PDF). It gives you back an Excel workpaper that a CPA can actually work from.

- **Structured extraction** — vendor, date, line items, subtotal, tax, discount, tip, payment method, currency.
- **Cross-validated numbers** — extraction is checked against arithmetic tie-outs, line-item sums, tax-allocation identities, and each province's statutory tax rate. Numbers that don't survive get flagged, not silently "fixed".
- **GIFI coding per line, not per receipt** — one T&T receipt can split into 8523 (hot food, meals & entertainment) and 8810 (groceries). That split is the whole point.
- **Three independent axes kept separate** — GIFI code (how it appears on the financial statements), tax treatment (how much is deductible: ITA 67.1 50% caps, CCA, capitalization), and deductibility (whether it's a business expense at all). Personal spending gets marked `N`, not quietly dressed up as an operating expense.
- **Everything gets recorded** — no receipt is dropped for being non-deductible. Exclusion is expressed by a flag, so the CPA sees the full set of documents the client handed over.
- **Field-level provenance** — every value carries a source tag, so any row in the workpaper traces back to the original image file. That's the part CRA cares about during an audit.

Output is a four-sheet workbook: line items, documents, raw tool outputs, and a validation report with 13 quality gates and a ranked exception list.

## What it's for

Canadian small-business tax prep, CPA workpaper preparation, and batch processing of receipt photos. It targets English, French, and Chinese receipts.

It's **not** for handwritten receipts, non-Canadian receipts (different tax rules, GIFI doesn't apply), or reading a single receipt in conversation — plain vision handles that fine.

The GIFI codes and tax treatment notes are advisory. Final Schedule 1 adjustments and the deductibility calls stay with the CPA.

## Installation

Clone into your skills directory:

```bash
git clone https://github.com/mebusw/invoice-canada-cpa.git ~/.claude/skills/invoice-canada-cpa
```

Or, if you keep skills elsewhere (e.g. `~/.agents/skills/`), clone there instead.

Then invoke it by describing the task — "process these receipts", "extract data from these invoices", "categorize these expenses by GIFI", "build me an expense workpaper" — and the skill activates on its own.

### Requirements

The skill needs at least one vision model available, and picks its mode automatically:

| Mode | Requires | Behaviour |
|---|---|---|
| **dual-vision** | a vision LLM **and** the `mineru` skill | Two independent sources, cross-reconciled field by field |
| **single-vision** | a vision LLM only | Single source, tighter review thresholds to compensate |

For the vision LLM, either the `mmx` CLI (MiniMax) or an OpenAI key (`OPENAI_API_KEY`) works. Both modes produce the same deliverables; dual-vision just catches more.

Local OCR tools are deliberately not used — the vision model already does OCR, layout, and semantic understanding in one pass, and a local parser only redoes the weakest part of that.

## License

See the repository for license details.
