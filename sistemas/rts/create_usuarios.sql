-- ══════════════════════════════════════════════════════════════
--  RTS — Tabela de usuários do sistema
--  Banco: bancovz
--  Execute este script uma única vez no MySQL/Workbench
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `bancovz`.`usuarios` (
  `id`            INT            NOT NULL AUTO_INCREMENT,
  `email`         VARCHAR(255)   NOT NULL,
  `senha_hash`    VARCHAR(255)   NOT NULL,
  `nome`          VARCHAR(255)   NOT NULL DEFAULT '',
  `ativo`         TINYINT(1)     NOT NULL DEFAULT 1,
  `criado_em`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ultimo_acesso` DATETIME       NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `email_UNIQUE` (`email` ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Primeiro usuário (senha: Tb123) ──────────────────────────────────────────
INSERT INTO `bancovz`.`usuarios` (`email`, `senha_hash`, `nome`, `ativo`)
VALUES (
  'thiago.barros@venezanet.com',
  '$2b$10$FFwdhhjlP2N5CJNl7UBBm.j/2nFb.nzZDD6jpV0N.tKSpoj8.QymK',
  'Thiago Barros',
  1
);

-- Para adicionar mais usuários no futuro, use o script abaixo
-- (substitua os valores e gere o hash via: node -e "const b=require('bcryptjs');b.hash('SENHA',10).then(console.log)")
--
-- INSERT INTO `bancovz`.`usuarios` (`email`, `senha_hash`, `nome`, `ativo`)
-- VALUES ('novo@venezanet.com', '$2b$10$...hash...', 'Nome Completo', 1);
