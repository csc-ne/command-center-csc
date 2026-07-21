# Command Center CSC

Monorepo tecnico dos sistemas operacionais do **Centro de Solucoes
Conectadas (CSC)** da Veneza Equipamentos Pesados. Todos os sistemas
rodam em containers Docker numa VM Windows Server (192.168.0.106) e
compartilham o Portal como provedor unico de SSO (JWT HS256).

Documentacao adicional em `docs/`:
- [ARQUITETURA.md](docs/ARQUITETURA.md) — diagrama de fluxos, dependencias, DB layout
- [DEPLOY_STEP_BY_STEP.md](docs/DEPLOY_STEP_BY_STEP.md) — comandos exatos do Git ate a VM
- [DEPLOY_MFA_EMAIL.md](docs/DEPLOY_MFA_EMAIL.md) — migracao TOTP -> email
- [RDA_CHANGELOG_TEMPLATE.md](docs/RDA_CHANGELOG_TEMPLATE.md) — template de entrega RDA
- [RTS_DOCKER_README.md](docs/RTS_DOCKER_README.md), [RTS_VM_SETUP.md](docs/RTS_VM_SETUP.md)

---

## 1. Sumario dos sistemas

| Sistema             | Path                                | Stack                                 | Porta ext | Postgres                    |
|---------------------|-------------------------------------|---------------------------------------|-----------|-----------------------------|
| Portal              | `sistemas/portal/`                  | Node/Express + JWT + Nodemailer OAuth | 4001      | csc_veneza / command_center |
| ↳ CSC Dashboard     | `sistemas/portal/csc-dashboard/`    | Node/Express + Postgres dedicado      | 4011      | csc_dashboard (5434)        |
| ↳ DFA Dashboard     | `sistemas/portal/dfa-dashboard/`    | Node/Express + Postgres dedicado      | 4013      | dfa_dashboard (5435)        |
| ↳ PSI Dashboard     | `sistemas/portal/psi-dashboard/`    | Node/Express + volume disco (SheetJS) | 4015      | —                           |
| RTS                 | `sistemas/rts/`                     | Python loop + Node dashboard + Firebase | 8080    | csc_veneza + MySQL bancovz  |
| RTA                 | `sistemas/rta/`                     | Node/Express                          | 3021      | csc_veneza                  |
| RDA                 | `sistemas/rda/`                     | Node proxy + Python Flask/gunicorn    | 5050      | csc_veneza                  |
| RCA                 | `sistemas/rca/`                     | Node/Express                          | 3031      | csc_veneza                  |
| Fleet Intelligence  | `sistemas/fleet-intelligence/`      | FastAPI + React/Vite (nginx)          | 8087      | csc_veneza / fleet_inteligence |

Total: **14 containers em producao** (contando dbs dedicados e frontends).

---

## 2. Fluxo de autenticacao (SSO)

O Portal e a unica porta de entrada de novos logins. Uma vez logado,
qualquer satelite valida o mesmo cookie sem precisar de novo login.

```
1. Usuario abre http://192.168.0.106:8080 (RTS)
2. RTS confere cookie portal_token — nao existe
3. RTS redireciona: http://192.168.0.106:4001/?redirect=http://192.168.0.106:8080
4. Portal exibe tela de login (email + senha)
5. Portal valida email @venezanet.com no PG (command_center.users)
6. Portal valida senha (bcrypt)
7. Portal gera codigo MFA de 6 digitos, salva em mfa_email_codes
8. Portal envia email via SMTP.SendAsApp (OAuth Azure) para o usuario
9. Usuario digita codigo (validade 15 min)
10. Portal assina JWT HS256 com PORTAL_JWT_SECRET (payload: email, name, role)
11. Portal seta Cookie: portal_token=<jwt>; HttpOnly; Path=/; SameSite=Lax
12. Portal redireciona de volta pro RTS
13. RTS le cookie, valida assinatura com o MESMO PORTAL_JWT_SECRET
14. RTS aceita a sessao. Sem re-login.
```

**Componentes criticos do SSO:**
- `PORTAL_JWT_SECRET` no `C:\env\.env` PRECISA ser identico em todos
  os satelites. Rotacionar esse secret invalida TODOS os cookies ativos.
