# IBM MQ — Root Cause Analysis (RCA) Template

## 1. Summary
- **Issue:** 
- **Incident Time:** YYYY-MM-DD HH:MM (timezone)
- **Severity:** Low / Medium / High
- **Environment:** Dev / QA / Stage / Prod

## 2. User Question
- (Exact question asked by engineer)

## 3. Relevant MQ Logs Retrieved
- Files retrieved:
  - AMQERR01
  - FDC files
  - Channel logs
  - Application logs
- Important snippets:
  - `AMQ9637: Channel is not available due to SSL error.`
  - `AMQ9544: Channel ended abnormally.`
  - `MQRC_NOT_AUTHORIZED (2035)`

## 4. MQ Analysis (AI / Analyst Interpretation)
- (Interpretation of logs and sequence of events)

## 5. Root Cause
- **Primary Cause Identified:** 

## 6. Evidence (Direct MQ Log References)
- (Log lines / FDC file names / timestamps)

## 7. Impact
- Messages stuck in DLQ
- Channels impacted
- Downstream flows impacted
- Start — End timestamps
- Number of messages affected

## 8. Recommended Fix (Immediate)
- (Step-by-step remediation actions with owners)

## 9. Preventive Measures
- (Monitoring, expiry alerts, runbooks, etc.)

## 10. Confidence Score
- Low / Medium / High

## 11. Engineer Feedback
- ✔️ Correct / ❌ Incorrect / 🔄 Partially Correct
- Comments:
