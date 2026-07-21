# Inventário de Higienização — RTS / RTA / RDA

**Data:** 2026-05-22
**Fase:** 1 de 4 (higienização)
**Regra aplicada:** nada foi apagado. O que não é produção foi movido para uma pasta `_legacy/` dentro de cada projeto. Tudo é reversível (basta mover de volta, ou `git checkout`).

**Critério objetivo de "produção":** o que os `Dockerfile` / `docker-compose.yml` referenciam (build ou bind-mount), mais o que roda no host por design (GUI PySide6 e Firebase Functions do RTS, conforme comentários no próprio `docker-compose.yml`).

---

## 1. RTS

### Movido para `RTS/_legacy/`

| Item | Tipo | Por que não é produção |
|---|---|---|
| `rts_docs_marco/` (era a pasta interna `RTS/RTS/`) | 31 docs `.md`/`.txt` de março | Resíduo da reorganização anterior. Pasta aninhada com mesmo nome do projeto. Excluída do build pelo `.dockerignore`. |
| `.archive/` | Docs + scripts antigos | Já era um arquivo morto declarado. |
| `docs/` | Documentação de março | Histórica; nenhum container referencia. |
| `debug/` | Scripts de teste/diagnóstico | Excluída do build pelo `.dockerignore`. |
| `initializer/` | Dashboard antigo + `_old/` (backups) | `initializer/dashboard/ARCHIVED.md` declara a pasta arquivada. O dashboard atual é a raiz (`index.html` + `connection/`). |
| `production/` | `ENV_TEMPLATE.env` + `PRODUCTION_README.md` | Apenas documentação. |
| `.env.backup` | Backup do `.env` | Cópia antiga de credenciais. |
| `gitignore_bk.txt` | Backup do `.gitignore` | Cópia antiga. |
| `AdesivoMelhorCSC_.png` | Imagem 4.9 MB | Duplicata (com `_` no nome) de `AdesivoMelhorCSC.png`. A versão sem `_` é a usada no `Dockerfile.dashboard`. |
| `oldfavicon.png` | Imagem | O nome declara "old". O favicon ativo é `favicon.jpg`. |
| `dash-alerts-main.zip` | Arquivo `.zip` | Pacote compactado antigo. |
| `RTS_SERVER.bat` | Script `.bat` | O próprio arquivo diz "DEPRECIADO — substituído por START.bat". |

### Mantido — produção

Núcleo Python (conteinerizado): `main.py`, `rts_core.py`, `alerts_api.py`, `whatsapp_api.py`, `BD_alertas.py`, `batch_alert_sender.py`, `validators.py`, `token_wpp_manager.py`, `business_hours.py`, `runtime_config.py`, `jd_token_manager.py`, `force_renew_media.py`, `refreshing_token.py`, `lib/`.
Dashboard web (conteinerizado): `connection/`, `index.html`, `login.html`, `script.js`, `style.css`, `src/`, `audios/`, e os assets `logo.png`, `logoJD.png`, `favicon.jpg`, `backgroundCSC.jpg`, `WIRTGEN_Logo.png`, `whatsapp-icon-logo.png`, `AdesivoMelhorCSC.png`, `OperadorNota1000.mp4`.
Roda no host por design (não conteinerizado): `interface/` (GUI PySide6), `functions/` (Firebase).
Infra/config: `docker/`, `.env`, `.dockerignore`, `.gitignore`, `.firebaserc`, `firebase.json`, `.token_cache.json`, `package.json`, `package-lock.json`, `requirements.txt`, `README.md`, `logo/`.
`START.bat` — **mantido**: é o iniciador atual no host (sobe auth John Deere + dashboard + GUI).

### Itens antes em dúvida — investigados e resolvidos

Movidos para `_legacy/` (confirmados mortos após leitura de cada arquivo):

| Item | Por que é morto |
|---|---|
| `RTS_PLAY.bat` | O próprio arquivo se declara "DEPRECIADO — substituído por START.bat". |
| `CREATE_ENV.bat` | Gera um `.env` desatualizado (faltam chaves atuais: `SESSION_SECRET`, `APP_ID`, `APP_SECRET`, `REFRESH_TOKEN`, `PHONE_NUMBER_ID`) e contém marcadores de conflito de merge não resolvidos (`<<<<<<< HEAD`). |
| `deploy_wpp_toggle.ps1` | Deploy pontual da feature "WPP Toggle", já entregue. Operações genéricas de container estão em `docker/scripts/`. |
| `import-data-to-db.py` | Seed único da tabela `contatos` a partir de um Excel em `C:/Users/robert.araujo/Downloads/` — caminho inexistente nesta máquina. |
| `libs.txt` | Lista de pacotes não-pinada (dump tipo `pip list`); o arquivo curado e pinado é `requirements.txt`. |

