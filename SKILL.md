---
name: invoice-canada-cpa
description: Extract structured data from Canadian receipt and invoice images using multi-modal AI vision models (MiniMax vision CLI + MinerU Precision Parse) with LLM-as-judge cross-validation, then map each expense to a CRA GIFI code for T2 filing. Use this skill whenever the user mentions processing receipts, extracting invoice data, OCR on receipts, expense extraction, GIFI coding, T2 Schedule 125, Schedule 1 adjustments, or converting receipt images into a structured expense spreadsheet. Triggers on phrases like "process these receipts", "extract data from invoices", "OCR these photos", "categorize expenses by GIFI", "build an expense workpaper". Especially useful for Canadian small-business tax preparation, CPA workpapers, and batch processing of receipt photos or PDFs. ALWAYS use this skill when the user provides receipt images and wants structured data out — the cross-validation pipeline and the CRA-verified GIFI mapping produce far better results than handling it inline.
---

# 加拿大发票多模态提取与 GIFI 分类

**核心理念**：让视觉模型和 LLM 做它们擅长的事（语义理解、版面识别、判断真伪），避免用正则和硬编码规则来"教"机器做事。规则应该集中在**评估**层面（勾稽、税率合理性、GIFI 映射），不在**提取**层面。

## 何时使用

**使用本 skill**，当用户提供收据/发票图片（JPG、PNG、PDF）并需要以下任一结果：

- 结构化数据提取（商户、日期、金额、税、支付方式）
- GIFI code 映射，用于加拿大 T2 申报（Schedule 125）
- 费用分类与税务处理判断
- 收据数据的 Excel 工作底稿
- 经质量校验、可审计的费用记录

**不要使用本 skill** 的情况：

- 单张收据、用户只想在对话里读一下 —— 直接用视觉能力即可
- 手写收据（属于另一个领域）
- 非加拿大收据（税务规则不同，GIFI 不适用）
- 英/法/中之外的语言（模型训练数据偏差大）

## 流水线总览

```
阶段 1  多模态提取（并行）
  ├─ MiniMax vision (mmx) — 一次性 prompt，含明细 + 金额 + 商户
  └─ MinerU Precision Parse — markdown 结构化文本
        │
阶段 2  LLM-as-judge（你，Claude）
  ├─ 合并两个来源，按可信度仲裁
  ├─ 勾稽（subtotal + tax = total；有折扣用折扣版）
  ├─ 税率合理性（vs 所属省法定税率）
  └─ 每个字段打上来源标签
        │
阶段 3  GIFI 映射 + Excel 输出
  ├─ 商户 + 明细 + 金额 → LLM 给出 GIFI code + 税务处理
  ├─ 3 sheet 工作簿（决策 / 原始 / 校验）
  └─ 标注 review_required 的行供 CPA 复核
```

**为什么只用两个工具而不是写复杂 parser？** MinerU 和 MiniMax 都是云端视觉模型。MiniMax 在语义识别（商户、日期、明细结构）上更强；MinerU 在保留表格结构（数值精度、税额分行）上更强。**让模型自己解析输出，不要再用正则二次抽取**。

## 阶段 1：多模态提取

### 1.1 MiniMax vision — 一个 prompt 拿全字段

```bash
mmx vision describe \
  --image <path> \
  --prompt "$(cat <<'EOF'
You are extracting data from a Canadian receipt photo. Read the image carefully and return ONLY a JSON object (no markdown fences, no commentary) with this exact shape — populate every field you can read, use null for missing:

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
EOF
)" \
  --quiet --output text
```

**关键设计**：
- 一个 prompt 拿全部字段 → 不需要拼接多个 pass 的结果
- `line_items` 在 prompt 里**显式要求**：模型有空间布局感知，给指令要求它"逐行列出"会提高 recall
- `discount` 和 `tip` 单独成字段：避免把折扣/小费并入 subtotal（这会污染税率计算）
- `confidence` 让模型自己评估自己输出的可靠性
- `notes` 留给模型标注异常（折扣说明、汇率、混合篮子）

**不要二次正则抽取**。MiniMax 返回的 stdout 直接是 JSON 或带 ```json``` 围栏的 JSON，找到第一个完整 JSON 块后**用 `json.loads` 验证**。**不要试图用正则拆字段**。

