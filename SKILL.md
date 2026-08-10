---
name: invoice-canada-cpa
description: Extract structured data from Canadian receipt and invoice images using multi-modal AI (MiniMax + MinerU + Tesseract OCR) with LLM cross-validation, then map each expense to a CRA GIFI code for T2 filing. Use this skill whenever the user mentions processing receipts, extracting invoice data, OCR on receipts, expense extraction, GIFI coding, T2 Schedule 125, Schedule 1 adjustments, or converting receipt images into a structured expense spreadsheet. Triggers on phrases like "process these receipts", "extract data from invoices", "OCR these photos", "categorize expenses by GIFI", "build an expense workpaper". Especially useful for Canadian small-business tax preparation, CPA workpapers, and batch processing of receipt photos or PDFs. ALWAYS use this skill when the user provides receipt images and wants structured data out — the cross-validation pipeline and the CRA-verified GIFI mapping produce far better results than handling it inline.
---

# 加拿大发票多模态提取与 GIFI 分类

从加拿大收据图片中提取结构化数据的成熟流水线：三个 AI 工具并行提取，LLM 交叉验证，再映射到 CRA GIFI code，产出可供 CPA 复核的 T2 工作底稿。

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

三个阶段顺序执行，每阶段的产出是下一阶段的输入。

```
阶段 1  多模态提取（并行）
  MiniMax JSON（语义）│ MinerU md（数值）│ Tesseract（本地兜底）
        │
阶段 2  LLM 交叉验证
  商户/日期 → MiniMax   金额 → MinerU，勾稽不平则回退
  税率合理性检查（生产环境唯一外部锚点）
  每个字段打上来源标签
        │
阶段 3  GIFI 分类 + Excel 输出
  商户 + 明细 + 金额 → GIFI code
  GIFI 映射与税务处理分两条轴，互不覆盖
  3 个 sheet（决策/原始/校验）+ 通用 9 道质量闸门
```

**为什么用三个工具而不是一个？** 三者失效模式互补：MiniMax 懂版面语义，MinerU 读表格数值精度高，Tesseract 提供本地兜底。交叉验证后在 12 张收据的测试集上达到 12/12，任何单一工具都会漏 1–3 张。

## 阶段 1：多模态提取

尽量并行跑三个工具。总耗时由最慢的决定（MinerU 云端约 30 秒/张）。

### 1.1 MiniMax（mmx vision）—— 语义理解

```bash
mmx vision describe --image <path> \
  --prompt "Extract from this Canadian receipt. Return ONLY valid JSON:
{\"vendor\":\"\",\"vendor_cn\":\"\",\"address\":\"\",\"date\":\"YYYY-MM-DD\",\"time\":\"HH:MM:SS\",\"subtotal\":0.0,\"discount\":0,\"tax\":0.0,\"tax_label\":\"HST|GST|PST\",\"total\":0.0,\"currency\":\"CAD\",\"payment_method\":\"Visa|MasterCard|Debit|Cash\",\"payment_account\":\"\",\"line_items\":[{\"name\":\"\",\"price\":0.0},\"taxable\":true}]}" \
  --quiet --output text
```

再用正则 `\{[\s\S]*\}` 抠出 JSON 块解析。

- **擅长**：商户名、日期、支付方式、商品明细、地址。
- **弱点**：旋转图片上的数值精度差，横放的收据会完全失败。

### 1.2 MinerU Precision Parse —— 数值精度

```bash
python3 /Users/jacky/.agents/skills/mineru/run_mineru.py <image> --timeout 300
```

输出 `output_<image>/full.md`，保留表格结构的 markdown。

- **擅长**：subtotal、tax、total 等需要勾稽的数值。
- **弱点**：版面检测会漏掉皱褶/小票上的小文本块（BBQ 收据上实测丢失 SubTotal/Discount/H.S.T. 三行）。仅在 Precision Parse 不可用时才退到 Agent 轻量模式 —— 该模式实测会在 CDN 下载时报 SSL 错误。

### 1.3 Tesseract OCR —— 本地兜底

```bash
bash ~/.agents/skills/ocr-image-text-extract/scripts/preprocess_ocr.sh <image> eng
```

默认不启用，只作为 sanity check 或处理简单清晰的英文收据。以下情况必然失败：中文字符（乱码）、旋转图片、皱褶/长小票、结构丢失（只剩数字没有字段标签）。