- SMTP OAuth Azure PRECISA estar funcional. Sem SMTP, MFA nao chega
  e nenhum login novo funciona (sessoes ativas continuam ok ate expirar).

**Approval push (opcional):**
Cada email de MFA vem tambem com um botao "Autorizar login". Clicar
grava um `approval_token` no PG. Enquanto o usuario espera o email,
a tela do Portal faz polling em `/api/mfa/check-approval` a cada 2s.
Se detecta approval, faz login sem precisar digitar o codigo.

---

## 3. Fluxo do RTS (loop de alertas)

Sistema mais complexo. Duas partes:

### 3.1 `rts-core` (container Python, headless)

```
LOOP a cada N minutos:
1. Renovar access_token da John Deere (se refresh_token vencer, cache
   em .token_cache.json). refresh_token e rotacionado a cada renovacao.
2. Consultar API JD: GET /organizations/{id}/equipment-alerts
3. Para cada alerta novo:
   a. Extrair DTC, PIN, cliente, severidade
   b. Consultar public.rts_contatos: telefones autorizados desse cliente
   c. INSERT em public.rts_alertas (status=PENDENTE)
   d. Chamar whatsapp_api.send_alert() com template Meta
   e. Se envio OK: UPDATE status=ENVIADO. Se falhou: status=FALHOU
4. Batch retry: pega alertas FALHOU dos ultimos N minutos e reenvia
5. WppTokenManager (background thread): verifica se TKWPP tem <24h
   pra expirar; se sim, renova via APP_ID/APP_SECRET e escreve novo
   TKWPP em C:\env\.env (por isso o bind-mount do .env NAO tem :ro
   no compose do RTS — precisa de write)
```

### 3.2 `rts-dashboard` (container Node)

- Express + Socket.IO na porta 8080
- Reflete o estado da tabela `rts_alertas` em tempo real (Firebase Realtime DB propaga eventos)
- Filtros: por marca (JD/WIRTGEN), por status, por periodo
- Modo WPP (AUTO/FORCE_ON/FORCE_OFF) — restrito a `RTS_WPP_ADMIN_EMAILS`

### 3.3 Fora do Docker (host)

- `interface/app.py` (PySide6): GUI que o operador usa para autenticar manualmente no John Deere quando o refresh_token expira/e revogado. NAO conteinerizado.
- `functions/`: Firebase Functions (webhooks WhatsApp). Deploy separado via CLI Firebase.

---

## 4. Fluxo do RDA (relatorios mensais automaticos)

```
CRON (dia 01 de cada mes 04:00):
1. Loop sobre RDA_BATCH_CLIENTES (formato: Estado|ID_JD|Nome;...)
2. Para cada cliente:
   a. Chamar rda_py_data_movel(cliente_id, data_ini, data_fim)
   b. Backend Python (Flask) roda 9 queries em paralelo via ThreadPoolExecutor
   c. Gera graficos com matplotlib + contextily
   d. Monta PDF final (usa fonts/, labels/, icons/)
   e. Salva em relatorios_mensais/batch_mensal_{id}_{periodo}.pdf
3. Cria marker: relatorios_mensais/batch_done_YYYY-MM.marker
   (se marker existe, batch nao roda de novo no mesmo mes)
```

Manual: usuario acessa `http://192.168.0.106:5050`, faz login SSO,
escolhe cliente + periodo, gera PDF sob demanda em `relatorios_gerados/`.

---

## 5. Sub-dashboards do Portal (upload xlsx + Postgres dedicado)

Cada sub-dashboard tem estrutura padrao:

```
sistemas/portal/<name>-dashboard/
├── backend/          # Node/Express: recebe upload, valida, insere no PG
│   ├── server.js
│   ├── db.js
│   ├── mapper.js     # mapeia colunas do xlsx -> colunas da tabela
│   └── package.json
├── frontend/         # Node/Express: serve estatico + proxy /api
│   ├── index.html    # SPA com fetch + Chart.js
│   └── server.js
├── database/init.sql # schema + tabela (roda 1x no primeiro boot do PG)
└── docker/           # 3 servicos: <name>-db (Postgres) + backend + frontend
```

