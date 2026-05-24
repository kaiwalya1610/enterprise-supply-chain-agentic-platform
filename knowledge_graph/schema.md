# abc.co Lightweight Knowledge Graph Schema

## Purpose

The graph stores durable business relationships used for query routing, retrieval expansion, and exact lookups. It is derived metadata. Source documents and the CSV remain the source of truth.

## Node Types

- `Company`: abc.co.
- `Branch`: Mumbai, Delhi, Bangalore, Hyderabad.
- `Team`: Operations, Logistics, Procurement, Inventory Planning, Customer Success, Finance, COO Office.
- `Role`: Role-based owners such as Logistics Manager, Finance Manager, CFO.
- `Document`: Dataset source files.
- `Policy`: Procurement and communication policy concepts.
- `Procedure`: Shipment escalation and customer communication procedures.
- `KPI`: Inventory metrics such as Inventory Aging and Stockout Risk.
- `ApprovalThreshold`: Procurement and service-credit amount bands.
- `EscalationLevel`: Shipment delay severity levels.
- `SKU`: Inventory item from the CSV.
- `Category`: Product category from the CSV.
- `Supplier`: Preferred supplier from the CSV.
- `Rule`: Business rule or trigger condition.

## Edge Types

- `OWNS`
- `APPROVES`
- `ESCALATES_TO`
- `RESPONSIBLE_FOR`
- `DEFINED_IN`
- `APPLIES_TO`
- `STOCKED_AT`
- `SUPPLIED_BY`
- `BELONGS_TO_CATEGORY`
- `TRIGGERS`
- `REQUIRES_APPROVAL_FROM`
- `CALCULATED_FROM`
- `RELATED_TO`
- `HAS_SKU`
- `REQUIRES`

## Required Edge Properties

- `source_doc`: Source file that supports the edge.
- `section`: Source section when available.

## Examples

```json
{
  "subject": "Procurement Request ₹5,00,001 to ₹15,00,000",
  "relationship": "REQUIRES_APPROVAL_FROM",
  "object": "CFO",
  "source": "procurement_approval_policy.md",
  "section": "Approval Threshold Matrix"
}
```

```json
{
  "subject": "Severity 3",
  "relationship": "ESCALATES_TO",
  "object": "Logistics Manager",
  "source": "shipment_escalation_sop.md",
  "section": "Delay Severity Classification"
}
```
