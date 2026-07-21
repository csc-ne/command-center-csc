# Fleet Intelligence

Plataforma de workflow (Kanban) para gerenciar a jornada de equipamentos da frota —
organiza trabalho por responsabilidade e prioridade, transformando dados em filas
de ação. MVP da fase 1: login, criação de fluxos, fases e cards arrastáveis.

Inspirado em Pipefy / Linear. Preparado para crescer nas próximas fases com
Machine List, POPs, Planos, Conectividade e alertas inteligentes.

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 14+
- **Frontend:** React 18 · Vite · TailwindCSS · @dnd-kit · lucide-react
- **Auth:** JWT (HS256) + bcrypt
- **Deploy:** Docker Compose (backend + frontend/nginx)
- **DB:** PostgreSQL da VM (host da 192.168.0.106), banco `csc_veneza`,
  schema dedicado **`fleet_inteligence`** (para conviver com outras aplicações
  no mesmo banco sem conflito de tabelas)

## Estrutura

```
Fleet Inteligence/
├── backend/               # FastAPI
│   ├── app/
│   │   ├── api/          # rotas: auth, users, boards, phases, cards
│   │   ├── core/         # security (JWT/bcrypt), seed admin
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── config.py     # settings via .env
│   │   ├── database.py   # engine + session
│   │   └── main.py       # FastAPI app
│   ├── sql/init.sql      # schema + seed admin
│   └── Dockerfile
├── frontend/              # React + Vite
│   ├── src/
│   │   ├── api/          # axios client
│   │   ├── components/   # Kanban, UI, Layout, ThemeToggle
│   │   ├── context/      # Auth + Theme
│   │   ├── pages/        # Login, Boards, BoardView
│   │   ├── lib/utils.js
│   │   ├── App.jsx · main.jsx · index.css
│   ├── nginx.conf        # reverse proxy /api → backend
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Pré-requisitos na VM 192.168.0.106

1. **Docker + Compose plugin** instalados
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # faça logout/login depois
   ```
2. **PostgreSQL** já rodando e acessível. Precisa:
   - Aceitar conexão do host/container (ajuste `pg_hba.conf` e `listen_addresses` se necessário)
   - Um banco criado (veja passo 1 abaixo)
3. **Porta 80 livre** no host (a aplicação sobe em `http://192.168.0.106`)

## Deploy — passo a passo

### 1. Preparar o banco

A aplicação **reutiliza** o banco existente `csc_veneza` da VM mas instala
todas as suas tabelas dentro de um schema isolado chamado `fleet_inteligence`,
para não colidir com outras aplicações que também moram em `csc_veneza`
(ex.: CSC Veneza).

O próprio `init.sql` já cuida de:
- criar o schema `fleet_inteligence` se não existir,
- criar as tabelas (`users`, `boards`, `phases`, `cards`) prefixadas pelo schema,
- instalar triggers e seed do admin inicial.

Rode o schema inicial (com o seu usuário do Postgres):

```bash
psql -U henrique -d csc_veneza -h 192.168.0.106 -f backend/sql/init.sql
```

> O usuário precisa ter permissão para `CREATE SCHEMA` em `csc_veneza`. Se
> for outro usuário que for rodar o app, conceda:
> ```sql
> GRANT USAGE ON SCHEMA fleet_inteligence TO henrique;
> GRANT ALL ON ALL TABLES IN SCHEMA fleet_inteligence TO henrique;
> GRANT ALL ON ALL SEQUENCES IN SCHEMA fleet_inteligence TO henrique;
> ALTER DEFAULT PRIVILEGES IN SCHEMA fleet_inteligence
>   GRANT ALL ON TABLES TO henrique;
> ```

> **Alternativa:** o próprio backend cria o usuário admin padrão no startup se a
> tabela `users` estiver vazia. Mas as tabelas precisam existir — rode o
> `init.sql` antes.

### 2. Configurar `.env`

```bash
cp .env.example .env
nano .env
```

Preencha com suas credenciais reais:

```env
POSTGRES_HOST=host.docker.internal   # Postgres rodando no host da VM
POSTGRES_PORT=5432
POSTGRES_USER=henrique
POSTGRES_PASSWORD=sua_senha_aqui
POSTGRES_DB=csc_veneza
# O schema fleet_inteligence é aplicado automaticamente pelo SQLAlchemy
# (ver backend/app/database.py). Não precisa configurar aqui.

# Gere uma chave forte:
JWT_SECRET_KEY=$(openssl rand -hex 64)

CORS_ORIGINS=http://192.168.0.106,http://localhost
```