Mantidos na raiz (funcionais — não são mortos):

| Item | Por que fica |
|---|---|
| `STOP.bat` | Par do `START.bat` — encerramento atual no host. |
| `SETUP_SCHEDULER.bat`, `REMOVE_SCHEDULER.bat` | Agendador do modo host (07:00 / 17:50), coerente com `START.bat`/`STOP.bat`. |
| `START_NODE.bat` | Atalho funcional para subir só o servidor Node. |
| `create_sa.py` | Bootstrap do `connection/serviceAccount.json`. |
| `export_alerts.py` | Utilitário funcional de exportação da tabela `alertas` para Excel. |

### Recomendado apagar — build artifacts (regeneráveis)

| Item | Tamanho |
|---|---|
| `venv/` | 757 MB |
| `node_modules/` | 252 MB |
| `functions/node_modules/` | 57 MB |
| `__pycache__/` | 176 KB |

Total RTS: **~1,06 GB**. São diretórios recriáveis e específicos da máquina onde foram gerados — não deveriam estar numa cópia do repositório.

---

## 2. RDA

### Movido para `RDA/_legacy/`

| Item | Por que não é produção |
|---|---|
| `backend/app_original.py` | Versão antiga. O `Dockerfile.rda-backend` usa `app.py`. O próprio `.dockerignore` já o excluía do build. |
| `backend/report_0.2.6.4.py` | Versão antiga. `app.py` (produção) carrega `report_0.2.6.5.py`. |
| `kernel/modulo_sql.py` | Não é importado por ninguém. Os dois `report_*.py` importam `modulo_sql_rev2`. |
| `pdf/_init__.py` | Erro de digitação (1 underscore). Duplica o `__init__.py` correto, que permanece. |

### Mantido — produção

`backend/{app.py, report_0.2.6.5.py, package.json}`, `frontend/`, `kernel/` (sem o `modulo_sql.py`), `pdf/` (sem o typo), `fonts/`, `labels/`, `icons/`, `docker/`, `relatorios_gerados/` (alvo de volume), `.env`, `.dockerignore`.

RDA não tinha `venv/`, `node_modules/` nem `__pycache__/` na cópia — está limpo nesse aspecto.

---

## 3. RTA

Você recopiou a pasta da VM. Ela chegou **limpa e correta** — sem contaminação do RDA (o problema relatado na análise anterior não existe mais nesta cópia).

Conteúdo: `backend/{server.js, db.js, queries.js, package.json, package-lock.json}`, `frontend/{index.html, favicon.jpg}`, `docker/{Dockerfile.rta, docker-compose.yml}`, `logo/`, `.env`.

Verificado: o `docker-compose.yml` é o correto do RTA (serviço `rta`, porta 3021, usa `Dockerfile.rta`); o `.env` é o do RTA (`RTA_PG_*`, `RTA_PORT=3021`). **Nada a mover.**

Único item regenerável: `backend/node_modules/` (5,3 MB) — opcional apagar.

---

## 4. Mudança técnica aplicada

`_legacy/` foi adicionado ao `.dockerignore` do RTS e do RDA, para que a pasta de legados não entre no contexto de build das imagens Docker.

## 5. Achado de segurança (não corrigido — fora do escopo desta fase)

Segredos reais em texto puro dentro do repositório, registrados aqui para você tratar depois:

- `create_sa.py` (raiz do RTS) embute a **chave privada do service account do Firebase** em texto puro.
- `_legacy/CREATE_ENV.bat` embute credenciais reais (`USERDB`/`PSS` do MySQL, `clientSecret` do John Deere).
- `RTA/.env`, `RDA/.env` e `RTS/.env` têm a senha do Postgres (`331477`) em texto puro; `portal/.env` tem a senha real do Office365.

Recomendação: rotacionar essas credenciais e nunca versioná-las. Posso tratar isso numa etapa dedicada se você quiser.

## 6. Pendências para você decidir

1. **Build artifacts** (`venv/` 757MB, `node_modules/` 252MB, `functions/node_modules/` 57MB, `__pycache__/`) — apagar? Liberam ~1 GB. Ainda aguardando sua confirmação.
2. **Conteúdo das pastas `_legacy/`** — revise quando puder. Quando liberar, eu apago o que autorizar.
