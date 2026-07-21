-- ============================================================
-- Migration 002: Campos de registro e verificação de usuários
-- Roda DEPOIS do init.sql (idempotente com IF NOT EXISTS / ADD IF)
-- ============================================================
SET search_path TO fleet_inteligence, public;

-- Novos campos na tabela users
ALTER TABLE fleet_inteligence.users
    ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verification_code VARCHAR(6),
    ADD COLUMN IF NOT EXISTS verification_code_expires_at TIMESTAMPTZ;

-- Tabela de log de atividades
CREATE TABLE IF NOT EXISTS fleet_inteligence.activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES fleet_inteligence.users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user ON fleet_inteligence.activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON fleet_inteligence.activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_action ON fleet_inteligence.activity_logs(action);

-- Atualizar trigger de updated_at para incluir activity_logs (não precisa,
-- activity_logs não tem updated_at)

-- ============================================================
-- SEED: remover admin genérico antigo e inserir usuários reais
-- Senha padrão: 123@mudar (hash bcrypt abaixo)
-- ============================================================
DELETE FROM fleet_inteligence.users WHERE email = 'admin@veneza.com';

INSERT INTO fleet_inteligence.users
    (email, username, full_name, hashed_password, role, is_email_verified, is_approved)
VALUES
    ('henrique.albuquerque@venezanet.com', 'henrique.albuquerque', 'Henrique Albuquerque',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE),
    ('iremar.barros@venezanet.com', 'iremar.barros', 'Iremar Barros',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE),
    ('thiago.barros@venezanet.com', 'thiago.barros', 'Thiago Barros',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE),
    ('artur.catunda@venezanet.com', 'artur.catunda', 'Artur Catunda',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE),
    ('eduardo.souza@venezanet.com', 'eduardo.souza', 'Eduardo Souza',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE),
    ('oscar.rabelo@venezanet.com', 'oscar.rabelo', 'Oscar Rabelo',
     '$2b$12$mwKsNCT5mj9NJNJEsCLJpux3FlV87XJ/dckL248etd/5oXUt/WerG', 'admin', TRUE, TRUE)
ON CONFLICT (email) DO UPDATE SET
    hashed_password = EXCLUDED.hashed_password,
    role = EXCLUDED.role,
    is_email_verified = EXCLUDED.is_email_verified,
    is_approved = EXCLUDED.is_approved;
