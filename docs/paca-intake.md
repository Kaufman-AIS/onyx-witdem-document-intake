# Intake → Paca (optional)

When `PACA_API_URL`, `PACA_API_KEY`, and `PACA_PROJECT_ID` are set on the intake
service, a successful Document Intake run also creates:

1. A Paca **task** titled `[doc_type] …` with Drive link in the description
2. A Paca **document** with the intake summary

Google Tasks behaviour is unchanged (parallel). Failures are loud: intake
`ok` becomes false and `error` explains the Paca sync failure (visible in
Witdem via the `intake.paca` span).

Field mapping: see
[Kaufman-AIS/ticket-workflow-system `docs/intake-paca-mapping.md`](https://github.com/Kaufman-AIS/ticket-workflow-system/blob/main/docs/intake-paca-mapping.md)
(on the feature branch until merged).

## Enable on Hostinger

Add to the intake container env (do not commit secrets):

```bash
PACA_API_URL=http://host.docker.internal:8090   # or http://172.17.0.1:8090 / public HTTPS once DNS is live
PACA_API_KEY=paca_…
PACA_PROJECT_ID=<uuid of Intake Demo project>
```

Until `paca.kaufman-ais.com` has public DNS + TLS, prefer the host gateway bind
`127.0.0.1:8090` via Docker `extra_hosts` / host network as appropriate.
