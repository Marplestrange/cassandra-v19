/* Le Salon et les conversations entre comptes : /api/salon/*, /api/conv/* (V18) -> capacités salon.* (et comptes.* pour les agents invités) du noyau.
   Le salon V19 est cloisonné par fil (membres) : il n'y a plus de « tête-à-tête solo » ni de salon des agents réservé à l'administrateur. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const z = (n) => String(n).padStart(2, "0");
  const ts = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds()); };
  const fil = (b) => +(b.fil != null ? b.fil : b.id);
  // Le fil, comme l'écran V18 le lit (dates en texte, propriétaire au format « humain:compte »).
  const fil18 = (f) => Object.assign({}, f, { par: "humain:" + f.proprietaire, cree: ts(f.cree), dernier: ts(f.dernier), origine: "salon", session: "", promu_a: 0, depuis_humain: f.depuis_humain || 0 });
  // Un message : les destinataires et les sources restent du JSON en texte, comme dans la base V18.
  const msg18 = (m) => Object.assign({}, m, { ts: ts(m.ts), destinataires: JSON.stringify(m.destinataires || []), sources: JSON.stringify(m.sources || []) });

  P("/api/salon/fils", "salon.fils", { args: (r) => ({ statut: r.body.statut || "", archives: !!r.body.archives }), sortie: (x) => ok({ fils: (x.fils || []).map(fil18) }) });
  P("/api/salon/fil", "salon.fil_creer", { args: (r) => ({ titre: r.body.titre || "", but: r.body.but || "" }), sortie: (x) => ok({ id: x.id }) });
  P("/api/salon/supprimer", "salon.fil_supprimer", { args: (r) => ({ fil: fil(r.body) }), sortie: (x) => ok({ messages: (x.messages || []).length }) });
  P("/api/salon/statut", null, {
    faire: async (req, agir) => {
      const f = fil(req.body), st = String(req.body.statut || "");
      if (st === "archive") { await agir("salon.ranger", { fil: f, archive: true }); return ok({}); }
      if (st === "ouvert") await agir("salon.ranger", { fil: f, archive: false });
      await agir("salon.fil_statut", { fil: f, statut: st });
      return ok({});
    },
  });
  P("/api/salon/mode", "salon.fil_mode", { args: (r) => ({ fil: fil(r.body), mode: r.body.mode || "" }), sortie: (x) => ok({ mode: x.mode }) });
  P("/api/salon/terrain", "salon.fil_terrain", { args: (r) => ({ fil: fil(r.body), terrain: r.body.terrain || "" }), sortie: (x) => ok({ terrain: x.terrain }) });
  P("/api/salon/dire", "salon.dire", { args: (r) => ({ fil: fil(r.body), destinataires: r.body.destinataires || [], corps: r.body.corps || "", sources: r.body.sources || [] }), sortie: (x) => ok({ id: x.id, destinataires: x.destinataires }) });
  // Lire un fil : le « vu » de l'humain se pose en même temps (ses non-lus survivent au rechargement), et le résumé du passé accompagne la première page.
  P("/api/salon/lire", null, {
    faire: async (req, agir) => {
      const b = req.body, f = fil(b);
      const r = await agir("salon.lire", { fil: f, depuis: +(b.depuis || 0), limite: +(b.limite || 60), avant: +(b.avant || 0) });
      const msgs = r.messages || [];
      if (msgs.length && !b.avant) agir("salon.vu", { fil: f }).catch(() => {});
      let resume = null;
      if (!b.depuis && !b.avant) { try { resume = (await agir("salon.resume", { fil: f })).resume; } catch (e) {} }
      return ok({ messages: msgs.map(msg18), resume });
    },
  });
  P("/api/salon/attendre", "salon.attendre", { args: (r) => ({ fil: fil(r.body), depuis: +(r.body.depuis || 0), delai: +(r.body.delai || 25) }), sortie: (x) => ok({ messages: (x.messages || []).map(msg18) }) });
  P("/api/salon/chercher", "salon.chercher", { args: (r) => ({ question: r.body.q || "", fil: +(r.body.fil || 0), limite: +(r.body.limite || 40) }), sortie: (x) => ok({ resultats: (x.resultats || []).map((m) => Object.assign({}, m, { ts: ts(m.ts), origine: "salon", par: "" })) }) });
  P("/api/salon/journal", "salon.journal", { args: (r) => ({ limite: +(r.body.limite || 50) }), sortie: (x) => ok({ journal: (x.journal || []).map((j) => Object.assign({}, j, { ts: ts(j.ts) })) }) });
  P("/api/salon/message_supprimer", "salon.message_supprimer", { args: (r) => ({ fil: fil(r.body), id: +r.body.id }), sortie: (x) => ok({ id: x.message.id }) });
  P("/api/salon/budget", "reglages.regler", { args: (r) => ({ cle: "salon.budget_tours", valeur: +r.body.budget }), sortie: (x) => ok({ budget: x.valeur }) });
  P("/api/salon/etat", null, {
    faire: async (req, agir) => {
      const [e, m, ag] = await Promise.all([agir("salon.etat", {}), agir("modeles.lister", {}).catch(() => ({})), agir("comptes.mes_agents", {}).catch(() => ({ agents: [] }))]);
      const roles = (m && m.roles) || {};
      const modeles = (m && m.modeles) || [];
      const nomModele = (id) => { const x = modeles.find((y) => y.id === id); return x ? x.nom : ""; };
      return ok({
        residents: (e.residents || []).map((r) => Object.assign({}, r, { modele: nomModele(r.nom === "cassandra" ? roles.principal : roles.itare_citadelle), payant: false, dernier_mot: ts(r.dernier_mot) })),
        invites: (ag.agents || []).map((a) => ({ nom: a.compte, cree: ts(a.cree), par: a.invite_par, compte: a.invite_par, dernier_vu: "", actif: 1 })),
        budget: e.budget, presence: true, terrains: e.terrains,
      });
    },
  });
  // Les agents invités : un jeton rendu UNE fois ; l'agent agit pour son invitant.
  P("/api/salon/inviter", "comptes.inviter_agent", { args: (r) => ({ nom: r.body.nom || "" }), sortie: (x) => ok({ nom: x.compte, jeton: x.jeton }) });
  P("/api/salon/revoquer", "comptes.revoquer_agent", { args: (r) => ({ nom: r.body.nom || "" }), sortie: (x) => ok({ revoques: x.revoques }) });
  P("/api/salon/oublier", null, { faire: async () => ok({ effaces: 0 }) });
  P("/api/salon/invites", "comptes.mes_agents", { args: () => ({}), sortie: (x) => ok({ invites: (x.agents || []).map((a) => ({ nom: a.compte, cree: ts(a.cree), par: a.invite_par, compte: a.invite_par, dernier_vu: "", actif: 1 })) }) });

  // Les conversations entre comptes : un fil du salon dont les membres sont des personnes.
  const conv18 = (f) => ({ id: f.id, titre: f.titre, dernier: ts(f.dernier), lu_id: 0, non_lus: f.nonlus, apercu: "", membres: [f.proprietaire].concat(f.membres || []).sort(), presence: {} });
  P("/api/conv/fils", null, {
    faire: async (req, agir) => { const x = await agir("salon.fils", { archives: true }); return ok({ fils: (x.fils || []).map(conv18), rangement: { archive: (x.fils || []).filter((f) => f.range === "archive").map((f) => String(f.id)), retire: [] } }); },
  });
  P("/api/conv/ouvrir", null, {
    faire: async (req, agir) => {
      const f = fil(req.body);
      const [lu, mb, tous] = await Promise.all([agir("salon.lire", { fil: f, limite: +(req.body.limite || 200) }), agir("salon.membres", { fil: f }), agir("salon.fils", { archives: true })]);
      const meta = (tous.fils || []).find((x) => x.id === f) || {};
      agir("salon.vu", { fil: f }).catch(() => {});
      const moi = (CASS.moi && CASS.moi.compte) || "";
      return ok({ fil: f, titre: meta.titre || "", membres: [mb.proprietaire].concat((mb.membres || []).map((m) => m.compte)).sort(), lignes: (lu.messages || []).map((m) => ({ id: m.id, auteur: String(m.auteur).replace(/^humain:/, ""), corps: m.corps, ts: ts(m.ts) })), moi });
    },
  });
  P("/api/conv/creer", null, {
    faire: async (req, agir) => {
      const avec = (req.body.avec || []).map(String), r = await agir("salon.fil_creer", { titre: req.body.titre || "" });
      for (const c of avec) await agir("salon.membre_inviter", { fil: r.id, compte: c });
      return ok({ fil: r.id, id: r.id });
    },
  });
  P("/api/conv/dire", "salon.dire", { args: (r) => ({ fil: fil(r.body), corps: r.body.corps || "", destinataires: [] }), sortie: (x) => ok({ id: x.id }) });
  P("/api/conv/inviter", "salon.membre_inviter", { args: (r) => ({ fil: fil(r.body), compte: r.body.qui || "" }), sortie: ok });
  P("/api/conv/quitter", "salon.membre_retirer", { args: (r) => ({ fil: fil(r.body) }), sortie: ok });
  P("/api/conv/ranger", "salon.ranger", { args: (r) => ({ fil: +r.body.ref, archive: r.body.etat === "archive" }), sortie: ok });
  P("/api/conv/supprimer", "salon.fil_supprimer", { args: (r) => ({ fil: +r.body.ref }), sortie: ok });
  P("/api/conv/correspondants", null, {
    faire: async (req, agir) => { const l = await agir("comptes.lister", {}); const moi = (CASS.moi && CASS.moi.compte) || ""; return ok({ comptes: (l.comptes || []).filter((c) => c.type !== "systeme" && c.type !== "agent" && c.compte !== moi).map((c) => c.compte).sort() }); },
  });
})();
