# Inventory Performance KPI Guide

---

## Document Control

| Field | Value |
|---|---|
| Document ID | ABC-INV-GDE-003 |
| Version | 1.2 |
| Owner | Inventory Planning Team |
| Approved By | Head of Operations |
| Effective Date | 2025-07-01 |
| Last Reviewed | 2026-01-20 |
| Review Cycle | Quarterly |
| Classification | Internal Use Only |

---

## Revision History

| Version | Date | Author | Change Summary |
|---|---|---|---|
| 1.0 | 2025-01-15 | Inventory Planning Team | Initial release |
| 1.1 | 2025-04-10 | Inventory Planning Team | Added dead stock definition; updated slow-moving threshold; added data quality rules |
| 1.2 | 2025-07-01 | Inventory Planning Team | Added sell-through rate formula; revised excess stock multiplier from 3x to 2.5x; added seasonal and contract reservation exceptions |

---

## Purpose

This guide establishes standardized definitions, calculation methods, reporting thresholds, and interpretation guidelines for all inventory performance key performance indicators (KPIs) used by abc.co. It is intended to ensure that:

- All branches use consistent definitions when reporting and reviewing inventory health
- Inventory data can be reliably compared across branches and time periods
- KPI thresholds are applied uniformly, reducing subjective interpretation
- The Inventory Planning Team, Operations Team, and Senior Management operate from a shared understanding of inventory status
- Automated reporting systems, dashboards, and RAG-assisted tools can reference authoritative definitions

This guide does not prescribe remediation actions. Decisions about reordering, write-offs, promotions, or vendor negotiations are made by the Inventory Planning Team and Branch Operations Lead in consultation with the Head of Operations.

---

## Scope

This guide applies to:

- All SKUs managed by abc.co across the Mumbai, Delhi, Bangalore, and Hyderabad branches
- Branch-level and SKU-level inventory reporting
- All product categories: Office Supplies, Pantry Goods, Cleaning Supplies, Small Electronics, Ergonomic Furniture, and Facility Consumables
- All reporting cadences: daily dashboards, weekly branch reviews, and monthly operations reviews

This guide does not apply to in-transit inventory (items dispatched but not yet received at a branch), items held in quarantine pending quality review, or returned goods pending assessment.

---

## KPI Summary Table

| KPI | Short Definition | Calculation Basis | Reporting Frequency | Primary Owner |
|---|---|---|---|---|
| Inventory Aging | Days an item has been in stock | Current Date − Last Receipt Date (or Last Movement Date if later) | Daily dashboard; weekly review | Inventory Planning Team |
| Slow-Moving Inventory | Stock with high aging and low recent sales | Aging > 60 days AND sales_last_30_days < 20 units | Weekly branch review | Inventory Planning Team |
| Reorder Level | Minimum stock threshold triggering replenishment | Set per SKU per branch based on lead time and average sales | Daily dashboard | Inventory Planning Team |
| Stockout Risk | Stock at or below reorder level | stock_units ≤ reorder_level OR projected demand > available supply before lead time ends | Daily dashboard | Inventory Planning Team + Operations |
| Sell-Through Rate | Proportion of received stock sold in a period | Units Sold ÷ Units Received × 100 | Monthly | Inventory Planning Team |
| Excess Stock | Stock significantly above demand | stock_units > 2.5 × average_sales_last_30_days | Weekly branch review | Inventory Planning Team |
| Dead Stock | Long-aged stock with no recent sales | Aging > 120 days AND sales_last_30_days = 0 | Monthly operations review | Inventory Planning Team + Finance |

---

## Inventory Aging

### Definition

Inventory aging is the number of days an item has remained in stock since the date of receipt or the date of last inventory movement, whichever is later.

The aging metric is used to assess how long individual SKUs have been sitting in branch warehouses without being consumed by orders. High aging values indicate a mismatch between procurement quantities and actual demand, or a decline in product demand.

### Calculation

```
Aging Days = Current Date − Last Receipt Date
```

If a warehouse management system records a last movement date (such as a stock adjustment, partial consumption, or transfer between locations) that is later than the last receipt date, the last movement date may be substituted for operational reporting purposes. The substitution must be noted in the reporting record.

### Aging Bands