### 1.4 输入清点（生产默认路径）

**生产环境的文件名不含任何信息**，形如 `IMG_4523.jpg`、`WhatsApp Image 2026-08-10 at 14.32.11.jpeg`、`扫描件_001.pdf`。**不要从文件名解析金额，也不要因为文件名"不规范"就要求用户重命名。**

提取前先建立 manifest，为每份输入分配稳定 ID：

| 字段 | 说明 |
|---|---|
| `doc_id` | 稳定主键，如 `2026-0001`。后续所有产物都引用它 |
| `source_file` | 原始文件名，原样保留，不改名 |
| `file_hash` | 文件内容 SHA-256，用于识别**同一文件重复上传** |
| `page_no` | 多页 PDF 的页码；单图为 1 |
| `doc_type` | `receipt` / `signature_slip` / `statement` / `unknown` |

`doc_type` 必须在提取阶段就判定 —— **receipt**（有明细、有税额分行）是唯一正当的费用来源；**signature_slip**（有 AUTH 码/TIP 行/无明细）是支付凭证，须与收据配对去重；**statement**（多笔交易列表）**不是源始凭证，不可逐行提取**。判定特征与处理规则见 `references/production-inputs.md`。

> **可选的回归测试模式**：本仓库 `references/invoices/canada/` 下的测试集采用 `vendor_total_tax.jpg` 命名（如 `shoppers_84.69_9.75.jpg`），末两位数字是人工标注的 ground truth，用于回归验证。**这是测试集专有约定，不是生产输入的假设。** 仅当文件名确实匹配该模式时才启用文件名核对闸门。

## 阶段 2：LLM 交叉验证

这是整条流水线的核心。LLM（也就是你）充当裁判，按显式优先级规则合并三个来源，并做勾稽检查。

### 2.1 字段优先级规则

| 字段 | 主来源 | 回退 | 理由 |
|---|---|---|---|
| `vendor` | MiniMax | MinerU（首个标题） | 语义 > 正则 |
| `date` | MiniMax | MinerU | 视觉模型更擅长日期格式归一化 |
| `address` | MiniMax | MinerU | 街道/城市模式需要语义理解 |
| `subtotal` | MinerU | MiniMax | 表格数值精度是 MinerU 的强项 |
| `tax` | MinerU | MiniMax | 同上 |
| `discount` | MinerU | MiniMax | 同上 |
| `total` | MinerU | MiniMax | 同上 |
| `payment` | MiniMax | MinerU（关键词） | "VISA"/"MASTERCARD" 识别 |
| `line_items` | MiniMax | 无回退 | 数组结构只有 JSON 输出可靠 |

选「主来源」的准则是：**哪个工具的失效模式危害更小**。MiniMax 可能读错旋转收据的商户名，但它不会凭空编造商户；MinerU 可能漏掉小文本块，但它读到的数值是准的。

### 2.2 勾稽检查（最关键的信号）

选定数值后，必须验证收据的会计等式：

```python
# 标准情况（无折扣）
if abs(subtotal + tax - total) > 0.05:
    ...  # 不平 —— 回退到备选来源

# 有折扣（餐厅常先打折再计税）
if discount > 0:
    if abs(subtotal - discount + tax - total) > 0.05:
        ...  # 不平

# 零税率基本食品
if abs(subtotal - total) > 0.05:
    ...  # 不平
```

若 MinerU 的三个数值勾稽不平，三个一起回退到 MiniMax。若 MiniMax 也不平，说明数据存在真实矛盾 —— **标记为人工复核，不要猜**。

> **实现陷阱**：判断缺失值必须用 `value is None`，绝不能用 `value or -1`。表达式 `0.0 or -1` 返回 `-1`，会把合法的零值误判为缺失，导致零税率收据的勾稽检查全部失败。

### 2.3 来源标注

每个字段都必须记录来自哪个工具。这是审计的硬要求，没有例外：

```json
{
  "vendor": "Costco Wholesale",
  "vendor_source": "MiniMax",
  "subtotal": 859.96,
  "subtotal_source": "MinerU",
  "tax_source": "MinerU (value found in markdown)",
  "tax_label_source": "MiniMax"
}
```

