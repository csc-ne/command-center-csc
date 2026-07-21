-- =========== COMMAND CENTER CSC ============
-- init.sql — Schema completo para autenticacao com MFA/TOTP + registro + audit
-- ==============================================================================
--
-- Banco: portal_auth
-- Tabelas:
--   users              — cadastro de usuarios @venezanet.com
--   email_verifications — codigos de verificacao de email (4 digitos)
--   approval_tokens    — tokens de aprovacao enviados ao admin
--   totp_secrets       — segredos TOTP por usuario (MFA)
--   trusted_devices    — dispositivos confiaveis (skip password)
--   sessions           — sessoes ativas (JWT tracking)
--   login_attempts     — rate limiting / audit basico
--   audit_logs         — registro completo de acoes na plataforma

-- ─── Enums ───────────────────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('admin', 'operador', 'visualizador');
CREATE TYPE user_status AS ENUM ('pending_verification', 'pending_approval', 'active', 'inactive');

-- ─── Users ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    role            user_role    NOT NULL DEFAULT 'operador',
    status          user_status  NOT NULL DEFAULT 'pending_verification',
    mfa_enabled     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_access_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

ALTER TABLE users ADD CONSTRAINT chk_email_domain
    CHECK (email LIKE '%@venezanet.com');

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_status ON users (status);

-- ─── Email Verifications ─────────────────────────────────────────────────────
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

CREATE INDEX idx_email_verif_user ON email_verifications (user_id);

-- ─── Approval Tokens ─────────────────────────────────────────────────────────
-- Token enviado por email ao admin (csc.ne@venezanet.com) para aprovar cadastro

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

CREATE INDEX idx_approval_tokens_token ON approval_tokens (token);
CREATE INDEX idx_approval_tokens_user ON approval_tokens (user_id);

-- ─── TOTP Secrets ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS totp_secrets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    secret          VARCHAR(255) NOT NULL,
    verified        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ─── Trusted Devices ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trusted_devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_hash     VARCHAR(255) NOT NULL,
    device_name     VARCHAR(255),
    ip_address      VARCHAR(45),
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, device_hash)
);

CREATE INDEX idx_trusted_devices_user ON trusted_devices (user_id);
CREATE INDEX idx_trusted_devices_expires ON trusted_devices (expires_at);

-- ─── Sessions ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions (user_id);
CREATE INDEX idx_sessions_token ON sessions (token_hash);
CREATE INDEX idx_sessions_expires ON sessions (expires_at);

-- ─── Login Attempts ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS login_attempts (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    ip_address      VARCHAR(45),
    success         BOOLEAN      NOT NULL DEFAULT FALSE,
    failure_reason  VARCHAR(100),
    attempted_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_login_attempts_email ON login_attempts (email, attempted_at);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address, attempted_at);

-- ─── Audit Logs ──────────────────────────────────────────────────────────────
-- Registro de todas as acoes relevantes na plataforma (visivel apenas para admins)
-- Categorias: auth, access, admin, system

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

CREATE INDEX idx_audit_logs_user ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);
CREATE INDEX idx_audit_logs_category ON audit_logs (category);
CREATE INDEX idx_audit_logs_created ON audit_logs (created_at);
CREATE INDEX idx_audit_logs_cat_date ON audit_logs (category, created_at DESC);