| Aging Band | Days Range | Interpretation | Required Action |
|---|---|---|---|
| Fresh Inventory | 0–30 days | Normal; recently received | Monitor |
| Normal Aging | 31–60 days | Within acceptable range | Monitor |
| Slow-Moving | 61–90 days | Elevated risk; approaching slow-moving threshold | Flag for review |
| High Aging Risk | 91–120 days | Significant risk of write-off; demand review required | Inventory Planning review; consider promotion or reallocation |
| Dead-Stock Review | Over 120 days | Dead-stock candidate; write-off risk | Escalate to Finance and Head of Operations |

### Notes

- Aging is measured at the SKU and branch level. A SKU may have different aging values at different branches.
- Items reserved for contract customers are flagged in the inventory system and may be excluded from dead-stock review if the contract specifies a delivery window beyond 120 days. Exclusion requires Inventory Planning Team approval.
- Seasonal items (e.g., specific pantry goods purchased for festive periods) may be excluded from slow-moving classification during the relevant off-season, subject to documentation in the inventory management system.

---

## Slow-Moving Inventory

### Definition

Slow-moving inventory is any SKU that meets both of the following conditions simultaneously:

1. **Aging Days > 60** (i.e., the item has been in stock for more than 60 days), AND
2. **sales_last_30_days < 20 units** (i.e., fewer than 20 units of the SKU have been sold in the most recent 30-day period at that branch)

A SKU that meets only one of these conditions is not classified as slow-moving.

### Exceptions

- Items designated as **seasonal** in the product catalog are excluded from slow-moving classification during documented off-season periods.
- Items flagged as **reserved for contract customer** are excluded if the contract specifies a delivery window that extends beyond the 60-day aging threshold.
- Items that are part of an active **promotional bundle** or **bulk order fulfillment** and are pending dispatch are excluded for the duration of the order hold.

### Reporting

Slow-moving inventory is reported weekly in the Branch Inventory Review. The Inventory Planning Team provides a slow-moving SKU list per branch, including aging days, sales in the last 30 days, stock quantity, and estimated stock value. Branch Operations Leads are required to review and acknowledge the list within 2 business days.

---

## Reorder Level

### Definition

The reorder level is the minimum stock quantity for a given SKU at a given branch, below which a replenishment review is automatically triggered. It represents the minimum buffer required to fulfill expected orders during the supplier's lead time, plus a safety margin.

### Calculation Basis

Reorder levels are set by the Inventory Planning Team per SKU per branch and are reviewed quarterly or when supplier lead times or demand patterns change materially. The calculation considers:

- Average daily sales velocity for the SKU at that branch (calculated over the most recent 90 days)
- Supplier lead time in days (as recorded in the vendor record)
- Safety stock factor (default: 1.2x the lead time demand, adjustable for high-demand or critical SKUs)

Reorder levels are stored in the inventory management system per SKU-branch combination and must not be altered without Inventory Planning Team approval.

### Trigger Action

When stock_units for a SKU at a branch fall at or below the reorder level, the Inventory Planning Team receives an automatic notification and is required to review the replenishment need within 1 business day. If replenishment is confirmed, a procurement request is raised to the Procurement Team.

---

## Stockout Risk

### Definition

A SKU is classified as at **stockout risk** when either of the following conditions is true:

- **Condition A:** `stock_units ≤ reorder_level` — the current stock has fallen to or below the defined replenishment trigger, OR
- **Condition B:** Projected demand for the SKU during the remaining supplier lead time period exceeds the current available stock, based on the current daily sales velocity

A SKU in stockout risk status does not necessarily mean a stockout is imminent, but it requires immediate review by the Inventory Planning Team.

### Severity

| Stockout Risk Level | Condition | Action |
|---|---|---|
| Watch | stock_units between reorder_level and 1.25× reorder_level | Monitor; no immediate action required |
| At Risk | stock_units ≤ reorder_level | Replenishment review within 1 business day |
| Critical | stock_units = 0 or demand will exceed supply before lead time ends | Immediate escalation to Branch Operations Lead; consider emergency procurement or inter-branch transfer |

---

## Sell-Through Rate

### Definition

Sell-through rate measures the proportion of received inventory that has been sold within a defined reporting period. It is used to evaluate demand efficiency and procurement accuracy.

### Calculation