常用来源标签：`MiniMax`、`MinerU`、`MinerU (value found in markdown)`、`MiniMax (MinerU missing)`、`VISUAL`、`GROUND_TRUTH (LLM seeded)`。

当 MinerU 的 markdown 里含有预期数值时，标注为 `MinerU (value found in markdown)` —— 表示 LLM 在 markdown 文本中检索到了已知值，这比解析 markdown 结构更可靠。

### 2.4 税率合理性检查（生产环境的主外部锚点）

勾稽、总额平衡都只验证**内部自洽** —— 三个工具一起读错同一个数字时全部失效。生产环境没有文件名 ground truth，**法定税率是唯一不依赖外部输入的独立锚点**：加拿大各省税率是常量，实际税率不可能超过法定税率。

先由商户地址判定省份，再取法定税率：

| 省 / 地区 | 构成 | 合计税率 |
|---|---|---|
| AB、NT、NU、YT | GST 5% | **5%** |
| SK | GST 5% + PST 6% | 5% 或 **11%** |
| BC、MB | GST 5% + PST 7% | 5% 或 **12%** |
| ON | HST 13% | **13%** |
| QC | GST 5% + QST 9.975% | 5% 或 **14.975%** |
| NS | HST 14%（2025-04-01 起；之前 15%） | **14%** |
| NB、NL、PE | HST 15% | **15%** |

> 非 HST 省份（AB/SK/BC/MB/QC）的 PST/QST **不适用于所有商品**，因此 5%（仅 GST）与合计税率都是合法值。HST 省份没有这个问题。

判定逻辑 —— **上界是硬检查，这是最可靠的信号**：

```python
rate = tax / subtotal          # subtotal 必须是不含税、不含小费的净额

if rate > statutory + 0.005:   # 超过法定税率
    ERROR   # 数值读错了：多半是 tax 读成了 total，或 subtotal 漏读
elif abs(rate - statutory) <= 0.005 or rate == 0:
    PASS    # 全额计税，或零税率（基本食品/处方药）
elif 0 < rate < statutory:
    NOTE    # 混合篮子：部分商品零税率。杂货店常见，合理
            # 但若商户是餐厅/加油站等全额计税业态 → 转 ERROR
```

**税率还能反向定位错误。** 勾稽不平时，用法定税率判断三个数字里哪个是错的，而不是整组回退：

```python
if abs(subtotal * (1 + statutory) - total) < 0.05:
    # subtotal 与 total 自洽 → 错的是 tax，按税率重算并标注来源为 DERIVED
if abs((total - tax) * (1 + statutory) - total) < 0.05:
    # tax 与 total 自洽 → 错的是 subtotal
```

**必须跳过本检查的情况**（跳过要在报告中显式记录，不能静默通过）：

- 非 CAD 收据（境外税率不同）、`subtotal` 缺失/为 0、含小费签购单（见 `references/production-inputs.md` §3）
- 商户地址缺失 → 标 `review_required`，不要默认按安大略 13% 处理

## 阶段 3：GIFI 分类

### 3.1 先分清三个层次

这三者**不是一回事**，混淆会直接导致错误的 T2 申报：

| 层 | 是谁的东西 | 回答什么问题 |
|---|---|---|
| **COA**（会计科目表） | 企业自己 | 企业**怎么记账** |
| **Expense Category**（管理分类） | 企业/软件 | 企业**怎么看账** |
| **GIFI code** | CRA | CRA **怎么看你的财务报表** |

关系是 **COA → GIFI 多对一**：企业可以有 3 个不同的 COA 科目，最终都归到同一个 GIFI code。不要设计成一对一。

完整链路（本 skill 只负责到 GIFI，Schedule 1 之后交 CPA）：

```
Transaction → COA → Expense Category → 财务报表行项 → GIFI code
           → T2 Schedule 125 → Tax Treatment → Schedule 1 调整 → 应税所得
```

### 3.2 GIFI 区块速查

GIFI 全表约 **700 个** code（随 CRA 版本变化，不要当成固定数字）。遇到生僻项时，先用区块定位范围，再去 `references/gifi-taxonomy.md` 查明细：

