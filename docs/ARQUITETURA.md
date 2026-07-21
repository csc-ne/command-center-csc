# Arquitetura — Command Center CSC

Documento de referencia para quem chegar novo no projeto. Explica o que
cada sistema faz, como eles se conectam entre si, onde os dados moram,
e como o SSO amarra tudo.

---

## 1. Visao geral em 30 segundos

O CSC (Centro de Solucoes Conectadas) opera nove aplicacoes web/servico
diferentes, todas rodando em containers Docker numa mesma VM Windows
Server. Um sistema central chamado **Portal (Command Center)** e a unica
porta de entrada: qualquer usuario faz login uma vez la e obtem um cookie
JWT que os outros sistemas (RTS, RTA, RDA, RCA, Fleet e os tres
sub-dashboards do proprio Portal) validam para conceder acesso.

Cada sistema roda em porta propria, tem seu proprio Postgres (nos casos
dos sub-dashboards) ou compartilha o Postgres da VM (banco `csc_veneza`).
Nenhum sistema tem `.env` embutido: todos leem de `C:\env\.env` no host
da VM, injetado nos containers via bind-mount do Docker Compose.

---

## 2. Mapa dos sistemas

```
                                +------------------+
                                |     USUARIO      |
                                |    (navegador)   |
                                +--------+---------+
                                         |
                                         v
+------------------------------------------------------------------+
|                    PORTAL (Command Center)                       |
|                        porta 4001                                |
|  - Login unificado + MFA por email + push approval               |
|  - Emite cookie portal_token (JWT HS256 assinado)                |
|  - PORTAL_JWT_SECRET compartilhado com TODOS os satelites        |
+------------------------------------------------------------------+
   |          |          |          |          |          |
   v          v          v          v          v          v
[CSC-DASH] [DFA-DASH] [PSI-DASH] [RTS]    [RTA]      [RDA] [RCA] [FLEET]
 4011       4013       4015       8080     3021       5050  3031  8087
   |          |          |          |          |          |     |    |
   v          v          v          v          v          v     v    v
[Postgres  [Postgres [Disco      [PG csc_    [PG csc_    [PG csc_veneza]
 dedicado   dedicado local +     veneza +    veneza]
 5434]      5435]    xlsx]       MySQL
                                 bancovz +
                                 Firebase]
```

Legenda: cada sistema tem seu proprio compose. Todos validam o cookie
`portal_token` emitido pelo Portal (SSO). Os sub-dashboards internos do
Portal (CSC/DFA/PSI) vivem dentro de `sistemas/portal/` mas rodam como
composes independentes.

---

## 3. O que cada sistema faz

### Portal (Command Center) — `sistemas/portal/` — porta 4001

**Funcao:** login unificado da CSC. Todo usuario da equipe faz login aqui.

**Fluxo de autenticacao:**
1. Usuario acessa qualquer sistema (ex.: `http://192.168.0.106:8080` = RTS).
2. Se nao tem cookie `portal_token` valido, e redirecionado para o Portal.
3. Portal valida email + senha + codigo MFA de 6 digitos por email
   (Office365 via OAuth Azure).
4. Portal seta cookie `portal_token` (JWT HS256 assinado com
   `PORTAL_JWT_SECRET`) no dominio da VM.
5. Todo satelite valida esse cookie usando o mesmo secret. Sem re-login.

**Depende de:**
- Postgres da VM (`csc_veneza`, schema `command_center`).
- Office365 (SMTP via OAuth2 Azure App Registration).

**Sobe 2 containers:** `portal-backend` (API Node/Express, interna
porta 4000) + `portal-frontend` (Node/Express proxy + static, porta 4001).

**Sub-dashboards internos** (rodam em composes proprios):

- **CSC Dashboard (`csc-dashboard`)** — porta 4011
  - Machine List + POPs
  - Upload de xlsx por email autorizado
  - Postgres proprio na 5434 (`csc_dashboard`)
- **DFA Dashboard (`dfa-dashboard`)** — porta 4013
  - Dealer Financial Analysis
  - Postgres proprio na 5435 (`dfa_dashboard`)
- **PSI Dashboard (`psi-dashboard`)** — porta 4015
  - Post Sales Intelligence
  - Sem Postgres: processa xlsx client-side (SheetJS no browser)
  - Armazena arquivos em disco no volume `psi-data`

### RTS — Real Time Support — `sistemas/rts/` — porta 8080

**Funcao:** monitorar alertas da John Deere e disparar notificacoes
WhatsApp automaticas para clientes.

**Fluxo operacional:**
1. `rts-core` (container Python) roda em loop, consulta a API da John
   Deere via OAuth2, busca alertas (DTCs) das maquinas de cada cliente.
2. Para cada alerta novo, dispara mensagem via WhatsApp Business API
   (Meta Graph API v17).
3. Persiste tudo no Postgres (`csc_veneza`, tabela `rts_alertas`) e no
   MySQL legado (`bancovz`, mantido para compatibilidade).