> ⚠️ **不要用 `re.search(r"\{[\s\S]*\}")` 判断调用是否成功。** subprocess 超时抛出的异常字符串里**包含被回显的 prompt**，而 prompt 本身就是一段 JSON schema —— 正则会匹配成功，于是一次彻底失败的调用被静默记成成功。实测中最大的一张 Costco 小票（66 行明细）就是这样蒙混过关的。判定成功必须用 `json.loads` 是否抛异常。

**超时**：默认 `timeout=300`。明细行多的小票（50+ 行）在 120s 会超时；`timeout=60` 必然失败。超时后重试一次，仍失败则显式记为提取失败，不要写入空结果。


### 1.2 MinerU Precision Parse — 表格保真

**必须直接调用 `precision_parse`，不要用 `run_mineru.py` 的命令行入口**：

```python
import sys
sys.path.insert(0, "/Users/jacky/.agents/skills/mineru")
from run_mineru import precision_parse

precision_parse(image_path, timeout=300)
```

> ⚠️ `run_mineru.py` 的 CLI (`main()`) 调用的是 `parse_with_fallback()`，其 docstring 明写「**优先使用 Agent API**，失败时降级到 Precision API」—— Agent 是主路径。这与本 skill「生产环境只用 Precision Parse」直接冲突。Agent 失败只打印一行日志，随后被成功的降级吞掉，产物看起来完全正常，**违规不可见**。不要用 CLI。

`precision_parse` 按**当前工作目录**写出 `./output_<stem>/full.md`，**不接受输出目录参数**。并行处理多图时必须给每个调用独立 cwd（`subprocess` + `cwd=`），否则互相覆盖。

输出保留表格结构。**MinerU markdown 是给 LLM-judge 看的输入，不是给 regex 用的结构化数据**。

**已知限制**：Agent 轻量模式在 CDN 下载时常报 SSL 错误。生产环境只用 Precision Parse；Precision Parse 不可用时**显式报错**，不要静默退到 Agent。

**⚠️ MinerU 会整段编造内容。** 实测一张 $5.50 超市小票，其 `full.md` 尾部被追加约 600 字关于「2017 年上海浦东发展银行最高额保证合同」的中文段落 —— 票面上没有任何这类文字。**MinerU 输出中未被图像或 MiniMax 佐证的内容一律丢弃**，不得并入 `notes` / `vendor` / 明细。


### 1.3 输入清点

提取前先建立 manifest。**生产环境的文件名不含任何信息**，形如 `IMG_4523.jpg`、`WhatsApp Image 2026-08-10 at 14.32.11.jpeg`。不要从文件名解析任何业务字段。

| 字段 | 说明 |
|---|---|
| `doc_id` | 稳定主键，如 `2026-0001`。后续所有产物都引用它 |
| `source_file` | 原始文件名，原样保留，不改名 |
| `file_hash` | 文件内容 SHA-256，用于识别**同一文件重复上传** |
| `page_no` | 多页 PDF 的页码；单图为 1 |
| `doc_type` | `receipt` / `signature_slip` / `statement` / `unknown` |

`doc_type` 由 MiniMax 在 JSON 里返回，但要 LLM-judge 复核：
- **receipt**：有明细、有税额分行 → **唯一正当的费用来源**
- **signature_slip**：有 AUTH 码 / TIP 行 / 无明细 → 支付凭证，须与收据配对去重
- **statement**：多笔交易列表 → **不是源始凭证，不可逐行提取为费用**

## 阶段 2：LLM-as-judge 交叉验证

**你就是裁判**。拿 MiniMax JSON 和 MinerU markdown 两个产物，按下面的规则合并、判断、纠错。**不要写 regex parser** —— 你已经能看到结构化 JSON 和 markdown 文本，直接阅读、判断。

### 2.1 字段合并优先级

| 字段 | 主来源 | 回退 | 理由 |
|---|---|---|---|
| `vendor` / `vendor_cn` / `address` | MiniMax | MinerU 文本检索 | 视觉模型语义理解更强 |
| **`date` / `time`** | **MinerU** | MiniMax | 见下方警告 —— 实测 MiniMax 12 张错 2 张，MinerU 两次都对 |
| `subtotal` / `tax` / `discount` / `total` | MinerU | MiniMax | MinerU 表格保真，数值可靠 |
| `line_items` | MiniMax（数组结构） | MinerU markdown 表格解析 | JSON 数组比 markdown 表格好处理 |
| `payment_method` | MiniMax | MinerU 关键词 | 模型判断"VISA" / "MASTERCARD" |