| 区块 | Code 范围 | 内容 | 对应报表 |
|---|---|---|---|
| Assets | 1000–2599 | 现金、应收、存货、固定资产、投资 | Balance Sheet |
| Liabilities | 2600–3499 | 应付、借款、债务、准备 | Balance Sheet |
| Equity | 3500–3999 | 股本、留存收益、储备、OCI | Balance Sheet |
| Revenue | 8000–8299 | 销售、投资收益、其他收入 | Income Statement |
| Cost of Sales | 8300–8519 | COGS / 直接成本 / 毛利 | Income Statement |
| **Operating Expenses** | **8520–9368** | **收据费用几乎都落在这里** | Income Statement |
| Farming | 9370–9898 | 农业专用收入/支出 | Income Statement |
| Tax / Net Income | 9970–9999 | 税前利润、所得税、非常项目、净利 | Income Statement |

### 3.3 ⚠️ Generic 父子陷阱（最容易犯的错）

GIFI 自身有层级。**父级 generic 项不是子项的小计** —— CRA 官方明确说明 generic item *does not represent the total of the items in the block*。

```
8520 Advertising and promotion   ← generic（父）
├── 8521 Advertising             ← specific（子）
├── 8522 Donations
├── 8523 Meals and entertainment
└── 8524 Promotion
```

由此得出两条硬规则：

1. **能定位到 specific 子项就绝不记 generic 父项。** 餐费记 8523，不是 8520。
2. **绝不把子项加总写进父项。** 8520 ≠ 8521+8522+8523+8524。

数据结构必须能表达这层关系，因此每条 GIFI 记录至少需要 `gifi_code`、`gifi_parent`、`is_generic`、`is_total` 四个字段，而不是只有 `gifi_code` + `gifi_name`。

同样是 generic 块头的还有：8710（利息与银行费用）、8760（营业税/牌照/会费）、8860（专业服务费）、8960（修理维护）、9130（耗材）、9150（电脑相关）、9220（水电）。

### 3.4 收据场景常用 GIFI code（已与 CRA Appendix A 逐条核对）

| GIFI | 官方名称 | 典型触发 | 备注 |
|---|---|---|---|
| **8521** | Advertising | Google/Meta 广告、报纸广告 | 8520 是 generic，别用 |
| **8522** | Donations | 慈善捐赠 | 不能当普通费用扣，Schedule 1 单独处理 |
| **8523** | Meals and entertainment | 餐厅、外卖、熟食柜、招待 | 税务上受 50% 限制（见 3.5） |
| **8690** | Insurance | 商业保险 | |
| **8710** | Interest and bank charges | 银行手续费、利息 | 明细可用 8715/8716 |
| **8761** | Memberships | 行业协会会费 | 需论证业务相关性 |
| **8762** | Business taxes | 市政/营业税 | |
| **8810** | Office expenses | 一般办公支出 | **办公费是 8810，不是 8575** |
| **8811** | Office stationery and supplies | 纸张、文具 | |
| **8812** | Office utilities | 办公室电/气/暖/电话 | |
| **8860** | Professional fees | 工程师、顾问等专业服务 | 有更细的就用细的 |
| **8861** | Legal fees | 律师、公证 | 需区分资本性/经营性 |
| **8862** | Accounting fees | CPA、记账 | |
| **8911** | Real estate rental | 办公室租金 | |
| **8960** | Repairs and maintenance | 设备/办公室维修 | **可能涉及资本 vs 费用** |
| **9060** | Salaries and wages | 员工工资 | |
| **9130** | Supplies | 经营耗材 | |
| **9150** | Computer-related expenses | 电脑、软件、SaaS | 9151 升级 / 9152 网络 |
| **9200** | Travel expenses | 机票、酒店、住宿 | **差旅是 9200，不是 8523** |
| **9201** | Meetings and conventions | 会议、参会研讨 | |
| **9220** | Utilities | 水电燃气 | 9224 燃料 |
| **9225** | Telephone and telecommunications | 电话、通讯 | 需按业务比例分摊 |
| **9270** | Other expenses | 实在归不进去的 | **catch-all 是 9270，尽量少用** |
| **9281** | Vehicle expenses | 汽油、轮胎、洗车、汽车维修 | **车辆费用是 9281** |

> 完整分类学、父子映射表、master data schema 见 `references/gifi-taxonomy.md`。
> 遇到本表没有的商品/服务时，先读该文件再决定 code，不要凭印象猜。

### 3.5 GIFI 映射与税务处理必须分开

