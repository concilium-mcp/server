<p align="center">
  <img src="docs/assets/hero.png" alt="MCP RAG API" width="280" />
</p>

<h1 align="center">MCP RAG API</h1>

<p align="center">
  <strong>English</strong> · <a href="README.pt-BR.md">Português</a> · <a href="README.es.md">Español</a>
</p>

A Python **MCP** server and **REST API** built on **PostgreSQL + pgvector**. It gives your AI agents two things:

- **Knowledge base (RAG):** documents that any agent can query, insert and update, with semantic and keyword search, versioning and duplicate warnings.
- **Agent registry:** each agent has a profile (instructions), memory, session summaries and tasks stored in the database. A new chat loads all of that and picks up where the last one left off.

You manage everything **by talking to Claude**: registering agents, adjusting rules, approving changes and granting autonomy.

> Architecture and design decisions: [PLANO.md](PLANO.md) (Portuguese)

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Configuration (.env)](#3-configuration-env)
4. [Authentication](#4-authentication)
5. [Running the server](#5-running-the-server)
6. [Connecting to Claude](#6-connecting-to-claude)
7. [Tutorial: first use](#7-tutorial-first-use)
8. [Tutorial: registering and using an agent](#8-tutorial-registering-and-using-an-agent)
9. [Tutorial: autonomy and proposals](#9-tutorial-autonomy-and-proposals)
10. [Using the REST API](#10-using-the-rest-api)
11. [Reference](#11-reference)
12. [Maintenance](#12-maintenance)
13. [Common problems](#13-common-problems)
14. [Production deployment (Coolify)](#14-production-deployment-coolify)
15. [License](#15-license)

---

## 1. Prerequisites

| What | Why | How to check |
|---|---|---|
| DB-DOCKER **Postgres** running | database (container `db-postgres`, pgvector image, port 5432) | `docker ps --filter name=db-postgres` |
| [uv](https://docs.astral.sh/uv/) | installs Python and the dependencies | `uv --version` |
| Docker | only if you will run the API in a container | `docker --version` |
| Claude Code (or Claude Desktop) | to talk to the MCP server | `claude --version` |
| An embeddings provider key | to turn text into vectors | see [step 3](#3-configuration-env) |

This project **does not start its own database**: it uses a `kb` database inside the shared Postgres.

## 2. Installation

```bash
cd /mnt/l/Workspace/PERSON/concilium/server

# creates the project database in the shared Postgres (first time only)
docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb"

# installs the dependencies
uv sync
```

Tables are created automatically the first time the server starts.

## 3. Configuration (.env)

```bash
cp .env.example .env
```

Open `.env` and set **at least** the embeddings provider:

| `EMBEDDING_PROVIDER` | Requires | Notes |
|---|---|---|
| `voyage` (default) | `VOYAGE_API_KEY` | key from voyageai.com |
| `openai` | `OPENAI_API_KEY` | model `text-embedding-3-small` |
| `local` | `uv sync --extra local` | runs on your machine (BAAI/bge-m3 model, ~2 GB, good at Portuguese); free, slower |
| `fake` | nothing | **only to test the installation**: search has no semantic understanding |

Example:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/kb
EMBEDDING_PROVIDER=voyage
VOYAGE_API_KEY=pa-xxxxxxxx
```

> ⚠️ Choose the provider before inserting documents. Vectors from different providers are not compatible, and there is no reindex command yet.

Other `.env` options (the defaults usually work):

| Variable | Default | Purpose |
|---|---|---|
| `KB_API_KEY` | (empty) | the server's single key — required in production; see [step 4](#4-authentication) |
| `KB_AUTH_DISABLED` | `false` | `true` allows everything without a key — **development only** |
| `CHUNK_WORDS` / `CHUNK_OVERLAP_WORDS` | 450 / 60 | size of the pieces documents are split into |
| `DUPLICATE_THRESHOLD` | 0.92 | similarity at which `add_document` warns that the content is a duplicate |
| `LOAD_AGENT_MEMORY_LIMIT` | 15 | how many memories the agent receives when starting a chat |

## 4. Authentication

This server has **a single key**, defined in `.env`:

```env
KB_API_KEY=put-a-long-random-key-here
```

Generate a strong one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Every access — REST and MCP, HTTP and stdio — requires the `Authorization: Bearer <KB_API_KEY>` header (except `/health`). In development you can set `KB_AUTH_DISABLED=true` in `.env` to operate without the header.

## 5. Running the server

**Option A: local (development)**

```bash
uv run mcp-rag-api serve            # add --reload to restart when the code changes
```

**Option B: Docker (API only; the database is still `db-postgres`; uses the same `Dockerfile.coolify` as production)**

```bash
docker compose up -d --build
docker compose logs -f api
```

To check it is up:

```bash
curl http://localhost:8000/health        # {"status":"ok"}
```

- Interactive REST API docs: http://localhost:8000/docs
- MCP endpoint: http://localhost:8000/mcp

## 6. Connecting to Claude

### Claude Code

```bash
claude mcp add --transport http kb http://localhost:8000/mcp \
  --header "Authorization: Bearer $KB_API_KEY"
```

Check with `claude mcp list` (`kb` should show as connected). Inside Claude Code, the `/mcp` command shows the tools.

### Claude Desktop (Windows, with the project on WSL)

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kb": {
      "command": "wsl",
      "args": ["-e", "bash", "-lc", "cd /mnt/l/Workspace/PERSON/concilium/server && uv run mcp-rag-api stdio"]
    }
  }
}
```

Restart Claude Desktop. In this mode (stdio) the HTTP server does not need to be running: the Desktop starts the process itself, and authentication uses the `KB_API_KEY` from `.env`.

### Your own agents (Claude API / Agent SDK)

Point the MCP client to `https://YOUR_DOMAIN/mcp` with the `Authorization: Bearer <KB_API_KEY>` header. For production, see [deploying on Coolify](#14-production-deployment-coolify).

## 7. Tutorial: first use

With Claude Code connected (step 6), just talk normally. The examples below are requests you type in the chat, followed by the tool Claude calls.

**1. Create a collection**
> Create a collection called "manuals" for our internal manuals.

→ `create_collection`

**2. Insert knowledge**
> Add to the manuals collection: "Refund policy: customers can request a refund within 7 days of purchase, through the portal, informing the order number."

→ `add_document`. If something very similar already exists, the server **does not duplicate**: it returns the similar document, and Claude suggests updating that one instead.

**3. Query**
> What is the refund window? Answer citing the source.

→ `search_knowledge`. The answer comes with title and `document_id`. The `/mcp__kb__answer_with_sources` prompt already instructs Claude to answer this way.

**4. Update**
> The refund window changed to 30 days, update the document.

→ `update_document` with `change_note`. This creates version 2, and the previous one stays in history (`document_history`).

**5. Sync from another system**
Use `upsert_document` with an `external_id` (for example, the id in your CRM). If the document already exists, it is updated; if not, it is created.

## 8. Tutorial: registering and using an agent

### 8.1 Registering, by talking to Claude

In Claude Code connected with the `KB_API_KEY`, type:

```
/mcp__kb__design_agent
```

or simply:

> Register a post-sales support agent, cordial tone, that only uses the manuals collection and never promises a refund without checking the policy.

Claude will:
1. ask whatever is missing (goal, tone, rules, collections, permissions, autonomy);
2. show you the assembled profile (slug, system prompt, collections and scopes) and **ask for your confirmation**;
3. call `create_agent` and hand you the agent's **slug**.

To use the agent, the connection is the same as always (`KB_API_KEY` is the server's only key): connect the MCP client and ask Claude to start as the agent with the `start_as_agent <slug>` prompt (or the `/mcp__kb__start_as_agent <slug>` command), which calls `load_agent` and assumes its profile.

You can seed memories and tasks at the same time:
> Add to the support agent the memory "client ACME prefers WhatsApp" and the task "review the FAQ by Friday".

→ `add_agent_memory` and `add_agent_task`

### 8.2 Using the agent

In a chat connected to the server, ask: *"load your profile"* and provide the slug (or use `/mcp__kb__start_as_agent support`). Claude calls `load_agent` and receives:
- the profile (system prompt, version, rules);
- the most important memories;
- the **last session summary** and the next steps;
- the open tasks.

During the work, the agent uses:

| Situation | Tool |
|---|---|
| query the knowledge base | `search_knowledge` |
| remember something specific | `recall` |
| learned something durable | `remember` (if a similar memory already exists, it is updated instead of duplicated) |
| wrong memory | `forget` (deletes or fixes) |
| new or completed task | `upsert_task` |
| end of chat or a milestone | `save_session` with summary and next steps |

The next day, in another chat (or another tool), `load_agent` brings it all back.

> Tip: the `/mcp__kb__save_learning` prompt asks the agent to review the conversation and save memories, documents, tasks and the summary in one go.

### 8.3 Adjusting the agent later

With the `KB_API_KEY`:

| Request in the chat | Tool |
|---|---|
| "In the support agent, add the rule: always confirm the order number." | `update_agent` (creates a new version) |
| "Show the support agent's history." | `get_agent` |
| "Roll support back to version 2." | `restore_agent_version` |
| "Create a support-vip agent from support, with a more formal tone." | `clone_agent` |
| "Deactivate the support agent." | `archive_agent` |

### 8.4 Optional: Claude Code subagents

```bash
uv run mcp-rag-api sync-agents
```

Generates `.claude/agents/<slug>.md` from the database, to use the agents as Claude Code subagents. The source of truth remains the database: run it again after changing an agent.

## 9. Tutorial: autonomy and proposals

An agent can suggest changes to its own profile with `propose_agent_update`. What happens depends on **autonomy**, which only you control:

| Autonomy | What happens to the proposal |
|---|---|
| **off** (default) | stays pending until you approve it |
| **on** | is applied right away as a new version (and remains in history) |

Requests in the chat, with the `KB_API_KEY`:

> Let the support agent update itself.

→ `set_agent_autonomy(auto_apply_updates=true)`

> Turn off support's self-updates.

> Is there a pending change proposal?

→ `list_agent_proposals`

> Approve proposal 3. / Reject proposal 4, reason: tone too informal.

→ `review_agent_update`

**Safety locks:** the agent can **never** turn on its own autonomy nor change its own permissions or collections. Those fields are ignored in its proposals, and the management tools require the `agents:manage` scope.

## 10. Using the REST API

All routes require `Authorization: Bearer <KB_API_KEY>`. The full list, with a test form, is at http://localhost:8000/docs.

```bash
KEY=$KB_API_KEY
API=http://localhost:8000

# search
curl -s -X POST $API/search -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"query": "refund window", "top_k": 3}'

# insert a document
curl -s -X POST $API/documents -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"collection": "manuals", "title": "Opening hours", "content": "Support from 8am to 6pm."}'

# create/update by external id (sync)
curl -s -X PUT $API/documents/upsert -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"collection": "manuals", "external_id": "crm-42", "title": "Contact", "content": "Extension 200."}'

# agent context (same response as load_agent)
curl -s $API/agents/support/context -H "Authorization: Bearer $KEY"

# turn on autonomy
curl -s -X PUT $API/agents/support/autonomy -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"auto_apply_updates": true}'
```

## 11. Reference

### Authentication and scopes

This lean version of the server accepts **only the single key from `.env`** (`KB_API_KEY`), which operates with the `admin` scope — that is, everything is allowed. There is no per-agent key issuance.

The scopes below still exist **on each agent's profile** (`agents.scopes`, `agents.allowed_collections`): they document the agent's intended permissions and are used by the full version (web-server), but they do not restrict access on this server:

| Scope | Allows |
|---|---|
| `read` | query the knowledge base; read and write its own memory, sessions and tasks |
| `write` | insert and update documents (includes `read`) |
| `agents:manage` | register and configure agents, approve proposals, turn on autonomy |
| `admin` | everything, including granting `agents:manage` or `admin` to an agent |

### MCP tools

| Group | Tools |
|---|---|
| Knowledge base | `search_knowledge`, `get_document`, `list_documents`, `list_collections`, `create_collection`, `add_document`, `update_document`, `upsert_document`, `archive_document`, `document_history` |
| Agent (self) | `load_agent`, `recall`, `remember`, `forget`, `save_session`, `list_sessions`, `list_tasks`, `upsert_task`, `propose_agent_update` |
| Management (`agents:manage`) | `create_agent`, `update_agent`, `set_agent_autonomy`, `get_agent`, `list_agents`, `clone_agent`, `archive_agent`, `restore_agent_version`, `list_agent_proposals`, `review_agent_update`, `add_agent_memory`, `add_agent_task` |

**Prompts:** `design_agent`, `start_as_agent`, `answer_with_sources`, `save_learning`.
**Resource:** `agent://{slug}/context`.

### Commands

| Command | What it does |
|---|---|
| `uv run mcp-rag-api serve [--port 8000] [--reload]` | REST API + MCP over HTTP |
| `uv run mcp-rag-api stdio` | MCP over stdio (uses `KB_API_KEY`) |
| `uv run mcp-rag-api migrate` | applies pending migrations (`serve` already does this) |
| `uv run mcp-rag-api sync-agents [--out .claude/agents]` | exports the agents for Claude Code |
| `uv run mcp-rag-api cleanup` | removes expired memories |

## 12. Maintenance

**Expired memory cleanup.** Schedule the command, for example in `crontab -e`:

```cron
0 3 * * * cd /mnt/l/Workspace/PERSON/concilium/server && /home/oadri/.local/bin/uv run mcp-rag-api cleanup
```

**Backup** of the `kb` database:

```bash
docker exec db-postgres pg_dump -U user -d kb -Fc > kb_$(date +%F).dump
# restore:
docker exec -i db-postgres pg_restore -U user -d kb --clean < kb_2026-09-29.dump
```

**Audit.** Every write lands in the `audit_log` table (who, what, when):

```bash
docker exec db-postgres psql -U user -d kb -c "SELECT created_at, actor, action, target FROM audit_log ORDER BY id DESC LIMIT 20"
```

**Tests:**

```bash
uv sync --extra dev
uv run pytest tests/unit
# integration: the target database is WIPED on every run
docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb_test"   # once
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/kb_test uv run pytest tests/integration
```

## 13. Common problems

| Symptom | Likely cause | Fix |
|---|---|---|
| `database "kb" does not exist` | database not created | `docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb"` |
| `connection refused` on port 5432 | `db-postgres` stopped | start the DB-DOCKER compose |
| `extension "vector" is not available` | Postgres without pgvector | use the `pgvector/pgvector` image (the one `db-postgres` uses) |
| `VOYAGE_API_KEY not configured` (or OpenAI) | missing key in `.env` | fill the key or change `EMBEDDING_PROVIDER` |
| `Invalid API key` | the `Bearer` does not match the `KB_API_KEY` from `.env` | check the variable and the header |
| `401` on `/mcp` | missing or invalid key: the whole `/mcp` requires a key, even to list tools | check the `Authorization: Bearer <KB_API_KEY>` header |
| `No access to collection 'x'` | collection outside the agent's `allowed_collections` | adjust with `update_agent` |
| Search returns unrelated things | `EMBEDDING_PROVIDER=fake` | use a real provider |
| API in Docker cannot reach the database | container outside the `db_network` network | check `docker network ls` and the network name in `docker-compose.yml` |
| Port 8000 busy | another service using the port | `uv run mcp-rag-api serve --port 8010` and adjust `claude mcp add` |
| Claude does not see the tools | server down or wrong header | `curl localhost:8000/health`, `claude mcp list`, check the `Bearer` |

## 14. Production deployment (Coolify)

**Zero-Git** flow, same as the other projects: GitLab CI tests, builds the image (`Dockerfile.coolify`) and publishes it to the GitLab Registry. Coolify only pulls the image and starts the container — no source code on the VPS.

```
push to main → test:pytest → build:push (registry) → deploy:coolify (webhook) → Coolify pulls and starts
```

### 14.1 Database: Postgres with pgvector on Coolify

There is no local `db-postgres` in production. Create a database in Coolify:

1. **+ New → Database → PostgreSQL**.
2. In **Configuration → Image**, switch to `pgvector/pgvector:pg16`. The default Postgres image **does not have** the `vector` extension, and without it the migrations fail.
3. Save and start the database. Note the **Postgres URL (internal)**, something like `postgres://postgres:PASSWORD@<uuid>:5432/postgres`.

If you already have a Postgres with pgvector on Coolify, just create a new database on it (`CREATE DATABASE kb`) and use the internal URL pointing to `/kb`.

### 14.2 GitLab

1. Push the project to a GitLab repository (branch `main`).
2. In **Settings → CI/CD → Variables**, create:

| Variable | Value |
|---|---|
| `COOLIFY_WEBHOOK` | `https://<coolify>/api/v1/deploy?uuid=<APP-UUID>&force=false` (fill it in after creating the app, in step 14.3) |
| `COOLIFY_SECRET` | Coolify token with deploy permission (**Keys & Tokens → API tokens**) |
| `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` | optional, if Coolify is behind Cloudflare Access |
| `INSTALL_LOCAL_EMBEDDINGS` | optional, `true` to include the local model in the image (much larger) |

3. In **Settings → Repository → Deploy tokens**, create a token with `read_registry`. Coolify uses this token to pull the image.

The first push to `main` already runs the tests (unit and integration, with a temporary pgvector Postgres in CI) and publishes `registry.gitlab.com/<group>/mcp-rag-api:latest`.

### 14.3 Application on Coolify

1. **+ New → Docker Image**, with the image `registry.gitlab.com/<group>/mcp-rag-api:latest`.
   - Private registry: register the GitLab deploy token on the server (`docker login registry.gitlab.com`) or in the Coolify registry credentials.
2. **Ports Exposes:** `8000`.
3. **Domains:** `https://kb.yourdomain.com`. Coolify/Traefik handles SSL.
4. **Health check:** enable it, with path `/health` and port `8000`. The image also has its own `HEALTHCHECK`.
5. **Environment Variables:**

| Variable | Example |
|---|---|
| `DATABASE_URL` | **internal** URL of the Postgres from step 14.1 (swap `postgres://` for `postgresql://` if you prefer; both work) |
| `EMBEDDING_PROVIDER` | `voyage` |
| `VOYAGE_API_KEY` or `OPENAI_API_KEY` | provider key |
| `KB_API_KEY` | single strong key (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `KB_AUTH_DISABLED` | **do not set** in production (default `false`) |

6. **Deploy.** Migrations run on their own at startup. Copy the app's **Deploy Webhook** into the `COOLIFY_WEBHOOK` GitLab variable.
7. Keep **1 replica**. The app holds no state between requests (stateless), but two replicas starting together would race the migrations.

### 14.4 Authentication in production

The server's only key is the `KB_API_KEY`, defined in the app's **Environment Variables** on Coolify (step 14.3). Generate a strong one, save it and deploy. To connect:

```bash
curl https://kb.yourdomain.com/health          # {"status":"ok"}
claude mcp add --transport http kb https://kb.yourdomain.com/mcp \
  --header "Authorization: Bearer $KB_API_KEY"
```

From there, everything follows tutorials 7 to 9.

### 14.5 Care

- **Security:** the whole `/mcp` requires a valid key (without a key it answers `401`, even to list tools). The REST API also requires a key; only `/health` is public.
- **Cloudflare Access:** if the domain is protected by Access, MCP clients (Claude Code, Desktop, API) do not pass the login screen. Create a *Bypass* rule for `kb.yourdomain.com/mcp` and `/health`; authentication is handled by the `KB_API_KEY`.
- **Local embeddings:** with `INSTALL_LOCAL_EMBEDDINGS=true` the image includes PyTorch and the model needs about 2–3 GB of RAM. Prefer `voyage` or `openai` on a small VPS.
- **Backup:** enable scheduled database backups in Coolify (**Database → Backups**).
- **Expired memory cleanup:** in the app's **Scheduled Tasks**, create `mcp-rag-api cleanup` with schedule `0 3 * * *`.

### 14.6 Testing the production image locally

```bash
docker build -f Dockerfile.coolify -t mcp-rag-api:local .
docker run --rm --network db_network -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:password@db-postgres:5432/kb \
  --env-file .env mcp-rag-api:local
```

## 15. License

This project is open source, under the [Apache License 2.0](LICENSE).
