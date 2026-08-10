# GIFI 完整分类学与数据模型

本文件是 `SKILL.md` 第 3 章的深度支撑。**触发条件**：遇到 SKILL.md 3.4 表之外的 code、需要判断 generic/specific、需要判断资本性 vs 费用、或需要给出 Schedule 1 处理提示时，读本文件。

所有 code 与名称均核对自 CRA《RC4088 — General Index of Financial Information》Appendix A（Complete listing of the GIFI）。

---

## 1. 三层概念的边界

| 层 | Owner | 回答的问题 | 举例 |
|---|---|---|---|
| Transaction | 企业 | 发生了什么 | CPA invoice $1,000 |
| COA | 企业 | 怎么记账 | `6320 Accounting Fees` |
| Expense Category | 企业/软件 | 怎么看账（管理口径） | `Professional Fees` |
| Financial Statement Line | 会计准则 | 报表怎么呈现 | `Professional fees $1,000` |
| **GIFI code** | **CRA** | **CRA 怎么读你的报表** | **8862 Accounting fees** |
| T2 Schedule 125 | CRA | 申报表怎么填 | `8862 → $1,000` |
| Tax Treatment | 税法 | 能不能扣、扣多少 | 按业务用途全额可扣 |
| Schedule 1 | CRA | 账面利润怎么调成应税所得 | 调整额 0 |

**COA → GIFI 是多对一。** 企业可以有 `6320 Accounting Fees`、`6325 Bookkeeping`、`6330 Year-end Review` 三个科目，全部映射到 GIFI 8862。设计成一对一是错误的。

## 2. GIFI 区块结构

GIFI 全表约 **700 个** financial statement item（Statistics Canada 历史口径约 685–700）。数量随 CRA 版本变化，**不要把 700 当作永久固定的官方数字**。对外表述用 "approximately 700 standardized financial statement codes"。

| 区块 | Code 范围 | 内容 | 报表 |
|---|---|---|---|
| Assets | 1000–2599 | 现金、应收、存货、资本性资产、投资 | Balance Sheet |
| Liabilities | 2600–3499 | 应付、借款、债务、准备 | Balance Sheet |
| Equity | 3500–3999 | 股本、留存收益、储备、OCI | Balance Sheet |
| Revenue | 8000–8299 | 销售、投资收益、其他收入（8299 = Total revenue） | Income Statement |
| Cost of Sales | 8300–8519 | COGS、直接成本、毛利 | Income Statement |
| Operating Expenses | 8520–9368 | 广告、薪酬、租金、差旅、专业服务等 | Income Statement |
| Farming | 9370–9898 | 农业专用收入/支出 | Income Statement |
| Tax / Extraordinary / Net Income | 9970–9999 | 税前利润、所得税、非常项目、净利 | Income Statement |

小计项：`9367 Total operating expenses`、`9368 Total expenses`、`9369 Net non-farming income`、`8299 Total revenue`。**这些是 total 项，绝不能用来给单张收据归类。**

## 3. Generic 块头清单（禁止直接使用）

CRA 明确：generic item **does not represent the total of the items in the block**。generic 项既不是小计，也不该在有 specific 子项时被占用。

下表列出营运费用区里所有需要警惕的块头及其常用子项：

| Generic 块头 | 名称 | 常用 specific 子项 |
|---|---|---|
| **8520** | Advertising and promotion | 8521 Advertising / 8522 Donations / 8523 Meals and entertainment / 8524 Promotion |
| **8620** | Employee benefits | 8621 Group insurance benefits / 8622 Employer's portion of employee benefits / 8623 Contributions to deferred income plans |
| **8710** | Interest and bank charges | 8711 Interest on short-term debt / 8713 Interest on mortgages / 8714 Interest on long-term debt / 8715 Bank charges / 8716 Credit card charges / 8717 Collection and credit costs |
| **8760** | Business taxes, licences, and memberships | 8761 Memberships / 8762 Business taxes / 8763 Franchise fees / 8764 Government fees |
| **8860** | Professional fees | 8861 Legal fees / 8862 Accounting fees / 8863 Consulting fees / 8864 Architect fees / 8865 Appraisal fees / 8869 Brokerage fees |
| **8910** | Rental | 8911 Real estate rental / 8913 Condominium fees / 8914 Equipment rental / 8915 Motor vehicle rentals / 8916 Moorage |
| **8960** | Repairs and maintenance | 8961 Buildings / 8962 Vehicles / 8963 Boats / 8964 Machinery / 9010 Other / 9013 Security / 9014 Garbage removal |
| **9060** | Salaries and wages | 9061 Commissions / 9063 Bonuses / 9064 Directors fees / 9065 Management salaries / 9066 Employee salaries |
| **9130** | Supplies | 9131 Small tools / 9132 Shop expense / 9133 Uniforms / 9134 Laundry / 9135 Food and catering |
| **9150** | Computer-related expenses | 9151 Upgrade / 9152 Internet |
| **9220** | Utilities | 9223 Heat / 9224 Fuel costs / 9225 Telephone and telecommunications |

