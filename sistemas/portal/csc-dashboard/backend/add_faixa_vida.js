const p = require('./db');
const q = `
ALTER TABLE machine_list ADD COLUMN IF NOT EXISTS faixa_vida_estendida TEXT;
ALTER TABLE pops ADD COLUMN IF NOT EXISTS faixa_vida_estendida TEXT;
`;
p.query(q).then(function() {
  console.log("Coluna faixa_vida_estendida adicionada com sucesso nas duas tabelas");
  process.exit();
}).catch(function(e) {
  console.error("Erro:", e.message);
  process.exit(1);
});