Fluxo de upload:
1. Usuario logado (portal_token valido) faz upload de .xlsx
2. Backend valida se `req.user.email` esta em `<NAME>_UPLOAD_ALLOWED_EMAILS`
3. Se autorizado: parseia xlsx (SheetJS/xlsx), mapeia colunas, INSERT no PG dedicado
4. Frontend renderiza graficos a partir do PG

---

## 6. Fleet Intelligence (workflow Kanban)

Diferente dos outros — stack moderna, arquitetura de dominio:

- **Backend:** FastAPI + SQLAlchemy 2 + Pydantic
- **Frontend:** React 18 + Vite + Tailwind + @dnd-kit (drag-and-drop)
- **Auth propria:** JWT independente (JWT_SECRET_KEY) para operacoes internas + validacao adicional do cookie do Portal para SSO
- **Schema dedicado no csc_veneza:** `fleet_inteligence` (typo preservado; migracao para `fleet_intelligence` planejada)

Entidades: `users`, `boards` (fluxos), `phases` (colunas), `cards`
(itens arrastaveis), `card_attachments`, `activity_logs`.

---

## 7. Configuracao unica: `C:\env\.env`

Nao existe `.env` dentro de nenhum sistema. Todos os `docker-compose.yml`
apontam para `C:\env\.env` no host Windows Server.

### 7.1 Como o codigo le

Deteccao de plataforma em todo Node/Python:

```javascript
// Node — padrao em todo server.js
const _envPath = process.platform === "win32"
  ? "C:\\env\\.env"
  : path.join(__dirname, "..", ".env");
require("dotenv").config({ path: _envPath });
```

```python
# Python — padrao em todos os scripts que rodam no host
import platform, os
from dotenv import load_dotenv
_ENV_PATH = r"C:\env\.env" if platform.system() == "Windows" else os.path.join(...)
load_dotenv(_ENV_PATH)
```

No host Windows Server (fora container): le direto `C:\env\.env`.
No container Linux (Docker Desktop): le `/app/.env`, que e um bind-mount
declarado no compose:

```yaml
volumes:
  - C:/env/.env:/app/.env:ro
```

### 7.2 Excecao: RTS

O `.env` do RTS **nao pode** ser `:ro` porque `whatsapp_api.py` e
`token_wpp_manager.py` usam `dotenv.set_key()` para persistir o TKWPP
renovado automaticamente. O compose do RTS monta sem read-only:

```yaml
- C:/env/.env:/app/.env    # sem :ro
```

### 7.3 Populacao inicial

Copie `.env.example` para `C:\env\.env` e preencha:

```powershell
New-Item -ItemType Directory -Path C:\env -Force
Copy-Item .env.example C:\env\.env
notepad C:\env\.env
```

---

## 8. Layout de dados

### 8.1 PostgreSQL da VM (`192.168.0.106:5432`, database `csc_veneza`)

| Schema                | Owner            | Tabelas principais |
|-----------------------|------------------|--------------------|
| `command_center`      | Portal           | users, sessions, mfa_email_codes, approval_tokens, audit_logs, login_attempts, email_verifications |
| `public`              | RTS, RTA, RDA, RCA | rts_alertas, rts_contatos, mensagens_rtdb (compat MySQL) |
| `fleet_inteligence`   | Fleet            | users, boards, phases, cards, card_attachments, card_links, board_connections, activity_logs |
| `layer_bronze`        | leitura (RTA, RTS) | opc_notifications_events, opc_equipment, opc_engine_hours |
| `grarantia`           | leitura (Portal, RTA) | jd_protect, power_gard_plus_care |

### 8.2 Postgres dedicados (containers)

| Container | Volume Docker                | Porta host | Database         |
|-----------|------------------------------|-----------:|------------------|
| csc-db    | csc-dashboard_csc-pgdata     | 5434       | csc_dashboard    |
| dfa-db    | dfa-dashboard_dfa-pgdata     | 5435       | dfa_dashboard    |

### 8.3 MySQL legado (`192.168.0.106:3306`, `bancovz`)

Usado apenas pelo RTS. Em processo de descontinuacao. Tabelas migradas
para o schema `public` do `csc_veneza`.

---

## 9. Dependencias cruzadas (blast radius)

