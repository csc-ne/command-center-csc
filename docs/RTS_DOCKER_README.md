# RTS — Deploy em Docker (modo híbrido)

Esta pasta contém **tudo que é específico de containerização**: Dockerfiles,
compose, scripts de operação, unit systemd e documentação de VM.

> **Escopo deliberado:** nem tudo do RTS roda em container. A GUI PySide6 e o
> fluxo OAuth do John Deere (Selenium com login humano) continuam no host.
> O que está containerizado é o **loop 24/7** que monitora alertas e dispara
> WhatsApp + o **painel web** (Node/Express/Socket.IO).

## Arquitetura

```
┌─────────────────────── VM / Host ────────────────────────┐
│                                                          │
│  ┌─ rts-core  (container) ────────────────┐              │
│  │  python rts_core.py (headless)         │              │
│  │   ├─ MessageShooter (loop de alertas)  │              │
│  │   ├─ WppTokenManager (renova token)    │              │
│  │   └─ HTTP status :5001 (/status)       │              │
│  └────────────────────────────────────────┘              │
│                     │ MySQL :3306 (host)                 │
│                     │ Graph API (internet)               │
│                     │                                    │
│  ┌─ rts-dashboard (container) ────────────┐              │
│  │  node connection/server.js             │              │
│  │   ├─ Express :8080                     │              │
│  │   ├─ Socket.IO                         │              │
│  │   └─ Firebase Admin (RTDB)             │              │
│  └────────────────────────────────────────┘              │
│                                                          │
│  ─── HOST (não containerizado) ──────────                │
│   - interface/app.py  (GUI PySide6, sob demanda)         │
│   - OAuth JD (Selenium, sob demanda)                     │
│   - MySQL bancovz (porta 3306)                           │
└──────────────────────────────────────────────────────────┘
```

## Estrutura da pasta

```
docker/
├── Dockerfile.core             # imagem Python headless
├── Dockerfile.dashboard        # imagem Node (painel)
├── docker-compose.yml          # orquestração dos 2 serviços
├── requirements.docker.txt     # deps Python do core (subset de requirements.txt)
├── .env.example                # template de .env (raiz)
├── README.md                   # este arquivo
├── VM_SETUP.md                 # guia passo-a-passo para subir em VM
├── scripts/
│   ├── preflight.sh            # checa env, deps, conectividade
│   ├── build.sh                # docker compose build
│   ├── up.sh                   # docker compose up -d
│   ├── down.sh                 # docker compose down
│   ├── logs.sh                 # logs -f
│   ├── status.sh               # compose ps + /status + docker stats
│   └── install-vm.sh           # bootstrap de VM Ubuntu 22.04+
└── systemd/
    └── rts.service             # unit para auto-start no boot
```

## Pré-requisitos

- **Docker Engine 24+** (ou Docker Desktop em dev)
- **docker compose plugin v2** (`docker compose version`)
- **.env** preenchido na raiz do projeto (copiar de `docker/.env.example`)
- **connection/serviceAccount.json** presente (Firebase Admin)
- **MySQL** acessível: se estiver no próprio host, o compose usa
  `host.docker.internal` via `extra_hosts`; se estiver em outra máquina,
  aponte `HOST_DB` / `IPDESKTOPDB` para o IP real no .env.

## Fluxo rápido

```bash
# 1. Primeira vez (ou após 'git pull')
cd docker/scripts
bash preflight.sh      # valida .env, SA, conectividade
bash build.sh          # docker compose build

# 2. Subir
bash up.sh             # -d

# 3. Observar
bash status.sh         # snapshot
bash logs.sh rts-core  # follow

# 4. Derrubar
bash down.sh
```

## Endpoints

| Endpoint                           | Serviço        | Propósito                          |
| ---------------------------------- | -------------- | ---------------------------------- |
| `http://localhost:5001/status`     | rts-core       | JSON: uptime, last_loop, business_hours |
| `http://localhost:5001/healthz`    | rts-core       | 200 OK = processo vivo             |
| `http://localhost:8080/`           | rts-dashboard  | painel web                         |

## Variáveis de ambiente relevantes

O `.env` na raiz é lido por ambos os containers (via `env_file`). Além das
chaves já existentes no projeto, o container aceita:

| Var                    | Default           | Onde é lida              |
| ---------------------- | ----------------- | ------------------------ |
| `RTS_HEADLESS`         | `1` (forçado)     | `main.py` → stubs de Qt  |
| `RTS_LOG_LEVEL`        | `INFO`            | `rts_core.py`            |
| `RTS_STATUS_PORT`      | `5001`            | `rts_core.py`            |
| `RTS_BUSINESS_START`   | `08:00`           | `business_hours.py`      |
| `RTS_BUSINESS_END`     | `17:50`           | `business_hours.py`      |
| `RTS_BUSINESS_DAYS`    | `0,1,2,3,4`       | `business_hours.py`      |
| `TZ`                   | `America/Recife`  | container                |

## Atualização / deploy de nova versão

```bash
cd /opt/rts
git pull
cd docker/scripts
bash build.sh          # rebuild só do que mudou
bash up.sh             # compose up -d faz rolling restart
```

Se a unit systemd estiver ativa:

```bash
sudo systemctl reload rts   # pull + up -d
# ou
sudo systemctl restart rts
```

## Regras de negócio preservadas

- **RTS está sempre ON** dentro do container: não há botão ligar/desligar
  nem timeout de inatividade.
- **Renovação de token** (JD e WhatsApp) ocorre 24/7, independente do
  expediente. Isso é crítico para que o sistema esteja pronto às 08:00
  sem exigir intervenção manual.
- **Alertas e métricas só contam seg–sex 08:00–17:50** (configurável via
  `RTS_BUSINESS_*`). Fora dessa janela, o loop dorme 60s e repete.

## Troubleshooting

| Sintoma                                         | Checar                                         |
| ----------------------------------------------- | ---------------------------------------------- |
| `rts-core` em restart loop                      | `bash logs.sh rts-core` — normalmente é MySQL inacessível ou `.env` mal montado |
| `rts-dashboard` sobe e cai                      | `serviceAccount.json` não montado corretamente |
| Alertas não saem mesmo em horário comercial     | `/status` mostra `is_business_hours:false`? TZ incorreto no host |
| Token WhatsApp expira sem renovar               | `APP_ID` / `APP_SECRET` / `WPP_ACCOUNT_ID` ausentes no `.env` |
| `host.docker.internal` não resolve              | Linux antigo: adicionar `extra_hosts` manualmente (já está no compose) |

Consulte também **`VM_SETUP.md`** para o passo-a-passo em Ubuntu 22.04.