**规则**：能定位到 specific 就用 specific；确实只能到块头层级时（如笼统的「办公室维修」），可用块头，但必须置 `is_generic = true` 并标 `review_required`。

## 4. 营运费用完整对照表（8520–9368 常用段）

| GIFI | 官方名称 | CRA 列举的典型内容 |
|---|---|---|
| 8521 | Advertising | catalogues, media expenses, publications |
| 8522 | Donations | charitable / Crown / political donations |
| 8523 | Meals and entertainment | tickets（剧院、演唱会、体育赛事）、商务餐 |
| 8524 | Promotion | booths, demonstrations, displays, prospectus, samples, seminars given |
| 8570 | Amortization of intangible assets | deferred charges, patents, franchises, copyrights, trademarks, R&D |
| 8571 | Goodwill impairment loss | 2002 及以后年度 |
| 8590 | Bad debt expense | 坏账准备、坏账核销 |
| 8620 | Employee benefits | association dues, clothing allowance, lodging, room and board |
| 8621 | Group insurance benefits | 医疗、牙科、寿险计划 |
| 8622 | Employer's portion of employee benefits | CPP、EI、QPIP、WCB、公司养老金 |
| 8623 | Contributions to deferred income plans | RPP、DPSP、EPSP |
| 8670 | Amortization of tangible assets | 有形资产折旧（**账面口径**） |
| 8690 | Insurance | bonding, fire, liability insurance, premiums |
| 8710 | Interest and bank charges | — |
| 8715 | Bank charges | — |
| 8716 | Credit card charges | — |
| 8761 | Memberships | 行业协会会费 |
| 8762 | Business taxes | 市政/营业税 |
| 8764 | Government fees | 政府规费 |
| 8810 | Office expenses | 一般办公支出 |
| 8811 | Office stationery and supplies | 纸张、文具 |
| 8812 | Office utilities | 办公室 electricity, gas, heating, hydro, telephone |
| 8813 | Data processing | word processing |
| 8860 | Professional fees | engineering fees, professional services, surveyor fees |
| 8861 | Legal fees | lawyer and notary fees |
| 8862 | Accounting fees | bookkeeping |
| 8863 | Consulting fees | — |
| 8871 | Management and administration fees | — |
| 8876 | Training expense | — |
| 8911 | Real estate rental | apartment, building, land, office rentals |
| 8913 | Condominium fees | — |
| 8914 | Equipment rental | 电脑设备、影印机、办公机器、施工设备租赁 |
| 8915 | Motor vehicle rentals | 车辆租赁（**与 9281 自有车辆费用区分**） |
| 8960 | Repairs and maintenance | — |
| 8962 | Repairs and maintenance – Vehicles | 车辆维修 |
| 9010 | Other repairs and maintenance | — |
| 9013 | Security | — |
| 9014 | Garbage removal | — |
| 9060 | Salaries and wages | — |
| 9066 | Employee salaries | office salaries |
| 9110 | Sub-contracts | contract labour, contract work, custom work, hired labour |
| 9130 | Supplies | medical supplies, wrapping and packing supplies |
| 9131 | Small tools | — |
| 9133 | Uniforms | — |
| 9135 | Food and catering | 员工餐饮采购（**与 8523 招待餐区分**） |
| 9150 | Computer-related expenses | — |
| 9151 | Upgrade | 软件升级 |
| 9152 | Internet | — |
| 9180 | Property taxes | municipal and realty taxes |
| 9200 | Travel expenses | airfare, hotel rooms, travel allowance, accommodations |
| 9201 | Meetings and conventions | seminars attended（**参加**，区别于 8524 的**举办**） |
| 9220 | Utilities | hydro |
| 9223 | Heat | — |
| 9224 | Fuel costs | coal, diesel, fuel, natural gas, oil, propane（**非车用**） |
| 9225 | Telephone and telecommunications | — |
| 9270 | Other expenses | catch-all，**尽量避免过度使用** |
| 9271 | Cash over/short | — |
| 9273 | Selling expenses | courier, customs, delivery and installation, distribution |
| 9276 | Warranty expenses | — |
| 9281 | Vehicle expenses | automobile expenses, gas, motor vehicle fuel, **tires**, vehicle washing |
| 9282 | Research and development | — |
| 9284 | General and administrative expenses | marketing and administration, office and general, selling and administrative |
| 9367 | Total operating expenses | **total 项，禁止用于归类** |
| 9368 | Total expenses | **total 项，禁止用于归类** |

