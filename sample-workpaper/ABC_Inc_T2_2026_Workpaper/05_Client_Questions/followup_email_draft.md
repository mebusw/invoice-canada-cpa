# Follow-up Email Draft — 客户催收邮件草稿

> 教学样例 · 由 Review Agent 自动起草 (对应课程设计: 自动起草催收邮件)
> 发送对象: ABC Consulting Inc. 客户 · 发送方: 事务所 (占位)

---

## 邮件正文 (可直接发送版本)

**Subject: ABC Consulting Inc. — FY2026 Tax Documents Needed (Priority List)**

Dear [Client Contact],

Thank you for providing your FY2026 source documents. We have completed the first
pass of document extraction and review for your 2026 corporate tax return (T2).

**What we have received (6 invoices):**
- Expressway tolls: 2 invoices ($19.34 + $16.71)
- Hotels: 2 invoices ($2,796.00 + $577.10)
- Meals: 2 invoices ($653.90 + $240.00)

**To complete your tax file, we need the following items by August 20, 2026:**

*High priority:*
1. July 2026 bank statement
2. Invoices issued to your clients / contracts (to support $185,000 of receipts)
3. Intercompany payment agreement with Shanghai Kouqi Enterprise Management
   Consulting Co., Ltd. — all 6 expenses above were invoiced to this related entity,
   and we need documentation to support the expenses belong to ABC Consulting Inc.

*Medium priority:*
4. Vehicle mileage log (odometer record)
5. Purchase invoice for computer/server equipment (purchased March 18, 2026)
6. Flight itineraries (June 5, 2026)
7. Prior year T2 return (2025)
8. Office lease agreement
9. Business purpose notes for meal expenses
10. Payroll summary / T4 details
11. Subcontractor payee information

*Low priority:*
12. Insurance policy details

You can upload the documents to your client folder as before. Please let us know
if any items are not applicable — we can mark them accordingly.

Once we receive the above, we will update the workpaper package and prepare the
draft for your review.

Best regards,

[Your Name]
[Firm Name] — CPA
[Phone] | [Email]

---

## 中文对照 (教学用)

**主题: ABC Consulting Inc. — 2026 年度税务资料催收清单**

尊敬的客户:

感谢您提供 2026 年度报税资料。我们已完成首轮资料抽取与复核。

**已收到 (6 张发票):** 通行费 2 张 ($19.34 + $16.71) / 住宿 2 张 ($2,796.00 + $577.10) / 餐费 2 张 ($653.90 + $240.00)

**请在 2026-08-20 前补充:**
- 高优先: ① 7 月银行对账单 ② 已开票记录/合同 (支撑 $185,000 收款) ③ 与上海扣启企业管理咨询有限公司的代付协议 (6 张发票抬头均为该关联公司)
- 中优先: ④ 里程日志 ⑤ 设备采购发票 ⑥ 机票行程单 ⑦ 上年度 T2 ⑧ 租赁协议 ⑨ 餐费业务目的说明 ⑩ 工资汇总/T4 资料 ⑪ 外包收款人信息
- 低优先: ⑫ 保单明细

收到资料后我们将更新工作底稿, 准备报税草稿供您复核。

---

## 教学要点 (供讲师)

| 要点 | 说明 |
|---|---|
| 📩 **自动起草** | 邮件由 Review Agent 基于 `missing_information.xlsx` 自动生成, 分类优先级与风险对应 |
| 🎯 **优先级排序** | HIGH 项直接对应高风险事项 R2/R3 (关联方、收入完整性) |
| 💡 **AI 边界** | AI 只起草 → CPA 审阅修改 → CPA 发送 (AI 不代发邮件, 不替 CPA 沟通) |
| 📝 **占位符** | 收件人/签字/联系方式为占位, 发送前需 CPA 确认 |
| 🧾 **逐项可追踪** | 每项缺失资料都可回溯到 `missing_information.xlsx` 的风险说明 |

> 完整风险分析见 `04_Tax_Review/risk_flags.md` (R1–R10)。
