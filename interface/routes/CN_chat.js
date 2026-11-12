// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le fil principal : /api/chat, /api/chat/stream, /api/chat/stop (V18) -> agents
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #084f60
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le fil principal : /api/chat, /api/chat/stream, /api/chat/stop (V18) -> agents.converser du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=084f60 ▼▼▼
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
  // Le fil gardé en mémoire peut avoir disparu (supprimé depuis « Conversations », ou un autre compte à l'écran) : on le retrouve ou on le recrée, une fois, au lieu de répondre « introuvable » jusqu'au rechargement.
  async function parler(agir, message) {
    const dire = async () => agir("agents.converser", { conversation_id: await fil(agir), message: message, agent: "cassandra" });
    try { return await dire(); } catch (e) {
      if (!/introuvable/i.test(String((e && e.message) || e))) throw e;
      conv = null;
      return dire();
    }
  }
  const flux = (texte) => new Response(new ReadableStream({
    start(c) { c.enqueue(enc.encode("data: " + JSON.stringify({ token: texte }) + "\n\n")); c.enqueue(enc.encode("data: " + JSON.stringify({ done: true }) + "\n\n")); c.close(); },
  }), { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } });

  CASS.route("POST", "/api/chat/stream", null, {
    faire: async (req, agir) => flux(texteDe(await parler(agir, String(req.body.message || "")))),
  });
  CASS.route("POST", "/api/chat", null, {
    faire: async (req, agir) => {
      const r = await parler(agir, String(req.body.message || ""));
      return { ok: true, response: texteDe(r), reply: texteDe(r) };
    },
  });
  CASS.route("POST", "/api/chat/stop", null, { faire: async (req, agir) => { if (conv) await agir("agents.arreter", { id: conv }); return { ok: true }; } });
  // La trace d'Itare du bureau (V18 : /api/itare/traces, /api/itare/trace/annuler) : ce que l'agent a fait pour ce compte, et le retour arrière — les actes et « Défaire » du module agents.
  CASS.route("POST", "/api/itare/traces", null, {
    faire: async (req, agir) => {
      const r = await agir("agents.actes", { agent: "itare", limite: Number((req.body || {}).limit) || 30 });
      const iso = (t) => { try { return new Date(t * 1000).toISOString(); } catch (e) { return ""; } };
      return { ok: true, traces: (r.actes || []).map((a) => ({ id: a.acte, genre: a.capacite, libelle: a.capacite.replace(".", " · ").replace(/_/g, " "), ts: iso(a.ts), annule: a.retour === "defaite", annulable: !!a.defaisable })) };
    },
  });
  CASS.route("POST", "/api/itare/trace/annuler", null, {
    faire: async (req, agir) => { await agir("agents.defaire", { acte: Number((req.body || {}).id) || 0, raison: "demandé depuis la trace du bureau" }); return { ok: true }; },
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
