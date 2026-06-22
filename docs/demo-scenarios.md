# Demo scenarios

Five ready-to-run conversations. Start the API (`uvicorn app.main:app --reload`)
and use the `curl` snippets, Swagger, or the Telegram bot. Use the **same
`session_id`** within a scenario to exercise memory.

> All responses below are illustrative (demo / mock mode is deterministic but
> phrasing may differ slightly).

## 1. Ask about agency services
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s1","user_message":"What services do you offer?"}'
```
> `intent: service_question`, answer grounded in `services.md`, `sources: ["services.md", ...]`.

## 2. Ask about pricing
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s2","user_message":"How much does the Growth package cost?"}'
```
> `intent: pricing_question`, answer from `pricing.md`.

## 3. Become a lead (launch an ad campaign)
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s3","user_message":"I want to launch a Google Ads campaign for my store."}'
# > intent: create_lead, agent asks for name + contact (collect_missing_info)

curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s3","user_message":"My name is Sam Carter, email sam@store.example, budget $3,000/mo."}'
# > action_taken: created_lead, created_lead_id: <id>
```
Verify: `curl localhost:8000/crm/leads`.

## 4. Out-of-scope question > escalation
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s4","user_message":"I have a billing dispute, can I speak to a manager?"}'
```
> `intent: human_escalation`, `escalated: true`, `created_ticket_id: <id>`.
Verify: `curl localhost:8000/tickets`.

## 5. Follow-up that uses memory
```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s5","user_message":"Im interested in SEO, my name is Priya."}'
# agent remembers name + service interest

curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s5","user_message":"You can reach me at priya@studio.example"}'
# > lead created using remembered name + service from the earlier message
```

Check aggregate impact any time: `curl localhost:8000/metrics/demo`.