### 几个最常被搞混的配对

| 容易混 | 正确区分 |
|---|---|
| 8523 vs 9200 | 8523 = 餐饮招待；9200 = 差旅（机票/酒店）。差旅中的餐费仍归 8523 |
| 8523 vs 9135 | 8523 = 招待/商务餐（受 50% 限制）；9135 = Food and catering 经营性餐饮采购 |
| 8524 vs 9201 | 8524 = 自己举办的研讨会/展位；9201 = 参加他人的会议/研讨会 |
| 9224 vs 9281 | 9224 = 取暖/发电用燃料；9281 = 车用汽油 |
| 8915 vs 9281 | 8915 = 租车；9281 = 自有车辆的运行费用 |
| 8812 vs 9220 | 8812 = 办公室专属水电；9220 = 一般水电 |
| 8570 vs 8670 | 8570 = 无形资产摊销；8670 = 有形资产折旧 |
| 8590 vs 8710 | 8590 = 坏账；8710 = 利息与银行费用 |
| 8810 vs 9284 | 8810 = 办公费；9284 = 一般管理费用（更宽口径） |

### 常见误用警告

以下 code **不存在**或含义与直觉相反，历史上本 skill 曾误用：

| 错误写法 | 实际含义 | 应改为 |
|---|---|---|
| 8520 = Motor vehicle expenses | 8520 = Advertising and promotion（generic） | 9281 |
| 8521 = Meals & entertainment | 8521 = Advertising | 8523 |
| 8523 = Travel | 8523 = Meals and entertainment | 9200 |
| 8575 = Office expenses | 营运费用清单中无 8575 | 8810 |
| 8810 = catch-all | 8810 = Office expenses（有明确含义） | 9270 |
| 8530 = Rent | — | 8911 |
| 8540 = Salaries and wages | — | 9060 |
| 8545 = Subcontracts | — | 9110 |
| 8550 = Telephone and utilities | — | 9220 / 9225 |
| 8560 = Professional fees | — | 8860 / 8861 / 8862 |
| 8565 = Insurance | — | 8690 |
| 8570 = Advertising | 8570 = 无形资产摊销 | 8521 |
| 8590 = Interest and bank charges | 8590 = 坏账 | 8710 |
| 8605 = Professional development | — | 8876 Training expense |
| 8610 = Amortization of tangible assets | 8610 = Loan losses | 8670 |
| 9270 = Software / subscriptions | 9270 = Other expenses | 9150 |

> 根因：这些多数是 **T2125（个体户 Statement of Business Activities）行号**或凭印象编造的号段，被误当成 GIFI。T2125 与 GIFI 在 8523/9200/9281 等处恰好重合，更容易让人产生「都对」的错觉。**判定标准只有一个：能否在 CRA Appendix A 中查到。**

## 5. Tax Treatment 轴（与 GIFI 映射相互独立）

GIFI 决定「报表怎么归类」，税务处理决定「能扣多少」。两条轴分开存储，不要合并成一列。

| 场景 | GIFI | Tax treatment | Schedule 1 |
|---|---|---|---|
| 商务餐饮/招待 | 8523 | 50% 上限（ITA 67.1） | 不可扣的 50% 加回 |
| 长途运输业司机餐费 | 8523 | 更高比例（特殊规则） | 按适用比例 |
| 会计折旧 | 8670 | 账面折旧不可扣 | **全额加回**，改按 Schedule 8 计 CCA |
| 无形资产摊销 | 8570 | 同上 | 全额加回，按 CCA Class 14/14.1 |
| 慈善捐赠 | 8522 | 不是经营费用 | 加回后按捐赠扣除单独处理 |
| 政治捐赠 | 8522 | 不可扣 | 加回 |
| 罚款与罚金 | 9270 | 不可扣（ITA 67.6） | 加回 |
| 资本性维修 | 8960 | 不可当期扣 | 加回并资本化，计 CCA |
| 收购相关律师费 | 8861 | 资本性支出 | 加回并计入资产成本 |
| 坏账准备 | 8590 | 准备金一般不可扣 | 加回；实际核销才可扣 |
| 会员费（俱乐部） | 8761 | 娱乐性俱乐部会费不可扣 | 加回 |
| 境外增值税 | 随费用科目 | 无 ITC，计入费用总额 | 无调整 |

