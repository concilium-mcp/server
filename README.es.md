<p align="center">
  <img src="docs/assets/hero.png" alt="MCP RAG API" width="280" />
</p>

<h1 align="center">MCP RAG API</h1>

<p align="center">
  <a href="README.md">English</a> · <a href="README.pt-BR.md">Português</a> · <strong>Español</strong>
</p>

Un servidor **MCP** y una **API REST** en Python, con **PostgreSQL + pgvector**. Ofrece dos cosas a tus agentes de IA:

- **Base de conocimiento (RAG):** documentos que cualquier agente puede consultar, insertar y actualizar, con búsqueda semántica y por palabra clave, versionado y aviso de duplicados.
- **Registro de agentes:** cada agente tiene perfil (instrucciones), memoria, resúmenes de sesión y tareas guardados en la base de datos. Un chat nuevo carga todo eso y continúa donde lo dejó.

Todo se gestiona **conversando con Claude**: registrar agentes, ajustar reglas, aprobar cambios y conceder autonomía.

> Arquitectura y decisiones: [PLANO.md](PLANO.md) (en portugués)

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación](#2-instalación)
3. [Configuración (.env)](#3-configuración-env)
4. [Autenticación](#4-autenticación)
5. [Ejecutar el servidor](#5-ejecutar-el-servidor)
6. [Conectar con Claude](#6-conectar-con-claude)
7. [Tutorial: primer uso](#7-tutorial-primer-uso)
8. [Tutorial: registrar y usar un agente](#8-tutorial-registrar-y-usar-un-agente)
9. [Tutorial: autonomía y propuestas](#9-tutorial-autonomía-y-propuestas)
10. [Usar la API REST](#10-usar-la-api-rest)
11. [Referencia](#11-referencia)
12. [Mantenimiento](#12-mantenimiento)
13. [Problemas comunes](#13-problemas-comunes)
14. [Despliegue en producción (Coolify)](#14-despliegue-en-producción-coolify)
15. [Licencia](#15-licencia)

---

## 1. Requisitos previos

| Qué | Para qué | Cómo comprobarlo |
|---|---|---|
| Postgres del **DB-DOCKER** en marcha | base de datos (contenedor `db-postgres`, imagen pgvector, puerto 5432) | `docker ps --filter name=db-postgres` |
| [uv](https://docs.astral.sh/uv/) | instala Python y las dependencias | `uv --version` |
| Docker | solo si vas a ejecutar la API en contenedor | `docker --version` |
| Claude Code (o Claude Desktop) | conversar con el MCP | `claude --version` |
| Clave de un proveedor de embeddings | transformar texto en vectores | ver el [paso 3](#3-configuración-env) |

Este proyecto **no levanta base de datos propia**: usa una base de datos `kb` dentro del Postgres compartido.

## 2. Instalación

```bash
cd /mnt/l/Workspace/PERSON/concilium/server

# crea la base de datos del proyecto en el Postgres compartido (solo la primera vez)
docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb"

# instala las dependencias
uv sync
```

Las tablas se crean solas la primera vez que el servidor arranca.

## 3. Configuración (.env)

```bash
cp .env.example .env
```

Abre el `.env` y define **al menos** el proveedor de embeddings:

| `EMBEDDING_PROVIDER` | Necesita | Observación |
|---|---|---|
| `voyage` (predeterminado) | `VOYAGE_API_KEY` | clave en voyageai.com |
| `openai` | `OPENAI_API_KEY` | modelo `text-embedding-3-small` |
| `local` | `uv sync --extra local` | se ejecuta en tu máquina (modelo BAAI/bge-m3, ~2 GB, bueno en portugués); gratis, más lento |
| `fake` | nada | **solo para probar la instalación**: la búsqueda no entiende significado |

Ejemplo:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/kb
EMBEDDING_PROVIDER=voyage
VOYAGE_API_KEY=pa-xxxxxxxx
```

> ⚠️ Elige el proveedor antes de insertar documentos. Los vectores de proveedores distintos no son compatibles, y todavía no existe un comando de reindexación.

Otras opciones del `.env` (los valores predeterminados suelen valer):

| Variable | Predeterminado | Para qué |
|---|---|---|
| `KB_API_KEY` | (vacío) | la clave única del servidor — obligatoria en producción; ver el [paso 4](#4-autenticación) |
| `KB_AUTH_DISABLED` | `false` | `true` permite todo sin clave — **solo en desarrollo** |
| `CHUNK_WORDS` / `CHUNK_OVERLAP_WORDS` | 450 / 60 | tamaño de los fragmentos en los que se dividen los documentos |
| `DUPLICATE_THRESHOLD` | 0.92 | similitud a partir de la cual `add_document` avisa de que el contenido está duplicado |
| `LOAD_AGENT_MEMORY_LIMIT` | 15 | cuántas memorias recibe el agente al iniciar un chat |

## 4. Autenticación

Este servidor tiene **una sola clave**, definida en el `.env`:

```env
KB_API_KEY=pon-una-clave-larga-y-aleatoria
```

Genera una clave segura con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Todo acceso — REST y MCP, HTTP y stdio — exige el header `Authorization: Bearer <KB_API_KEY>` (excepto `/health`). En desarrollo puedes poner `KB_AUTH_DISABLED=true` en el `.env` para operar sin el header.

## 5. Ejecutar el servidor

**Opción A: local (desarrollo)**

```bash
uv run mcp-rag-api serve            # añade --reload para reiniciar al editar el código
```

**Opción B: Docker (solo la API; la base de datos sigue siendo `db-postgres`; usa el mismo `Dockerfile.coolify` de producción)**

```bash
docker compose up -d --build
docker compose logs -f api
```

Para comprobar que está en marcha:

```bash
curl http://localhost:8000/health        # {"status":"ok"}
```

- Documentación interactiva de la API REST: http://localhost:8000/docs
- Endpoint MCP: http://localhost:8000/mcp

## 6. Conectar con Claude

### Claude Code

```bash
claude mcp add --transport http kb http://localhost:8000/mcp \
  --header "Authorization: Bearer $KB_API_KEY"
```

Compruébalo con `claude mcp list` (debería aparecer `kb` conectado). Dentro de Claude Code, el comando `/mcp` muestra las tools.

### Claude Desktop (Windows, con el proyecto en WSL)

Edita `%APPDATA%\Claude\claude_desktop_config.json`:

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

Reinicia Claude Desktop. En este modo (stdio) el servidor HTTP no necesita estar en marcha: el Desktop inicia el proceso él solo, y la autenticación usa el `KB_API_KEY` del `.env`.

### Tus propios agentes (Claude API / Agent SDK)

Apunta el cliente MCP a `https://TU_DOMINIO/mcp` con el header `Authorization: Bearer <KB_API_KEY>`. Para producción, ver el [despliegue en Coolify](#14-despliegue-en-producción-coolify).

## 7. Tutorial: primer uso

Con Claude Code conectado (paso 6), conversa normalmente. Los ejemplos de abajo son peticiones que escribes en el chat, seguidas de la tool que Claude invoca.

**1. Crear una colección**
> Crea una colección llamada "manuales" para nuestros manuales internos.

→ `create_collection`

**2. Insertar conocimiento**
> Añade a la colección manuales: "Política de reembolso: el cliente puede pedir reembolso hasta 7 días después de la compra, por el portal, indicando el número de pedido."

→ `add_document`. Si ya existe algo muy parecido, el servidor **no duplica**: devuelve el documento similar, y Claude sugiere actualizar ese documento.

**3. Consultar**
> ¿Cuál es el plazo de reembolso? Responde citando la fuente.

→ `search_knowledge`. La respuesta viene con título y `document_id`. El prompt `/mcp__kb__answer_with_sources` ya instruye a Claude a responder así.

**4. Actualizar**
> El plazo de reembolso cambió a 30 días, actualiza el documento.

→ `update_document` con `change_note`. Esto genera la versión 2, y la anterior queda en el historial (`document_history`).

**5. Sincronizar desde otro sistema**
Usa `upsert_document` con un `external_id` (por ejemplo, el id en el CRM). Si el documento ya existe, se actualiza; si no, se crea.

## 8. Tutorial: registrar y usar un agente

### 8.1 Registro, conversando con Claude

En Claude Code conectado con el `KB_API_KEY`, escribe:

```
/mcp__kb__design_agent
```

o simplemente:

> Registra un agente de soporte posventa, tono cordial, que solo usa la colección manuales y nunca promete reembolso sin consultar la política.

Claude va a:
1. preguntar lo que falte (objetivo, tono, reglas, colecciones, permisos, autonomía);
2. mostrarte el perfil montado (slug, system prompt, colecciones y scopes) y **pedir tu confirmación**;
3. llamar a `create_agent` y entregarte el **slug** del agente registrado.

Para usar el agente, la conexión es la misma de siempre (el `KB_API_KEY` es la única clave del servidor): conecta el cliente MCP y pide a Claude que inicie como el agente con el prompt `start_as_agent <slug>` (o el comando `/mcp__kb__start_as_agent <slug>`), que llama a `load_agent` y asume su perfil.

Puedes sembrar memorias y tareas en el mismo momento:
> Añade al agente soporte la memoria "el cliente ACME prefiere WhatsApp" y la tarea "revisar el FAQ antes del viernes".

→ `add_agent_memory` y `add_agent_task`

### 8.2 Usar el agente

En un chat conectado al servidor, pide: *"carga tu perfil"* e indica el slug (o usa `/mcp__kb__start_as_agent soporte`). Claude llama a `load_agent` y recibe:
- el perfil (system prompt, versión, reglas);
- las memorias más importantes;
- el **resumen de la última sesión** y los próximos pasos;
- las tareas abiertas.

Durante el trabajo, el agente usa:

| Situación | Tool |
|---|---|
| consultar la base | `search_knowledge` |
| recordar algo específico | `recall` |
| aprendió algo duradero | `remember` (si ya existe una memoria parecida, se actualiza en lugar de duplicarse) |
| memoria errónea | `forget` (borra o corrige) |
| tarea nueva o completada | `upsert_task` |
| fin del chat o un hito | `save_session` con resumen y próximos pasos |

Al día siguiente, en otro chat (u otra herramienta), `load_agent` lo trae todo de vuelta.

> Consejo: el prompt `/mcp__kb__save_learning` pide al agente que revise la conversación y guarde memorias, documentos, tareas y el resumen de una vez.

### 8.3 Ajustar el agente después

Con el `KB_API_KEY`:

| Petición en el chat | Tool |
|---|---|
| "En el agente soporte, añade la regla: confirmar siempre el número de pedido." | `update_agent` (genera una nueva versión) |
| "Muestra el historial del agente soporte." | `get_agent` |
| "Vuelve a poner soporte en la versión 2." | `restore_agent_version` |
| "Crea un agente soporte-vip a partir de soporte, con un tono más formal." | `clone_agent` |
| "Desactiva el agente soporte." | `archive_agent` |

### 8.4 Opcional: subagentes de Claude Code

```bash
uv run mcp-rag-api sync-agents
```

Genera `.claude/agents/<slug>.md` a partir de la base de datos, para usar los agentes como subagentes de Claude Code. La fuente de la verdad sigue siendo la base de datos: ejecútalo de nuevo después de cambiar un agente.

## 9. Tutorial: autonomía y propuestas

Un agente puede sugerir cambios en su propio perfil con `propose_agent_update`. Lo que pasa depende de la **autonomía**, que solo tú controlas:

| Autonomía | Qué pasa con la propuesta |
|---|---|
| **desactivada** (predeterminado) | queda pendiente hasta que la apruebes |
| **activada** | se aplica enseguida como nueva versión (y queda en el historial) |

Peticiones en el chat, con el `KB_API_KEY`:

> Deja que el agente soporte se actualice solo.

→ `set_agent_autonomy(auto_apply_updates=true)`

> Desactiva la autoactualización de soporte.

> ¿Hay alguna propuesta de cambio pendiente?

→ `list_agent_proposals`

> Aprueba la propuesta 3. / Rechaza la propuesta 4, motivo: tono demasiado informal.

→ `review_agent_update`

**Bloqueos de seguridad:** el agente **nunca** puede activar su propia autonomía ni cambiar sus propios permisos o colecciones. Esos campos se ignoran en sus propuestas, y las tools de gestión exigen el scope `agents:manage`.

## 10. Usar la API REST

Todas las rutas exigen `Authorization: Bearer <KB_API_KEY>`. La lista completa, con formulario de prueba, está en http://localhost:8000/docs.

```bash
KEY=$KB_API_KEY
API=http://localhost:8000

# buscar
curl -s -X POST $API/search -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"query": "plazo de reembolso", "top_k": 3}'

# insertar documento
curl -s -X POST $API/documents -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"collection": "manuales", "title": "Horario", "content": "Atención de 8h a 18h."}'

# crear/actualizar por id externo (sincronización)
curl -s -X PUT $API/documents/upsert -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"collection": "manuales", "external_id": "crm-42", "title": "Contacto", "content": "Extensión 200."}'

# contexto de un agente (misma respuesta que load_agent)
curl -s $API/agents/soporte/context -H "Authorization: Bearer $KEY"

# activar la autonomía
curl -s -X PUT $API/agents/soporte/autonomy -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"auto_apply_updates": true}'
```

## 11. Referencia

### Autenticación y scopes

Esta versión reducida del servidor acepta **solo la clave única del `.env`** (`KB_API_KEY`), que opera con scope `admin` — es decir, todo permitido. No existe emisión de claves por agente.

Los scopes de abajo siguen existiendo **en el perfil de cada agente** (`agents.scopes`, `agents.allowed_collections`): documentan la intención de permiso del agente y los usa la versión completa (web-server), pero no restringen el acceso en este servidor:

| Scope | Permite |
|---|---|
| `read` | consultar la base; leer y escribir su propia memoria, sesiones y tareas |
| `write` | insertar y actualizar documentos (incluye `read`) |
| `agents:manage` | registrar y configurar agentes, aprobar propuestas, activar la autonomía |
| `admin` | todo, incluido conceder `agents:manage` o `admin` a un agente |

### Tools MCP

| Grupo | Tools |
|---|---|
| Base | `search_knowledge`, `get_document`, `list_documents`, `list_collections`, `create_collection`, `add_document`, `update_document`, `upsert_document`, `archive_document`, `document_history` |
| Agente (sobre sí mismo) | `load_agent`, `recall`, `remember`, `forget`, `save_session`, `list_sessions`, `list_tasks`, `upsert_task`, `propose_agent_update` |
| Gestión (`agents:manage`) | `create_agent`, `update_agent`, `set_agent_autonomy`, `get_agent`, `list_agents`, `clone_agent`, `archive_agent`, `restore_agent_version`, `list_agent_proposals`, `review_agent_update`, `add_agent_memory`, `add_agent_task` |

**Prompts:** `design_agent`, `start_as_agent`, `answer_with_sources`, `save_learning`.
**Resource:** `agent://{slug}/context`.

### Comandos

| Comando | Qué hace |
|---|---|
| `uv run mcp-rag-api serve [--port 8000] [--reload]` | API REST + MCP por HTTP |
| `uv run mcp-rag-api stdio` | MCP por stdio (usa `KB_API_KEY`) |
| `uv run mcp-rag-api migrate` | aplica migraciones pendientes (`serve` ya lo hace) |
| `uv run mcp-rag-api sync-agents [--out .claude/agents]` | exporta los agentes para Claude Code |
| `uv run mcp-rag-api cleanup` | elimina memorias expiradas |

## 12. Mantenimiento

**Limpieza de memorias expiradas.** Programa el comando, por ejemplo en `crontab -e`:

```cron
0 3 * * * cd /mnt/l/Workspace/PERSON/concilium/server && /home/oadri/.local/bin/uv run mcp-rag-api cleanup
```

**Copia de seguridad** de la base de datos `kb`:

```bash
docker exec db-postgres pg_dump -U user -d kb -Fc > kb_$(date +%F).dump
# restaurar:
docker exec -i db-postgres pg_restore -U user -d kb --clean < kb_2026-09-29.dump
```

**Auditoría.** Toda escritura queda en la tabla `audit_log` (quién, qué, cuándo):

```bash
docker exec db-postgres psql -U user -d kb -c "SELECT created_at, actor, action, target FROM audit_log ORDER BY id DESC LIMIT 20"
```

**Tests:**

```bash
uv sync --extra dev
uv run pytest tests/unit
# integración: la base de datos indicada se BORRA en cada ejecución
docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb_test"   # una vez
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/kb_test uv run pytest tests/integration
```

## 13. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `database "kb" does not exist` | base de datos no creada | `docker exec db-postgres psql -U user -d defaultdb -c "CREATE DATABASE kb"` |
| `connection refused` en el puerto 5432 | `db-postgres` parado | sube el compose del DB-DOCKER |
| `extension "vector" is not available` | Postgres sin pgvector | usa la imagen `pgvector/pgvector` (la de `db-postgres`) |
| `VOYAGE_API_KEY no configurada` (u OpenAI) | falta la clave en el `.env` | rellena la clave o cambia el `EMBEDDING_PROVIDER` |
| `Chave de API inválida` | el `Bearer` no coincide con el `KB_API_KEY` del `.env` | revisa la variable y el header |
| `401` en `/mcp` | clave ausente o inválida: todo el `/mcp` exige clave, incluso para listar las tools | revisa el header `Authorization: Bearer <KB_API_KEY>` |
| `Sin acceso a la colección 'x'` | colección fuera de `allowed_collections` del agente | ajústalo con `update_agent` |
| La búsqueda devuelve cosas sin relación | `EMBEDDING_PROVIDER=fake` | usa un proveedor real |
| La API en Docker no accede a la base de datos | contenedor fuera de la red `db_network` | revisa `docker network ls` y el nombre de la red en `docker-compose.yml` |
| Puerto 8000 ocupado | otro servicio usando el puerto | `uv run mcp-rag-api serve --port 8010` y ajusta el `claude mcp add` |
| Claude no ve las tools | servidor caído o header errado | `curl localhost:8000/health`, `claude mcp list`, revisa el `Bearer` |

## 14. Despliegue en producción (Coolify)

Flujo **Zero-Git**, igual que los otros proyectos: el GitLab CI prueba, construye la imagen (`Dockerfile.coolify`) y publica en el GitLab Registry. Coolify solo hace pull de la imagen y sube el contenedor, sin código fuente en la VPS.

```
push a main → test:pytest → build:push (registry) → deploy:coolify (webhook) → Coolify hace pull y sube
```

### 14.1 Base de datos: Postgres con pgvector en Coolify

En producción no existe el `db-postgres` local. Crea una base de datos en Coolify:

1. **+ New → Database → PostgreSQL**.
2. En **Configuration → Image**, cambia a `pgvector/pgvector:pg16`. La imagen predeterminada de Postgres **no tiene** la extensión `vector`, y sin ella las migraciones fallan.
3. Guarda e inicia la base de datos. Anota la **Postgres URL (internal)**, algo como `postgres://postgres:CONTRASEÑA@<uuid>:5432/postgres`.

Si ya tienes un Postgres con pgvector en Coolify, basta crear una base de datos nueva en él (`CREATE DATABASE kb`) y usar la URL interna apuntando a `/kb`.

### 14.2 GitLab

1. Sube el proyecto a un repositorio en GitLab (branch `main`).
2. En **Settings → CI/CD → Variables**, crea:

| Variable | Valor |
|---|---|
| `COOLIFY_WEBHOOK` | `https://<coolify>/api/v1/deploy?uuid=<UUID-del-app>&force=false` (rellénala después de crear el app, en el paso 14.3) |
| `COOLIFY_SECRET` | token de Coolify con permiso de deploy (**Keys & Tokens → API tokens**) |
| `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` | opcional, si Coolify está detrás de Cloudflare Access |
| `INSTALL_LOCAL_EMBEDDINGS` | opcional, `true` para incluir el modelo local en la imagen (bastante más grande) |

3. En **Settings → Repository → Deploy tokens**, crea un token con `read_registry`. Coolify usa ese token para descargar la imagen.

El primer push a `main` ya ejecuta los tests (unitarios y de integración, con un Postgres pgvector temporal en el CI) y publica `registry.gitlab.com/<grupo>/mcp-rag-api:latest`.

### 14.3 Aplicación en Coolify

1. **+ New → Docker Image**, con la imagen `registry.gitlab.com/<grupo>/mcp-rag-api:latest`.
   - Registry privado: registra el deploy token de GitLab en el servidor (`docker login registry.gitlab.com`) o en las credenciales de registry de Coolify.
2. **Ports Exposes:** `8000`.
3. **Domains:** `https://kb.tudominio.com`. Coolify/Traefik se encarga del SSL.
4. **Health check:** actívalo, con path `/health` y puerto `8000`. La imagen también trae su propio `HEALTHCHECK`.
5. **Environment Variables:**

| Variable | Ejemplo |
|---|---|
| `DATABASE_URL` | URL **interna** del Postgres del paso 14.1 (cambia `postgres://` por `postgresql://` si prefieres; ambos funcionan) |
| `EMBEDDING_PROVIDER` | `voyage` |
| `VOYAGE_API_KEY` u `OPENAI_API_KEY` | clave del proveedor |
| `KB_API_KEY` | clave única y segura (genera con `python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `KB_AUTH_DISABLED` | **no la definas** en producción (predeterminado `false`) |

6. **Deploy.** Las migraciones se ejecutan solas al arrancar. Copia el **Deploy Webhook** del app en la variable `COOLIFY_WEBHOOK` de GitLab.
7. Mantén **1 réplica**. La app no guarda estado entre peticiones (stateless), pero dos réplicas subiendo a la vez competirían por las migraciones.

### 14.4 Autenticación en producción

La única clave del servidor es el `KB_API_KEY`, definido en las **Environment Variables** del app en Coolify (paso 14.3). Genera una segura, guárdala y lanza el deploy. Para conectar:

```bash
curl https://kb.tudominio.com/health          # {"status":"ok"}
claude mcp add --transport http kb https://kb.tudominio.com/mcp \
  --header "Authorization: Bearer $KB_API_KEY"
```

A partir de ahí, todo sigue como en los tutoriales 7 a 9.

### 14.5 Cuidados

- **Seguridad:** todo el `/mcp` exige clave válida (sin clave, responde `401`, incluso para listar tools). La API REST también exige clave, y solo `/health` es público.
- **Cloudflare Access:** si el dominio está protegido por Access, los clientes MCP (Claude Code, Desktop, API) no pasan por la pantalla de login. Crea una regla *Bypass* para `kb.tudominio.com/mcp` y `/health`; la autenticación queda a cargo del `KB_API_KEY`.
- **Embeddings locales:** con `INSTALL_LOCAL_EMBEDDINGS=true` la imagen incluye PyTorch y el modelo necesita unos 2–3 GB de RAM. Prefiere `voyage` u `openai` en una VPS pequeña.
- **Copia de seguridad:** activa las copias programadas de la base de datos en Coolify (**Database → Backups**).
- **Limpieza de memorias expiradas:** en **Scheduled Tasks** del app, crea `mcp-rag-api cleanup` con frecuencia `0 3 * * *`.

### 14.6 Probar la imagen de producción localmente

```bash
docker build -f Dockerfile.coolify -t mcp-rag-api:local .
docker run --rm --network db_network -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:password@db-postgres:5432/kb \
  --env-file .env mcp-rag-api:local
```

## 15. Licencia

Este proyecto es open source, bajo la [Licencia Apache 2.0](LICENSE).
