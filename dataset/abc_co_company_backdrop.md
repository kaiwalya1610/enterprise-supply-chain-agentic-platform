# abc.co Company Backdrop

abc.co is a fictional B2B operations company used for testing a document-grounded AI assistant. The company supplies office essentials, pantry goods, cleaning supplies, small electronics, and facility items to coworking spaces, boutique hotels, clinics, and regional offices across India.

The company has grown faster than its internal documentation. Teams know the work, but the guidance is scattered across SOPs, policy notes, reports, emails, and spreadsheets. The assistant should help employees find grounded answers without guessing.

## Company profile

- Name: abc.co
- Industry: B2B retail operations and supply chain services
- Customers: coworking spaces, hotels, clinics, and regional offices
- Operating regions: West, North, South, and Central India
- Main business model: recurring supply orders, urgent replenishment orders, and managed inventory support
- Internal goal: reduce time spent searching for operational guidance

## Branches

abc.co operates through four main branches.

| Branch | Role |
|---|---|
| Mumbai | Main warehouse and west-zone fulfillment hub |
| Delhi | North-zone fulfillment and procurement hub |
| Bangalore | High-volume electronics and technology client orders |
| Hyderabad | Back-office operations, reporting, and KPI review center |

## Internal teams

### Operations

The Operations team tracks orders, coordinates warehouse activity, handles shipment delays, and escalates delivery issues.

Common questions:

- What should I do if a customer shipment is delayed?
- Who owns delayed shipment escalation after 24 hours?
- When should Customer Success contact the customer?

### Procurement

The Procurement team handles purchase requests, vendor coordination, approval routing, and emergency purchases.

Common questions:

- Who approves a purchase request above a certain amount?
- What is the emergency procurement process?
- When does Finance need to review a vendor purchase?

### Inventory Planning

The Inventory Planning team monitors aging inventory, stockout risk, reorder levels, sell-through, and slow-moving stock.

Common questions:

- What does inventory aging mean?
- Which SKUs are slow-moving?
- Which branch has the highest stockout risk?

### Customer Success

The Customer Success team sends customer updates, handles delay communication, and coordinates service credits or remediation requests.

Common questions:

- How should we inform a customer about a shipment delay?
- Can support promise a refund?
- What tone should customer delay emails use?

### Finance

The Finance team reviews large purchase requests, validates invoices, monitors monthly spend, and approves exceptions.

Common questions:

- When does Finance approval become mandatory?
- Who approves purchases above the standard threshold?
- What information is required before Finance can approve a request?

## Business problem

abc.co has useful internal knowledge, but employees lose time looking for it.

The same questions come up repeatedly:

- What is the escalation process for delayed shipments?
- What is the approval workflow for procurement requests?
- What does inventory aging mean?
- Which branch has the highest sales?
- Can Customer Success promise a refund?
- What should we do when the available documents do not answer the question?

The assistant should answer these questions only when the answer is supported by the provided documents or structured data.

## Assistant use case

The AI assistant is intended for internal employees who need fast answers from company documents and operational data.

The assistant should:

- Retrieve relevant policy or SOP snippets.
- Answer using only the provided sources.
- Cite the source file and snippet used.
- Abstain when the answer is not supported.
- Ask for clarification when a question is too vague.
- Use structured data for numerical questions instead of asking the language model to calculate.
