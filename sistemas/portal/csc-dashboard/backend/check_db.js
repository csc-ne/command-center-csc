const p = require('./db');
const q = "SELECT table_catalog, column_name, character_maximum_length FROM information_schema.columns WHERE table_name='machine_list' AND character_maximum_length IS NOT NULL";
p.query(q).then(function(r) {
  console.log("Database:", r.rows.length ? r.rows[0].table_catalog : "no varchar columns found");
  console.log("VARCHAR columns:", JSON.stringify(r.rows, null, 2));
  process.exit();
}).catch(function(e) {
  console.error("Error:", e.message);
  process.exit(1);
});