```
Sell-Through Rate (%) = (Units Sold in Period ÷ Units Received in Period) × 100
```

A sell-through rate below 50% in a 30-day period for a non-seasonal, non-contract SKU indicates potential overstock and should trigger a review of procurement quantities.

### Reporting

Sell-through rate is reported monthly at the SKU and category level. Category-level sell-through rates help identify structural demand shifts that may require catalog adjustments.

---

## Excess Stock

### Definition

Excess stock is a condition where the quantity of a SKU on hand significantly exceeds anticipated near-term demand, creating unnecessary capital tie-up and warehouse space consumption.

### Threshold

A SKU is classified as **excess stock** when:

```
stock_units > 2.5 × average_sales_last_30_days
```

where `average_sales_last_30_days` is the average number of units sold per day in the last 30 days, multiplied by 30 to give the 30-day demand estimate.

### Exceptions

- SKUs reserved for a specific contract customer order are excluded from excess stock classification for the duration of the reservation.
- SKUs procured as part of a bulk purchase approved by the Finance Manager for cost optimization purposes are flagged as "bulk purchase" in the system and excluded for up to 90 days from receipt date.
- SKUs subject to a supplier minimum order quantity (MOQ) constraint that exceeds typical demand may be excluded from the classification, subject to Inventory Planning Team documentation.

---

## Dead Stock

### Definition

Dead stock is any SKU at a specific branch that meets both of the following conditions:

1. **Aging Days > 120** — the item has been in stock for more than 120 days, AND
2. **sales_last_30_days = 0** — no units of the SKU have been sold at that branch in the most recent 30-day period

Dead stock represents the highest-risk inventory category due to the risk of obsolescence, damage, or write-off. Dead stock items must be reviewed by the Inventory Planning Team and Finance Team for write-off eligibility or disposal options.

### Required Actions

- Dead stock is reported monthly in the Operations Review.
- The Inventory Planning Team must initiate a disposition review within 10 business days of the monthly report.
- Disposition options include: inter-branch reallocation, vendor return (if contract allows), markdown promotion, or write-off.
- Write-offs above ₹10,000 per SKU require Finance Manager approval.
- Write-offs above ₹1,00,000 per transaction require CFO approval.

---

## Branch-Level Reporting

Each branch submits inventory performance data through the warehouse management system on the following cadences. The Inventory Planning Team at Hyderabad consolidates and validates branch data before publishing reports.

- **Daily:** Stock level dashboard updated automatically from warehouse management system. Operations Coordinators review stockout risk and reorder alerts.
- **Weekly:** Branch Operations Lead reviews slow-moving and excess stock SKU lists. Inventory Planning Team publishes a branch-level aging summary.
- **Monthly:** Full KPI dashboard covering all seven KPIs published to Senior Management. Finance Team reviews dead stock and write-off candidates.

---

## Reporting Cadence

| Report | Frequency | Publisher | Recipients | Data Source |
|---|---|---|---|---|
| Stock Level Dashboard | Daily | Automated (WMS) | Operations Team, Inventory Planning | Warehouse Management System |
| Slow-Moving SKU Report | Weekly | Inventory Planning Team | Branch Operations Leads, Head of Operations | WMS + KPI calculation |
| Stockout Risk Alert | Daily | Automated (WMS) | Inventory Planning Team, Operations Coordinator | WMS reorder level trigger |
| Branch Aging Summary | Weekly | Inventory Planning Team | Branch Operations Leads | WMS |
| Monthly KPI Dashboard | Monthly | Inventory Planning Team (Hyderabad) | Head of Operations, COO, Finance Team | WMS + consolidated calculations |
| Dead Stock and Write-Off Review | Monthly | Inventory Planning Team | Finance Manager, Head of Operations | WMS + aging calculation |

---

## Data Quality Rules

The following data quality rules apply to all inventory records. Records that fail these rules must be flagged for correction before inclusion in KPI calculations.