> ⚠️ **绝不因为日期"看起来在未来"就修改票面日期。** 申报年度由调用方给定，**不由模型推断**。
>
> 实测：MiniMax 对一张 T&T 小票返回 `2021-03-26`，并在自己的 `notes` 里写「2021 比 2026 这个未来日期更合理」—— 这是知识截止日导致的幻觉，模型**用先验覆盖了印在票面上的事实**，年份和日期同时错（正确值 `2026-03-21`）。该行会因此掉出申报年度、被期间闸门剔除。同批 12 张里 MiniMax 有 6 张误标 "future-dated"。
>
> 日期优先取 MinerU：收银/授权时间戳在小票上通常重复出现 2–3 次（交易行、AUTH 行、店铺 CODE），OCR 保真度高、可交叉验证。

### 2.2 勾稽 —— 硬性算式

```python
if discount is not None and discount > 0:
    tieout_ok = abs((subtotal - discount) + tax - total) <= 0.05
elif tax == 0:
    tieout_ok = abs(subtotal - total) <= 0.05
else:
    tieout_ok = abs(subtotal + tax - total) <= 0.05
```

**判断缺失值必须用 `value is None`**，绝不能用 `value or -1`。表达式 `0.0 or -1` 返回 `-1`，会把合法的零值误判为缺失，导致零税率收据的勾稽检查全部失败。

**`discount` 字段的唯一正确含义：印在 SUBTOTAL 与 TAX 之间、尚未计入 subtotal 的整单折扣。**

| 票面写法 | 是否填 `discount` |
|---|---|
| `SubTotal 94.07 / 10% DISCOUNT 9.41 / H.S.T. 11.02` | ✅ 填 9.41 —— 折扣发生在税前，改变计税基数 |
| Costco `TOTAL DISCOUNT(S) $49.50` | ❌ 填 0 —— 这是各行 TPD 即时折让的**合计**，已净额计入 subtotal |
| Walmart `WAS $4.97 YOU SAVED $2.49` | ❌ 填 0 —— item-level 回滚价，印出的行价已是折后价 |

**重复扣减会直接打破勾稽**：Costco 那张 `1170.84 − 49.50 + 144.62 ≠ 1315.46`。已净额化的折扣写进 `notes`，不写进 `discount`。实测 12 张里有 3 张踩这个坑。

若勾稽不平，**重新读 MinerU markdown**（你手里有全文），看是哪个数字错，纠正后重算。**不要写 fallback chain** —— LLM 直接判断。

### 2.2b 明细加总勾稽 —— 最强的单行纠错手段

```python
line_sum_ok = abs(sum(item.price for item in line_items) - subtotal) <= 0.02
```

**这是本流水线中最有效的确定性校验。** 实测 4 处数值冲突里有 3 处由它直接判定，无需重读图像、无需主观取舍：

| 冲突 | MiniMax | MinerU | 加总裁定 |
|---|---|---|---|
| 袋装甜橙 | 39.98 | 9.98 | MiniMax（唯有它加总 = 印出的 165.81） |
| 台湾白菜 | 3.83 | 3.03 | MiniMax（加总 = 64.78） |
| DNR ROLLS | 2.48 | 2.88 | MiniMax（加总 = 100.23） |

**它比勾稽更强**：勾稽只看 subtotal / tax / total 三个汇总数，看不见单行 OCR 滑移；明细加总能定位到**具体是哪一行错了**。

**用法**：两个工具的 `line_items` 不一致时，**哪一版能加总到票面印出的 subtotal，就采信哪一版** —— 这比 §2.1 的先验优先级表更可靠，应优先于它。加总对不上且无法定位到具体行时，标 `review_required`。


### 2.3 税率合理性 —— 生产环境唯一的外部锚点

勾稽只验证**内部自洽**，三个工具一起读错同一个数字时全部失效。**法定税率是不依赖外部输入的独立锚点**：实际税率不可能超过法定税率。

