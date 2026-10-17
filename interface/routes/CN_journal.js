// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le Journal : /api/journal/* (V18) -> capacités journal
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #bc86c8
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le Journal : /api/journal/* (V18) -> capacités journal.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=bc86c8 ▼▼▼
/* Le Journal : /api/journal/* (V18) -> capacités journal.* du noyau.
   Le journal des agents (fil, dire, ecrire, prompt) a ses propres routes ; le lecteur multi-sources rend les mêmes enveloppes à sept clés. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const z = (n) => String(n).padStart(2, "0");
  const ts = (t) => { if (typeof t !== "number" && !/^\d{9,11}(\.\d+)?$/.test(String(t))) return t || ""; const d = new Date(parseFloat(t) * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds()); };

  P("/api/journal/sources", "journal.sources", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/journal/read", "journal.lire", {
    args: (r) => ({ source: r.body.source || "", limit: +(r.body.limit || 100), offset: +(r.body.offset || 0), query: r.body.query || "", since: r.body.since || "" }),
    sortie: (x) => ok(x),
  });
  P("/api/journal/search", "journal.chercher", { args: (r) => ({ question: r.body.query || "", per_source: +(r.body.per_source || 5) }), sortie: (x) => ok(x) });
  P("/api/journal/flux", "journal.flux", {
    args: (r) => ({ sources: r.body.sources || [], limit: +(r.body.limit || 200), niveau: r.body.niveau || "", acteur: r.body.acteur || "", query: r.body.query || "", since: r.body.since || "", equilibre: true, bruit: r.body.bruit !== false }),
    sortie: (x) => ok(x),
  });
  P("/api/journal/resume", "journal.resume", { args: (r) => ({ heures: +(r.body.heures || 24) }), sortie: (x) => ok(x) });
  P("/api/journal/timeline", "journal.timeline", {
    args: (r) => ({ at: r.body.at || "", window_min: +(r.body.window_min || 15), sources: r.body.sources || [], limit: +(r.body.limit || 400) }),
    sortie: (x) => ok(x),
  });
  P("/api/journal/stats", "journal.stats", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/journal/export", "journal.exporter", {
    args: (r) => ({ source: r.body.source || "", fmt: r.body.format || "csv", query: r.body.query || "", limit: +(r.body.limit || 5000) }),
    sortie: (x) => ok(x),
  });
  // Les veilles sur motif : une source vide vaut « tous les journaux ».
  P("/api/journal/watch", "journal.veilles", { args: () => ({}), sortie: (x) => ok({ watches: x.veilles || [] }) });
  P("/api/journal/watch/save", "journal.veille_poser", {
    args: (r) => ({ source: r.body.source || "", pattern: r.body.pattern || "", label: r.body.label || "", enabled: r.body.enabled !== false, wid: r.body.id || null }),
    sortie: (x) => ok(x),
  });
  P("/api/journal/watch/delete", "journal.veille_retirer", { args: (r) => ({ wid: +r.body.id }), sortie: (x) => ok(x) });

  // Le journal des agents : le fil (dans l'ordre où il s'est dit), la lecture rognée, et les écritures.
  P("/api/journal/agents/fil", "journal.fil", { args: (r) => ({ n: +(r.body.n || 14), depuis: r.body.depuis || "" }), sortie: (x) => ok(x) });
  P("/api/journal/agents/lire", "journal.agents_lire", {
    args: (r) => ({ n: +(r.body.n || 8), qui: r.body.qui || "", cherche: r.body.cherche || "", entier: !!r.body.entier }),
    sortie: (x) => ok(x),
  });
  P("/api/journal/agents/prompt", "journal.prompt", { args: (r) => ({ n: +(r.body.n || 5) }), sortie: (x) => ok(x) });
  P("/api/journal/agents/dire", "journal.agents_dire", { args: (r) => ({ etiquette: r.body.etiquette || "", message: r.body.message || "" }), sortie: (x) => ok(x) });
  P("/api/journal/agents/ecrire", "journal.agents_ecrire", {
    args: (r) => ({ qui: r.body.qui || "", modele: r.body.modele || "", etiquette: r.body.etiquette || "", consigne: r.body.consigne || "", dossier: r.body.dossier || "", reponse: r.body.reponse || "" }),
    sortie: (x) => ok(x),
  });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
