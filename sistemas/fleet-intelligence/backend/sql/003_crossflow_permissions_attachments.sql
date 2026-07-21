-- ============================================================
-- 003 — Cross-flow connections, board permissions, card links,
--       card attachments
-- ============================================================

-- 1. Board connections: configures which boards communicate
CREATE TABLE IF NOT EXISTS fleet_inteligence.board_connections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_board_id UUID NOT NULL REFERENCES fleet_inteligence.boards(id) ON DELETE CASCADE,
    target_board_id UUID NOT NULL REFERENCES fleet_inteligence.boards(id) ON DELETE CASCADE,
    -- Phase in source board that triggers the link
    trigger_phase_id UUID NOT NULL REFERENCES fleet_inteligence.phases(id) ON DELETE CASCADE,
    -- Phase in target board where the child card is created
    target_phase_id  UUID NOT NULL REFERENCES fleet_inteligence.phases(id) ON DELETE CASCADE,
    -- Phase in target board that marks completion
    completion_phase_id UUID NOT NULL REFERENCES fleet_inteligence.phases(id) ON DELETE CASCADE,
    -- Phase in source board to advance parent card to after completion
    advance_to_phase_id UUID NOT NULL REFERENCES fleet_inteligence.phases(id) ON DELETE CASCADE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_different_boards CHECK (source_board_id != target_board_id)
);

CREATE INDEX IF NOT EXISTS idx_board_connections_source ON fleet_inteligence.board_connections(source_board_id);
CREATE INDEX IF NOT EXISTS idx_board_connections_target ON fleet_inteligence.board_connections(target_board_id);

-- 2. Board permissions: controls who can see each board
-- If a board has NO rows here, everyone can see it (open).
-- If it has rows, only listed users + admins can see it.
CREATE TABLE IF NOT EXISTS fleet_inteligence.board_permissions (
    id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    board_id UUID NOT NULL REFERENCES fleet_inteligence.boards(id) ON DELETE CASCADE,
    user_id  UUID NOT NULL REFERENCES fleet_inteligence.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_board_user UNIQUE (board_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_board_permissions_board ON fleet_inteligence.board_permissions(board_id);
CREATE INDEX IF NOT EXISTS idx_board_permissions_user ON fleet_inteligence.board_permissions(user_id);

-- 3. Card links: parent-child relationship across flows
CREATE TABLE IF NOT EXISTS fleet_inteligence.card_links (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id   UUID NOT NULL REFERENCES fleet_inteligence.board_connections(id) ON DELETE CASCADE,
    source_card_id  UUID NOT NULL REFERENCES fleet_inteligence.cards(id) ON DELETE CASCADE,
    target_card_id  UUID NOT NULL REFERENCES fleet_inteligence.cards(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, completed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_card_links_source ON fleet_inteligence.card_links(source_card_id);
CREATE INDEX IF NOT EXISTS idx_card_links_target ON fleet_inteligence.card_links(target_card_id);

-- 4. Card attachments: files uploaded to cards
CREATE TABLE IF NOT EXISTS fleet_inteligence.card_attachments (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_id     UUID NOT NULL REFERENCES fleet_inteligence.cards(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES fleet_inteligence.users(id) ON DELETE SET NULL,
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(500) NOT NULL,
    file_size   INTEGER NOT NULL DEFAULT 0,
    mime_type   VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_card_attachments_card ON fleet_inteligence.card_attachments(card_id);

-- Apply updated_at trigger to board_connections
DROP TRIGGER IF EXISTS trg_board_connections_updated ON fleet_inteligence.board_connections;
CREATE TRIGGER trg_board_connections_updated
    BEFORE UPDATE ON fleet_inteligence.board_connections
    FOR EACH ROW EXECUTE FUNCTION fleet_inteligence.set_updated_at();
