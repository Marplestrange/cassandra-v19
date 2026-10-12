/* Contacts : /api/itare/contact/* et /api/itare/mail/contacts (V18) -> capacités contacts.* du noyau.
   Le noyau a gardé les noms de champs de la V18 ; il rend les dates en secondes, l'écran les lit en texte. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const z = (n) => String(n).padStart(2, "0");
  const ts18 = (t) => { if (typeof t !== "number") return t || ""; const d = new Date(t * 1000); return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds()); };
  const c18 = (c) => (c && typeof c === "object" ? Object.assign({}, c, { created_at: ts18(c.created_at), updated_at: ts18(c.updated_at) }) : c);
  const ids = (b) => (Array.isArray(b.ids) ? b.ids : b.id != null ? [b.id] : []).map(Number);

  const liste = { args: (r) => ({ query: r.body.query || "", limite: +(r.body.limit || 200), favoris: !!r.body.favorites_only, dossier_id: r.body.dossier_id == null ? undefined : r.body.dossier_id, vue: r.body.vue || "" }), sortie: (x) => ok({ contacts: (x.contacts || []).map(c18) }) };
  P("/api/itare/mail/contacts", "contacts.lister", liste);
  P("/api/itare/contact/corbeille", "contacts.lister", { args: () => ({ vue: "corbeille", limite: 500 }), sortie: liste.sortie });
  P("/api/itare/contact/get", "contacts.voir", { args: (r) => ({ id: +r.body.id }), sortie: (x) => ok({ contact: c18(x) }) });
  P("/api/itare/contact/save", null, {
    faire: async (req, agir) => {
      const b = req.body, a = {};
      for (const k of ["display_name", "phone", "mobile", "company", "job_title", "address", "website", "notes", "tags", "vault_ref", "emails", "favorite", "photo", "dossier_id", "anniversaire"]) if (k in b) a[k] = b[k];
      if (b.id) { a.id = +b.id; await agir("contacts.modifier", a); return ok({ id: a.id }); }
      const r = await agir("contacts.creer", a);
      return ok({ id: r.id });
    },
  });
  P("/api/itare/contact/delete", "contacts.supprimer", { args: (r) => ({ ids: ids(r.body) }), sortie: ok });
  P("/api/itare/contact/corbeille/mettre", "contacts.supprimer", { args: (r) => ({ ids: ids(r.body) }), sortie: ok });
  P("/api/itare/contact/restaurer", "contacts.restaurer", { args: (r) => ({ ids: ids(r.body) }), sortie: ok });
  P("/api/itare/contact/corbeille/purger", "contacts.purger_corbeille", { args: () => ({}), sortie: ok });
  P("/api/itare/contact/archiver", "contacts.archiver", { args: (r) => ({ ids: ids(r.body), archive: r.body.archive !== false }), sortie: ok });
  P("/api/itare/contact/deplacer", "contacts.deplacer", { args: (r) => ({ ids: ids(r.body), dossier_id: +(r.body.dossier_id || 0) }), sortie: ok });
  P("/api/itare/contact/dossiers", "contacts.dossiers", { args: () => ({}), sortie: ok });
  P("/api/itare/contact/dossier/save", "contacts.dossier_enregistrer", { args: (r) => ({ nom: r.body.nom || "", id: r.body.id, parent_id: +(r.body.parent_id || 0) }), sortie: ok });
  P("/api/itare/contact/dossier/delete", "contacts.dossier_supprimer", { args: (r) => ({ id: +r.body.id }), sortie: ok });
  P("/api/itare/contact/for_addr", "contacts.pour_adresse", { args: (r) => ({ adresse: r.body.addr || "" }), sortie: (x) => ok({ found: !!x.trouvee, contact: c18(x.contact) }) });
  P("/api/itare/contact/of", "contacts.pour_cible", { args: (r) => ({ kind: r.body.kind || "", ref: String(r.body.ref || "") }), sortie: (x) => ok({ contacts: (x.contacts || x || []).map ? (x.contacts || x).map(c18) : [] }) });
  P("/api/itare/contact/link", "contacts.lier", { args: (r) => ({ id: +r.body.contact_id, kind: r.body.kind || "", ref: String(r.body.ref || ""), role: r.body.role || "autre", label: r.body.label || "" }), sortie: ok });
  P("/api/itare/contact/unlink", "contacts.delier", { args: (r) => ({ id: +r.body.contact_id, kind: r.body.kind || "", ref: String(r.body.ref || "") }), sortie: ok });
  P("/api/itare/contact/duplicates", "contacts.doublons", { args: () => ({}), sortie: ok });
  P("/api/itare/contact/merge", "contacts.fusionner", { args: (r) => ({ source: +(r.body.src ?? r.body.src_id), destination: +(r.body.dst ?? r.body.dst_id) }), sortie: ok });
  P("/api/itare/contact/fusion/lot", "contacts.fusionner_certaines", { args: (r) => ({ paires: r.body.paires || [] }), sortie: ok });
  P("/api/itare/contact/pas_doublon", "contacts.pas_doublon", { args: (r) => ({ a: +r.body.a, b: +r.body.b, annuler: !!r.body.annuler }), sortie: ok });
  P("/api/itare/contact/vcard/import", "contacts.vcard_importer", { args: (r) => ({ texte: r.body.text || "" }), sortie: ok });
  P("/api/itare/contact/vcard/export", "contacts.vcard_exporter", { args: (r) => ({ ids: r.body.ids }), binaire: (x) => ({ b64: btoa(unescape(encodeURIComponent(typeof x === "string" ? x : x.texte || x.vcard || ""))), type: "text/vcard", nom: "contacts.vcf" }) });
  P("/api/itare/contact/csv/apercu", "contacts.csv_apercu", { args: (r) => ({ contenu_b64: btoa(unescape(encodeURIComponent(r.body.contenu || ""))) }), sortie: ok });
  P("/api/itare/contact/csv/importer", "contacts.csv_importer", { args: (r) => ({ contenu_b64: btoa(unescape(encodeURIComponent(r.body.contenu || ""))), appariement: r.body.appariement, dossier_id: 0 }), sortie: ok });
})();
