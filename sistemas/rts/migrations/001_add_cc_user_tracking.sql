-- Migração: Adiciona rastreamento de usuário do Command Center nos atendimentos
-- Data: 2026-06-14
-- Descrição: Registra qual usuário do CC iniciou e finalizou cada atendimento

-- Colunas para quem INICIOU o atendimento (clicou "Iniciar atendimento")
ALTER TABLE rts_mensagens ADD COLUMN IF NOT EXISTS atendido_por_cc VARCHAR(255);
ALTER TABLE rts_mensagens ADD COLUMN IF NOT EXISTS atendido_por_cc_email VARCHAR(255);

-- Colunas para quem FINALIZOU o atendimento (clicou "Encerrar atendimento")
ALTER TABLE rts_mensagens ADD COLUMN IF NOT EXISTS finalizado_por_cc VARCHAR(255);
ALTER TABLE rts_mensagens ADD COLUMN IF NOT EXISTS finalizado_por_cc_email VARCHAR(255);

-- Índice para consultas de relatório por usuário CC
CREATE INDEX IF NOT EXISTS idx_rts_mensagens_atendido_por_cc
  ON rts_mensagens (atendido_por_cc)
  WHERE atendido_por_cc IS NOT NULL;
