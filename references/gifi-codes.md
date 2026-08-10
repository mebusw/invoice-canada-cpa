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
| 8710 | Interest and bank charges | 银行手续费、利息 | 视资金用途 | 明细 8715 / 8716 |
| 8911 | Real estate rental | 办公室租金 | 100% | 租金是 8911，**不是 8530** |
| 8960 | Repairs and maintenance | 设备/办公室维修 | 视情况 | **可能是资本性支出** |
| 9060 | Salaries and wages | 员工工资 | 100% | 工资是 9060，**不是 8540** |
| 9130 | Supplies | 经营耗材 | 100% | |
| 9150 | Computer-related expenses | 电脑、软件、SaaS 订阅 | 100% | 软件订阅是 9150，**不是 9270** |
| 9200 | Travel expenses | 机票、酒店、住宿 | 100% | 差旅是 9200，**不是 8523** |
| 9201 | Meetings and conventions | 参加会议/研讨会 | 100% | |
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

**默认：车辆运行费用走 9281 当期费用化。** CRA 在 9281 下明确列举 automobile expenses、gas、motor vehicle fuel、**tires**、vehicle washing。

因此：
- 单独更换轮胎、换机油、洗车、日常维修 → **9281 当期费用**，不资本化
- 车辆维修若金额大且延长寿命 → 可能落 8962（Repairs and maintenance – Vehicles），并需判断资本性
- 只有**取得车辆本身**（或随车购置的整体资产）才计入资本性资产，按 CCA Class 10（30% 余额递减）折旧
- 租车 → 8915 Motor vehicle rentals，与自有车辆的 9281 区分

**参照案例**：4 条轮胎单价 $209.99（$839.96 + $20 环保费）合计 $971.75。金额虽大，但按 CRA 列举仍属 9281 营运费用。**不要自行认定为资本支出** —— 标记 `review_required = true` 交 CPA 判断。

> 历史错误：早期版本把轮胎写成「>$500 即资本化 CCA Class 10」，且 GIFI 填 8520（实为广告推广）。两处都是错的。

## 境外增值税

加拿大 ITC **不适用于**境外增值税（中国增值税、欧盟 VAT、美国销售税）。境外税款计入费用总额。

T2 处理：
- 境外收据按含税总额入账
- 不要把境外税额单列为「可抵扣」
- 工作底稿注明：「Foreign VAT, non-recoverable per ITA」

当前数据集全部为境内收据，本节为备查。

## 商户 → GIFI 映射（基于 12 张收据测试集）

| 商户 | GIFI | 依据 |
|---|---|---|
| Walmart | 8810 / 8811（办公）或 8523（餐饮） | 消耗品 → 办公；员工食材 → 餐饮 |
| Costco | 8810 / 8811（办公）或 9281（轮胎） | 大宗消耗品 → 办公；轮胎 → 车辆费用 |
| Shoppers Drug Mart | 8810 | 药品/健康用品，一般计办公室急救 |
| T&T Supermarket | 8523 或 9130 | 熟食/备餐 → 8523；一般食材看用途 |
| H Mart | 8523 | 同 T&T |
| Canadian Tire | 9281 | 汽车配件、机油、保养用品 |
| BBQ / 各类餐厅 | 8523 | 餐饮招待，50% 限制 |
| 航空、酒店 | 9200 | 差旅 |
| 会议、研讨会 | 9201 | 参会 |

这些是启发式。CPA 会根据以下因素调整：物品的实际用途、公司是否有在岗用餐的员工、业务是否涉及车队。

## 何时标记为需要复核

出现以下情况时置 `gifi_review_needed = true` 并在 Validation_Report 中列出：

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