先由商户地址判定省份（地址里出现 `ON` / `Markham` / `Thornhill` / `Toronto` 等关键词 → ON），再取法定税率：

| 省 / 地区 | 合计税率 |
|---|---|
| AB / NT / NU / YT | **5%** |
| SK | **11%** |
| BC / MB | **12%** |
| ON | **13%** |
| QC | **14.975%** |
| NS | **14%**（2025-04-01 起） |
| NB / NL / PE | **15%** |

> 非 HST 省份的 PST/QST **不适用于所有商品**，因此 5%（仅 GST）与合计税率都是合法值。

判定规则 —— **上界是硬检查**：

```
rate = tax / subtotal          # subtotal 必须是不含税、不含小费的净额

if rate > statutory + 0.005:   # 超过法定税率 → ERROR（数值读错）
elif abs(rate - statutory) <= 0.005 or rate == 0:
    PASS                        # 全额计税，或零税率（基本食品/处方药）
elif 0 < rate < statutory:
    NOTE                        # 混合篮子：部分商品零税率（杂货店合理；餐厅异常 → 转 ERROR）
```

**跳过本检查**（必须显式记录原因，不能静默通过）：
- 非 CAD 收据（境外税率不同）
- `subtotal` 缺失 / 为 0
- 含小费签购单
- 商户地址缺失 → 标 `review_required`，不要默认按安大略 13%

### 2.4 来源标注

每个字段都必须记录来自哪个工具。这是审计的硬要求：

```json
{
  "vendor": "Costco Wholesale",
  "vendor_source": "MiniMax",
  "subtotal": 859.96,
  "subtotal_source": "MinerU",
  "tax_source": "MinerU",
  "line_items_source": "MiniMax",
  "notes": "discount ignored — MinerU's 'TOTAL DISCOUNTS $49.50' is sum of item-level discounts, not a single receipt discount"
}
```

常用来源标签：`MiniMax` / `MinerU` / `MiniMax (MinerU disagreement)` / `MiniMax (corrected from MinerU)` / `VISUAL` / `DERIVED (subtotal + tax = total)`。

**让 LLM-judge 自己写 `notes`**。它读得懂上下文，知道哪个数字值得说明。

## 阶段 3：GIFI 分类

### 3.1 三层概念

| 层 | Owner | 回答什么问题 |
|---|---|---|
| **COA**（会计科目表） | 企业 | 企业怎么记账 |
| **Expense Category** | 企业/软件 | 企业怎么看账 |
| **GIFI code** | CRA | CRA 怎么看你的财务报表 |

关系是 **COA → GIFI 多对一**：企业可以有 3 个不同的 COA 科目，最终都归到同一个 GIFI code。

完整链路（本 skill 只负责到 GIFI，Schedule 1 之后交 CPA）：

```
Transaction → COA → Expense Category → 财务报表行项 → GIFI code
           → T2 Schedule 125 → Tax Treatment → Schedule 1 调整 → 应税所得
```

### 3.2 GIFI 区块速查

| 区块 | Code 范围 | 对应报表 |
|---|---|---|
| Assets | 1000–2599 | Balance Sheet |
| Liabilities | 2600–3499 | Balance Sheet |
| Equity | 3500–3999 | Balance Sheet |
| Revenue | 8000–8299 | Income Statement |
| Cost of Sales | 8300–8519 | Income Statement |
| **Operating Expenses** | **8520–9368** | **收据费用几乎都落在这里** |
| Farming | 9370–9898 | Income Statement |
| Tax / Net Income | 9970–9999 | Income Statement |

### 3.3 Generic 父子陷阱

GIFI 自身有层级。**父级 generic 项不是子项的小计** —— CRA 官方明确说明 generic item *does not represent the total of the items in the block*。

```
8520 Advertising and promotion   ← generic（父）
├── 8521 Advertising             ← specific（子）
├── 8522 Donations
├── 8523 Meals and entertainment
└── 8524 Promotion
```

两条硬规则：
1. **能定位到 specific 子项就绝不记 generic 父项。** 餐费记 8523，不是 8520。
2. **绝不把子项加总写进父项。** 8520 ≠ 8521+8522+8523+8524。

