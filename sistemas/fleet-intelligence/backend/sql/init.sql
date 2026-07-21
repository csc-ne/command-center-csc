-- ============================================================
-- Fleet Intelligence - Initial Schema
-- PostgreSQL 14+
-- Tabelas isoladas no schema `fleet_inteligence` para conviver
-- sem conflito com outras aplicações no mesmo banco.
-- ============================================================

-- Extensions (instaladas no schema public, disponíveis globalmente)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Schema dedicado da aplicação
CREATE SCHEMA IF NOT EXISTS fleet_inteligence;

-- Todas as criações subsequentes operam dentro deste schema
SET search_path TO fleet_inteligence, public;

-- ============================================================
-- USERS & ROLES
-- ============================================================
CREATE TABLE IF NOT EXISTS fleet_inteligence.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'operator'
        CHECK (role IN ('admin', 'operator', 'viewer')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON fleet_inteligence.users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON fleet_inteligence.users(username);

-- ============================================================
-- BOARDS (Fluxos de trabalho)
-- ============================================================
CREATE TABLE IF NOT EXISTS fleet_inteligence.boards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    color VARCHAR(20) DEFAULT 'indigo',
    icon VARCHAR(50) DEFAULT 'Workflow',
    owner_id UUID NOT NULL REFERENCES fleet_inteligence.users(id) ON DELETE RESTRICT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_boards_owner ON fleet_inteligence.boards(owner_id);
CREATE INDEX IF NOT EXISTS idx_boards_archived ON fleet_inteligence.boards(is_archived);

-- ============================================================
-- PHASES (Colunas do Kanban)
-- ============================================================
CREATE TABLE IF NOT EXISTS fleet_inteligence.phases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    board_id UUID NOT NULL REFERENCES fleet_inteligence.boards(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    position INTEGER NOT NULL,
    color VARCHAR(20) DEFAULT 'slate',
    wip_limit INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (board_id, position)
);

CREATE INDEX IF NOT EXISTS idx_phases_board ON fleet_inteligence.phases(board_id);

-- ============================================================
-- CARDS (Itens dentro das fases)
-- ============================================================
CREATE TABLE IF NOT EXISTS fleet_inteligence.cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_id UUID NOT NULL REFERENCES fleet_inteligence.phases(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    position INTEGER NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    assignee_id UUID REFERENCES fleet_inteligence.users(id) ON DELETE SET NULL,
    due_date TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_by UUID NOT NULL REFERENCES fleet_inteligence.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cards_phase ON fleet_inteligence.cards(phase_id);
CREATE INDEX IF NOT EXISTS idx_cards_assignee ON fleet_inteligence.cards(assignee_id);
CREATE INDEX IF NOT EXISTS idx_cards_priority ON fleet_inteligence.cards(priority);
CREATE INDEX IF NOT EXISTS idx_cards_due_date ON fleet_inteligence.cards(due_date);
CREATE INDEX IF NOT EXISTS idx_cards_metadata ON fleet_inteligence.cards USING GIN (metadata);

-- ============================================================
-- TRIGGER: updated_at automático
-- ============================================================
CREATE OR REPLACE FUNCTION fleet_inteligence.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['users', 'boards', 'phases', 'cards']) LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trg_%s_updated_at ON fleet_inteligence.%s;
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON fleet_inteligence.%s
            FOR EACH ROW EXECUTE FUNCTION fleet_inteligence.set_updated_at();
        ', t, t, t, t);
    END LOOP;
END $$;

-- ============================================================
-- SEED: usuário admin inicial
-- Senha: admin123 (troque no primeiro login)
-- ============================================================
INSERT INTO fleet_inteligence.users (email, username, full_name, hashed_password, role)
VALUES (
    'admin@veneza.com',
    'admin',
    'Administrador',
    '$2b$12$nCradRJ5xEPBvQdvQ6Tzb.LDkxAqcByD7xu/QQ3TSGBhjRsL2RW6y',
    'admin'
) ON CONFLICT (email) DO NOTHING;
