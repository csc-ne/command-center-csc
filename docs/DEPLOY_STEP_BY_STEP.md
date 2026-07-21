# Deploy Passo-a-Passo — do Git ate a VM em Producao

Comandos exatos, na ordem, para levar este repositorio do tester local
ate a VM `192.168.0.106` e subir cada sistema um por um, testando
individualmente antes de seguir.

---

## Parte 1 — Colocar o repo no GitHub (feito no tester)

### 1.1 Criar o repo novo no GitHub (manual, via navegador)

- Login em https://github.com/csc-ne
- **New repository**
- Nome sugerido: `command-center-csc`
- **NAO** marque "Initialize with README", `.gitignore` ou license
  (o repo local ja tem esses arquivos)
- Copie a URL HTTPS ou SSH do novo repo

### 1.2 Apagar o `.git/` antigo e criar repo Git novo

O `.git/` atual aponta pra `csc-ne/RTS.git`. Vamos comecar do zero para
o commit ficar limpo e sem historico misturado.

> Backup fisico: voce ja tem o zip em `C:\backup-csc\`. A tag
> `pre-reorg-2026-07-21` esta dentro do `.git/` que sera apagado — mas
> o zip cobre o rollback.

```powershell
cd "C:\Users\Henrique - veneza\Desktop\COMAND CENTER CSC"

# Apaga historico Git antigo
Remove-Item -Recurse -Force .git

# Inicializa repo novo na branch main
git init -b main

# Config de identidade (se ainda nao tiver global)
git config user.email "henrique.albuquerque@venezanet.com"
git config user.name "Henrique Albuquerque"
```

### 1.3 Confirmar que nenhum segredo vai pro Git

```powershell
# Simula o que seria commitado — se algum .env aparecer aqui, ABORTA
git status --ignored | Select-String "\.env|_SECRETS|serviceAccount\.json"
```

Esperado: as linhas devem estar dentro do bloco `Ignored files:`. Se
qualquer `.env` aparecer em **Untracked files** (fora de Ignored),
alguma coisa no `.gitignore` esta furada. Nao siga.

Alternativa mais direta:
```powershell
git check-ignore -v .env sistemas\rts\.env sistemas\rts\connection\serviceAccount.json
```

Deve retornar cada arquivo com a linha do `.gitignore` que o pega.

### 1.4 Primeiro commit

```powershell
git add .
git status  # confira o que esta indo — nenhum .env, nenhum node_modules

git commit -m "chore: initial commit - command center csc reorganizado

- Consolida 9 arquivos .env em C:\env\.env (fora do repo)
- Extrai chave privada Firebase e emails admin de codigo hardcoded
- Reorganiza sistemas em sistemas/ (portal/rts/rta/rda/rca/fleet-intelligence)
- Renomeia Fleet Inteligence -> fleet-intelligence
- Remove als/ (fora de prod, mesma porta do RCA)
- Remove 1.5 GB de peso morto (venv, node_modules, PDFs, _legacy)"
```

### 1.5 Conectar ao GitHub e enviar

```powershell
git remote add origin https://github.com/csc-ne/command-center-csc.git
git push -u origin main
```

Se pedir credenciais, use um Personal Access Token do GitHub (Settings
-> Developer settings -> Personal access tokens -> generate new,
escopo `repo`).

---

## Parte 2 — Preparar a VM `192.168.0.106`

Faca via RDP na VM Windows Server.

### 2.1 Confirmar que `C:\env\.env` existe

```powershell
Test-Path C:\env\.env
```

Deve retornar `True`. Se nao, copie do `_SECRETS_CONSOLIDATED.txt`
(que voce ainda tem — ou tinha — na VM).

### 2.2 Backup do estado atual da VM (por seguranca)

```powershell
# Ajuste o path se seu deploy antigo estiver em outro lugar
$OldPath = "C:\deploy\command-center"  # ou onde voce colocou hoje
$BackupPath = "C:\backup-csc\vm-pre-reorg-$(Get-Date -Format 'yyyy-MM-dd_HHmm').zip"

