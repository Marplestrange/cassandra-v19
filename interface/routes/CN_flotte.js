// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Flotte : /api/flotte/* et /api/multiserver/* (V18) -> capacités flotte
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #aba7ea
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Flotte : /api/flotte/* et /api/multiserver/* (V18) -> capacités flotte.* du noyau. Le parc, le verdict et les engagements parlent déjà la même langue ;
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=aba7ea ▼▼▼
/* Flotte : /api/flotte/* et /api/multiserver/* (V18) -> capacités flotte.* du noyau. Le parc, le verdict et les engagements parlent déjà la même langue ;
   l'historique, la disponibilité et les actions changent de clés. Les types Synology et Proxmox du registre ne sont pas encore portés. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const nom = (b) => String(b.name || b.nom || "");
  const MODIFIE = { svc_restart: 1, svc_start: 1, svc_stop: 1 };

  P("/api/flotte/parc", "flotte.parc", { args: () => ({}), sortie: ok });
  P("/api/flotte/verdict", "flotte.verdict", { args: () => ({}), sortie: ok });
  P("/api/flotte/engagement", "flotte.engagement", { args: (r) => ({ nom: nom(r.body), statut: r.body.statut || "", niveau: r.body.niveau || "" }), sortie: (x) => ok({ nom: x.nom, statut: x.statut, niveau: x.niveau }) });
  P("/api/flotte/oublier", "flotte.oublier", { args: (r) => ({ nom: nom(r.body) }), sortie: (x) => ok({ nom: x.nom, efface: x.efface }) });
  P("/api/flotte/ping", "flotte.ping", { args: (r) => ({ nom: nom(r.body) }), sortie: (x) => ok({ nom: x.nom, latence_ms: x.latence_ms, via: x.via, essais: x.essais, detail: x.detail }) });
  P("/api/flotte/history", "flotte.historique", {
    args: (r) => ({ nom: nom(r.body), heures: +(r.body.hours || 24) }),
    sortie: (h) => ok({ name: h.nom, hours: h.heures, samples: h.releves, availability: h.disponibilite,
      points: (h.points || []).map((p) => ({ ts: p.ts, online: p.en_ligne, cpu: p.cpu, ram: p.ram, disk: p.disque, health: p.sante, error: p.erreur })),
      events: (h.evenements || []).map((e) => ({ ts: e.ts, kind: e.genre, detail: e.detail, duration_min: e.duree_min })),
      links: (h.liens || []).map((l) => ({ name: l.nom, kind: l.genre, ref: l.ref, note: l.note, ts: l.ts })), releves: h.releves_detail || [] }),
  });
  P("/api/flotte/availability", "flotte.disponibilite", {
    args: (r) => ({ jours: +(r.body.days || 30) }),
    sortie: (d) => ok({ days: d.jours, reason: d.raison, machines: (d.machines || []).map((m) => ({ name: m.nom, samples: m.releves, availability: m.disponibilite, outages: m.pannes, downtime_min: m.indispo_min, downtime: m.indispo })) }),
  });
  P("/api/flotte/actions", "flotte.actions", { args: () => ({}), sortie: (x) => ok({ actions: (x.actions || []).map((a) => ({ key: a.cle, modifies: a.modifie, desc: a.description, needs_service: a.service_requis })) }) });
  // Lancer : une commande de lecture passe par flotte.diagnostic ; ce qui modifie exige la confirmation (409) puis passe par flotte.service_agir, avec preuve et retour.
  P("/api/flotte/act", null, {
    faire: async (req, agir) => {
      const b = req.body, action = String(b.action || ""), n = nom(b), service = String(b.service || "");
      if (MODIFIE[action]) {
        if (!b.confirm) return new Response(JSON.stringify({ ok: false, needs_confirm: true, reason: "« " + action + " » sur " + n + " modifie l'état de la machine distante." }), { status: 409, headers: { "Content-Type": "application/json" } });
        const r = await agir("flotte.service_agir", { nom: n, action, service });
        return ok({ action, machine: r.nom, service: r.service, exit_code: r.code, duration_ms: r.duree_ms, output: r.sortie });
      }
      const r = await agir("flotte.diagnostic", { nom: n, action, service });
      return { ok: r.code === 0, action, machine: r.machine, service: r.service, exit_code: r.code, duration_ms: r.duree_ms, command: r.commande, output: r.sortie };
    },
  });
  P("/api/flotte/links", "flotte.liens", { args: (r) => ({ nom: nom(r.body) }), sortie: (x) => ok({ links: (x.liens || []).map((l) => ({ name: l.nom, kind: l.genre, ref: l.ref, note: l.note, ts: l.ts })) }) });
  P("/api/flotte/link/save", "flotte.lien_enregistrer", { args: (r) => ({ nom: nom(r.body), genre: r.body.kind || "", ref: String(r.body.ref || ""), note: r.body.note || "" }), sortie: ok });
  P("/api/flotte/link/delete", "flotte.lien_retirer", { args: (r) => ({ nom: nom(r.body), genre: r.body.kind || "", ref: String(r.body.ref || "") }), sortie: ok });

  // Le registre.
  P("/api/multiserver/list", "flotte.machines", { args: () => ({}), sortie: (x) => ok({ servers: (x.machines || []).map((m) => ({ name: m.nom, url: m.url || m.hote, enabled: !!m.actif })) }) });
  P("/api/multiserver/add_device", null, {
    faire: async (req, agir) => {
      const b = req.body, t = b.type || "cassandra";
      if (t === "synology" || t === "proxmox") throw Object.assign(new Error("le type « " + t + " » n'est pas encore porté dans la flotte"), { statut: 501 });
      const a = { nom: nom(b), type: t };
      if (t === "ssh") Object.assign(a, { hote: b.host || "", port: +(b.port || 22), utilisateur: b.username || "root", auth: b.auth === "password" ? "mot_de_passe" : (b.auth === "key" ? "cle" : (b.auth || "tailscale")), cle: b.key || "", mot_de_passe: b.password || "", systeme: b.os || "" });
      else if (t === "ping") Object.assign(a, { hote: b.host || "", port: +(b.port || 80) });
      else Object.assign(a, { url: b.url || "", jeton: b.token || "" });
      const r = await agir("flotte.machine_ajouter", a);
      return ok({ action: r.action === "ajout" ? "added" : "updated", name: r.nom, type: t });
    },
  });
  P("/api/multiserver/remove", "flotte.machine_retirer", { args: (r) => ({ nom: nom(r.body) }), sortie: (x) => ok({ name: x.nom }) });
  P("/api/multiserver/toggle", "flotte.machine_basculer", { args: (r) => ({ nom: nom(r.body), actif: r.body.enabled !== false }), sortie: (x) => ok({ name: x.nom, enabled: !!x.actif }) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
