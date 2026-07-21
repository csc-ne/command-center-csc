-- =========== COMMAND CENTER CSC ============
-- Migration 002 — Fluxo de registro com verificacao de email + aprovacao admin + audit logs
-- ====================================================================================
--
-- Executar no banco portal_auth APOS o init.sql (001):
--   psql -h localhost -p 5433 -U portal -d portal_auth -f 002_registration_flow.sql
--
-- Mudancas:
--   1. Enum user_role (admin, operador, visualizador)
--   2. Enum user_status (pending_verification, pending_approval, active, inactive)
--   3. ALTER users: role -> enum, adiciona status, last_access_at
--   4. Nova tabela: email_verifications (codigo 4 digitos)
--   5. Nova tabela: approval_tokens (link de aprovacao para admin)
--   6. Nova tabela: audit_logs (acoes do usuario na plataforma)

BEGIN;

-- ─── 1. Enums ────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'operador', 'visualizador');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE user_status AS ENUM ('pending_verification', 'pending_approval', 'active', 'inactive');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ─── 2. ALTER users ──────────────────────────────────────────────────────────

-- Adicionar coluna status (sem dropar is_active ainda, para compatibilidade)
ALTER TABLE users ADD COLUMN IF NOT EXISTS status user_status NOT NULL DEFAULT 'active';

-- Adicionar last_access_at
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_access_at TIMESTAMPTZ;

-- Migrar role de VARCHAR para ENUM:
-- Primeiro renomeia a coluna antiga
ALTER TABLE users RENAME COLUMN role TO role_old;

-- Cria a nova coluna com enum
ALTER TABLE users ADD COLUMN role user_role NOT NULL DEFAULT 'operador';

-- Migra os dados existentes
UPDATE users SET role = CASE
    WHEN role_old = 'admin' THEN 'admin'::user_role
    WHEN role_old = 'visualizador' THEN 'visualizador'::user_role
    ELSE 'operador'::user_role
END;

-- Remove a coluna antiga
ALTER TABLE users DROP COLUMN role_old;

-- Indice para status (queries de pendentes)
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);

-- ─── 3. Email Verifications ──────────────────────────────────────────────────
-- Codigo de 4 digitos enviado por email para validar que o email eh do usuario

CREATE TABLE IF NOT EXISTS email_verifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code            VARCHAR(4) NOT NULL,
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    attempts        INT NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_email_verif_user ON email_verifications (user_id);

-- ─── 4. Approval Tokens ─────────────────────────────────────────────────────
-- Token enviado por email ao admin (csc.ne@venezanet.com) com link de aprovacao

CREATE TABLE IF NOT EXISTS approval_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token           VARCHAR(128) NOT NULL UNIQUE,
    used            BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by     VARCHAR(255),
    approved_role   user_role,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_tokens_token ON approval_tokens (token);
CREATE INDEX IF NOT EXISTS idx_approval_tokens_user ON approval_tokens (user_id);

-- ─── 5. Audit Logs ──────────────────────────────────────────────────────────
-- Registro de todas as acoes relevantes na plataforma (visivel apenas para admins)

CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email      VARCHAR(255) NOT NULL,
    action          VARCHAR(100) NOT NULL,
    category        VARCHAR(50) NOT NULL DEFAULT 'auth',
    details         JSONB,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Categorias previstas:
--   auth      — login, logout, mfa_setup, mfa_verify, register, approve
--   access    — acesso a sistemas (RTS, RTA, RDA)
--   admin     — acoes administrativas (alterar role, desativar user)
--   system    — alteracoes de configuracao (atualizacoes futuras)

CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_category ON audit_logs (category);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs (created_at);

-- Indice composto para queries de admin (filtro por periodo + categoria)
CREATE INDEX IF NOT EXISTS idx_audit_logs_cat_date ON audit_logs (category, created_at DESC);

COMMIT;
