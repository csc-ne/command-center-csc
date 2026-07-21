// Servidor estatico para desenvolvimento do frontend ALS
const express = require("express");
const path = require("path");
const app = express();
app.use(express.static(path.join(__dirname)));
app.get("*", (_req, res) => res.sendFile(path.join(__dirname, "index.html")));
app.listen(3032, () => console.log("[ALS Frontend DEV] http://localhost:3032"));
