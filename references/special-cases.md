# Special cases reference

Detailed walkthroughs of the five special cases observed in the 12-receipt test set. Each section explains what the receipt actually shows, what goes wrong if you don't handle it, and the correct handling.

## Case 1: Restaurant with pre-tax discount (BBQ receipt)

### The receipt

```
Lamb Skewers 6pcs                $7.95
Signature Clay Pot Beef Tripe   $22.95  DISCOUNT -$11.48
Lean Beef 8pcs                   $7.95
Korea style Pork Belly 4pcs      $6.95
Chicken Joints 4pcs              $7.95
Grilled Cabbage                  $5.95
Grilled Oyster Mushroom 2pcs    $6.95
Baby Cabbage with Garlic Sauce  $8.95
Traditional Corn and Pork Bone  $29.95
                                ──────
SubTotal                        $94.07
10% DISCOUNT                    -$9.41
H.S.T.                          $11.02
TOTAL                           $95.68
YOU SAVED                       $20.89
```

### What goes wrong without handling

If you treat this as a standard receipt: `subtotal + tax = 94.07 + 11.02 = 105.09 ≠ 95.68`. The tie-out check fails. If you fall back to a different source, you might pick $84.66 (the post-discount tax base, which is the right number mathematically but doesn't appear on the receipt).

### Correct handling

```python
# Ground truth: use the printed SubTotal
gt = {
    "subtotal": 94.07,    # the printed SubTotal line, not the tax base
    "discount": 9.41,     # the printed 10% DISCOUNT line
    "tax": 11.02,         # the printed H.S.T. line
    "total": 95.68,       # the printed TOTAL line
}

# Tie-out: handle discount
def check_tieout(s, t, tot, discount=0):
    if discount:
        return abs(s - discount + t - tot) < 0.05
    return abs(s + t - tot) < 0.05

# (94.07 - 9.41) + 11.02 = 95.68 ✓
```

### Why this matters

If you use the calculated tax base ($84.66) as the "subtotal", you will:
- Fail the filename check (filename says $11.02, which is on $84.66, but the receipt doesn't show $84.66)
- Mislead the CPA, who will wonder why the SubTotal in the workpaper doesn't match the receipt
- Create audit risk if CRA asks for the source document — the receipt says $94.07, your workpaper says $84.66

The principle: **always use what's printed on the receipt, even if a calculated value is mathematically cleaner.**

## Case 2: Zero-tax basic groceries

### The receipt

```
T&T Supermarket — Woodbine Store
9255 Woodbine Avenue, Markham, ON L6C 1Y9

Pork Neckbone         1.394 kg @ $4.39/kg        $6.12
RWA Ground Pork Lean  0.426 kg @ $8.80/kg        $3.77
RWA Ground Pork Lean  0.466 kg @ $8.80/kg        $4.12
Fresh Atlantic Salmon 0.752 kg @ $15.39/kg      $11.57
Green Onion           2 @ $0.98 ea              $1.96
Chinese Fuji Apple    1.115 kg @ $3.95/kg       $4.40
Chinese Fuji Apple    1.675 kg @ $3.95/kg       $6.62
Sunkist Oranges       1.325 kg @ $2.18/kg       $2.89
Taiwan Bok Choy       1.260 kg @ $3.04/kg       $3.83
Yu Choy Sprouts       0.555 kg @ $5.03/kg       $2.79
Longan (Case)         2 @ $2.69 ea              $5.36
An Ching Black Sesame Riceball 2 @ $2.99 ea     $5.98
                                              ──────
SubTotal                                    $64.78
HST                                          $0.00   (zero-rated basic groceries)
TOTAL                                       $64.78
```

### What goes wrong without handling

The Python expression `value or -1` returns `-1` when `value` is `0.0`. This means:

```python
# WRONG
if abs(subtotal + (tax or -1) - total) > 0.05:
    # ALWAYS fails for zero-tax receipts, even though the math is correct
```

The tie-out check falsely fails for valid zero-tax receipts.

### Correct handling

```python
# RIGHT
if tax is None:
    # tax not extracted — flag as missing
    pass
elif abs(subtotal + tax - total) > 0.05:
    # genuine tie-out failure
    pass
```

### Why this matters

T&T basic groceries, Walmart fresh produce, and most zero-rated staples have `tax = 0` by design. If your pipeline treats 0 as "missing" or "invalid", you'll generate false alarms on every grocery receipt.

The principle: **0 is a valid value, distinct from None.** Always use `is None` for "missing" checks, never `or -1`.

## Case 3: Rotated/sideways receipt (Costco tires)

### The receipt

The Costco tire purchase receipt is photographed at 90° rotation. The text reads sideways in the image. The relevant values:

```
TIRES
4 X 209.99 R16                 $839.96 H
4 X 5.00 (mounting/levy)        $20.00
SUBTOTAL                        $859.96
TIRE LEVY                       $20.00
HST                            $111.79
TOTAL                          $971.75
```

### What goes wrong without handling

- **MiniMax**: completely fails. Returns vendor as "How did we do today?" (the customer survey header), date as "2026-03-28" (a misread), and an HST of "13.0" (a misread of the HST rate).
- **MinerU**: partial success. The markdown contains the SUBTOTAL, HST, and TOTAL values, but the lines are jumbled because the layout analysis treats the sideways text as columns.
- **Tesseract**: completely fails on the rotated text.

### Correct handling

1. **Don't programmatically rotate the image** — the loss in OCR quality exceeds any gain. Use the source as-is.
2. **Attribute amounts to MinerU** if the markdown contains them (which it does for the values above).
3. **Attribute vendor and date to ground truth** (verified visually from the image) or to MinerU if it can read them.
4. **Validate the rotated receipt manually** if neither tool can extract cleanly. Document with `vendor_source: "VISUAL"` or similar.

```python
decision = {
    "vendor": "Costco Wholesale",  # manually verified
    "vendor_source": "VISUAL",      # both MiniMax and MinerU failed here
    "date": "2026-03-23",          # manually verified
    "date_source": "VISUAL",
    "subtotal": 859.96,            # from MinerU markdown
    "subtotal_source": "MinerU",
    "tax": 111.79,                 # from MinerU markdown
    "tax_source": "MinerU",
    "total": 971.75,               # from MinerU markdown
    "total_source": "MinerU",
}
```

### Why this matters

A sideways photo is a common real-world issue (someone takes a quick photo without rotating the phone first). The pipeline must not silently produce wrong values; it must clearly attribute the source so the CPA knows which values are confident and which need verification.

## Case 4: Mixed Chinese-English (T&T, BBQ, H Mart)

### The receipt

T&T receipts often have both English and Chinese on the same line:
```
百香瓦罐涮牛肚 Signature Clay Pot Beef Tripe    $22.95
烤高丽菜 Grilled Cabbage                          $5.95
```

H Mart receipts may have Korean brand names:
```
5323 Yonge St. North York ON. M2N5R4
5323 Yonge St, 노스요크
```

### What goes wrong without handling

- **Tesseract**: garbled output on Chinese characters (even with `chi_sim` language pack). Words like "百香" come out as random characters. The pipeline can't even verify Chinese vendor names.
- **MiniMax**: handles mixed text well because it's a vision-language model that understands context, not just OCR.
- **MinerU**: preserves the Chinese characters in markdown tables. Good for audit trail.

### Correct handling

1. **Prefer MiniMax for vendor name** when Chinese is involved. The vision model recognizes "大统华" as "T&T Supermarket".
2. **Preserve the original Chinese** in the output as a `vendor_cn` field, not just transliteration.
3. **Skip Tesseract for Chinese receipts** — don't waste time on a tool that will produce garbage.

```python
{
    "vendor": "T&T Supermarket",      # transliteration by MiniMax
    "vendor_cn": "大统华",              # original Chinese preserved
    "vendor_source": "MiniMax",
    "language_detected": "en+zh"
}
```

### Why this matters

The original Chinese characters are useful for:
- Audit trail (CPA can match the workpaper to the source document)
- Future ML training data
- Multilingual search

Discarding the Chinese loses information that's free to keep.

## Case 5: Filename mismatch (costco_315.46 → costco_1315.46)

### The situation

The original filename was `costco_315.46_144.62.jpg` but the receipt total is actually `$1,315.46` (the filename is missing the leading "1"). The tax `$144.62` is correct.

### What goes wrong without handling

- **Filename check fails**: `315.46 ≠ 1315.46`. Pipeline flags mismatch.
- **If you trust the filename**: you'd assign total=$315.46 in the workpaper. CRA audit would catch this immediately.
- **If you trust the receipt (correct choice)**: filename check stays failed, but values are correct.

### Correct handling

1. **Detect the mismatch** in the filename check.
2. **Use the receipt value as ground truth** (it's the source of truth).
3. **Decide: rename the file or document the discrepancy.**
   - If the user has time, rename to `costco_1315.46_144.62.jpg`. Clean.
   - If renaming is too disruptive, keep the old name and add a note in the validation report: "Filename 315.46 does not match receipt 1315.46. Used receipt value as ground truth."

```python
# In the validation report
mismatches.append({
    "filename": "costco_315.46_144.62.jpg",
    "filename_total": 315.46,
    "actual_total": 1315.46,
    "resolution": "Used receipt value 1315.46 as ground truth. Filename missing leading '1'. Recommend renaming file."
})
```

### Why this matters

The filename convention `vendor_total_tax.jpg` is a self-validation mechanism. It catches typos and data errors before they propagate. But when it fires, the response should be: investigate, fix the underlying issue, document. Not: silently use the wrong number.

## Summary table

| Case | Symptom | Root cause | Fix |
|---|---|---|---|
| 1: Restaurant discount | Tie-out fails | Discount applied pre-tax, not reflected in subtotal | Use printed SubTotal, add discount field, check `(sub - discount) + tax = total` |
| 2: Zero tax | Tie-out falsely fails | `0 or -1 == -1` Python gotcha | Use `is None` checks everywhere |
| 3: Rotated image | Wrong values | OCR/vision fails on rotated text | Don't rotate; use MinerU for amounts; mark other fields as `VISUAL` |
| 4: Mixed CN/EN | Vendor wrong in English-only tools | Tesseract garbles Chinese | Use MiniMax for vendor; preserve Chinese in `vendor_cn` |
| 5: Filename mismatch | Pipeline flags mismatch | Filename typo or data error | Use receipt value; rename or document |

All five are real cases from the 12-receipt test set. If your pipeline handles all five correctly, you can claim 12/12 success on the test set.