> Se o Postgres estiver em **outra máquina**, use o IP dela em `POSTGRES_HOST` e
> remova o bloco `extra_hosts` do `docker-compose.yml`.

### 3. Permitir conexão do container Docker ao Postgres do host

Edite `/etc/postgresql/<versão>/main/postgresql.conf`:

```
listen_addresses = '*'
```

E em `pg_hba.conf`, adicione (ajuste usuário/banco se necessário):

```
# Permitir rede Docker acessar o banco csc_veneza
host   csc_veneza   henrique   172.16.0.0/12   md5
host   csc_veneza   henrique   192.168.0.0/16  md5
```

Reinicie:

```bash
sudo systemctl restart postgresql
```

### 4. Subir os containers

```bash
docker compose up -d --build
```

Aguarde ~30s para o build. Verifique logs:

```bash
docker compose logs -f backend
```

### 5. Acessar

Abra no navegador: **http://192.168.0.106**

Login padrão:
- Usuário: `admin`
- Senha: `admin123`

⚠️ **Troque a senha do admin no primeiro login** (rota `PATCH /api/users/{id}`).

## Endpoints principais

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| POST | `/api/auth/login` | Login (JSON) | — |
| GET  | `/api/auth/me` | Usuário atual | ✓ |
| GET  | `/api/boards` | Listar fluxos | ✓ |
| POST | `/api/boards` | Criar fluxo | ✓ |
| GET  | `/api/boards/{id}` | Fluxo com fases + cards | ✓ |
| POST | `/api/boards/{id}/phases` | Criar fase | ✓ |
| POST | `/api/cards` | Criar card | ✓ |
| POST | `/api/cards/{id}/move` | Mover card (drag-and-drop) | ✓ |
| GET  | `/api/users` | Listar usuários | ✓ |
| POST | `/api/users` | Criar usuário | admin |

Documentação interativa: **http://192.168.0.106/api/docs** (se expor porta 8000
em dev; em produção o nginx só proxyfica `/api/*`, não o `/docs` por padrão —
adicione uma location no `nginx.conf` se precisar).

## Desenvolvimento local

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # ajuste para seu Postgres local
uvicorn app.main:app --reload
# API em http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# UI em http://localhost:5173, proxyfica /api → http://localhost:8000
```

## Roadmap (próximas fases)

Com o MVP em produção, a arquitetura já suporta:

- **Base de equipamentos (Machine List + POPs)** — novo módulo que cria cards
  automaticamente num fluxo "Revisões" com base em horas de uso
- **Alertas inteligentes** — job agendado que cria cards ao detectar:
  - Revisão com 100h de antecedência
  - Máquina sem comunicar
  - Renovação de plano
- **Planos e Revisões, Conectividade** — dashboards + integração com provedores
- **Usuários/permissões mais granulares** — papéis por board

O campo `metadata` JSONB nos cards já permite anexar dados do equipamento,
plano, etc. sem migrações.

## Troubleshooting

**Backend não sobe — `could not connect to server`**
O container não alcança o Postgres. Verifique:
- `POSTGRES_HOST` no `.env` (use `host.docker.internal` para Postgres no host)
- `pg_hba.conf` permite a rede Docker
- `listen_addresses = '*'` em `postgresql.conf`
- Firewall/`ufw` liberando porta 5432 para a rede Docker

**Login diz "Usuário ou senha incorretos"**
- Confira que rodou o `init.sql` no banco `csc_veneza` e que o schema
  `fleet_inteligence` realmente existe:
  ```sql
  \dn                                    -- lista schemas
  \dt fleet_inteligence.*                -- lista tabelas do schema
  SELECT username FROM fleet_inteligence.users;
  ```
- O seed cria `admin / admin123` apenas se a tabela `users` estiver vazia
- Em último caso, redefina manualmente:
  ```bash
  docker compose exec backend python -c "from app.core.security import hash_password; print(hash_password('admin123'))"
  # então:
  # UPDATE fleet_inteligence.users SET hashed_password='<hash>' WHERE username='admin';
  ```

**Erro `relation "..." does not exist` ou tabelas não encontradas**
- Isso costuma significar que o SQLAlchemy está olhando no schema errado.
  Cheque que o `init.sql` foi executado e que o schema `fleet_inteligence`
  tem as 4 tabelas. O backend seta `search_path TO fleet_inteligence, public`
  automaticamente em cada conexão (ver `backend/app/database.py`).

**CORS bloqueado**
- Adicione o IP/domínio em `CORS_ORIGINS` no `.env` e reinicie:
  `docker compose restart backend`
