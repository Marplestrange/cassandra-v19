/* Courrier : /api/courrier/etat, /api/itare/mail/*, /api/me/mailbox* (V18) -> capacités courrier.* et reglages.* du noyau.
   Le noyau parle français (dossier, objet, lu…), l'écran V18 anglais (folder, subject, seen…) : les adaptateurs ci-dessous font la traduction. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);
  const dossier = (b) => String(b.folder || "INBOX") || "INBOX";
  const uids = (b) => b.uids || b.uid;

  // une ligne de liste ou de « récents » : français -> V18
  const ligne = (m) => ({ uid: m.uid, from: m.de, from_name: m.de_nom, from_addr: m.de_addr, subject: m.objet, date: m.date, date_iso: m.date_iso,
    seen: !!m.lu, flagged: !!m.suivi, answered: !!m.repondu, has_attach: !!m.pj, size: m.taille, thread_key: m.fil || "", technique: m.technique, etat: m.etat, apercu: m.apercu });

  P("/api/courrier/etat", "courrier.etat", { args: () => ({}), sortie: (e) => ok(Object.assign({}, e, { recents: (e.recents || []).map(ligne).map((x, i) => Object.assign(x, { subject: x.subject || "(sans objet)" })) })) });

  P("/api/itare/mail/folders", "courrier.dossiers", {
    args: () => ({}),
    sortie: (r) => ok({ folders: (r.dossiers || []).map((d) => ({ name: d.nom, sep: "/", special: d.role || "", role_flag: !d.role_ecarte, depth: d.profondeur || 0, unseen: d.non_lus || 0, total: d.total })) }),
  });
  P("/api/itare/mail/list", "courrier.lister", {
    args: (r) => ({ dossier: dossier(r.body), limite: +(r.body.limit || 25), non_lus: !!r.body.unseen_only, decalage: +(r.body.offset || 0), requete: r.body.query || "", etat: r.body.etat || "" }),
    sortie: (r) => ok({ folder: r.dossier, messages: (r.messages || []).map(ligne), total: r.total, offset: r.decalage, limit: r.limite, comptes: r.classes || {}, etat: r.etat || "", has_more: !!r.encore }),
  });
  P("/api/itare/mail/read", "courrier.lire", {
    args: (r) => ({ uid: String(r.body.uid || ""), dossier: dossier(r.body), html: r.body.with_html !== false }),
    sortie: (m) => ok({ uid: m.uid, folder: m.dossier, from: m.de, to: m.a, cc: m.cc, reply_to: m.repondre_a, subject: m.objet, date: m.date, date_iso: m.date_iso, message_id: m.message_id,
      references: m.references, thread_key: m.fil, body: m.texte, html: m.html, remote_images: m.images_distantes,
      attachments: (m.pieces || []).map((p) => ({ index: p.index, filename: p.nom, content_type: p.type, size: p.taille, inline: !!p.inline, cid: p.cid })) }),
  });
  P("/api/itare/mail/attachment", "courrier.piece", {
    args: (r) => ({ uid: String(r.body.uid || ""), index: +(r.body.index || 0), dossier: dossier(r.body) }),
    binaire: (p) => ({ b64: p.donnees_b64, type: p.type, nom: p.nom }),
  });
  P("/api/itare/mail/flag", "courrier.drapeau", {
    args: (r) => ({ uids: uids(r.body), champ: String(r.body.flag || "seen"), valeur: r.body.value !== false, dossier: dossier(r.body) }),
    sortie: (x) => ok({ count: (x.uids || []).length, uids: x.uids }),
  });
  P("/api/itare/mail/move", "courrier.deplacer", { args: (r) => ({ uids: uids(r.body), destination: String(r.body.dest || ""), dossier: dossier(r.body) }), sortie: (x) => ok({ moved: (x.uids || []).length, to: x.destination, method: x.methode }) });
  P("/api/itare/mail/archive", "courrier.archiver", { args: (r) => ({ uids: uids(r.body), dossier: dossier(r.body) }), sortie: (x) => ok({ moved: (x.uids || []).length, to: x.destination, method: x.methode }) });
  P("/api/itare/mail/delete", "courrier.supprimer", { args: (r) => ({ uids: uids(r.body), dossier: dossier(r.body) }), sortie: (x) => ok({ deleted: (x.uids || []).length, to: x.destination, permanent: false }) });
  P("/api/itare/mail/folder/create", "courrier.dossier_creer", { args: (r) => ({ nom: String(r.body.name || "") }), sortie: (x) => ok({ name: x.nom }) });

  // Ma boîte : les réglages du module, par compte. Le mot de passe est un secret : il ne revient jamais.
  const R = (reglages, cle) => { const x = reglages.find((y) => y.cle === "courrier." + cle); return x ? x.valeur : undefined; };
  P("/api/me/mailbox", null, {
    faire: async (req, agir) => {
      const rg = (await agir("reglages.lire", { module: "courrier" }, false)).reglages;
      const h = R(rg, "imap_hote") || "", u = R(rg, "imap_identifiant") || "";
      const s = rg.find((y) => y.cle === "courrier.imap_mot_de_passe");
      return { ok: true, source: h ? "personnelle" : "aucune", host: h, port: R(rg, "imap_port") || 993, user: u, ssl: R(rg, "imap_chiffre") !== false, configuree: !!(h && u),
        smtp_host: R(rg, "smtp_hote") || "", smtp_port: R(rg, "smtp_port") || 587, smtp_user: R(rg, "smtp_identifiant") || "", mot_de_passe_pose: !!(s && s.pose) };
    },
  });
  P("/api/me/mailbox/save", null, {
    faire: async (req, agir) => {
      const b = req.body;
      if (!String(b.host || "").trim() || !String(b.user || "").trim()) throw Object.assign(new Error("serveur et identifiant sont requis"), { statut: 400 });
      const poser = (cle, valeur) => agir("reglages.regler", { cle: "courrier." + cle, valeur });
      await poser("imap_hote", String(b.host).trim());
      if (b.port) await poser("imap_port", +b.port);
      await poser("imap_identifiant", String(b.user).trim());
      await poser("imap_chiffre", b.ssl !== false);
      if (b.password) await agir("reglages.regler_secret", { cle: "courrier.imap_mot_de_passe", valeur: String(b.password) });
      if (b.smtp_host) await poser("smtp_hote", String(b.smtp_host).trim());
      if (b.smtp_port) await poser("smtp_port", +b.smtp_port);
      if (b.smtp_user) await poser("smtp_identifiant", String(b.smtp_user).trim());
      if (b.smtp_password) await agir("reglages.regler_secret", { cle: "courrier.smtp_mot_de_passe", valeur: String(b.smtp_password) });
      return { ok: true, output: "Boîte enregistrée." };
    },
  });
  P("/api/me/mailbox/detach", null, {
    faire: async (req, agir) => {
      for (const c of ["imap_hote", "imap_identifiant", "imap_mot_de_passe", "smtp_hote", "smtp_identifiant", "smtp_mot_de_passe"]) await agir("reglages.reinitialiser", { cle: "courrier." + c });
      return { ok: true, output: "Boîte détachée. Vos messages restent sur le serveur." };
    },
  });
})();