if (Test-Path $OldPath) {
    Compress-Archive -Path $OldPath -DestinationPath $BackupPath
    Write-Host "Backup criado em $BackupPath"
}
```

### 2.3 Derrubar TODOS os containers antigos

```powershell
# Lista tudo que esta rodando
docker ps

# Derruba todos os containers CSC (nomes sao previsiveis)
docker stop portal-backend portal-frontend `
            rts-core rts-dashboard `
            rta-dashboard `
            rda-frontend rda-backend `
            rca-dashboard `
            fi-backend fi-frontend `
            csc-db csc-backend csc-frontend `
            dfa-db dfa-backend dfa-frontend `
            psi-backend psi-frontend `
            als-dashboard 2>$null

# Remove os containers parados (nao afeta os volumes)
docker container prune -f
```

### 2.4 Clonar o repo novo

```powershell
# Sugestao de path: C:\command-center-csc
cd C:\
git clone https://github.com/csc-ne/command-center-csc.git
cd command-center-csc
```

### 2.5 Sanity check antes de subir

```powershell
# Verifica que sistemas/ existe e os composes estao la
Test-Path sistemas\portal\docker\docker-compose.prod.yml
Test-Path sistemas\rts\docker\docker-compose.yml
Test-Path sistemas\rta\docker\docker-compose.yml
Test-Path sistemas\rda\docker\docker-compose.yml
Test-Path sistemas\rca\docker\docker-compose.yml
Test-Path sistemas\fleet-intelligence\docker-compose.yml

# Verifica que o .env central esta acessivel
Test-Path C:\env\.env

# Verifica que Docker Desktop esta rodando
docker version
```

Todos devem retornar `True` / sem erro.

---

## Parte 3 — Subir sistema por sistema, testando cada um

**Ordem obrigatoria:** Portal primeiro (emite JWT). Depois os
sub-dashboards do Portal (dependem de `PORTAL_JWT_SECRET`). Depois
os satelites (RTS, RTA, RDA, RCA, Fleet).

Depois de cada sistema, verifique log + health antes de subir o proximo.

### 3.1 Portal (Command Center)

```powershell
cd C:\command-center-csc\sistemas\portal\docker
docker compose --env-file C:\env\.env -f docker-compose.prod.yml up -d --build

# Aguarde ~30s e verifique
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f portal-backend
```

**Log esperado:**
- `[EMAIL] SMTP conectado com sucesso.`
- Nenhum erro de conexao com Postgres.
- `portal-backend rodando na porta 4000` ou similar.

**Teste manual:**
- Abra no navegador: `http://192.168.0.106:4001`
- Deve carregar a tela de login.
- Faca login com email @venezanet.com — deve receber MFA no email.

**Se falhar:** `docker compose -f docker-compose.prod.yml logs portal-backend`
mostra o erro. Comum: `PORTAL_JWT_SECRET` ausente do `.env` central.

### 3.2 Sub-dashboards do Portal

```powershell
cd C:\command-center-csc\sistemas\portal\csc-dashboard\docker
docker compose --env-file C:\env\.env up -d --build
docker compose logs -f csc-backend
```
Teste: `http://192.168.0.106:4011` — deve pedir login via Portal e
redirecionar de volta com sessao ativa.

```powershell
cd C:\command-center-csc\sistemas\portal\dfa-dashboard\docker
docker compose --env-file C:\env\.env up -d --build
docker compose logs -f dfa-backend
```
Teste: `http://192.168.0.106:4013`

```powershell
cd C:\command-center-csc\sistemas\portal\psi-dashboard\docker
docker compose --env-file C:\env\.env up -d --build
docker compose logs -f psi-backend
```
Teste: `http://192.168.0.106:4015`

### 3.3 RTS