4. `rts-dashboard` (container Node) serve o painel web para operadores
   verem alertas em tempo real (Socket.IO).
5. O token WhatsApp se auto-renova via `WppTokenManager` (Python) que
   escreve de volta em `C:\env\.env` (bind-mount NAO usa `:ro`).

**Fora do Docker** (roda no host):
- **GUI PySide6** (`interface/app.py`) — operador usa quando precisa
  autenticar manualmente no John Deere.
- **Firebase Functions** (`functions/`) — deploy separado via CLI
  Firebase, apenas para webhooks WhatsApp.

**Depende de:**
- Postgres da VM.
- MySQL legado (`bancovz` — em processo de descontinuacao).
- John Deere API (OAuth2 com refresh token).
- Meta WhatsApp Business API.
- Firebase Realtime Database.

**Sobe 2 containers.** GUI + Functions no host.

### RTA — Real Time Alert — `sistemas/rta/` — porta 3021

**Funcao:** dashboard standalone para visualizar alertas em tempo real.
Le do mesmo Postgres do RTS mas nao dispara mensagens.

**Sobe 1 container.**

### RDA — Relatorios de Desempenho Automaticos — `sistemas/rda/` — porta 5050

**Funcao:** gerar PDFs de desempenho de frota. Tem geracao manual (via
UI) e batch automatico dia 01 de cada mes (para lista de clientes em
`RDA_BATCH_CLIENTES`).

**Fluxo:**
1. Usuario acessa `http://192.168.0.106:5050`, faz login via Portal.
2. Escolhe cliente (ID JD ou PIN de chassi) e periodo.
3. Frontend (Node/Express) proxya para o backend (Python/Flask).
4. Backend roda 9 queries em paralelo (`ThreadPoolExecutor`), gera
   graficos (matplotlib + contextily) e monta o PDF.
5. PDF salvo em `relatorios_gerados/` no host.

Batch mensal escreve em `relatorios_mensais/` (ambos ignorados pelo Git).

**Sobe 2 containers:** `rda-frontend` (Node, porta 5050) +
`rda-backend` (Python Flask, porta 5051 interna).

### RCA — Relatorio de Coletas e Analises — `sistemas/rca/` — porta 3031

**Funcao:** dashboard Node/Express para relatorios de coletas.

**Sobe 1 container.**

### Fleet Intelligence — `sistemas/fleet-intelligence/` — porta 8087

**Funcao:** Kanban de workflow para gerenciar a jornada de equipamentos
da frota. MVP fase 1: login, criacao de fluxos, fases e cards
arrastaveis. Preparado para fase 2 (Machine List, POPs, alertas
inteligentes).

**Stack diferente do resto:**
- Backend: FastAPI (Python 3.12) + SQLAlchemy 2.
- Frontend: React 18 + Vite + Tailwind + @dnd-kit.
- Postgres na VM (`csc_veneza`, schema dedicado `fleet_inteligence`).
- Auth propria (JWT independente) + validacao do cookie do Portal.

**Sobe 2 containers:** `fi-backend` (FastAPI, interna 8000) +
`fi-frontend` (nginx servindo React build, porta 8087).

---

## 4. Dependencias cruzadas (o que quebra o que)

| Se cair...           | Quebra...                                                 |
|----------------------|-----------------------------------------------------------|
| Postgres da VM       | Portal, RTS, RTA, RDA, RCA, Fleet (todos usam `csc_veneza`)|
| Portal (SSO)         | Todos os satelites — usuarios nao conseguem novo login    |
| `PORTAL_JWT_SECRET`  | Cookies existentes ficam invalidos em todos os sistemas   |
| MySQL `bancovz`      | Apenas o RTS (nao afeta os outros)                        |
| John Deere API       | Apenas o RTS (loop de alertas para de rodar)              |
| WhatsApp Meta API    | Apenas o RTS (dashboard funciona, mas nao dispara msgs)   |
| Firebase             | Apenas o RTS (dashboard perde realtime; loop continua)    |
| SMTP Office365       | Novos logins no Portal (MFA por email nao chega)          |
| SMTP Gmail (Fleet)   | Cadastros/notificacoes do Fleet Intelligence              |

**Nenhum sistema cai se outro satelite (nao-Portal) cair.** Isolamento
por rede Docker (cada sistema tem sua propria bridge network).

---

## 5. Layout do banco de dados

Postgres da VM (`192.168.0.106:5432`, database `csc_veneza`):

| Schema                 | Dono            | Uso                                       |
|------------------------|-----------------|-------------------------------------------|
| `command_center`       | Portal          | users, sessions, mfa_email_codes, audit_logs, login_attempts, approval_tokens |
| `public`               | RTS + RTA + RDA + RCA | rts_alertas, rts_contatos, mensagens_rtdb (compat MySQL), etc. |
| `fleet_inteligence`    | Fleet           | users, boards, phases, cards              |
| `layer_bronze`         | RTA (leitura)   | opc_notifications_events (fonte)          |