**资本 vs 费用判定要点**：延长资产寿命、提升产能、或产生新资产 → 资本性；恢复原状、日常保养 → 当期费用。金额大不必然等于资本性，但应触发 `review_required`。

## 6. Master Data Schema

每条费用记录建议的完整字段。`gifi_parent` / `is_generic` / `is_total` 是防父子陷阱的关键，缺一不可。

| 字段 | 示例 | Owner | 用途 |
|---|---|---|---|
| `coa_code` | 6320 | 企业 | GL 科目 |
| `coa_name` | Accounting Fees | 企业 | 记账 |
| `expense_category` | Professional Fees | 企业/软件 | 管理分类 |
| `financial_statement` | Income Statement | 会计准则 | 报表定位 |
| `fs_line_item` | Professional fees | 企业/CPA | 报表呈现 |
| `gifi_code` | 8862 | CRA | T2 映射 |
| `gifi_name` | Accounting fees | CRA | 标准名称 |
| `gifi_parent` | 8860 | CRA hierarchy | 层级关系 |
| `gifi_level` | Detail | CRA | Detail / Generic |
| `is_generic` | false | CRA | 是否块头 |
| `is_total` | false | CRA | 是否小计项 |
| `tax_treatment` | Deductible subject to ITA | 税法 | 税务判断 |
| `deductible_pct` | 100% | 税法 | 可扣比例 |
| `schedule_1_adjustment` | 0 | 税法 | 账 → 税调整 |
| `supporting_docs` | Invoice | 实务 | 审计轨迹 |
| `confidence` | 0.98 | AI | 映射置信度 |
| `review_required` | No | CPA workflow | 人工复核标记 |

反面例子 —— 只有两个字段是不够的，无法表达层级，必然踩父子陷阱：

```
gifi_code
gifi_name
```

## 7. 端到端示例

一家加拿大咨询公司支付 **$1,000 给 CPA 做年度会计服务**：

| 层级 | 分类 | 值 |
|---|---|---|
| Transaction | 原始交易 | CPA invoice $1,000 |
| COA | 会计科目 | `6320 Accounting Fees` |
| Expense Category | 管理分类 | `Professional Fees` |
| Financial Statement | P&L | `Professional fees $1,000` |
| GIFI | CRA code | **8862 Accounting fees**（父项 8860，非 generic） |
| T2 Schedule 125 | 申报填列 | `8862 → $1,000` |
| Tax Treatment | 税务处理 | 业务相关，全额可扣 |
| Schedule 1 | 调整 | 0 |
| Taxable income | 结果 | 进入应税所得计算 |

对比一张 **$200 客户商务餐** —— 注意两条轴的分离：

| 层级 | 值 |
|---|---|
| GIFI | **8523 Meals and entertainment**（父项 8520，非 generic） |
| Schedule 125 | `8523 → $200`（**记全额，不要在这里砍半**） |
| Tax Treatment | 50% 上限，ITA 67.1 |
| Schedule 1 | 加回 $100 |

**关键**：Schedule 125 上记录的是**账面全额**，50% 的限制在 Schedule 1 通过调整实现。不要在 GIFI 映射阶段把金额减半。

## 8. 遇到不确定的 code 时

1. 先用第 2 节的区块表定位范围（收据基本都在 8520–9368）
2. 在第 4 节表中找最贴近的 specific code
3. 找不到就去 CRA RC4088 Appendix A 查证 —— **不要凭印象编号**
4. 仍不确定：选最接近的上级块头，置 `is_generic = true`、`confidence < 0.7`、`review_required = true`，在 Validation_Report 中列出并交 CPA

来源：CRA《RC4088 General Index of Financial Information (GIFI)》Appendix A —— https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4088/general-index-financial-information-gifi.html