generic 块头清单（生产环境见到直接降级到 specific 子项或 `review_required`）：8520、8620、8710、8760、8860、8910、8960、9060、9130、9150、9220。每条 GIFI 记录至少要有 `gifi_code`、`gifi_name`、`gifi_parent`、`is_generic` 四个字段。

### 3.4 收据场景常用 GIFI code

LLM-judge 在做 GIFI 映射时直接读这个表决定。**这是一个启发性映射，不是固定规则**。完整列表参考 CRA RC4088 Appendix A。

| GIFI | 名称 | 典型触发 |
|---|---|---|
| 8521 | Advertising | Google/Meta 广告、报纸广告 |
| 8522 | Donations | 慈善捐赠（Schedule 1 另处理） |
| **8523** | **Meals and entertainment** | 餐厅、外卖、熟食柜、招待 |
| 8690 | Insurance | 商业保险 |
| 8710 / 8715 / 8716 | Interest and bank charges | 利息、信用卡费 |
| 8761 | Memberships | 行业协会会费 |
| 8762 | Business taxes | 市政/营业税 |
| **8810** | **Office expenses** | 一般办公支出 |
| 8811 | Office stationery and supplies | 纸张、文具 |
| 8812 | Office utilities | 办公室水电电话 |
| **8860 / 8861 / 8862** | **Professional fees** | 工程师、律师、CPA |
| 8911 | Real estate rental | 办公室租金 |
| **8960** | **Repairs and maintenance** | 设备/办公室维修（可能资本性） |
| 9060 | Salaries and wages | 员工工资 |
| 9130 | Supplies | 经营耗材 |
| **9150** | **Computer-related expenses** | 电脑、软件、SaaS 订阅 |
| 9200 | Travel expenses | 机票、酒店、住宿 |
| 9201 | Meetings and conventions | 参会 |
| 9220 / 9224 / 9225 | Utilities | 水电、电话、车用燃料 |
| 9270 | Other expenses | catch-all，少用 |
| **9281** | **Vehicle expenses** | 汽油、轮胎、洗车、汽车维修 |

### 3.5 GIFI 映射与税务处理必须分开

**同一个 GIFI code 可以对应不同的税务处理**。把二者混在一列是设计错误：

```
餐费
 ├── GIFI: 8523              ← 映射轴：报表怎么归类（不变）
 └── Tax Treatment:          ← 税务轴：能扣多少（另判）
       ├── 可扣 50%（ITA 67.1）
       └── 不可扣 50% → Schedule 1 加回
```

常见场景：

| 场景 | GIFI | 税务处理 |
|---|---|---|
| 餐饮招待 | 8523 | 50% 上限（ITA 67.1）；另 50% Schedule 1 加回 |
| 会计折旧 | 8670 | 账面折旧不可扣；Schedule 1 全额加回，按 Schedule 8 计 CCA |
| 无形资产摊销 | 8570 | 同上 |
| 慈善捐赠 | 8522 | 不是经营费用；Schedule 1 加回后按捐赠扣除另处理 |
| 修理维护 | 8960 | 需判定资本性 vs 当期费用 |
| 律师费 | 8861 | 资本性（收购）需资本化 |
| 坏账 | 8590 | 准备金一般不可扣；实际核销才可扣 |

**本 skill 输出 GIFI code + 税务处理提示（`tax_treatment`、`deductible_pct`），不做最终 Schedule 1 调整**。

### 3.5b 可扣除性是独立于 GIFI 的第三根轴

**本 skill 的定位是「记录客户交来的全部凭证」，不是「只出可申报的费用」。** 因此：

> **每一张凭证、每一条明细都要进底稿，一条都不排除。** 不该扣的不靠「不记录」来表达，而是靠 `is_deductible` 明确标出来。

这一点必须做对，否则会产生真实的执业风险。实测中 12 张里有 8 张是超市杂货，**被迫**落到 8810 Office expenses —— 因为 9130 在 generic 黑名单上，排除法只剩 8810。结果是：**非经营性支出被"洗"成了一个看起来合理的营运费用**，唯一信号只剩 `review_required`。$1,315 的维生素尤其典型。

正确做法是把三根轴分开：

