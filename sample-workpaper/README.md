# Workpaper Sample — 教学样例包

> 对应课程: **Build your first AI Accounting Employee with OpenClaw**
> 场景: 从客户资料 → Working Paper Package (AI 准备, CPA 决定)
> 生成日期: 2026-08-05 · 纯本地运行, 未连接任何第三方服务

---

## 这是什么

一套完整的 **T2 Working Paper 教学样例**, 演示课程设计中的 To-Be 工作流:

```
客户资料(发票等)
   ↓ [Agent 1] Document Extraction (OCR + 抽取)
   ↓ [Agent 2] Expense Classification (COA + GIFI 建议)
   ↓ [Agent 3] Tax Review Agent (知识库: Checklist + 风险)
Working Paper Package ← 你在这里
   ↓ CPA 人工录入 ProFile + Review + 签字
```

## 目录结构

```
ABC_Inc_T2_2026_Workpaper/
├── 01_Source_Documents/          ← 6 张发票原件 (5 PDF + 1 JPG, 从 references/invoices/ 复制)
├── 02_AI_Extraction/
│   ├── extracted_transactions.xlsx   交易级明细: 发票抽取(勾稽✓) + 银行流水样例 + 分类汇总
│   └── document_summary.md           抽取汇总: 6/6 成功, 合计 $4,303.05
├── 03_GIFI_Workpaper/
│   ├── trial_balance.xlsx            试算平衡表 (借方 227,400 = 贷方 227,400 ✓)
│   ├── gifi_mapping.xlsx             COA → GIFI 映射建议 (含置信度)
│   └── financial_statement_draft.xlsx 财务报表草稿 (净利 $52,600, 报表平衡✓)
├── 04_Tax_Review/
│   ├── tax_review_report.md          ★ 核心输出: 复核报告 (R1–R10 + Checklist)
│   ├── missing_information.xlsx      12 项缺失资料 (按优先级)
│   └── risk_flags.md                 风险清单 (3 高 / 5 中 / 4 低)
└── 05_Client_Questions/
    └── followup_email_draft.md       自动起草的客户催收邮件 (英文版+中文对照)
```

## 数据真实性说明 (教学必须讲清)

| 数据 | 来源 |
|---|---|
| 6 张发票金额 | ✅ **真实抽取** (references/invoices/ 的 PDF/JPG, OCR+文本抽取) |
| 发票数字勾稽 | ✅ 每张 金额+税额=价税合计, 全部通过 |
| 收入/银行流水/工资等 | 🎭 **编造样例** (标注"编造") |
| 币种 | ¥ 按 1:1 视作 CAD (教学简化) |

## 数字勾稽链 (demo 跑通的验证)

```
6 张发票合计 $4,303.05
  = 通行费 36.05 + 餐费 893.90 + 差旅住宿 3,373.10   ✓ (分类汇总)
→ 试算平衡表: 借方 227,400 = 贷方 227,400            ✓
→ 财务报表: 资产 95,000 = 负债 35,240 + 权益 59,760  ✓
→ 净利润 = 收入 185,000 − 支出 132,400 = 52,600      ✓
```

## 教学演示剧本 (5 分钟版)

1. **开场:** "AI 员工替 CPA 收资料、整理资料、提醒异常" — 展示 `01_Source_Documents/` 里五花八门的原始单据
2. **Agent 1 抽取:** 打开 `02_AI_Extraction/extracted_transactions.xlsx` 发票 sheet, 指出勾稽校验通过
3. **Agent 2 分类:** 打开 `gifi_mapping.xlsx`, 讲"通行费→8520、餐费→8521(50%限制)、住宿→8523"
4. **Agent 3 复核:** 打开 `tax_review_report.md`, 讲 R1(餐费50%)、R2(发票抬头是关联公司!) — 这是最出彩的发现
5. **收尾:** 打开 `followup_email_draft.md` — "AI 甚至把催资料邮件都起草好了", 然后强调:
   **AI 准备, CPA 决定, CPA 签字 — 录入 ProFile 由 CPA 完成**

## 已知说明

- 课程设计示例目录名为 `ABC_Inc_T2_2025_Workpaper`; 本样例发票均为 2026 年日期,
  故使用 `ABC_Inc_T2_2026_Workpaper` 保持一致 (FYE 2026-12-31)。
- 发票购买方为"上海扣启企业管理咨询有限公司" — 教学中刻意保留, 用于演示
  Review Agent 的关联方风险识别 (R2)。
- 本包所有文件均由 AI 本地生成, 未调用 Google Drive / Gmail / Obsidian 等外部服务。

> **AI 准备. CPA 决定. CPA 签字.**
