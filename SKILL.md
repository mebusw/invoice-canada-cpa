---
name: invoice-canada-cpa
description: >
  加拿大 CPA 数字员工工作流: 从客户资料(发票/收据/银行流水, PDF/JPG/Excel)抽取金额数字、
  分类到加拿大会计科目(COA)与 GIFI 建议码、生成完整 T1/T2 Working Paper Package
  (试算平衡表 / GIFI 映射 / 财务报表草稿 / 税务复核报告 / 风险清单 / 缺失资料 / 催收邮件草稿)。
  当用户提到 workpaper、working paper、报税、T1、T2、GIFI、发票抽取、OCR、费用分类、
  expense classification、tax review、风险清单、缺失资料、催收邮件、试算平衡、
  财务报表草稿、加拿大 CPA 课程或教学演示时, 一定要用本 skill——哪怕用户只是说
  "帮我整理这些发票"或"看看这些票据"——本 skill 负责"AI 准备, CPA 决定"中的 AI 前半段。
---

# Invoice → Working Paper (加拿大 CPA 数字员工工作流)

## 定位

AI 完成报税流程的**前半段资料整理**(收资料 → 抽取 → 分类 → 检查 → 提醒),
CPA 完成后半段专业判断(录入 ProFile → Review → 签字)。

> **AI 准备. CPA 决定. CPA 签字.**
> 本 skill 的所有输出都是供 CPA 复核的工作底稿, 不是最终申报, 不要替 CPA 做最终判断。

## 使用模式

| 模式 | 说明 |
|---|---|
| **演示模式(默认)** | 本地文件; 发票数字真实抽取, 其余数据(银行流水/工资等)可编造但**必须逐条标注"编造"**; 不连接 Google Drive / Gmail / Obsidian 等任何第三方服务 |
| 生产模式(未来) | 从 Google Drive 拉取客户资料、查 Obsidian 知识库; 当前课程阶段不实现 |

**依赖工具**(生成 Excel 时需要): `python3 + openpyxl`; PDF 文本用 `pdftotext`, 图片 OCR 可以选用大模型本身的图片理解能力或者`/ocr-image-text-extract` SKILL，即`tesseract`(中文包 `chi_sim`)。工具缺失时换其他可用方法, 并交叉验证数字。

## 工作流总览

```
客户资料(发票/收据/银行流水)
   ↓ [Agent 1] Document Extraction — OCR + 抽取 + 勾稽校验
   ↓ [Agent 2] Expense Classification — COA + GIFI 建议
   ↓ [Agent 3] Tax Review — Checklist + 风险 + 缺失资料
Working Paper Package
   ↓ CPA 录入 ProFile + Review + 签字 (AI 不做)
```

## Step 1 — 收集源文件

- 接受 PDF / JPG / PNG / Excel / 邮件附件等任意格式, 格式越杂越能体现 AI 价值。
- 原始文件**原样复制**到 `01_Source_Documents/`, 保留原始文件名(乱文件名是真实世界的常态, 不要整理)。
- 把每份文件的来源记入抽取表(真实客户资料 vs 演示编造), 便于 CPA 追溯。

## Step 2 — 抽取 (Document Extraction)

对每个文件抽取结构化字段, 并做**逐张勾稽校验**:

- 字段: 发票号码 / 开票日期 / 销售方 / 购买方 / 项目类别(中+英文) / 金额(不含税) / 税率 / 税额 / 价税合计。
- PDF 优先 `pdftotext -layout`; 图片用 OCR; 如果抽取出的数字**无法通过勾稽校验**, 换工具重新抽取, 不要将就。
- **每张必须验证: 金额 + 税额 = 价税合计**。失败则标记异常并人工复核, 通过才入账。
- 负数行(退货/折扣, 如 668.77 − 51.89)要自动合并进总额, 并在备注注明。
- 原币非加元时: 演示模式按 1:1 简化视作 CAD 并显式声明; 真实业务需按汇率折算。

抽取结果写入 `extracted_transactions.xlsx` 的发票 sheet + `document_summary.md` 汇总。
**数字是全流程的锚点**——后面试算平衡、财务报表全靠它们, 这一层错了后面全错。

## Step 3 — 分类 (Expense Classification)

每笔交易给出: 中文类别 → 英文类别 → 会计科目 COA → **GIFI 建议码 + 置信度**。

两条核心税务规则(课程重点):

1. **外国增值税不可抵扣**: 中国增值税等外国税在加拿大不可申请 ITC,
   **按含税金额入账**——这是加拿大税务的正确处理, 不用调整, 但要在 workpaper 里记录理由。
2. **发票抬头 ≠ 客户主体时自动标记风险**: 例如发票购买方是关联公司 → 提示需要代付协议/业务实质,
   这通常是 CRA 挑战费用归属的第一个切入点。

金额较大或模式异常的单笔(如 2 间房的酒店大额发票)应备注"建议核对", 不擅自判断。

## Step 4 — 生成 Workpaper Package

**固定使用这个结构**(对应课程设计 Demo 输出):

