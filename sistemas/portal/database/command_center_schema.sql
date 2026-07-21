-- =====================================================================
-- COMMAND CENTER CSC — Schema de autenticação (MFA/TOTP + registro + audit)
-- =====================================================================
-- Alvo: banco de PRODUÇÃO  csc_veneza  (PostgreSQL @ 192.168.0.106:5432)
-- Schema dedicado: command_center
--   → isolado de layer_bronze / public / demais objetos do RTA e RDA.
--
-- COMO EXECUTAR:
--   psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza -f command_center_schema.sql
--
-- Observações:
--   • Script IDEMPOTENTE — pode ser re-executado sem erro.
--   • O usuário que executar (henrique) torna-se dono do schema e das tabelas.
--   • Substitui o antigo banco dedicado portal_auth. As tabelas são as mesmas
--     do database/init.sql original, agora qualificadas no schema command_center.
-- =====================================================================

-- gen_random_uuid() é nativo do PostgreSQL >= 13.
-- Se o csc_veneza rodar PostgreSQL < 13, descomente a linha abaixo:
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── Schema ──────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS command_center;

SET search_path TO command_center, public;

-- ─── Enums ───────────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE command_center.user_role AS ENUM ('admin', 'operador', 'visualizador');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE command_center.user_status AS ENUM ('pending_verification', 'pending_approval', 'active', 'inactive');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── users ───────────────────────────────────────────────────────────────────
-- Cadastro de usuários @venezanet.com. Fonte única de identidade para o
-- Command Center e, via SSO, para RTS / RTA / RDA.
CREATE TABLE IF NOT EXISTS command_center.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    role            command_center.user_role   NOT NULL DEFAULT 'operador',
    status          command_center.user_status NOT NULL DEFAULT 'pending_verification',
    mfa_enabled     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_access_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_email_domain CHECK (email LIKE '%@venezanet.com')
);
CREATE INDEX IF NOT EXISTS idx_users_email  ON command_center.users (email);
CREATE INDEX IF NOT EXISTS idx_users_status ON command_center.users (status);

-- ─── email_verifications ─────────────────────────────────────────────────────
-- Código de 4 dígitos enviado por email para validar que o email é do usuário.
CREATE TABLE IF NOT EXISTS command_center.email_verifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES command_center.users(id) ON DELETE CASCADE,
    code            VARCHAR(4)  NOT NULL,
    verified        BOOLEAN     NOT NULL DEFAULT FALSE,
    attempts        INT         NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id)
);
CREATE INDEX IF NOT EXISTS idx_email_verif_user ON command_center.email_verifications (user_id);

-- ─── approval_tokens ─────────────────────────────────────────────────────────
-- Token enviado por email ao admin para aprovar o cadastro de um novo usuário.
CREATE TABLE IF NOT EXISTS command_center.approval_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES command_center.users(id) ON DELETE CASCADE,
    token           VARCHAR(128) NOT NULL UNIQUE,
    used            BOOLEAN      NOT NULL DEFAULT FALSE,
    approved_by     VARCHAR(255),
    approved_role   command_center.user_role,
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_approval_tokens_token ON command_center.approval_tokens (token);
CREATE INDEX IF NOT EXISTS idx_approval_tokens_user  ON command_center.approval_tokens (user_id);

-- ─── mfa_email_codes ─────────────────────────────────────────────────────────
-- Código de 6 dígitos enviado por email para MFA no login.
-- push_token permite aprovação via link no email (push approval).
CREATE TABLE IF NOT EXISTS command_center.mfa_email_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES command_center.users(id) ON DELETE CASCADE,
    code            VARCHAR(6)   NOT NULL,
    push_token      VARCHAR(128) NOT NULL UNIQUE,
    verified        BOOLEAN      NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mfa_email_codes_user    ON command_center.mfa_email_codes (user_id);
CREATE INDEX IF NOT EXISTS idx_mfa_email_codes_push    ON command_center.mfa_email_codes (push_token);
CREATE INDEX IF NOT EXISTS idx_mfa_email_codes_expires ON command_center.mfa_email_codes (expires_at);

-- ─── sessions ────────────────────────────────────────────────────────────────
-- Sessões ativas (rastreamento do JWT portal_token).
CREATE TABLE IF NOT EXISTS command_center.sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES command_center.users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON command_center.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token   ON command_center.sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON command_center.sessions (expires_at);

-- ─── login_attempts ──────────────────────────────────────────────────────────
-- Rate limiting / auditoria básica de tentativas de login.
CREATE TABLE IF NOT EXISTS command_center.login_attempts (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    ip_address      VARCHAR(45),
    success         BOOLEAN      NOT NULL DEFAULT FALSE,
    failure_reason  VARCHAR(100),
    attempted_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON command_center.login_attempts (email, attempted_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip    ON command_center.login_attempts (ip_address, attempted_at);

-- ─── audit_logs ──────────────────────────────────────────────────────────────
-- Registro de ações na plataforma. Categorias: auth, access, admin, system.
CREATE TABLE IF NOT EXISTS command_center.audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES command_center.users(id) ON DELETE SET NULL,
    user_email      VARCHAR(255) NOT NULL,
    action          VARCHAR(100) NOT NULL,
    category        VARCHAR(50)  NOT NULL DEFAULT 'auth',
    details         JSONB,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user     ON command_center.audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action   ON command_center.audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_category ON command_center.audit_logs (category);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created  ON command_center.audit_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_cat_date ON command_center.audit_logs (category, created_at DESC);

-- ─── Verificação ─────────────────────────────────────────────────────────────
-- Após executar, confira com:
--   SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'command_center' ORDER BY table_name;
-- Esperado: 8 tabelas (users, email_verifications, approval_tokens,
--           totp_secrets, trusted_devices, sessions, login_attempts, audit_logs).
