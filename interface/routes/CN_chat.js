// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le fil principal : /api/chat, /api/chat/stream, /api/chat/stop (V18) -> agents
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #4163c1
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le fil principal : /api/chat, /api/chat/stream, /api/chat/stop (V18) -> agents.converser du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=4163c1 ▼▼▼
/* Le fil principal : /api/chat, /api/chat/stream, /api/chat/stop (V18) -> agents.converser du noyau.
   Le noyau rend la réponse d'un bloc ; l'écran V18 lit un flux « data: {token} » : on le lui fabrique (un seul jeton, puis « done »).
   Le fil principal est la conversation « Fil principal » du compte, créée au premier message. */
(function () {
  let conv = null;
  const enc = new TextEncoder();
  async function fil(agir) {
    if (conv) return conv;
    const l = (await agir("agents.conversations", {})).conversations || [];
    const f = l.find((c) => c.agent === "cassandra" && c.titre === "Fil principal");
    conv = f ? f.id : (await agir("agents.conversation_creer", { agent: "cassandra", titre: "Fil principal" })).id;
    return conv;
  }
  function texteDe(r) {
    if (r.texte) return r.texte;
    const pannes = (r.actions || []).filter((a) => a && a.statut === "panne").map((a) => a.erreur);
    return pannes.length ? "⚠ " + pannes.join(" ; ") : "(aucune réponse)";
  }
  const flux = (texte) => new Response(new ReadableStream({
    start(c) { c.enqueue(enc.encode("data: " + JSON.stringify({ token: texte }) + "\n\n")); c.enqueue(enc.encode("data: " + JSON.stringify({ done: true }) + "\n\n")); c.close(); },
  }), { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } });

  CASS.route("POST", "/api/chat/stream", null, {
    faire: async (req, agir) => {
      const id = await fil(agir);
      const r = await agir("agents.converser", { conversation_id: id, message: String(req.body.message || ""), agent: "cassandra" });
      return flux(texteDe(r));
    },
  });
  CASS.route("POST", "/api/chat", null, {
    faire: async (req, agir) => {
      const id = await fil(agir);
      const r = await agir("agents.converser", { conversation_id: id, message: String(req.body.message || ""), agent: "cassandra" });
      return { ok: true, response: texteDe(r), reply: texteDe(r) };
    },
  });
  CASS.route("POST", "/api/chat/stop", null, { faire: async (req, agir) => { if (conv) await agir("agents.arreter", { id: conv }); return { ok: true }; } });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
