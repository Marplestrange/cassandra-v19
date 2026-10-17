/* Agenda : /api/itare/event*, /api/itare/events, /api/itare/reminders, /api/rappel/* (V18) -> capacités agenda.* du noyau. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const EV = { titre: "summary", debut: "start_at", fin: "end_at", journee: "all_day", lieu: "location", alarme: "alarm", projet_id: "project_id", quand: "when", texte: "text", echeance: "due_at", statut: "status" };
  const VERS19 = CASS.inverse(EV);
  const STATUT18 = { attente: "pending", fait: "done" };
  const STATUT19 = { pending: "attente", done: "fait", snoozed: "attente" };
  const rappel18 = (r) => { const x = CASS.cles(r, EV); if (x.status) x.status = STATUT18[x.status] || x.status; return x; };

  P("/api/itare/events", null, {
    faire: async (req, agir) => {
      const args = { du: (req.body.from || "").slice(0, 10), au: (req.body.to || "").slice(0, 10) };
      const [cal, evs, dist] = await Promise.all([agir("agenda.calendrier", args), agir("agenda.evenements", args), agir("agenda.caldav_etat", {}).catch(() => ({}))]);
      return { ok: true, events: CASS.cles(evs.evenements || [], EV), items: (cal.elements || []).map((x) => rappel18(x)), distant: !!(dist && (dist.configure || dist.configuree)) };
    },
  });
  P("/api/itare/event/save", "agenda.evenement_enregistrer", {
    args: (r) => { const b = r.body, a = {}; for (const k of Object.keys(b)) { if (k === "id" || k === "origine") continue; a[VERS19[k] || k] = b[k]; } if (b.id) a.id = +b.id; return a; },
    sortie: (x) => ok({ id: x.id }),
  });
  P("/api/itare/event/delete", "agenda.evenement_supprimer", { args: (r) => ({ id: +r.body.id }), sortie: ok });
  P("/api/itare/event/context", "agenda.evenement", { args: (r) => ({ id: +r.body.id }), sortie: (x) => ok(CASS.cles(x, EV)) });
  P("/api/itare/event/link", "agenda.lien_ajouter", { args: (r) => ({ id: +r.body.id, kind: r.body.kind || "", ref: String(r.body.ref || ""), label: r.body.label || "" }), sortie: ok });
  P("/api/itare/event/unlink", "agenda.lien_retirer", { args: (r) => ({ id: +r.body.id, kind: r.body.kind || "", ref: String(r.body.ref || "") }), sortie: ok });
  P("/api/itare/agenda/import", "agenda.ical_importer", { args: (r) => ({ texte: r.body.ics || "", etiquette: r.body.name || "import" }), sortie: ok });

  P("/api/itare/reminders", "agenda.rappels", { args: () => ({ inclure_faits: true }), sortie: (x) => ok({ reminders: (x.rappels || []).map(rappel18), faits_anciens: 0 }) });
  P("/api/rappel/creer", "agenda.rappel_enregistrer", { args: (r) => ({ texte: r.body.text || "", echeance: r.body.due || undefined }), sortie: (x) => ok({ id: x.id }) });
  P("/api/rappel/ecrire", "agenda.rappel_enregistrer", {
    args: (r) => { const c = r.body.champs || {}; return { id: +r.body.id, texte: c.text, echeance: c.due_at, statut: c.status ? STATUT19[c.status] || c.status : undefined }; },
    sortie: (x) => ok({ id: x.id }),
  });
  P("/api/rappel/accuser", "agenda.rappel_statut", { args: (r) => ({ id: +r.body.id, statut: "fait" }), sortie: ok });
  P("/api/rappel/supprimer", "agenda.rappel_supprimer", { args: (r) => ({ id: +r.body.id }), sortie: ok });
  P("/api/rappel/fiche", null, {
    faire: async (req, agir) => {
      const l = (await agir("agenda.rappels", { inclure_faits: true })).rappels || [];
      const x = l.find((y) => y.id === +req.body.id);
      if (!x) throw Object.assign(new Error("rappel introuvable"), { statut: 404 });
      return ok({ rappel: rappel18(x), reminder: rappel18(x) });
    },
  });
  // « reporter » : décaler l'échéance d'un délai (« 1h », « 1d », « 1w »…) à partir de maintenant.
  P("/api/rappel/reporter", null, {
    faire: async (req, agir) => {
      const m = /^(\d+)\s*([mhdw])/i.exec(String(req.body.delai || "1h")) || [0, 1, "h"];
      const ms = { m: 60e3, h: 3600e3, d: 86400e3, w: 604800e3 }[m[2].toLowerCase()] * +m[1];
      const d = new Date(Date.now() + ms), z = (n) => String(n).padStart(2, "0");
      const echeance = d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes());
      await agir("agenda.rappel_enregistrer", { id: +req.body.id, echeance, statut: "attente" });
      return ok({ id: +req.body.id, due_at: echeance });
    },
  });
})();