这是两条独立的轴。**同一个 GIFI code 可以对应不同的税务处理**，把二者混在一列是设计错误：

```
餐费
 ├── COA: 6250
 ├── Expense Category: Meals
 ├── GIFI: 8523              ← 映射轴：报表怎么归类（不变）
 └── Tax Treatment:          ← 税务轴：能扣多少（另判）
       ├── 可扣部分 50%（ITA 67.1）
       └── 不可扣部分 50% → Schedule 1 加回
```

必须分开处理的常见场景：

| 场景 | GIFI（不变） | 税务处理（另一条轴） |
|---|---|---|
| 餐饮招待 | 8523 | 50% 上限，ITA 67.1；另 50% 在 Schedule 1 加回 |
| 会计折旧 | 8670 | **账面折旧 ≠ CCA**；Schedule 1 全额加回，改按 Schedule 8 计 CCA |
| 无形资产摊销 | 8570 | 同上，账税分离 |
| 捐赠 | 8522 | 不是普通费用；Schedule 1 加回后另按捐赠扣除处理 |
| 修理维护 | 8960 | 需判定资本性支出 vs 当期费用 |
| 律师费 | 8861 | 资本性（如收购）需资本化，不能当期扣 |
| 坏账 | 8590 | 准备金与实际核销的税务处理不同 |

**本 skill 的职责边界**：输出 GIFI code + 税务处理提示（`tax_treatment`、`deductible_pct`），**不做最终的 Schedule 1 调整** —— 那是 CPA 的判断。

### 3.6 商户 → GIFI 启发式

常见商户的映射表（Canadian Tire→9281、T&T/BBQ→8523、Costco/Walmart→8810/8811、航空酒店→9200 等）见 `references/gifi-codes.md`。

**GIFI 建议一律是 advisory**，最终由 CPA 结合完整财务图景确认。

> **轮胎不要想当然资本化**：CRA 把 tires 明确列在 9281 营运费用下。单独更换轮胎一般当期费用化；只有随车辆购置一并取得时才考虑资本化并计 CCA（Class 10）。金额大时标记 `review_required` 交 CPA，不要自行认定为资本支出。

## Excel 输出

必须产出 3 个 sheet 的工作簿，结构不可变更（审计要求）：

| Sheet | 内容 | 用途 |
|---|---|---|
| **Decisions** | N 行最终交叉验证后的数据 | 主交付物 |
| **Raw_Outputs** | MiniMax JSON 与 MinerU markdown 并排 | 审计轨迹 |
| **Validation_Report** | 4 个板块：文件名核对、勾稽、来源标注、GIFI 汇总 | CPA 复核入口 |

Decisions sheet 的列必须覆盖以下字段（来自 master data schema，完整版见 `references/gifi-taxonomy.md`）：

```
coa_code, coa_name, expense_category,
fs_line_item, gifi_code, gifi_name, gifi_parent, is_generic,
tax_treatment, deductible_pct, schedule_1_flag,
supporting_doc, confidence, review_required,
<各字段的 _source 列>
```

`gifi_parent` / `is_generic` 两列专门用来防 3.3 的父子陷阱；`confidence` 与 `review_required` 决定 CPA 优先看哪几行。

## 质量闸门

分两组。**通用闸门在任何输入上都必须跑**；可选闸门只在恰好具备 ground truth 时启用 —— 不具备时**记为 SKIPPED 并写明原因，不得算作通过**。

### 通用闸门（生产必跑，9 项）

1. **文档分类**：每份输入的 `doc_type` 已判定；`statement` 未被当作收据逐行提取
2. **去重**：无重复行 —— 按 `file_hash` 查重复上传，按（商户 + 日期 + 金额 + 卡号后四位）查签购单/收据配对
3. **勾稽平衡**：每张收据 subtotal + tax（有折扣减 discount，有小费另计）= total
4. **税率合理性**：实际税率未超过所属省法定税率；跳过的行已记录原因（见 2.4）
5. **期间归属**：日期落在申报年度内；跨期项已单独列出
6. **币种**：`currency` 非空；非 CAD 行已附汇率与折算日
7. **GIFI 已赋值**：每行都有 GIFI code 与费用分类
8. **GIFI 合法性**：code 确实存在于 CRA 清单，且**不是 generic 块头、不是 total 项**
9. **来源标注**：每个字段都有非空来源标签；`DERIVED`（反算值）已单独标记

