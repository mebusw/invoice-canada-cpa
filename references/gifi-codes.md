# GIFI 选择规则与税务处理（收据场景）

GIFI（General Index of Financial Information）是 CRA 用于 T2 公司税申报的标准化科目体系。本文件覆盖**收据类费用**最常用的 code、选择规则与税务处理要点。

完整分类学、generic 父子映射、master data schema 见 `references/gifi-taxonomy.md`。

## 定位

CPA 会把 GIFI code 录入 ProFile / Taxprep 完成 T2 申报。**AI 给出的 GIFI 一律是 advisory** —— 最终由 CPA 结合完整财务图景确认。本 skill 必须始终输出 GIFI 建议，但绝不宣称它是最终答案。

## 高频 code（覆盖 90% 收据）

| Code | 官方名称 | 触发 | 可扣比例 | 注意 |
|---|---|---|---|---|
| 8523 | Meals and entertainment | 餐厅、快餐、熟食柜、商务招待 | **50%**（ITA 67.1） | 报表记全额，Schedule 1 加回一半 |
| 8810 | Office expenses | 一般办公支出 | 100% | 办公费是 8810，**不是 8575** |
| 8811 | Office stationery and supplies | 纸张、文具 | 100% | 比 8810 更具体时优先 |
| 8862 | Accounting fees | CPA、记账 | 100% | 父项 8860 |
| 8861 | Legal fees | 律师、公证 | 视情况 | 资本性 vs 经营性需区分 |
| 8690 | Insurance | 商业保险 | 100% | |
| 8710 | Interest and bank charges | 银行手续费、利息 | 视资金用途 | 明细 8715/8716 |
| 8911 | Real estate rental | 办公室租金 | 100% | 租金是 8911，**不是 8530** |
| 8960 | Repairs and maintenance | 设备/办公室维修 | 视情况 | **可能是资本性支出** |
| 9060 | Salaries and wages | 员工工资 | 100% | 工资是 9060，**不是 8540** |
| 9130 | Supplies | 经营耗材 | 100% | |
| 9150 | Computer-related expenses | 电脑、软件、SaaS 订阅 | 100% | 软件订阅是 9150，**不是 9270** |
| 9200 | Travel expenses | 机票、酒店、住宿 | 100% | 差旅是 9200，**不是 8523** |
| 9201 | Meetings and conventions | 参加会议会议 | 100% | |
| 9220 | Utilities | 水电燃气 | 按业务比例 | 9225 电话通讯 |
| 9270 | Other expenses | 归不进去的 | 视情况 | catch-all 是 9270，尽量少用 |
| 9281 | Vehicle expenses | 汽油、轮胎、洗车、车辆维修 | 100% | 车辆费用是 9281，**不是 8520** |

> **8520 / 8710 / 8760 / 8860 / 8960 / 9130 / 9150 / 9220 是 generic 块头**，有具体子项时禁止直接使用。详见 `references/gifi-taxonomy.md` 第 3 节。

## 50% 餐饮限制（ITA 67.1）

**法条**：《所得税法》67.1(a) 将食品、饮料与娱乐支出的可扣额限制为**实际金额的 50%**。

**适用**：餐厅堂食、商务会谈的咖啡、熟食柜/热食台的备餐、体育赛事与演出票、公司聚餐与团队用餐。

**不适用**：作为应税福利提供给员工的餐食（另有处理规则）、家庭办公的日常食材（一般不可扣）。办公室零食属灰区，交 CPA 判断。

**实现方式**：
- `gifi_code` = 8523，**金额记全额**
- `deductible_pct` = `50%`
- `schedule_1_flag` = `true`，在报告中注明「可扣额为记录金额的一半」
- **不要在提取阶段把金额减半** —— 50% 限制是在申报时通过 Schedule 1 调整实现的

## 车辆费用与资本化（9281 / CCA Class 10）

**默认：车辆运行费用走 9281 当期费用化。** CRA 在 9281 下明确列举 automobile附件、gas、motor vehicle fuel、**tires**、vehicle washing。

因此：
- 单独更换轮胎、换机油、洗车、日常维修 → **9281 当期费用**，不资本化
- 车辆维修若金额大且延长寿命 → 可能落 8962（Repairs and maintenance – Vehicles），并需判断资本性
- 只有**取得车辆本身**（或随车购置的整体资产）才计入资本性资产，按 CCA Class 10（30% 余额递减）折旧
- 租车 → 8915 Motor vehicle rentals，与自有车辆的 9281 区分

> 历史错误：早期版本把轮胎写成「>$500 即资本化 CCA Class 10」，且 GIFI 填 8520（实为广告推广）。两处都是错的。

## 境外增值税

加拿大 ITC **不适用于**境外增值税（中国增值税、欧盟 VAT、美国销售税）。境外税款计入费用总额。

T2 处理：
- 境外收据按含税总额入账
- 不要把境外税额单列为「可抵扣」
- 工作底稿注明：「Foreign VAT, non-recoverable per ITA」

## 商户 → GIFI 启发式

| 商户类型 | GIFI | 依据 |
|---|---|---|
| 加油站、汽车配件、轮胎店 | 9281 | 汽车维护 |
| 餐厅、外卖、熟食柜、咖啡店 | 8523 | 餐饮 |
| 超市杂货（无餐饮） | 8810 / 9130 | 消耗品 |
| 药店、健康用品 | 8810 | 急救/办公 |
| 航空、酒店 | 9200 | 差旅 |
| 会议、研讨会 | 9201 | 参会 |
| 加油站 / 轮胎店 / 汽车配件 | 9281 | 车辆 |

**不要硬编码商户名映射**。LLM 看语义比看字符串好。Costco 可能是 8810（杂货）也可能是 9281（轮胎）；T&T 可能 9130（基本食材）也可能是 8523（热食）；最终由 line_items + 商户类型联合决定。

## 何时标记为需要复核

出现以下情况时置 `review_required = true` 并在 Validation_Report 中列出：

- 一张收据混合多类物品（食材 + 家用 + 办公用品）
- 商户罕见、无归类先例
- 金额大到可能改变性质（如 $5,000 的办公设备可能是资本性）
- 只能定位到 generic 块头、无法确定 specific 子项
- 需要判断资本性 vs 当期费用
- 需要 Schedule 1 调整判断

## 查不到 code 时

GIFI 全表约 **700 个** code（随 CRA 版本变化）。上表已覆盖收据场景 90% 的情况。若确实不匹配：

1. 用区块范围定位（收据费用几乎都在 8520–9368）
2. 查 `references/gifi-taxonomy.md` 第 4 节完整对照表
3. 仍找不到则查证 CRA RC4088 Appendix A，**不要凭印象编号**
4. 输出时附 `confidence` 与 `review_required = true`

来源：CRA《RC4088 General Index of Financial Information (GIFI)》Appendix A —— https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4088/general-index-financial-information-gifi.html