| Field | Rule |
|---|---|
| SKU | Must not be blank; must match approved SKU registry |
| Branch | Must be one of: Mumbai, Delhi, Bangalore, Hyderabad |
| Aging Days | Must be ≥ 0; cannot be negative; records with negative aging must be flagged for system audit |
| Reorder Level | Must be ≥ 0; cannot be null; default is 0 if not set, but Inventory Planning Team must review any SKU with reorder level = 0 |
| sales_last_30_days | Must be numeric and ≥ 0; null values are treated as 0 for KPI calculation purposes but flagged for correction |
| Unit Cost | Must be numeric, > 0, and denominated in INR |
| Last Receipt Date | Must be a valid date in YYYY-MM-DD format; cannot be a future date |
| Manual Adjustments | All manual changes to stock quantities must include a reason code and the name of the authorizing manager |

---

## Example Interpretations

### Example 1: Aging Classification

A box of ergonomic footrests (SKU: ERG-FTRST-03) was received at the Hyderabad branch on 2026-01-15. As of the report date, 2026-05-01, the item has been in stock for 106 days with no sales in the past 30 days.

- **Aging Days:** 106 days → classified as **High Aging Risk** (91–120 days)
- **Not yet dead stock:** Aging does not exceed 120 days
- **Action required:** Inventory Planning Team review; consider inter-branch reallocation or targeted promotion

---

### Example 2: Stockout Risk

A pantry supply SKU — premium ground coffee (SKU: PNTR-COFFEE-02) — at the Bangalore branch has stock_units = 18, reorder_level = 25, and supplier_lead_time_days = 5. Daily sales velocity is approximately 4 units per day.

- **Condition A:** stock_units (18) ≤ reorder_level (25) → **At Risk**
- **Condition B:** Projected demand over lead time = 4 × 5 = 20 units. Current stock (18) < projected lead time demand (20) → **Critical**
- **Action:** Immediate escalation to Branch Operations Lead; emergency procurement review or inter-branch transfer from Mumbai branch.

---

### Example 3: Dead Stock

A batch of USB-A to USB-C cables (SKU: ELEC-USB-CA-07) at the Delhi branch was received on 2025-12-01. As of 2026-05-01, aging is 151 days. sales_last_30_days = 0.

- **Aging Days:** 151 days → exceeds 120-day threshold
- **Sales last 30 days:** 0 → meets second dead-stock condition
- **Classification:** **Dead Stock**
- **Action:** Included in monthly dead stock report. Inventory Planning Team to initiate disposition review within 10 business days. Finance Team to assess write-off value.

---

### Example 4: Excess Stock

A SKU for premium recycled paper reams (SKU: OFF-PAPER-R01) at the Mumbai branch shows stock_units = 1,200. sales_last_30_days = 160 units (average daily sales ≈ 5.3 units/day). 30-day demand estimate = 160 units. 2.5 × 160 = 400.

- **stock_units (1,200) > 2.5 × 30-day demand (400)** → **Excess Stock**
- Note: If this was a bulk purchase approved by Finance for cost optimization, it should be flagged as "bulk purchase" in the system and excluded for up to 90 days from receipt date.
- **Action:** Inventory Planning Team to review procurement quantities and adjust next order cycle.

---

## Limitations

All KPI values must be interpreted in the context of the following factors, which are not fully captured in the raw inventory data:

- **Seasonality:** Certain product categories (pantry goods, cleaning supplies) may experience seasonal demand cycles that affect aging and sell-through rates.
- **Contract customer reservations:** Stock reserved for specific customers under supply agreements may appear as slow-moving or excess but is operationally committed.
- **Vendor lead time variability:** Supplier lead times recorded in the system may not reflect actual lead time variability, which can cause reorder level calculations to underestimate buffer requirements.
- **New SKU ramp-up:** Newly introduced SKUs may show high aging and low sales in the first 60 days due to demand ramp-up rather than structural poor performance.

Inventory Planning Team members are expected to apply contextual judgment when interpreting KPI flags and must document their rationale when excluding items from standard classification thresholds.

---

## Related Documents

- ABC-FIN-POL-007 — Procurement Approval and Vendor Purchase Policy
- ABC-OPS-SOP-004 — Shipment Delay Escalation Standard Operating Procedure
- ABC-CORP-BG-001 — abc.co Company Operations Background

---

## Review and Maintenance

This guide is reviewed quarterly by the Inventory Planning Team and approved by the Head of Operations. Proposed changes to KPI definitions, thresholds, or reporting cadences must be reviewed by the Head of Operations before implementation. Branch Operations Leads are notified of any threshold changes at least 10 business days before they take effect.
