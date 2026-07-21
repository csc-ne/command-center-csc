# Command Center CSC

Monorepo dos sistemas operacionais do **Centro de Solucoes Conectadas (CSC)**
da Veneza Equipamentos Pesados. Todos os sistemas rodam em containers Docker
numa VM Windows Server (192.168.0.106) e compartilham o Command Center como
provedor unico de SSO (JWT).

## Sistemas

| Sistema             | Descricao                                                     | Porta |
|---------------------|---------------------------------------------------------------|------:|
| **Command Center**  | SSO unificado (login + MFA por email + push approval).        | 4001  |
| ↳ CSC Dashboard     | Machine List + POPs (uploads xlsx + Postgres dedicado).       | 4011  |
| ↳ DFA Dashboard     | Dealer Financial Analysis.                                    | 4013  |
| ↳ PSI Dashboard     | Post Sales Intelligence (SheetJS client-side, sem DB).        | 4015  |
| **RTS**             | Monitor de alertas John Deere -> notificacao WhatsApp.        | 8080  |
| **RTA**             | Dashboard de visualizacao de alertas em tempo real.           | 3021  |
| **RDA**             | Gerador de PDFs de desempenho de frota (batch mensal dia 01). | 5050  |
| **RCA**             | Relatorio de Coletas e Analises.                              | 3031  |
| **Fleet Intelligence** | Kanban de workflow (jornada de equipamentos), MVP fase 1.  | 8087  |

## Estrutura

```
COMAND-CENTER-CSC/
|-- sistemas/                     # cada sistema, isolado, com seu docker/
|   |-- portal/                   # Command Center + sub-dashboards
|   |   |-- backend/  frontend/  database/  docker/
|   |   |-- csc-dashboard/        # sub-dashboard: Machine List + POPs
|   |   |-- dfa-dashboard/        # sub-dashboard: Dealer Financial Analysis
|   |   \-- psi-dashboard/        # sub-dashboard: Post Sales Intelligence
|   |-- rts/                      # Real Time Support
|   |-- rta/                      # Real Time Alert
|   |-- rda/                      # Relatorios de Desempenho Automaticos
|   |-- rca/                      # Relatorio de Coletas e Analises
|   \-- fleet-intelligence/       # Kanban de workflow (FastAPI + React)
|-- docs/                         # documentacao historica e por sistema
|-- scripts/                      # deploy-all.ps1, stop-all.ps1
|-- .env.example                  # template do C:\env\.env
|-- .gitignore
|-- DEPLOY_VM.md                  # guia completo de deploy
\-- README.md
```

## Configuracao unica: `C:\env\.env`

Nao existe `.env` dentro de nenhum sistema. Todos os `docker-compose.yml`
apontam para `C:\env\.env` no host Windows Server. Cada container recebe
o arquivo via bind-mount em `/app/.env` e via `env_file`.

Motivo: um unico ponto de rotacao de segredos; nenhum segredo entra no
Git; sub-dashboards e satelites usam o mesmo `PORTAL_JWT_SECRET` para
validar cookies SSO sem duplicacao.

Para configurar uma nova maquina:
1. Copie `.env.example` para `C:\env\.env`.
2. Preencha os valores reais.
3. Rode os `docker compose up -d --build` conforme `DEPLOY_VM.md`.

## Deploy

Guia completo em [`DEPLOY_VM.md`](./DEPLOY_VM.md).

Deploy rapido (tudo de uma vez):
```powershell
.\scripts\deploy-all.ps1
```

Derrubar tudo:
```powershell
.\scripts\stop-all.ps1
```

## Desenvolvimento local

Este monorepo assume que os sistemas rodam **sempre via Docker**. Nao ha
suporte de primeira classe para rodar backends direto no host (embora a
maioria dos codigos detecte plataforma e caia para path relativo se
`C:\env\.env` nao existir).

Para desenvolver localmente sem Docker:
1. Crie `C:\env\.env` local com valores de dev.
2. Dentro do sistema desejado, siga o README interno se existir (RDA e
   Fleet Intelligence tem instrucoes de dev separadas).

## Historico e migracao

O repo foi reestruturado em 2026-07-21:
- Consolidacao de 9 arquivos `.env` em um unico `C:\env\.env`.
- Extracao de segredos hardcoded (chave privada Firebase, emails admin).
- Renomeacao `Fleet Inteligence` -> `fleet-intelligence` (sem typo, sem espaco).
- Remocao de `als/` (dashboard descontinuado, mesma porta do RCA).
- Peso morto: ~1.5 GB (venv, node_modules, PDFs gerados, backups aninhados).

Tag de seguranca com o estado anterior: `pre-reorg-2026-07-21`.
