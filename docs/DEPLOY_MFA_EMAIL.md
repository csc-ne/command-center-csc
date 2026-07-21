# Deploy — Migração MFA Email (Command Center)

Migra o MFA de TOTP/Authenticator para código de 6 dígitos por email + push approval.
Remove device trust — fluxo simplificado: sempre email + senha + código por email.

## Arquivos alterados (copiar para a VM)

```
portal/
├── .env                                    # PORTAL_BACKEND_URL corrigido, DEVICE_TRUST_DAYS comentado
├── database/
│   ├── command_center_schema.sql           # totp_secrets/trusted_devices → mfa_email_codes
│   └── migrations/
│       └── 001_mfa_email_migration.sql     # migration incremental
├── backend/
│   ├── package.json                        # sem otplib/qrcode
│   ├── package-lock.json                   # regenerado
│   ├── middleware/auth.js                   # sem getDeviceHash/isDeviceTrusted
│   ├── routes/mfa.js                       # reescrito (email code + push)
│   ├── routes/auth.js                      # sem login-mfa/check-device
│   └── services/email.js                   # novo template sendMfaLoginCode
└── frontend/
    └── index.html                          # sem QR/setup/mfa-only, com polling push
```

## Passo a passo na VM (192.168.0.106)

### 1. Copiar arquivos

Copie todos os arquivos listados acima para a pasta do portal na VM, sobrescrevendo os existentes.

### 2. Executar a migration no banco

```bash
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza \
     -f portal/database/migrations/001_mfa_email_migration.sql
```

Isso vai:
- Criar a tabela `mfa_email_codes` no schema `command_center`
- Setar `mfa_enabled = TRUE` para todos os usuários ativos
- Dropar `totp_secrets` e `trusted_devices`

Verificar:
```bash
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza \
     -c "SELECT table_name FROM information_schema.tables WHERE table_schema='command_center' ORDER BY table_name;"
```

Esperado: 7 tabelas (antes eram 8 — saíram `totp_secrets` e `trusted_devices`, entrou `mfa_email_codes`):
- approval_tokens
- audit_logs
- email_verifications
- login_attempts
- mfa_email_codes
- sessions
- users

### 3. Rebuild dos containers

```bash
cd portal/docker
docker compose -f docker-compose.prod.yml down
docker compose --env-file ../.env -f docker-compose.prod.yml up -d --build
```

O `--build` é obrigatório porque o `package.json` mudou (removeu otplib/qrcode) e o `npm ci` roda no build da imagem.

### 4. Verificar logs

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Conferir:
- `[EMAIL] SMTP conectado com sucesso.` — SMTP OK
- Nenhum erro de `otplib` ou `qrcode` (módulos removidos)
- Nenhum erro de `trusted_devices` ou `totp_secrets` (tabelas removidas)

### 5. Testar

1. Abrir `http://192.168.0.106:4001`
2. Digitar email @venezanet.com → vai direto para tela de senha (sem check-device)
3. Digitar senha → deve aparecer "Código de 6 dígitos enviado para [email]"
4. Checar email — deve ter chegado email com código + botão "Autorizar login"
5. Digitar o código de 6 dígitos → login completo
6. **OU** clicar no botão "Autorizar login" no email → login completa automaticamente via polling
7. Testar "Reenviar código" — deve enviar novo código e invalidar o anterior
8. Testar código expirado (esperar 5 min) — deve dar erro e pedir novo

## Rollback (se necessário)

Se precisar voltar ao TOTP:

```bash
# 1. Restaurar arquivos antigos (git checkout ou backup)
git checkout -- portal/backend/routes/mfa.js portal/backend/routes/auth.js \
  portal/backend/middleware/auth.js portal/backend/services/email.js \
  portal/backend/package.json portal/frontend/index.html portal/.env

# 2. Restaurar tabelas no banco
psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza \
     -f portal/database/command_center_schema.sql

# 3. Rebuild
cd portal/docker
docker compose -f docker-compose.prod.yml down
docker compose --env-file ../.env -f docker-compose.prod.yml up -d --build
```

Nota: os secrets TOTP dos usuários serão perdidos — todos terão que reconfigurar o authenticator.

## Impacto nos usuários

- Todos os usuários existentes perdem o setup TOTP anterior
- No próximo login (email + senha), recebem código por email automaticamente
- Não precisam mais de app autenticador
- Se o SMTP falhar, o login fica bloqueado (sem fallback)