| Se cair...                | Quebra...                                                     |
|---------------------------|---------------------------------------------------------------|
| PG `csc_veneza`           | Portal, RTS, RTA, RDA, RCA, Fleet — todos                     |
| Portal (SSO)              | Novos logins em qualquer satelite (sessoes ativas continuam)  |
| `PORTAL_JWT_SECRET` muda  | Cookies existentes viram invalidos globalmente                |
| MySQL `bancovz`           | RTS (loop de alertas mantem funcionando pela migracao ao PG)  |
| John Deere OAuth          | RTS loop para; alertas nao chegam                             |
| Meta WhatsApp API         | RTS nao envia mensagens; dashboard visual continua ok         |
| Firebase Realtime DB      | RTS perde push em tempo real (dashboard fica "estatico")      |
| SMTP Office365            | MFA nao chega em novos logins                                 |
| SMTP Gmail (Fleet)        | Fleet nao envia notificacoes de cadastro/aprovacao            |

**Isolamento:** cada sistema tem sua rede Docker bridge propria
(`portal-net`, `rts-net`, `rta-net`, etc.). A queda de um satelite
nao propaga para os outros.

---

## 10. Portas em uso

### 10.1 Expostas no host da VM

| Porta | Sistema                    | Notas                          |
|------:|----------------------------|--------------------------------|
| 4001  | Portal frontend            | Ponto unico de login (SSO)     |
| 4011  | CSC Dashboard frontend     | Machine List + POPs            |
| 4013  | DFA Dashboard frontend     | Dealer Financial Analysis      |
| 4015  | PSI Dashboard frontend     | Post Sales Intelligence        |
| 4010  | CSC Dashboard backend      | API REST direta                |
| 4012  | DFA Dashboard backend      | API REST direta                |
| 4014  | PSI Dashboard backend      | API REST direta                |
| 5001  | RTS core                   | /status /healthz (rede interna)|
| 5050  | RDA frontend               | Proxy pra rda-backend Flask    |
| 5434  | CSC Dashboard Postgres     | Acesso direto via DBeaver      |
| 5435  | DFA Dashboard Postgres     | Acesso direto via DBeaver      |
| 8080  | RTS dashboard              | Painel de alertas em tempo real|
| 8087  | Fleet Intelligence         | Kanban de workflow             |
| 3021  | RTA                        | Dashboard de alertas           |
| 3031  | RCA                        | Coletas e Analises             |

### 10.2 Internas (so via rede Docker)

| Porta | Servico          |
|------:|------------------|
| 4000  | portal-backend   |
| 5051  | rda-backend Flask (gunicorn) |
| 8000  | fi-backend FastAPI (uvicorn) |

---

## 11. Cache warming (Portal)

O Portal executa 3 queries pesadas em background 2s apos o boot para
evitar timeout na primeira requisicao HTTP:

```javascript
setTimeout(() => {
  getMachinesSummary().then(...)          // ~30-60s
  getJdProtectDetail().then(...)          // ~30-120s
  getGarantiaDetail().then(...)           // ~30-120s
}, 2000);
```

Enquanto a query pesada roda, requests para
`/api/dashboard/maintenance-detail?type=jdprotect` retornam
`{success:true, rows:[], warming:true}` (nao bloqueia). O frontend
detecta `warming:true` e agenda retry em 30s.

Cache TTL: 24h. Rebuild do container zera o cache — primeira consulta
pos-rebuild volta ao warming.

**Se JD PROTECT / GARANTIA aparecem vazios apos rebuild:**
1. Aguarde 2-3 minutos apos o `up -d --build`.
2. `docker logs portal-backend | Select-String "Warming"` — deve mostrar `Warming jdprotect-detail OK: N rows`.
3. F5 no navegador.
4. Se apos 5 min o log mostrar `Warming jdprotect-detail FALHOU: <erro>`, a query esta quebrada — investigar o schema `grarantia` ou `layer_bronze`.

---

## 12. Deploy

### 12.1 Fluxo diario

```powershell
# No tester (Windows local):
cd "C:\Users\Henrique - veneza\Desktop\COMAND CENTER CSC"
git add .
git commit -m "descricao objetiva"
git push

# Na VM (RDP):
cd C:\command-center-csc
git pull

# Rebuild APENAS do sistema afetado:
cd sistemas\<sistema>\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
```

