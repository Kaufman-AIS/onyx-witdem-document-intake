# Agency positioning: Witdem + existing agent infrastructure

## Short answer

Witdem is **not** a harness that requires redeploying agents on a new platform. It is a
**self-hosted observability and audit backend** that ingests OpenTelemetry traces and optional
business-semantics from systems you already run.

This demo proves the pattern for **Onyx as the knowledge brain**. The same boundary
instrumentation applies to LangChain services, n8n workflow steps, Slack bot backends, and
sub-agents — each exports telemetry to one Witdem receiver.

## Stack illustrated by this repo

```text
Browser → Onyx UI (https://127.0.0.1:3000 via witdem-proxy)
              → Onyx (search, tools, answer)
              → Witdem (corpus, replay, contracts)
```

In a full customer stack:

```text
Slack → n8n → Onyx → sub-agent
         │      │        │
         └──────┴────────┴── OTLP/SDK → Witdem
```

Distributed trace context (`traceparent`) links cross-service executions when each hop
participates in the same trace.

## Document intake (optional demo extension)

For the document intake flow, **Onyx decides relevance** in chat and calls the
`run_intake` custom tool when the user pastes or uploads something to file.
**Haystack executes intake** — classify → extract → Google Drive → Google Tasks → confirmation. **Witdem audits** the full run
as nested spans — Onyx is not replaced as the decision boundary, and the proxy does not
blindly start intake on every message.

## Integration depth

| Component | Witdem integration | Redeploy? |
| --- | --- | --- |
| Onyx (this demo) | HTTP API instrumentation | No |
| LangChain / LangGraph | `instrument()` wrapper | No — one line at compile boundary |
| Existing OTel apps | Point exporter at Witdem | No SDK |
| n8n | Custom node or HTTP wrapper spans | Workflow change only at boundary |
| Slack bot | Instrument the bot's backend service | No change to Slack |

## Audit capabilities (what teams avoid building)

- **Immutable corpus** of ingested telemetry
- **Execution replay** with observed paths, tools, models, latency, tokens, cost
- **Workflow analytics** — declared vs observed business stages (Witdem 0.1.4+)
- **Business outcomes** — product goals and decisions separate from “LLM returned 200”
- **Evaluation campaigns** for batch quality measurement
- **Privacy by default** — content capture off unless explicitly enabled

## What Witdem is not

- Not an agent host or orchestrator replacement
- Not a fork of Onyx, n8n, or Slack
- Not requiring migration to a single vendor platform