### 可选闸门（仅当具备 ground truth）

10. **文件名核对**：文件名匹配 `vendor_total_tax` 模式时，其数字与提取值一致 —— **仅适用于回归测试集**
11. **Ground truth 比对**：与已知正确值一致

### 批次级检查

- **总额平衡**：Σsubtotal + Σtax = Σtotal（含负数退款行）
- **置信度分布**：`confidence < 0.7` 的行数已统计并在 Validation_Report 置顶列出

**用脚本跑，不要靠眼睛看。** 正确做法是写一个打开 Excel 并逐条断言的校验脚本。**闸门 4 是生产环境唯一的外部锚点** —— 其余通用闸门全是内部自洽检查，跳过它等于放弃独立校验。

## 特殊情况

### A 组：测试集实测（12 张收据）

完整走查见 `references/special-cases.md`。三条必须记住的规则：

- **餐厅折扣**：以收据**打印的** SubTotal 为准，不用倒算的计税基数；增加 `discount` 字段套折扣版勾稽
- **零税率**：`tax = 0` 是合法值不是缺失，**永远用 `is None`，绝不用 `or -1`**
- **旋转收据**：MinerU 取金额、MiniMax 失效；**不要程序化旋转重跑 OCR**，原图比二次旋转的 OCR 可靠

### B 组：生产环境必须防御

这些在测试集里**没有出现过**，但生产输入中很常见。详细判定规则见 `references/production-inputs.md`。

| 情况 | 风险 | 规则 |
|---|---|---|
| **签购单 + 收据共存** | **重复入账**（同一笔消费两份凭证） | 按（商户+日期+金额+卡号后四位）配对。保留有明细的收据为主记录，签购单挂为 `supporting_doc`，**不另起一行** |
| **手写小费** | 破坏税率闸门 + 金额不符 | 小费**不计税**。实际扣款 = 收据 total + tip。`tip` 单列，**不得并入 subtotal**，否则实际税率被稀释、错误伪装成"混合篮子" |
| **退款 / 负数** | 符号丢失导致总额虚增 | 识别 `RETURN`/`REFUND`/`CREDIT`，**保留负号，不要取绝对值**。勾稽公式对负数同样成立，GIFI code 不变 |
| **对账单被当收据** | 凭空生成大量假费用行 | `statement` 不是源始凭证，**不可逐行提取**。它只能用于核对，不能作为费用来源 |
| **一图多票** | 只提取到其中一张 | 检测到多张小票边界时拆分为多个 `doc_id`；无法可靠拆分则标 `review_required`，不要只报第一张 |
| **同一收据重复拍摄** | 重复入账 | `file_hash` 查不出（像素不同）。靠（商户+日期+金额）配对，命中即标记 |
| **多页 PDF** | 跨页发票被拆成两笔 | 先判断是「一张发票跨多页」还是「多张独立凭证」。前者合并为一个 `doc_id`，后者按页拆分 |
| **模糊 / 反光 / 遮挡** | 三工具一起编造数字 | 三者对同一字段给出**互不相同**的值时，不要投票选多数 —— 标 `confidence < 0.5` 并要求重拍 |
| **非 CAD 币种** | 汇率缺失、税率闸门误报 | `currency` 必填，非 CAD 须附汇率与折算日，并**跳过税率闸门**（境外税率不同） |
| **押金 / 环保费 / 分期** | 计税基数错误 | 押金通常不计税；环保费（如轮胎 levy）计税。分期付款按合同总额而非当期扣款入账 |

## 已知限制与应对

| 限制 | 影响 | 应对 |
|---|---|---|
| MinerU Agent API 下载报 SSL 错误 | 无法用轻量模式 | 改用 Precision Parse |
| MinerU 版面检测漏小文本块 | subtotal/tax 行丢失 | 与 MiniMax 交叉验证；都失败则回退人工读取 |
| MiniMax 在旋转图片上失效 | 商户/日期错误 | 金额取 MinerU，商户人工读取 |
| Tesseract 中文乱码 | 字符错误 | 中文收据不用 Tesseract |
| `(x or -1)` 把 0 当缺失 | 勾稽误判为不平 | 一律用 `is None` |
| 从文件名解析金额 | 生产环境文件名无信息，闸门形同虚设 | 只在回归测试集启用（见 1.4） |

## 参考文件

正文放不下的细节：

- `references/gifi-taxonomy.md` —— GIFI 完整分类学、父子映射、税务处理轴、master data schema。**只要遇到 3.4 表之外的 code、或需要判断 generic/资本性/Schedule 1 的问题，先读它。**
- `references/gifi-codes.md` —— 收据场景的 GIFI 选择规则与税务处理要点
- `references/tool-calling.md` —— 各工具的精确命令与鉴权方式
- `references/production-inputs.md` —— 生产输入的处理规则。**输入不是策划好的测试集时（客户直接给的图片/PDF 批次），或遇到签购单、小费、退款、多页 PDF、一图多票、非 CAD 币种时，先读它。**
- `references/special-cases.md` —— A 组 5 个测试集情况的详细走查
- `docs/GIFI知识.md` —— GIFI 体系的背景知识与设计推导
- `evals/evals.json` —— 验证本 skill 的测试用例

## 快速检查清单

每批收据执行：

```markdown
□ 阶段 0（生产输入）
  □ manifest 已建立，每份输入有 doc_id / file_hash
  □ doc_type 已判定（receipt / signature_slip / statement）
  □ statement 已排除，未作为费用来源
  □ 多页 PDF 已判断结构（跨页发票 vs 独立凭证）

□ 阶段 1
  □ 全部完成 MiniMax JSON 提取 (N/N)
  □ 全部生成 MinerU full.md (M/N —— 有失败则记录所用回退)
  □ Tesseract 输出已保存（可选，用于 sanity check）

□ 阶段 2
  □ 每个字段都有来源标注（DERIVED 已单独标记）
  □ 每张收据勾稽通过
  □ 税率合理性已核（超法定税率=ERROR；跳过的已记原因）
  □ 折扣收据已套用折扣公式
  □ 零税率收据已用 is None 判断
  □ 小费已剥离出 subtotal

□ 阶段 3
  □ 每张收据都有 GIFI code
  □ 无 generic 块头（8520/8710/8760/8860/8960/9130/9150/9220）被直接使用
  □ GIFI 映射与 tax_treatment 分列填写
  □ 特殊处理已应用（餐饮 50%、折旧非 CCA、车辆费用 9281 等）
  □ Excel 写出 3 个 sheet（生产批次另加 Exceptions / Duplicates / Skipped_Gates）

□ 质量闸门
  □ 通用 9 项全部通过（见「质量闸门」章）
  □ 可选闸门已启用，或记为 SKIPPED 并写明原因
  □ 批次级：总额平衡、低置信度行已置顶列出

□ 交付
  □ 保存至指定输出目录（生产环境不要写回源目录）
  □ 通知 CPA 工作底稿待复核，Exceptions 优先看
  □ 附加声明："AI prepared, CPA to confirm"
```

## 何时上交 CPA

以下情况标记为 "needs CPA review"，不要自行定稿：

- 收据语言超出流水线处理范围
- 图像质量不足，三工具对同一字段给出互不相同的值
- 一图多票无法可靠拆分
- 签购单与收据配对存疑（可能是重复入账，也可能是两笔真实消费）
- 税率闸门报 ERROR 且反向定位无法确定哪个数字错
- 只有签购单没有明细收据，GIFI 无法可靠推断
- MiniMax 与 MinerU 给出不同数值且**都能通过勾稽**
- 疑似资本性支出（大额设备、随车购置、重大维修）
- 关联方交易（同一控制人下的不同公司）
- 涉及境外增值税（非加拿大 HST/GST/PST）
- GIFI 归类需要在 generic 与 specific 之间取舍，或需要 Schedule 1 调整判断

## 输出命名约定

Excel 文件：`{client}_{period}_workpaper_v{N}.xlsx`（生产）或 `round{N}_cross_validated.xlsx`（回归测试）。

**生产环境不要把产物写回源目录** —— 客户提供的原始凭证目录应保持只读，避免污染证据链：

`<工作目录>/01_source/` 放原始凭证（只读），`03_workpaper/` 放产物。不要把产物写回源目录。`

`manifest.csv` 与 `02_extraction/` 下的中间产物一并保留，它们构成审计轨迹 —— CRA 审计时需要能从工作底稿的任一行回溯到原始凭证文件。