```
一张明细
 ├── GIFI code        ← 报表怎么归类（CRA 口径，与是否可扣无关）
 ├── tax_treatment    ← 能扣多少（ITA 67.1 的 50%、CCA、资本化…）
 └── is_deductible    ← 这笔到底算不算经营支出（业务目的是否成立）
```

`is_deductible` 三态，**不允许留空**：

| 值 | 含义 | 处理 |
|---|---|---|
| `Y` | 业务目的明确成立 | 正常入费用 |
| `REVIEW` | 票面未说明业务目的，需客户提供背景 | **默认值** —— 入底稿，等 CPA 判定 |
| `N` | 明显个人消费 / 股东福利 | `deductible_pct = 0`、`schedule_1_flag = true`、GIFI 记 9270 |

判定要点：

- **票面本身几乎从不证明业务目的**。一张超市小票不会写"这是给员工的"。因此 `REVIEW` 是默认值，不是例外 —— 判成 `Y` 需要有依据（业态本身即经营性，如轮胎、办公用品）。
- **`N` 要敢下**。保健品、处方药、个人护理、明显的家庭采购 → 股东福利（ITA 15(1)），既不可扣、又是个人的应税福利。把它记成 8810 而不标 `N`，等于替客户把个人消费包装成费用。
- **不要用"记进 9270 就算处理了"来回避判断**。9270 是 GIFI 归类，不代表不可扣；可扣与否由 `is_deductible` 表达。
- **`business_purpose` 字段记录依据来源**（票面写明 / 客户说明 / 未说明），供审计回溯。

### 3.6 GIFI 决策指南（LLM-judge 必读）

LLM-judge 在给一行做 GIFI 映射时，**按下面顺序思考**：

1. **看 line_items**：商品/服务的具体名称比商户名更决定 GIFI。商户是 Costco，但买了一组轮胎 → 9281；买杂货 → 8810。
2. **判断业态**：商户业态决定默认 GIFI。餐厅/外卖 → 8523；加油站/汽车维修 → 9281；超市杂货（无餐饮） → 8810 或 9130；医院药房 → 8810。
3. **金额信号**：$5000+ 的设备、随车购置、装修 → 可能是资本性支出 → 标 `review_required`。
4. **勾稽 + 税率信号**：effective rate 远低于 statutory → 混合篮子（如 T&T 杂货）。这条**不直接改 GIFI**，但要在 `notes` 里标注，提醒 CPA 这是个需要判断的场景。
5. **不要硬编码商户映射**。商户名经常变（"Costco Wholesale" vs "Costco Wholesale #151" vs "COSTCO TIRE SHOP"），LLM 看语义比看字符串好。
6. **GIFI 是 advisory，不是 final**。最终由 CPA 结合完整财务图景确认。

**GIFI 判在明细行，不判在单据。** 底稿是明细级的（见「Excel 输出」），一张单据的不同明细可以落到不同 GIFI —— 这是明细级底稿最主要的价值：

- T&T 一张 $36.17 的小票：热食柜 + 白饭 + 凉皮（$27.58）→ **8523** 50%；草莓（$5.00）→ **8810** 100%
- Walmart 一张小票：食品杂货 → **8810**；灯泡 → **8810**（家用/办公耗材）
- Costco 一张 $1,315 的小票：鸡肉鸡蛋羊肉 → **8810**；保健品（$1,000+）→ **9270** 且 `is_deductible = N`

不要因为"整单大部分是 X"就把整单判成 X —— 那正是明细级底稿要消除的粗糙近似。

**轮胎的特例**：CRA 把 tires 明确列在 9281 营运费用下，**单独更换轮胎一般当期费用化**，不资本化。只有随车辆购置一并取得时才计 CCA Class 10。金额大时标记 `review_required` 交 CPA，不要自行认定为资本支出。

## Excel 输出

4 个 sheet 的工作簿。**底稿主体是明细级：一条消费明细一行**，同一张单据的多条明细占据连续多行，然后才是下一张单据。

| Sheet | 粒度 | 内容 |
|---|---|---|
| **Line_Items** | **一条明细一行** | 底稿主体。单据表头字段在每行重复（便于筛选/透视），每行独立带 GIFI + 可扣除性 + 来源标签 |
| **Documents** | 一张单据一行 | 单据级表头、汇总金额、勾稽/税率/期间闸门结果 |
| **Raw_Outputs** | 一张单据一行 | MiniMax JSON + MinerU markdown 并排，审计轨迹 |
| **Validation_Report** | — | 质量闸门 + 例外清单 + 判官纠正记录 + GIFI 分布 |