### 12.2 Ordem obrigatoria para deploy inicial

O Portal precisa estar de pe antes de qualquer satelite (SSO):

```powershell
# 1. Command Center (emite JWT)
cd sistemas\portal\docker
docker compose --env-file C:\env\.env -f docker-compose.prod.yml up -d --build

# 2. Sub-dashboards (validam JWT)
cd ..\csc-dashboard\docker && docker compose --env-file C:\env\.env up -d --build
cd ..\..\dfa-dashboard\docker && docker compose --env-file C:\env\.env up -d --build
cd ..\..\psi-dashboard\docker && docker compose --env-file C:\env\.env up -d --build

# 3. Satelites
cd ..\..\..\rts\docker && docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
cd ..\..\rta\docker && docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
cd ..\..\rda\docker && docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
cd ..\..\rca\docker && docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
cd ..\..\fleet-intelligence && docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
```

Alternativa: `.\scripts\deploy-all.ps1` executa a sequencia inteira.

### 12.3 Deploy do RTS — passo extra obrigatorio

Antes do primeiro `docker compose up -d --build` do RTS, gerar o
`serviceAccount.json` do Firebase a partir das vars `FIREBASE_*` do
`.env` central:

```powershell
cd sistemas\rts
python create_sa.py
# Confirma: Test-Path .\connection\serviceAccount.json  # deve ser True
```

Rode novamente apos qualquer rotacao da chave Firebase.

### 12.4 Firebase Functions (roda fora do Docker)

```powershell
cd sistemas\rts
firebase deploy --only functions --project rts-real-time-support-6ec6b
```

---

## 13. Troubleshooting rapido

### Container nao sobe
```powershell
docker compose logs -f <servico>
```
Erros mais comuns:
- **`_req is not defined`** — codigo Node espera variavel do .env que nao esta em `C:\env\.env`.
- **`Missing X from lock file`** — `package.json` mudou mas `package-lock.json` nao foi regenerado. Rodar `docker run --rm -v ${PWD}:/app -w /app node:18-alpine npm install --package-lock-only`.
- **`ECONNREFUSED 192.168.0.106:5432`** — Postgres do host nao aceita conexao da rede Docker. Verificar `pg_hba.conf` (adicionar `host csc_veneza <user> 172.16.0.0/12 md5`).

### Login nao funciona em NENHUM sistema
- Ver `docker logs portal-backend --tail 100`.
- Se `[EMAIL] SMTP OAuth2 conectado com sucesso` NAO aparecer: problema no `AZURE_*` (secret expirou? permissoes do App revogadas?).
- Se aparecer mas MFA nao chega: caixa de spam, ou o app do Azure perdeu a role `Application SMTP.SendAsApp`.

### JD PROTECT / GARANTIA vazio no dashboard
- Cache warming ainda em curso. `docker logs portal-backend | Select-String "Warming"`.
- Se `Warming ... FALHOU`: query quebrada — schema `grarantia` ou `layer_bronze` inconsistente.
- Aguardar 2-3 min pos-rebuild + F5 no navegador resolve na maioria dos casos.

### RTS nao envia WhatsApp
- `docker logs rts-core --tail 100`.
- Se `TKWPP invalido/expirado` — WppTokenManager deveria renovar sozinho. Verificar se o bind-mount de `C:\env\.env` NAO tem `:ro` (senao o set_key falha silenciosamente e o token nunca atualiza).
- Se `refresh_token JD expirado` — autenticar manualmente via GUI PySide6 no host (`python sistemas\rts\interface\app.py`).

### RDA batch mensal nao rodou dia 01
- Ver `sistemas/rda/relatorios_mensais/batch_done_YYYY-MM.marker`. Se existe, ja rodou.
- Se nao: `docker logs rda-backend --tail 200`. Provavelmente erro numa query especifica de algum ID da lista `RDA_BATCH_IDS`.

### Fleet caiu "could not connect to server"
- `pg_hba.conf` da VM precisa permitir a rede Docker do container Fleet.
- Confirmar: `docker exec fi-backend curl -v telnet://host.docker.internal:5432` — deve conectar.