```powershell
cd C:\command-center-csc\sistemas\rts

# Gera serviceAccount.json a partir das vars FIREBASE_* do .env central
# (primeira vez apenas, ou apos rotacao da chave Firebase)
python create_sa.py

cd docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f rts-core
```

**Log esperado (rts-core):**
- `Loading .env from /app/.env`
- Loop iniciado, primeira consulta a API John Deere OK.
- Se OAuth JD falhar, precisa autenticar manualmente via
  `sistemas\rts\interface\johndeere\JohnDeereAPI.py` no host.

**Log esperado (rts-dashboard):**
- `[RTS] .env carregado de: /app/.env`
- `[RTS] Real Time Support rodando na porta 8080`

**Teste:** `http://192.168.0.106:8080`

### 3.4 RTA

```powershell
cd C:\command-center-csc\sistemas\rta\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f rta
```

**Log esperado:**
- `[RTA] Real Time Alert rodando na porta 3021`
- `[RTA] Nova conexao PostgreSQL estabelecida`

**Teste:** `http://192.168.0.106:3021`

### 3.5 RDA

```powershell
cd C:\command-center-csc\sistemas\rda\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f
```

**Log esperado:**
- `rda-backend` health OK (porta 5051 interna).
- `rda-frontend` roteando na porta 5050.

**Teste:** `http://192.168.0.106:5050` — gere um relatorio de teste.

### 3.6 RCA

```powershell
cd C:\command-center-csc\sistemas\rca\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f rca
```

**Teste:** `http://192.168.0.106:3031`

### 3.7 Fleet Intelligence

```powershell
cd C:\command-center-csc\sistemas\fleet-intelligence
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml logs -f
```

**Log esperado:**
- `fi-backend` conecta no Postgres schema `fleet_inteligence`.
- `fi-frontend` (nginx) na porta 8087.

**Teste:** `http://192.168.0.106:8087`

---

## Parte 4 — Verificacao final

### 4.1 Status geral

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Sort-Object
```

Esperado: 14 containers ativos, todos com `Up X minutes (healthy)` ou
`Up X minutes` (nem todos tem healthcheck).

### 4.2 Fluxo completo de teste end-to-end

1. Abrir aba anonima: `http://192.168.0.106:4001`
2. Login com email @venezanet + MFA por email.
3. Navegar entre sistemas usando os botoes do Portal.
4. Cada sistema deve carregar SEM pedir login de novo (SSO funcionando).
5. No RTS, verificar que aparecem alertas recentes (loop rodando).
6. No RDA, gerar um relatorio de teste com PIN qualquer.
7. No Fleet, criar um card qualquer e arrastar entre fases.

### 4.3 Se algo quebrou

```powershell
# Ver logs de qualquer container
docker logs <nome-do-container> --tail 100

# Restart pontual (sem rebuild)
docker restart <nome-do-container>

# Rebuild de um sistema so
cd C:\command-center-csc\sistemas\<sistema>\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build --force-recreate
```

**Rollback total:**
```powershell
cd C:\
Rename-Item command-center-csc command-center-csc.broken
Expand-Archive C:\backup-csc\vm-pre-reorg-*.zip -DestinationPath C:\command-center-csc-old
# ... e siga o DEPLOY_VM.md antigo (backup no zip)
```

---

## Parte 5 — Atualizacoes futuras (fluxo normal)

Depois desse setup inicial, mudancas rotineiras (voce edita local, testa,
sobe pra VM) seguem:

**No tester (Windows local):**
```powershell
cd "C:\Users\Henrique - veneza\Desktop\COMAND CENTER CSC"
# ... edita arquivos ...
git add .
git commit -m "descricao do que mudou"
git push
```

**Na VM (via RDP):**
```powershell
cd C:\command-center-csc
git pull

# Rebuild apenas do sistema afetado
cd sistemas\<sistema>\docker
docker compose --env-file C:\env\.env -f docker-compose.yml up -d --build
```

Nao precisa mais copiar arquivos manualmente. O `.env` fica intocado
em `C:\env\.env` (fora do repo).