**为什么表头字段要在每行重复而不是只写首行**：合并单元格和留白会破坏筛选、排序和数据透视 —— 而按 GIFI 汇总、按可扣除性汇总正是 CPA 拿到这份底稿的主要用途。视觉分组靠**按单据交替底色**实现，不靠留空。

Line_Items sheet 必备列：

```
doc_id, line_no, source_file,                          ← 定位
vendor, date, province, currency, payment_method,      ← 单据表头（逐行重复）
item_name, item_name_cn, qty, line_amount,             ← 明细本身
line_tax_flag, line_taxable, line_tax_alloc,           ← 税（见下）
expense_category, gifi_code, gifi_name, gifi_parent, is_generic,
business_purpose, is_deductible, deductible_pct,       ← 可扣除性轴（§3.5b）
tax_treatment, schedule_1_flag,
confidence, review_required, line_source, notes
```

**`line_tax_alloc`（明细级税额分摊）**：先按票面税标（Costco 的 `H`、Walmart 的 `J`/`A`、T&T 的 `F`/`P`）判定每行是否计税，再把**单据实际税额**按应税行金额比例分摊：

```python
line_tax_alloc = doc_tax * (line_amount / Σ(应税行 line_amount))
```

这样 `Σ line_tax_alloc == doc_tax` **恒等成立**，不会因建模误差破坏勾稽。分摊值的来源标签必须是 `DERIVED (pro-rata over taxable lines)`，不能冒充票面读数。

税标判定同时是一道**独立校验**：把判为应税的行加总 × 法定税率，应当逼近票面税额。实测 12 张里有 5 张借此精确验证（如 Walmart `(8.98 + 0.20) × 13% = 1.19` 分毫不差），是继明细加总之后第二强的确定性检查。


## 质量闸门

13 道闸门，所有判定都应该由 LLM-judge 给出，而不是 regex：

| # | 闸门 | 判据 |
|---|---|---|
| 1 | **文档分类** | 每份输入的 `doc_type` 已判定；`statement` 未被当作收据提取 |
| 2 | **去重** | 无重复行（按 `file_hash` 查重；按（商户+日期+金额）查配对） |
| 3 | **勾稽平衡** | 每张收据满足 (subtotal − discount) + tax = total，容差 $0.05 |
| 4 | **明细加总** | Σ line_items == subtotal，容差 $0.02（见 §2.2b —— **最强的单行纠错手段**） |
| 5 | **税额分摊** | Σ line_tax_alloc == 单据 tax（按构造恒等；不等说明应税行判定有误） |
| 6 | **税率合理性** | 实际税率未超过所属省法定税率；跳过行已记录原因 |
| 7 | **期间归属** | 日期落在申报年度内；**未因"看起来是未来"而被模型改写**（§2.1） |
| 8 | **币种** | `currency` 非空；非 CAD 已附汇率 |
| 9 | **GIFI 已赋值** | **每条明细行**都有 GIFI code 与费用分类 |
| 10 | **GIFI 合法性** | code 在 CRA 清单中，且**不是 generic 块头**（§3.3） |
| 11 | **可扣除性已判定** | 每条明细行 `is_deductible` ∈ {Y, REVIEW, N}，无空值（§3.5b） |
| 12 | **来源标注** | 每个字段都有非空来源标签；`DERIVED` 已单独标记 |
| 13 | **明细覆盖率** | line_items 非空（空时 GIFI 仅依赖商户+金额，confidence 应降低） |

**所有闸门状态在 Validation_Report 里列出**。`confidence < 0.7` 的行在 Validation_Report 置顶供 CPA 优先看。

**闸门 4 与闸门 3 的分工**：勾稽（3）只看 subtotal / tax / total 三个汇总数，两个工具同时读错某一行明细时它照样通过；明细加总（4）能定位到**具体是哪一行错**。两者都过才算数值可信。

### 评估模式（`--eval`）

当输入文件名带有 ground truth（形如 `{vendor}_{total}_{tax}.jpg`，仅测试语料）时，应额外跑一道对照并输出逐张得分：

