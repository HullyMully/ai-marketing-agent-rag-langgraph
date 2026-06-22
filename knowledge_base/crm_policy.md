# NovaGrowth Agency – CRM & Lead Qualification Policy

> Internal synthetic policy for a fictional agency.

## Lead Qualification Criteria
A contact becomes a qualified lead when we can capture:
- **Name** of the person
- **Contact** (email or phone)
- **Service interest** (what they want help with)
- Ideally a **company** name and a rough **budget range**

If budget is unknown, still create the lead and mark budget as "unspecified".

## Required Fields to Create a Lead
At minimum: **name** and **contact**. The assistant should ask short follow-up
questions to collect any missing required fields before creating the lead.

## Lead Statuses
- **new**: just captured by the assistant.
- **contacted**: a human has reached out.
- **qualified**: fits our ICP and budget.
- **disqualified**: out of scope (e.g., enterprise-only need).

## Data Handling
- Only store business contact details the user voluntarily provides.
- Never store passwords, full payment-card numbers, or other sensitive data.
- All demo data in this project is synthetic.

## Budget Guidance
- Under $1,500/month: suggest the Starter package or a one-time project.
- $1,500–$5,000/month: Growth package.
- Above $5,000/month: Scale or a custom retainer.