Postgres dedicados (containers proprios, dentro dos sub-dashboards):

| Container   | Porta host | Database         | Uso                       |
|-------------|-----------:|------------------|---------------------------|
| `csc-db`    | 5434       | `csc_dashboard`  | Machine List + POPs       |
| `dfa-db`    | 5435       | `dfa_dashboard`  | Dealer Financial Analysis |

MySQL legado (`192.168.0.106:3306`, database `bancovz`):
- Apenas o RTS le/escreve. Em processo de descontinuacao (as tabelas
  criticas ja foram migradas para o Postgres).

---

## 6. Onde moram os segredos

Todos os segredos vivem em `C:\env\.env` no host Windows Server (VM).

Os `docker-compose.yml` fazem duas coisas:
1. `env_file: - C:/env/.env` — Docker injeta as variaveis no processo
   do container (equivale a `docker run --env-file`).
2. `volumes: - C:/env/.env:/app/.env` — o arquivo fisico e montado
   dentro do container em `/app/.env`, para casos onde o codigo faz
   `load_dotenv("/app/.env")` explicitamente (Python + Node).

Codigo Python e Node detecta a plataforma:
- No host Windows: le direto de `C:\env\.env`.
- No container Linux: le de `/app/.env` (que e o bind mount do arquivo
  do host).

**O que existe fora do `.env` central:**
- `sistemas/rts/connection/serviceAccount.json` — gerado por
  `python create_sa.py`, que le `FIREBASE_*` do `.env` central e monta
  o JSON. Nao commitar.
- `sistemas/rts/.token_cache.json` — cache do refresh token do John
  Deere, escrito em runtime. Nao commitar.

---

## 7. Onde ficam os outputs (nao versionar)

| Sistema | Output                                 | Onde                          |
|---------|----------------------------------------|-------------------------------|
| RTS     | Logs do rts-core                       | `sistemas/rts/logs/`          |
| RDA     | PDFs gerados sob demanda               | `sistemas/rda/relatorios_gerados/` |
| RDA     | PDFs do batch mensal automatico        | `sistemas/rda/relatorios_mensais/` |
| PSI     | Xlsx uploads                           | volume Docker `psi-data`      |
| Fleet   | Uploads de anexos                      | volume Docker `fi-uploads`    |

Todos ignorados pelo `.gitignore`.

---

## 8. Portas usadas (referencia rapida)

Externas (expostas no host da VM — acessiveis na rede da empresa):

| Porta | Sistema                    |
|------:|----------------------------|
| 4001  | Portal frontend            |
| 4011  | CSC Dashboard frontend     |
| 4013  | DFA Dashboard frontend     |
| 4015  | PSI Dashboard frontend     |
| 4014  | PSI Dashboard backend API  |
| 4010  | CSC Dashboard backend API  |
| 4012  | DFA Dashboard backend API  |
| 5001  | RTS core (health/status)   |
| 5050  | RDA frontend               |
| 5434  | CSC Dashboard Postgres     |
| 5435  | DFA Dashboard Postgres     |
| 8080  | RTS dashboard              |
| 8087  | Fleet Intelligence         |
| 3021  | RTA                        |
| 3031  | RCA                        |

Internas (so via rede Docker):

| Porta | Onde        |
|------:|-------------|
| 4000  | portal-backend |
| 5051  | rda-backend Flask |
| 8000  | fi-backend FastAPI |

---

## 9. Onde comecar quando algo quebrar

1. **Container nao sobe:** `docker compose logs -f <servico>` no compose
   correspondente. Erros mais comuns: `.env` ausente ou variavel obrigatoria
   nao setada (o codigo faz fail-fast em vez de usar default).

2. **Login nao funciona em nenhum sistema:** olhar o `portal-backend`.
   Se SMTP falhou, MFA nao chega. Se `PORTAL_JWT_SECRET` mudou, cookies
   ficam invalidos.

3. **RTS nao envia WhatsApp:** olhar `rts-core` logs. TKWPP expirado
   deveria auto-renovar (`WppTokenManager` roda a cada 30 min). Se o
   bind-mount de `C:\env\.env` estiver `:ro`, a escrita falha e o
   token nunca renova de fato.

4. **RDA batch mensal nao rodou dia 01:** verificar arquivo marker em
   `sistemas/rda/relatorios_mensais/batch_done_YYYY-MM.marker`. Se
   existe, ja rodou. Se nao, checar logs do `rda-backend`.

5. **Fleet caiu "could not connect to server":** conferir `pg_hba.conf`
   da VM permitindo a rede Docker (172.16.0.0/12).

Detalhes por sistema em `docs/RTS_VM_SETUP.md`, `docs/RTS_DOCKER_README.md`,
`docs/RDA_CHANGELOG_TEMPLATE.md`, `docs/DEPLOY_MFA_EMAIL.md`.