```python
gt_total, gt_tax = float(parts[-2]), float(parts[-1])
filename_check = abs(total - gt_total) <= 0.01 and abs(tax - gt_tax) <= 0.01
```

**这是唯一能量化判官质量的手段。** §2.1 的字段优先级表应当由 eval 数据反推得出，而不是凭直觉写死 —— 「date 该信谁」这类问题正是靠 eval 才发现写反了。生产语料没有 ground truth，但**每次改动 skill 后都应在测试语料上重跑 eval**，防止回归。


## 生产环境必须防御

生产输入里这些很常见，pipeline 必须正确处理：

| 情况 | 风险 | 处理 |
|---|---|---|
| 签购单 + 收据共存 | 重复入账 | 按（商户+日期+金额+卡号后四位）配对，签购单挂为 `supporting_doc` 不另起行 |
| 手写小费 | 破坏税率闸门 | 小费单独成 `tip` 字段，不并入 subtotal；GIFI 仍 8523 |
| 退款 / 负数 | 符号丢失 | 识别 `RETURN`/`REFUND`/`CREDIT`，保留负号 |
| 对账单被当收据 | 凭空生成假费用 | `statement` 不提取为费用行；对账单只用来发现漏传收据 |
| 一图多票 | 只提取一张 | 检测到多张边界时拆为多 `doc_id`；无法拆分则标 `review_required` |
| 同一收据重复拍摄 | 重复入账 | `file_hash` 查不出，靠（商户+日期+金额）配对 |
| 多页 PDF | 跨页发票被拆 | 先判断是「一张发票跨多页」还是「多张独立凭证」 |
| 模糊 / 反光 / 遮挡 | 三工具一起编 | 三者数值互不相同时标 `confidence < 0.5` 并要求重拍 |
| 非 CAD 币种 | 税率闸门误报 | 跳过税率闸门，附 `fx_rate` 与 `fx_date` |
| 押金 / 环保费 / 分期 | 计税基数错误 | 押金不计税；环保费（如轮胎 levy）计税；分期按合同总额入账 |

## 何时上交 CPA

以下情况标记 `review_required = true`：

- 收据语言超出流水线处理范围
- 图像质量不足，三工具对同一字段给出互不相同的值
- 一图多票无法可靠拆分
- 签购单与收据配对存疑
- 税率闸门报 ERROR 且反向定位无法确定哪个数字错
- 只有签购单没有明细收据
- MiniMax 与 MinerU 给出不同数值且**都能通过勾稽**
- 疑似资本性支出（大额设备、随车购置、重大维修）
- 关联方交易（同一控制人下的不同公司）
- 涉及境外增值税
- GIFI 归类需要在 generic 与 specific 之间取舍

## 输出命名与目录

- Excel：`{client}_{period}_workpaper_v{N}.xlsx`（生产）或 `{batch}_cross_validated.xlsx`（其他）
- 工作目录布局：
  - `01_source/` 放原始凭证（只读，不要写回源目录）
  - `02_extraction/` 放中间产物（MiniMax JSON、MinerU markdown）
  - `03_workpaper/` 放最终 Excel + `decisions.json`
- `manifest.json` 与 `02_extraction/` 下的中间产物保留，构成审计轨迹 —— CRA 审计时需要能从工作底稿任一行回溯到原始凭证文件

## 已知限制

| 限制 | 应对 |
|---|---|
| MinerU Agent API CDN 下载报 SSL 错误 | 降级到 `curl -k` 方案 |
| MinerU 在旋转图片上版面混乱 | 让 LLM-judge 自己从 MiniMax + MinerU 文本里校正 |
| MiniMax 在低对比度图片上漏字段 | LLM-judge 看 MinerU markdown 补齐；无法补齐则 `confidence < 0.7` |
| 长收据（杂货 50+ 行）MiniMax 漏 line_items | 依赖 MinerU markdown 表格回填 |

## 参考文件

正文放不下的细节放 references：

- `references/gifi-taxonomy.md` — GIFI 父子映射、税务处理、master data schema
- `references/gifi-codes.md` — 收据场景 GIFI 选择规则与税务处理要点
- `references/tool-calling.md` — 工具的精确命令与鉴权方式
- `references/production-inputs.md` — 生产输入的判定规则