---

## 14. Rollback de emergencia

### 14.1 Rollback de UM sistema apenas

Cada sistema pode ser revertido individualmente sem afetar os outros:

```powershell
# Ex.: rollback do Portal
cd C:\command-center-csc\sistemas\portal\docker
docker compose -f docker-compose.prod.yml down

# Volta pro path antigo (se ainda existir)
cd "C:\COMAND CENTER CSC\portal\docker"
docker compose --env-file ../.env -f docker-compose.prod.yml up -d --build
```

### 14.2 Rollback total do repo

```powershell
git log --oneline    # encontre o hash do commit bom
git reset --hard <hash>
git push --force
```

Ou via tag/branch de backup (se criada antes de mudanca grande):
```powershell
git checkout <tag-de-backup>
```

---

## 15. Fluxo de contribuicao (dev)

### 15.1 Editar codigo

Este monorepo assume dev **sempre via Docker**. Nao ha suporte de
primeira classe para rodar backends direto no host (embora a maioria
dos codigos detecte plataforma e caia para path relativo se `C:\env\.env`
nao existir).

Para desenvolver localmente sem Docker:
1. Crie `C:\env\.env` local com valores de dev.
2. Dentro do sistema desejado, siga o README interno se existir
   (RDA e Fleet Intelligence tem instrucoes de dev separadas).

### 15.2 Adicionar dependencia (Node)

```powershell
cd sistemas\<sistema>\backend
docker run --rm -v ${PWD}:/app -w /app node:18-alpine npm install <pkg> --save
# commita package.json + package-lock.json juntos
```

Nunca rode `npm install` no host se voce nao tem certeza da versao
do Node — divergencia entre host e Dockerfile quebra `npm ci`.

### 15.3 Adicionar variavel de ambiente

1. Adicione no `.env.example` (documenta o campo, sem valor).
2. Ajuste o codigo pra ler via `process.env.X` (Node) ou `os.getenv("X")` (Python).
3. Ajuste o `docker-compose.yml` se o container precisar receber a var:
   ```yaml
   environment:
     X: "${X}"
   ```
4. Preencha em `C:\env\.env` na VM.
5. Rebuild do container afetado.

### 15.4 Adicionar novo sistema

1. Cria `sistemas/<novo>/` com estrutura padrao: `backend/`, `frontend/`, `docker/`.
2. Compose deve ter `env_file: - C:/env/.env` e bind `- C:/env/.env:/app/.env`.
3. Nome dos containers/services previsivel: `<novo>-backend`, `<novo>-frontend`.
4. Se precisa de SSO: ler `portal_token` do cookie e validar com `PORTAL_JWT_SECRET`.
5. Adiciona novas variaveis em `.env.example` prefixadas com o nome do sistema (evita conflitos).
6. Atualiza `DEPLOY_VM.md` e este README com porta + descricao.

---

## 16. Ambientes

| Ambiente | Host                     | Uso                              |
|----------|--------------------------|----------------------------------|
| Producao | VM Windows Server 192.168.0.106 | `git pull` + `docker compose up` |
| Tester   | Windows local            | `git commit` + `git push`        |

Nao ha ambiente de staging separado — mudancas sao testadas
localmente e vao direto pra producao via `git pull`.

---

## 17. Historico

**2026-07-21 — Reestruturacao completa:**
- Consolidacao de 9 `.env` em `C:\env\.env`
- Extracao de segredos hardcoded (chave privada Firebase, arrays de email)
- Reorganizacao `sistemas/` (portal/rts/rta/rda/rca/fleet-intelligence)
- Renomeacao `Fleet Inteligence` -> `fleet-intelligence` (sem espaco, sem typo)
- Remocao `als/` (dashboard descontinuado, mesma porta do RCA)
- Purga de ~1.5 GB de peso morto (venv, node_modules, PDFs gerados, backups aninhados)
- Migracao para o repo `henriquejsa/command-center-csc` + fork `csc-ne/command-center-csc`

Tag de seguranca com o estado anterior: `pre-reorg-2026-07-21` (existiu no repo antigo `csc-ne/RTS.git`).
