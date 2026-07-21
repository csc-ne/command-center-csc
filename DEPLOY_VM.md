# Deploy na VM (192.168.0.106) — Command Center Completo

Guia para deploy de todos os sistemas na VM Windows Server + Docker Desktop.

## Pre-requisito unico: `C:\env\.env`

Todos os `.env` foram consolidados em `C:\env\.env` (Windows Server na VM).
Cada `docker-compose.yml` faz `env_file: - C:/env/.env` e monta esse arquivo
dentro de cada container como `/app/.env`. Se `C:\env\.env` nao existir, os
containers sobem sem variaveis e falham no primeiro `os.getenv/process.env`.

Modelo do conteudo: veja `_SECRETS_CONSOLIDATED.txt` (gerado uma vez para
consolidar segredos historicos; nao commitar).

## Sistemas e Portas

| Sistema             | Porta host | Compose path                                                |
|---------------------|-----------:|-------------------------------------------------------------|
| Command Center      | 4001       | `sistemas/portal/docker/docker-compose.prod.yml`            |
| ↳ CSC Dashboard     | 4011       | `sistemas/portal/csc-dashboard/docker/docker-compose.yml`   |
| ↳ DFA Dashboard     | 4013       | `sistemas/portal/dfa-dashboard/docker/docker-compose.yml`   |
| ↳ PSI Dashboard     | 4015       | `sistemas/portal/psi-dashboard/docker/docker-compose.yml`   |
| RTS                 | 8080       | `sistemas/rts/docker/docker-compose.yml`                    |
| RTA                 | 3021       | `sistemas/rta/docker/docker-compose.yml`                    |
| RDA                 | 5050       | `sistemas/rda/docker/docker-compose.yml`                    |
| RCA                 | 3031       | `sistemas/rca/docker/docker-compose.yml`                    |
| Fleet Intelligence  | 8087       | `sistemas/fleet-intelligence/docker-compose.yml`            |

## Pre-requisitos (apenas na primeira vez)

```powershell
# Schema do Command Center (portal)
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza `
     -f sistemas\portal\database\command_center_schema.sql

# Migration MFA email
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza `
     -f sistemas\portal\database\migrations\001_mfa_email_migration.sql

# Schema Fleet Intelligence
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza `
     -f sistemas\fleet-intelligence\backend\sql\init.sql
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza `
     -f sistemas\fleet-intelligence\backend\sql\002_users_registration.sql
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza `
     -f sistemas\fleet-intelligence\backend\sql\003_crossflow_permissions_attachments.sql

# Schemas dos sub-dashboards do portal (Postgres dedicados, sobem via Docker)
# init.sql roda automatico no primeiro `up` (docker-entrypoint-initdb.d).
```

## Deploy — subir tudo (com rebuild)

Ordem: portal primeiro (emite JWT), depois os satelites.

```powershell
# 1. Command Center (SSO)
cd sistemas\portal\docker
docker compose --env-file C:\env\.env -f docker-compose.prod.yml up -d --build

# 2. Sub-dashboards do portal (Machine List, DFA, PSI)
cd ..\..\portal\csc-dashboard\docker
docker compose --env-file C:\env\.env up -d --build

cd ..\..\dfa-dashboard\docker
docker compose --env-file C:\env\.env up -d --build

cd ..\..\psi-dashboard\docker
docker compose --env-file C:\env\.env up -d --build

# 3. Sistemas satelites
cd ..\..\..\rts\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build

cd ..\..\rta\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build

cd ..\..\rda\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build

cd ..\..\rca\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build

# 4. Fleet Intelligence (compose na raiz do sistema, nao em docker/)
cd ..\..\fleet-intelligence
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
```

Alternativa: use `scripts\deploy-all.ps1` (executa a sequencia inteira).

## Derrubar tudo

```powershell
cd sistemas\portal\docker              && docker compose -f docker-compose.prod.yml down
cd ..\csc-dashboard\docker              && docker compose down
cd ..\..\dfa-dashboard\docker           && docker compose down
cd ..\..\psi-dashboard\docker           && docker compose down
cd ..\..\..\rts\docker                  && docker compose -f docker-compose.yml down
cd ..\..\rta\docker                     && docker compose -f docker-compose.yml down
cd ..\..\rda\docker                     && docker compose -f docker-compose.yml down
cd ..\..\rca\docker                     && docker compose -f docker-compose.yml down
cd ..\..\fleet-intelligence             && docker compose -f docker-compose.yml down
```

Alternativa: `scripts\stop-all.ps1`.

## Firebase deploy (apos subir RTS)

```powershell
cd sistemas\rts
firebase deploy --only functions --project rts-real-time-support-6ec6b
```

O `serviceAccount.json` do RTS e gerado por `python create_sa.py`, que le
`FIREBASE_*` de `C:\env\.env`. Rode uma vez apos qualquer rotacao da chave.

## Verificar status

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Sort-Object
```

Esperado: 14+ containers rodando:
- csc-portal x2 (portal-backend, portal-frontend)
- csc-dashboard x3 (csc-db, csc-backend, csc-frontend)
- dfa-dashboard x3 (dfa-db, dfa-backend, dfa-frontend)
- psi-dashboard x2 (psi-backend, psi-frontend)
- rts x2 (rts-core, rts-dashboard)
- rta x1
- rda x2 (rda-frontend, rda-backend)
- rca x1
- fleet-intelligence x2 (fi-backend, fi-frontend)

## O que testar apos deploy

- `http://192.168.0.106:4001` — Command Center (login SSO unificado)
- `http://192.168.0.106:8080` — RTS (redireciona ao CC se nao logado)
- `http://192.168.0.106:3021` — RTA
- `http://192.168.0.106:5050` — RDA
- `http://192.168.0.106:3031` — RCA
- `http://192.168.0.106:4011` — CSC Dashboard (Machine List + POPs)
- `http://192.168.0.106:4013` — DFA Dashboard (Dealer Financial Analysis)
- `http://192.168.0.106:4015` — PSI Dashboard (Post Sales Intelligence)
- `http://192.168.0.106:8087` — Fleet Intelligence
- Botoes de navegacao entre sistemas em cada dashboard
- Logo do RTS renderizando corretamente
- Rate limiting nao bloqueando usuarios diferentes

## Pre-condicoes

- `C:\env\.env` existe na VM (todos os sistemas leem dele).
- `PORTAL_JWT_SECRET` no `.env` central e usado por todos os sistemas para
  validar o cookie `portal_token`. NAO alterar sem redeploy geral.
- `COOKIE_SECURE=false` (HTTP). Mudar para `true` com HTTPS.
- `pg_hba.conf` aceita conexoes da subnet Docker (172.16.0.0/12, 192.168.0.0/16).
- SMTP funcional (`SMTP_*` = Office365/OAuth Azure para o Portal;
  `FI_SMTP_*` = Gmail com app password para o Fleet).

## Rollback de emergencia

Se algo der errado apos a reorganizacao para `sistemas/`, o estado anterior
esta preservado em duas camadas:

1. **Git**: `git checkout backup/pre-reorg-2026-07-21` volta ao layout antigo.
2. **Zip fisico**: restaure de `C:\backup-csc\` (feito manualmente antes da reorg).
