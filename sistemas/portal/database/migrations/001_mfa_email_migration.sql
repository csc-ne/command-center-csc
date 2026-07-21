-- =====================================================================
-- Migration 001 — MFA Email Migration
-- Substitui TOTP/Authenticator por código de 6 dígitos via email
-- + push approval (link no email).
-- Remove device trust (fluxo simplificado: sempre email+senha+código).
-- =====================================================================
-- COMO EXECUTAR:
--   psql -h 192.168.0.106 -p 5432 -U henrique -d csc_veneza -f 001_mfa_email_migration.sql
-- =====================================================================

SET search_path TO command_center, public;

-- ─── 1. Nova tabela: mfa_email_codes ────────────────────────────────────────
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

-- ─── 2. Reset mfa_enabled para todos os usuários ───────────────────────────
-- Como o MFA agora é automático (sem setup), todos que tinham TOTP
-- precisam re-verificar via email no próximo login.
-- Seta mfa_enabled = TRUE para todos os ativos (o fluxo agora é sempre email code).
UPDATE command_center.users SET mfa_enabled = TRUE WHERE status = 'active';

-- ─── 3. Dropar tabelas obsoletas ────────────────────────────────────────────
-- totp_secrets — não será mais usado
DROP TABLE IF EXISTS command_center.totp_secrets;

-- trusted_devices — device trust removido do fluxo
DROP TABLE IF EXISTS command_center.trusted_devices;

-- ─── 4. Limpar códigos expirados periodicamente (sugestão de cron/job) ──────
-- DELETE FROM command_center.mfa_email_codes WHERE expires_at < NOW();
-- (Rodar via pg_cron ou job externo a cada hora)
