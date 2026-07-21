const functions = require("firebase-functions");
const admin = require("firebase-admin");

if (!admin.apps.length) {
  admin.initializeApp({
    databaseURL: "https://rts-real-time-support-6ec6b-default-rtdb.firebaseio.com"
  });
}

const rtdb = admin.database();
const { defineString } = require("firebase-functions/params");

const VERIFY_TOKEN = defineString("WEBHOOK_VERIFY_TOKEN", {
  default: "VENEZAWPPTOKEN"
});

exports.webhookwpp = functions.https.onRequest(async (req, res) => {
  try {
    if (req.method === "GET") {
      const mode = req.query["hub.mode"];
      const token = req.query["hub.verify_token"];
      const challenge = req.query["hub.challenge"];
      if (mode === "subscribe" && token === VERIFY_TOKEN.value()) {
        console.log(" Webhook verificado com sucesso!");
        return res.status(200).send(challenge);
      }
      return res.sendStatus(403);
    }

    if (req.method === "POST") {
      const body = req.body;
      console.log(" POST recebido:", JSON.stringify(body));

      const entry = body?.entry?.[0];
      const change = entry?.changes?.[0];
      const value = change?.value;
      const messages = value?.messages;
      const contacts = value?.contacts;

      if (messages?.length && contacts?.length) {
        const msg = messages[0];
        const contact = contacts[0];
        const phoneId = contact?.wa_id || "unknown";
        const profileName = contact?.profile?.name || "Cliente";
        const timestamp = parseInt(msg?.timestamp || Math.floor(Date.now() / 1000));
        const text = msg?.text?.body
          || msg?.button?.text
          || msg?.interactive?.button_reply?.title
          || msg?.interactive?.list_reply?.title
          || "(Mensagem sem texto)";

        const payload = {
          last_timestamp: timestamp,
          last_id_msg: msg.id || `msg_${Date.now()}`,
          last_message: text,
          contact_infos: {
            profile_name: profileName,
            phone_id: phoneId
          }
        };

        await rtdb.ref(`/chats/${phoneId}`).update(payload);
        console.log(` Mensagem salva em /chats/${phoneId}`);
      } else {
        console.log(" Nenhuma mensagem válida no payload.");
      }

      return res.status(200).send("EVENT_RECEIVED");
    }

    return res.sendStatus(405);
  } catch (err) {
    console.error(" Erro no webhook:", err);
    return res.status(500).send("Erro interno no servidor");
  }
});
