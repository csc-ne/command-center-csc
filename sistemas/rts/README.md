# RTS — Real Time Support

**Sistema de monitoramento de alertas John Deere com notificações automáticas via WhatsApp.**

Desenvolvido por Robert Araújo — Veneza Equipamentos Pesados S.A. / Centro de Soluções Conectadas (CSC) — Veneza Nordeste.

---

## Índice

- [Visão geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Como iniciar](#como-iniciar)
- [Configuração do `.env`](#configuração-do-env)
- [Fluxo do sistema](#fluxo-do-sistema)
- [Token WhatsApp — guia de atualização](#token-whatsapp--guia-de-atualização)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Testes e diagnóstico `debug/`](#testes-e-diagnóstico-debug)
- [Problemas conhecidos e soluções](#problemas-conhecidos-e-soluções)
- [Logs](#logs)

---

## Visão geral

O RTS:

1. Autentica com a API da John Deere via OAuth2
2. Consulta alertas (DTCs) das máquinas de cada cliente
3. Envia notificações automáticas via WhatsApp Business API (Meta)
4. Armazena todos os alertas e status de envio em banco MySQL
5. Reenvia automaticamente alertas que falharam (Batch Sender)

---

## Arquitetura

```
START.bat
  │
  ├── python interface\johndeere\JohnDeereAPI.py   → Flask (porta 5000)
  │   Servidor OAuth2 John Deere. Autentica e mantém o access token.
  │
  ├── node connection\server.js                    → Express (porta 8080)
  │   Dashboard web de visualização de alertas.
  │
  └── python interface\app.py                      → GUI PySide6
      │
      └── main.py (MessageShooter — QRunnable)
          │
          ├── alerts_api.py         → Busca alertas na API John Deere
          ├── BD_alertas.py         → Leitura/escrita no MySQL
          ├── whatsapp_api.py       → Envio de mensagens (Meta API)
          ├── validators.py         → Validação/normalização de telefones
          ├── batch_alert_sender.py → Reenvio automático de pendentes
          └── refreshing_token.py   → Renovação automática do token JD
```

### Camadas

| Camada | Responsável | Tecnologia |
|--------|------------|------------|
| Interface gráfica | `interface/app.py` | PySide6 |
| Loop de monitoramento | `main.py` | Python thread |
| API John Deere | `alerts_api.py` | REST + OAuth2 |
| Envio WhatsApp | `whatsapp_api.py` | Meta Graph API v17 |
| Banco de dados | `BD_alertas.py` | MySQL |
| Validação | `validators.py` | Python puro |
| Retry de envios | `batch_alert_sender.py` | Integrado ao loop |

---

## Como iniciar

### Pré-requisitos

- Python 3.10+ com venv instalado
- Node.js instalado
- MySQL rodando em `192.168.0.106`
- Token WhatsApp Business válido no `.env`

### Passos

```
1. Duplo clique em START.bat
2. Clique "Autenticar" → faça login John Deere no browser
3. Clique "Abrir Dashboard"
4. Clique "Ligar RTS"
```

O sistema começa a monitorar alertas e enviar WhatsApp automaticamente.

---

## Configuração do `.env`

```env
# ── John Deere OAuth2 ──────────────────────────────────────
clientId=0oao7mbg8lE1wBD0Q5d7
clientSecret=<seu_client_secret>

# ── MySQL ──────────────────────────────────────────────────
USERDB=robert
PSS=<senha_mysql>
IPDESKTOPDB=192.168.0.106

# ── MySQL (Node.js dashboard) ──────────────────────────────
USERNAME_DB=robert
PASSWORD_DB=<senha_mysql>
HOST_DB=192.168.0.106
SCHEMA_DB=bancovz

# ── WhatsApp Business API (Meta) ───────────────────────────
TKWPP=<token_meta>           # Token de acesso. Atualizar quando expirar.
MEDIAIDWPP=<media_id>         # ID da imagem do template (auto-gerenciado)
MEDIAIDEXP=<YYYY-MM-DD>       # Data de criação do media ID (auto-gerenciado)
PHONE_NUMBER_ID=103829652641038  # ID do número WhatsApp Business

# ── Meta App (para renovação automática) ───────────────────
APP_ID=1161066658108111
APP_SECRET=<app_secret>
WPP_ACCOUNT_ID=103829652641038
```

---

## Fluxo do sistema

### Loop principal (main.py — MessageShooter)

```
Loop externo (eterno):
  ├── Verifica status_rts (ON/OFF)
  ├── Para cada cliente em contatos:
  │   ├── Busca alertas na API John Deere
  │   ├── Para cada alerta do dia:
  │   │   ├── Consulta BD: alerta já enviado?
  │   │   └── Não enviado → send_alert() → send_wpp() → INSERT no BD
  │   └── ...
  └── Timer (300 iterações × 1s = 5 min):
      └── A cada 60s: send_pending_alerts() (Batch Sender)
```

### Batch Sender (batch_alert_sender.py)

Roda automaticamente a cada ~60 segundos dentro do loop:

```
SELECT alertas WHERE ENVIADO_PARA IN (NULL, 'WPP_NAO_ENVIADO', '')
Para cada alerta:
  └── Busca JDLink_ID → Busca telefone → Valida → send_wpp() → UPDATE BD
```

---

## Token WhatsApp — guia de atualização

### Por que o token precisa ser atualizado?

O token da Meta WhatsApp Business API pode expirar ou ser revogado. Quando isso ocorre, todos os envios falham com erro **401 Unauthorized**.

### Sintomas de token expirado

- Nenhum WhatsApp enviado mesmo com o RTS ligado
- Mensagem na interface: `Token WhatsApp inválido ou expirado!`
- Log em `logs/output/errors_YYYY-MM-DD.log`: `HTTPError: 401 Client Error: Unauthorized`

### Como atualizar o token

1. Acesse [Meta for Developers](https://developers.facebook.com/tools/explorer/)
2. Selecione seu app → Gere um novo User Access Token (permanente)
3. Abra o arquivo `.env` na raiz do projeto
4. Atualize a linha `TKWPP=<novo_token>`
5. **Não é necessário reiniciar o RTS** — o sistema lê o token do `.env` a cada envio

O Batch Sender irá reenviar automaticamente os alertas que ficaram com `WPP_NAO_ENVIADO` nos próximos 60 segundos.

---

## Estrutura de pastas

```
RTS/
├── .env                        # Configurações (não commitado)
├── README.md                   # Este arquivo
├── START.bat                   # Inicializador principal
├── STOP.bat                    # Para o RTS
│
├── main.py                     # Loop de monitoramento (MessageShooter)
├── whatsapp_api.py             # Envio WhatsApp Meta API
├── BD_alertas.py               # Operações MySQL
├── alerts_api.py               # API John Deere
├── batch_alert_sender.py       # Reenvio automático de pendentes
├── validators.py               # Validação/normalização de telefones
├── refreshing_token.py         # Renovação token John Deere
│
├── interface/                  # GUI PySide6
│   ├── app.py                  # Janela principal
│   ├── johndeere/
│   │   └── JohnDeereAPI.py     # Servidor Flask OAuth2 (porta 5000)
│   ├── forms/                  # Formulários de cadastro/edição
│   ├── signals/
│   │   └── Signals.py          # Sinais Qt entre threads
│   └── utils/
│       ├── check_auth.py       # Verifica autenticação JD
│       ├── field_widget.py     # Widget de campo customizado
│       └── open_bat_files.py   # Abre arquivos .bat
│
├── connection/                 # Dashboard Node.js
│   ├── server.js               # Express (porta 8080)
│   └── db.js                   # Conexão MySQL (Node)
│
├── logs/                       # Logs do sistema
│   ├── src/
│   │   └── loggers.py          # Logger centralizado
│   └── output/                 # Arquivos de log gerados
│       ├── errors_YYYY-MM-DD.log
│       ├── info_YYYY-MM-DD.log
│       ├── auth_server.log
│       └── dashboard.log
│
├── debug/                      # Testes e diagnóstico
│   ├── RUN_ALL_TESTS.py        # Executa toda a suíte de testes
│   ├── test_token_flow.py      # Testa fluxo do token WhatsApp
│   ├── test_whatsapp_send.py   # Testa envio WhatsApp (mock + real)
│   ├── test_database.py        # Testa conectividade MySQL
│   ├── test_phone_validation.py# Testa validação de telefones
│   ├── test_media_id.py        # Testa Media ID WhatsApp
│   ├── test_batch_sender.py    # Testa Batch Sender
│   ├── test_startup_env.py     # Testa ambiente e configuração
│   ├── logs/                   # Logs dos testes
│   ├── scripts/                # Scripts avulsos de diagnóstico
│   └── utils/                  # Utilitários de debug
│
└── docs/                       # Documentação histórica e análises
```

---

## Testes e diagnóstico `debug/`

### Executar todos os testes

```bat
cd <raiz do projeto>
venv\Scripts\activate
python debug\RUN_ALL_TESTS.py
```

### Testes individuais

| Arquivo | O que testa |
|---------|------------|
| `test_token_flow.py` | Bug principal corrigido: token dinâmico vs módulo congelado |
| `test_whatsapp_send.py` | Envio WhatsApp (mocked) + validação de token real |
| `test_database.py` | Conexão MySQL, tabelas, queries |
| `test_phone_validation.py` | Validação/normalização de telefones |
| `test_media_id.py` | Expiração e renovação de Media ID |
| `test_batch_sender.py` | Reenvio automático de alertas pendentes |
| `test_startup_env.py` | Ambiente, dependências, portas |

### Diagnóstico rápido de token

```bat
venv\Scripts\activate
python debug\test_whatsapp_send.py
```

Se W08 mostrar `FAIL Token INVÁLIDO ou EXPIRADO`, atualize `TKWPP` no `.env`.

---

## Problemas conhecidos e soluções

### 401 Unauthorized nos envios WhatsApp

Causa: Token expirado/revogado.

Solução:
1. Acesse [Meta for Developers](https://developers.facebook.com/tools/explorer/)
2. Gere novo token permanente
3. Cole em `TKWPP=` no `.env`
4. O sistema pega automaticamente no próximo envio (sem restart)

### Alertas com `ENVIADO_PARA = WPP_NAO_ENVIADO`

Causa: Token estava inválido quando o alerta foi processado.

Solução: Após atualizar o token, o Batch Sender reenvia automaticamente a cada 60s. Para reenviar imediatamente:

```bat
venv\Scripts\activate
python batch_alert_sender.py
```

### Media ID expirado (erro 400)

Causa: Media ID válido por 25 dias. Se `MEDIAIDEXP` está vencido, o sistema renova automaticamente no startup. Para forçar a renovação manual, atualize o token e reinicie o RTS.

### Dashboard não abre

Causa: Node.js não instalado ou `node_modules` ausente.

Solução:
```bat
npm install
node connection\server.js
```

---

## Logs

Os logs ficam em `logs/output/`:

| Arquivo | Conteúdo |
|---------|---------|
| `errors_YYYY-MM-DD.log` | Erros e exceções do loop de monitoramento |
| `info_YYYY-MM-DD.log` | Eventos informativos (startup, renovações) |
| `auth_server.log` | Saída do servidor Flask (John Deere) |
| `dashboard.log` | Saída do servidor Node.js (dashboard) |

---

## Histórico de correções

| Data | Arquivo | Correção |
|------|---------|---------|
| 26/03/2026 | `whatsapp_api.py` | **Bug crítico**: `tok` era variável de módulo congelada. Substituído por `_get_token()` que lê do `.env` com `override=True` a cada chamada |
| 26/03/2026 | `whatsapp_api.py` | `post_media_id()` usava `open("logo.png")` com caminho relativo. Substituído por `_LOGO_PATH` absoluto |
| 26/03/2026 | `whatsapp_api.py` | URL da API agora usa `PHONE_NUMBER_ID` do `.env` |
| 26/03/2026 | `main.py` | Mensagem específica para 401 orienta o operador a atualizar o token |
