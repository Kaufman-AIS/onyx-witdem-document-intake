# Onyx LLM usage patch

## Purpose

Onyx does not expose provider token usage to API clients by default. Witdem needs
`provider`, `model`, and token counts on generation spans to show cost per model
in the dashboard.

This local patch makes Onyx accumulate prompt and completion tokens across every
LLM step in a chat turn and expose the totals in two backward-compatible places:

- an `llm_usage` SSE packet immediately before the terminal `stop` packet;
- optional `llm_provider`, `llm_model`, and `usage` fields on
  `ChatFullResponse`.

Onyx only reports usage returned by the model provider. The patch does not
estimate or invent token counts. If the provider omits usage metadata, Witdem
correctly shows **Not measured** for cost.

Patch file: [`patches/onyx-llm-usage.patch`](../patches/onyx-llm-usage.patch).

## Apply

Run `setup-onyx.sh` first. After a fresh clone, replacement, or update of
`.onyx-upstream`, re-apply the saved patch:

```bash
cd examples/onyx-demo
./scripts/setup-onyx.sh
git -C .onyx-upstream apply ../patches/onyx-llm-usage.patch
```

To check whether the patch is already present without changing files:

```bash
git -C .onyx-upstream apply --reverse --check ../patches/onyx-llm-usage.patch
```

## Restart

The standard Compose stack does not bind-mount the backend source. Rebuild and
recreate `api_server` after applying the patch — a plain `docker compose restart`
of the existing image is insufficient.

```bash
cd examples/onyx-demo
docker compose \
  -f .onyx-upstream/deployment/docker_compose/docker-compose.yml \
  -f docker-compose.witdem-proxy.yml \
  build api_server
docker compose \
  -f .onyx-upstream/deployment/docker_compose/docker-compose.yml \
  -f docker-compose.witdem-proxy.yml \
  up -d --no-deps api_server
```

## Verify

Send a chat message and inspect the streaming response in the browser Network
panel or through the Witdem proxy. Before the final `stop` event, the stream
must contain a packet whose object resembles:

```json
{
  "obj": {
    "type": "llm_usage",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "prompt_tokens": 123,
    "completion_tokens": 45
  }
}
```

Token values vary by request. If the provider returns no usage metadata, Onyx
correctly omits the `llm_usage` packet.

**Witdem dashboard:** open **http://127.0.0.1:8501**, send a Knowledge-Agent chat
through the witdem-proxy (**http://127.0.0.1:3000** UI / **http://127.0.0.1:3001/api**
for scripts — not `:13000`, which bypasses the proxy), then inspect the run. When
usage is present and the model string matches the Witdem pricing catalog (for
example `gpt-4o-mini` or `gpt-5.6-sol`), the `onyx.generate` span shows input/output
tokens and cost. Unknown models still show tokens but cost stays **Not measured**
until the catalog entry exists (or you set `WITDEM_PRICING_FILE`).

The proxy reaches Witdem via the Docker network (`WITDEM_ENDPOINT=http://receiver:4318`
on `witdem_default`). If telemetry is missing, confirm the proxy is on that network
and that `contracts/` is present in the proxy image.