```
<Client>_T2_<FY>_Workpaper/
├── 01_Source_Documents/          ← Step 1 的原始单据副本
├── 02_AI_Extraction/
│   ├── extracted_transactions.xlsx   发票抽取 + 银行流水 + 分类汇总(按来源分 sheet, 每行标注来源)
│   └── document_summary.md           抽取汇总: 成功率 / 合计 / 勾稽结果 / 质量注意点
├── 03_GIFI_Workpaper/
│   ├── trial_balance.xlsx            试算平衡表(借方合计 = 贷方合计, 必须平衡)
│   ├── gifi_mapping.xlsx             COA → GIFI 映射(含置信度 + 注意事项)
│   └── financial_statement_draft.xlsx 财务报表草稿(利润表 + 资产负债表 + 编制说明)
├── 04_Tax_Review/
│   ├── tax_review_report.md          ★ 复核报告(执行摘要 + 风险 + Checklist + 下一步)
│   ├── missing_information.xlsx      缺失资料清单(按优先级, 带用途和缺失风险)
│   └── risk_flags.md                 风险事项清单(带依据与建议行动)
└── 05_Client_Questions/
    └── followup_email_draft.md       催收邮件草稿(英文正文 + 教学注释)
```

目录命名: 客户名 + 申报年度。注意用**发票实际日期**所属年度(本课程样例发票为 2026 年,
故用 `T2_2026` 而非示例的 `T2_2025`, 避免年度不符)。

Excel 规范(保持样例一致性): 表头深蓝底白字加粗、单元格边框、金额列 `#,##0.00` 数字格式、
关键提示行黄底加粗、风险行按严重度着色(HIGH 红 / MEDIUM 黄 / LOW 绿)。

## Step 5 — 税务复核 (Tax Review)

基于知识库 Checklist(生产中来自 Obsidian, 当前内嵌在本 skill, 见下文速查表), 产出:

- **风险清单 risk_flags.md**: 每条含 ID、严重度、类别、影响金额、建议行动、责任方、状态。
  典型风险类型: 税法限制(如餐费 50%)、关联方、收入完整性、异常检测(同比变化)、
  凭证缺失、申报义务(T4/T4A)、税务处理差异(摊销 vs CCA)、披露。
- **缺失资料 missing_information.xlsx**: 每条含用途/缺失风险/优先级, 按 HIGH/MEDIUM/LOW 排序。
- **复核报告 tax_review_report.md**: 执行摘要(做了什么、发现什么、下一步)→ 抽取与分类结果
  → 风险详述 → Checklist 结果 → 下一步。报告开头写清"首轮资料整理, 非税务意见"。

## Step 6 — 催收邮件草稿

基于缺失资料清单自动起草: 先列已收到清单(让客户安心), 再按优先级列缺失项和截止日期。
**AI 只起草, CPA 审阅修改后由 CPA 发送。** 演示模式附中文对照和教学要点。

## 质量闸门(生成后必须程序化验证)

这一条不能省——CPA 打开底稿第一眼看的就是数字能不能对上:

```
1. 每张发票: 金额 + 税额 = 价税合计
2. 发票合计 = 分类汇总合计
3. 试算平衡: 借方合计 = 贷方合计
4. 资产负债表: 资产 = 负债 + 权益
5. 利润表: 收入 − 支出 = 净利润
```

用脚本打开生成的 xlsx 逐项断言, 全部通过才算完成。任何一个不通过, 修数据重跑,
不要带着不平的数字交付——那会毁掉 CPA 对 AI 的信任。

## 税务规则速查(模拟知识库)

### GIFI 常用码(建议值, 最终以 ProFile 确认为准)

| 科目 | GIFI | 说明 |
|---|---|---|
| 咨询/服务收入 | 8299 | Service revenue |
| 汽车费用(油费/通行费) | 8520 | Motor vehicle expenses |
| 餐费与娱乐 | 8521 | ⚠️ ITA 67.1: 仅 50% 可扣除 |
| 差旅费(住宿/机票) | 8523 | Travel expenses |
| 办公室租金 | 8530 | Rent |
| 工资薪金 | 8540 | Salaries and wages; 需报 T4 |
| 外包服务 | 8545 | Subcontracts; 年付超 $500 需 T4A |
| 电话与水电 | 8550 | Telephone and utilities |
| 会计与法律费 | 8560 | Professional fees |
| 保险费 | 8565 | Insurance |
| 广告费 | 8570 | Advertising |
| 办公费/用品 | 8575 | Office expenses |
| 银行手续费 | 8590 | Interest and bank charges |
| 职业发展 | 8605 | Professional development |
| 摊销(折旧) | 8610 | ⚠️ 税务口径按 CCA (Schedule 8) 重算 |
| 软件/订阅 | 9270 | 课程设计示例码, 需 CPA 确认 |
| 现金 / 应收 / 固定资产 | 1000 / 1080 / 1400 | 资产负债表 |
| 应付 / 应付税 / 股东借款 | 2130 / 2280 / 2440 | 资产负债表 |
| 股本 / 留存收益 | 3100 / 3280 | 权益 |

> GIFI 码是 AI 建议值(附置信度), **不是最终申报码**——加免责声明, 让 CPA 在 ProFile 确认。
> 这是"AI 准备, CPA 决定"原则在分类层的体现。

### 复核 Checklist(10 项)

1. 收入 vs 银行收款核对
2. 费用票据齐全性
3. 餐费 50% 限制计算
4. 汽车费用合理性(里程日志)
5. CCA 计算(Schedule 8)
6. T4/T4A 申报义务
7. HST 对账(GST34)
8. 关联方交易检查
9. 上年对比分析(异常检测)
10. 外国税不可抵扣处理

## 参考样例

- `sample-workpaper/ABC_Inc_T2_2026_Workpaper/` — 本 skill 的 golden sample(课程设计 Demo 输出),
  含 README(教学剧本与勾稽链说明)。生成时对照其结构与风格。
- `references/课程设计.md` — 课程总纲: 三层拆解(Automation/Knowledge/CPA)、工具边界、宣传定位。
  理解"AI 做什么、AI 不做什么"时阅读。
