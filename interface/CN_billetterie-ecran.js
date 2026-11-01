// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Billetterie : l'écran du titulaire (vue d'ensemble, événements, ventes, personnes, argent)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #310eb4
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Billetterie : l'écran du titulaire (vue d'ensemble, événements, ventes, personnes, argent). Tout passe par les capacités billetterie.* : les règles sont dans le module, jamais ici.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=310eb4 ▼▼▼
// Billetterie : l'écran du titulaire (vue d'ensemble, événements, ventes, personnes, argent). Tout passe par les capacités billetterie.* : les règles sont dans le module, jamais ici.
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = (c, a) => K.agir("billetterie." + c, a), dire = K.dire, confirmer = K.confirmer;
  const B = CASS.billetterie = CASS.billetterie || { pages: {} };

  // ── aides communes ─────────────────────────────────────────────────────────
  const eur = (c) => (Number(c || 0) / 100).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  const cts = (v) => Math.round(parseFloat(String(v == null ? "" : v).replace(",", ".").replace(/\s/g, "") || "0") * 100) || 0;
  const euroCourt = (c) => (Number(c || 0) / 100).toFixed(2).replace(".", ",");
  const jour = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric" }) : "—");
  const jourCourt = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) : "—");
  const quand = (ts) => (ts ? String(ts).replace("T", " ").slice(0, 16) : "—");
  const ETATS_EVT = { brouillon: ["Brouillon", ""], "en vente": ["En vente", "ok"], complet: ["Complet", "al"], "annulé": ["Annulé", "dg"], "reporté": ["Reporté", "al"], "terminé": ["Terminé", ""] };
  const ETATS_CMD = { retenue: ["Réservée", "al"], en_attente: ["Virement attendu", "al"], payee: ["Payée", "ok"], remboursee: ["Remboursée", "dg"], annulee: ["Annulée", ""], expiree: ["Expirée", ""] };
  const puce = (t, c) => '<span class="p ' + (c || "") + '">' + esc(t) + "</span>";
  const puceEvt = (s) => { const x = ETATS_EVT[s] || [s, ""]; return puce(x[0], x[1]); };
  const puceCmd = (s) => { const x = ETATS_CMD[s] || [s, ""]; return puce(x[0], x[1]); };
  const MOYENS = { especes: "Espèces", carte_terminal: "Terminal carte", carte_declaree: "Carte (déclarée)", offert: "Offert", stripe: "Carte en ligne", virement: "Virement", helloasso: "HelloAsso", paypal: "PayPal" };

  // Le style est celui du KIT commun (.kit : cartes, boutons, onglets, pastilles .p, tuiles .stat, alertes, jauges), comme Dolibarr et les autres écrans V19. Ne reste ici que ce qui est propre à la billetterie.
  const CSS = ".sh-scene:has(>.sh-corps>.bl){width:100%;max-width:none}.sh-scene:has(>.sh-corps>.bl)>.sh-titre{display:none}.bl{width:100%}.bl>*{min-width:0}.bl button{font:inherit;color:inherit;cursor:pointer}" +
    ".bl .carte h2{font:650 15px/1.25 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.bl .carte h3{margin:0 0 6px}.bl .sub{color:var(--txt-soft);font-size:12.5px;margin:0}.bl .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.bl .row .sp{flex:1}" +
    ".bl .stat.cl{cursor:pointer;font:inherit;color:inherit}.bl .stat.cl:hover{border-color:var(--accent)}.bl .stat.al{border-color:color-mix(in srgb,var(--warn) 55%,transparent)}.bl .btn.sm{padding:4px 10px;font-size:12px}" +
    ".bl input[type=text],.bl input[type=search],.bl input[type=number],.bl input[type=date],.bl input[type=time],.bl select,.bl textarea{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:8px 11px;min-width:0;width:100%}.bl textarea{min-height:80px;resize:vertical}" +
    ".bl .tw{overflow-x:auto;background:var(--surface);backdrop-filter:blur(14px) saturate(150%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);padding:6px 10px}.bl table{border-collapse:collapse;width:100%;font-size:13px}" +
    ".bl th{font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}.bl td{padding:8px;border-bottom:1px solid var(--line);vertical-align:middle}.bl tr:last-child td{border-bottom:0}.bl td.n,.bl th.n{text-align:right}" +
    ".bl tr.cl{cursor:pointer}.bl tr.cl:hover td{background:color-mix(in srgb,var(--accent) 7%,transparent)}.bl .hint{font-size:12px;color:var(--txt-faint)}.bl .alerte{border-left-color:var(--warn)}.bl .alerte.dg{border-left-color:var(--danger)}" +
    ".bl .evt{display:grid;gap:6px;text-align:left;width:100%}.bl .evt:hover{border-color:var(--accent)}.bl .grille{grid-template-columns:repeat(auto-fill,minmax(290px,1fr))}" +
    ".bl .champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.bl .champs label,.bf label{display:grid;gap:3px;font-size:12px;color:var(--txt-soft)}.bl .champs label.large,.bf label.large{grid-column:1/-1}.bl .kv{display:grid;grid-template-columns:auto 1fr;gap:3px 14px;font-size:13px}.bl .kv dt{color:var(--txt-faint)}.bl .kv dd{margin:0}" +
    ".bf{display:grid;gap:10px}.bf input[type=text],.bf input[type=number],.bf input[type=date],.bf input[type=time],.bf select,.bf textarea{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:8px 11px;width:100%;min-width:0}.bf textarea{min-height:70px}.bf .deux{display:grid;grid-template-columns:1fr 1fr;gap:10px}.bf .coche{display:flex;gap:8px;align-items:center}.bf .coche input{width:auto}" +
    "@media(max-width:640px){.bl .stats{grid-template-columns:repeat(2,minmax(0,1fr))}.bf .deux{grid-template-columns:1fr}.bl td,.bl th{padding:7px 6px}}";

  // ── un formulaire en fenêtre : champs déclarés, valeurs rendues (ou null si on annule) ──
  // La fenêtre se referme AVANT que la promesse ne rende la main : on relève les valeurs au moment du clic.
  async function formulaire(titre, champs, valeurs, oui, danger) {
    valeurs = valeurs || {};
    const champ = (c) => {
      const v = valeurs[c.n] == null ? (c.def == null ? "" : c.def) : valeurs[c.n], id = "bf-" + c.n, large = c.t === "textarea" || c.large ? " large" : "";
      if (c.t === "note") return '<p class="hint" style="grid-column:1/-1;margin:0">' + c.l + "</p>";
      if (c.t === "check") return '<label class="coche' + large + '"><input type="checkbox" id="' + id + '"' + (v && v !== "0" ? " checked" : "") + "> " + esc(c.l) + "</label>";
      let ctrl;
      if (c.t === "select") ctrl = '<select id="' + id + '">' + (c.opts || []).map((o) => { const val = Array.isArray(o) ? o[0] : o, lib = Array.isArray(o) ? o[1] : o; return '<option value="' + esc(val) + '"' + (String(val) === String(v) ? " selected" : "") + ">" + esc(lib) + "</option>"; }).join("") + "</select>";
      else if (c.t === "textarea") ctrl = '<textarea id="' + id + '">' + esc(v) + "</textarea>";
      else if (c.t === "eur") ctrl = '<input type="text" inputmode="decimal" id="' + id + '" value="' + esc(v === "" ? "" : euroCourt(v)) + '" placeholder="0,00">';
      else ctrl = '<input type="' + (c.t || "text") + '" id="' + id + '" value="' + esc(v) + '"' + (c.t === "number" ? ' inputmode="numeric"' : "") + (c.ph ? ' placeholder="' + esc(c.ph) + '"' : "") + ">";
      return '<label class="' + large.trim() + '">' + esc(c.l) + ctrl + (c.aide ? '<span class="hint">' + esc(c.aide) + "</span>" : "") + "</label>";
    };
    const snap = {};
    const relever = (ev) => {
      if (!(ev.target.closest && ev.target.closest(".kit-m [data-c='oui']"))) return;
      champs.forEach((c) => { const n = document.getElementById("bf-" + c.n); if (!n) return; snap[c.n] = c.t === "check" ? n.checked : (c.t === "eur" ? cts(n.value) : (c.t === "number" ? (n.value === "" ? "" : Number(n.value)) : n.value.trim())); });
    };
    document.addEventListener("click", relever, true);
    const ok = await confirmer(titre, '<div class="bf">' + champs.map(champ).join("") + "</div>", oui || "Enregistrer", danger);
    document.removeEventListener("click", relever, true);
    return ok ? snap : null;
  }
  B.formulaire = formulaire;

  // ── les entités à gérer : une description, un seul code ────────────────────
  const OUINON = [["0", "Non"], ["1", "Oui"]];
  const STATUTS = ["Particulier", "Association", "Société"];
  const adresseChamps = [{ n: "adresse", l: "Adresse" }, { n: "code_postal", l: "Code postal" }, { n: "ville", l: "Ville" }];
  const ENT = {
    salle: { pl: "salles", un: "salle", titre: "Salles", save: "salle_save", del: "salle_delete", nouv: "Nouvelle salle", cols: [["nom", "Salle"], ["adresse", "Adresse"], ["assis", "Assis", "n"], ["debout", "Debout", "n"], ["location", "Location", "eur"], ["acompte", "Acompte", "eur"]],
      champs: [{ n: "nom", l: "Nom" }, { n: "adresse", l: "Adresse" }, { n: "contact", l: "Contact" }, { n: "assis", l: "Places assises", t: "number" }, { n: "debout", l: "Places debout", t: "number" }, { n: "location", l: "Prix de location (€)", t: "eur" }, { n: "acompte", l: "Acompte (€)", t: "eur" }, { n: "caution", l: "Caution (€)", t: "eur" },
        { n: "heure_fin", l: "Heure limite", t: "time" }, { n: "pmr", l: "Accessible PMR", t: "check" }, { n: "erp", l: "Catégorie ERP" }, { n: "bruit", l: "Règle de bruit" }, { n: "alcool", l: "Alcool" }, { n: "equipements", l: "Équipements", t: "textarea" }, { n: "annulation", l: "Conditions d’annulation de la salle", t: "textarea" }, { n: "assurance", l: "Assurance" }] },
    formule: { pl: "formules", un: "formule", titre: "Formules", save: "formule_save", del: "formule_delete", nouv: "Nouvelle formule", cols: [["nom", "Formule"], ["role", "Pour", "role"], ["forfait", "Forfait", "eur"], ["com", "Par place", "eur"], ["fixe", "Fixe", "eur"], ["palier_n", "Palier dès", "n"]],
      champs: [{ n: "nom", l: "Nom" }, { n: "role", l: "Pour qui", t: "select", opts: [["independant", "Revendeur indépendant (commission)"], ["artiste", "Artiste qui vend (forfait + commission)"], ["cachet", "Artiste qui ne vend pas (cachet fixe)"]], aide: "Le groupe ne change plus une fois la formule créée." },
        { n: "forfait", l: "Forfait / cachet (€)", t: "eur" }, { n: "com", l: "Commission par place (€)", t: "eur" }, { n: "fixe", l: "Fixe par événement (€)", t: "eur" }, { n: "palier_n", l: "Palier : à partir de (places)", t: "number" }, { n: "palier_com", l: "Commission au-delà du palier (€)", t: "eur" }, { n: "note", l: "Note", t: "textarea" }] },
    artiste: { pl: "artistes", un: "artiste", titre: "Artistes", save: "artiste_save", del: "artiste_delete", nouv: "Nouvel artiste", cols: [["scene", "Scène"], ["genre", "Genre"], ["mail", "Courriel"], ["vend", "Vend", "oui"], ["compte", "Compte", "txt"]],
      champs: [{ n: "scene", l: "Nom de scène" }, { n: "legal", l: "Nom légal" }, { n: "genre", l: "Genre" }, { n: "statut", l: "Statut", t: "select", opts: STATUTS }, { n: "mail", l: "Courriel" }, { n: "tel", l: "Téléphone" }, { n: "formule_id", l: "Formule", t: "select", opts: "formules:artiste,cachet" }, { n: "vend", l: "Vend lui-même ses places", t: "check" },
        { n: "compte", l: "Compte (son espace artiste)", aide: "L’identifiant de son compte : il verra son programme et son portefeuille." }, { n: "siret", l: "SIRET" }, { n: "tva", l: "N° TVA" }].concat(adresseChamps).concat([{ n: "rider", l: "Fiche technique (rider)", t: "textarea" }, { n: "bio", l: "Biographie", t: "textarea" }]) },
    revendeur: { pl: "revendeurs", un: "revendeur", titre: "Revendeurs", save: "revendeur_save", del: "revendeur_delete", nouv: "Nouveau revendeur", cols: [["nom", "Revendeur"], ["code", "Code"], ["type", "Type", "type"], ["mail", "Courriel"], ["actif", "Actif", "oui"], ["compte", "Compte", "txt"]],
      champs: [{ n: "nom", l: "Nom" }, { n: "statut", l: "Statut", t: "select", opts: STATUTS }, { n: "mail", l: "Courriel" }, { n: "tel", l: "Téléphone" }, { n: "compte", l: "Compte (son espace revendeur)", aide: "Un compte ne se lie qu’à un revendeur." }, { n: "actif", l: "Actif (peut vendre)", t: "check", def: true }, { n: "suspendu_motif", l: "Motif de suspension" }, { n: "siret", l: "SIRET" }].concat(adresseChamps) },
    promo: { pl: "promos", un: "code promo", titre: "Codes promo", save: "promo_save", del: "promo_delete", nouv: "Nouveau code", cols: [["code", "Code"], ["type", "Type", "promo"], ["valeur", "Valeur", "promoval"], ["fin", "Jusqu’au"], ["actif", "Actif", "oui"]],
      champs: [{ n: "code", l: "Code" }, { n: "type", l: "Type", t: "select", opts: [["pct", "Pourcentage"], ["eur", "Euros par billet"]] }, { n: "valeur", l: "Valeur", t: "number", aide: "Pourcentage, ou centimes par billet." }, { n: "max_usages", l: "Utilisations maximales (0 = illimité)", t: "number" }, { n: "fin", l: "Valable jusqu’au", t: "date" }, { n: "actif", l: "Actif", t: "check", def: true }] },
  };
  B.ENT = ENT;
  const cellule = (col, ligne) => {
    const v = ligne[col[0]], t = col[2];
    if (t === "eur") return '<td class="n">' + (v ? eur(v) : "—") + "</td>";
    if (t === "n") return '<td class="n">' + esc(v == null ? "" : v) + "</td>";
    if (t === "oui") return "<td>" + (v ? puce("oui", "ok") : puce("non", "")) + "</td>";
    if (t === "role") return "<td>" + puce({ independant: "Revendeur", artiste: "Artiste vendeur", cachet: "Cachet" }[v] || v, "ac") + "</td>";
    if (t === "type") return "<td>" + puce(v === "artiste" ? "Artiste" : "Indépendant", v === "artiste" ? "ac" : "") + "</td>";
    if (t === "promo") return "<td>" + (v === "pct" ? "Pourcentage" : "Euros") + "</td>";
    if (t === "promoval") return '<td class="n">' + (ligne.type === "pct" ? esc(v) + " %" : eur(v)) + "</td>";
    return "<td>" + (v ? esc(v) : '<span class="hint">—</span>') + "</td>";
  };

  // ── la scène ─────────────────────────────────────────────────────────────
  const PAGES = { b_vue: "vue", b_evenements: "evenements", b_ventes: "ventes", b_personnes: "personnes", b_argent: "argent", b_caisse: "caisse", b_controle: "controle", b_revendeur: "revendeur", b_artiste: "artiste" };
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.billetterie = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("bl-css")) { const st = document.createElement("style"); st.id = "bl-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit bl"; corps.appendChild(racine);
    const page = PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "vue";
    const S = { page: page, racine: racine, erreur: "", cache: {} };
    S.peut = (droit) => K.peut("billetterie." + droit);
    S.lire = async (cap, args, droit) => { if (droit && !S.peut(droit)) return null; try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } };
    S.geste = async (cap, args, ok) => { try { const r = await agir(cap, args || {}); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } };
    S.rendre = async () => {
      await K.droits();
      S.erreur = "";
      const f = B.pages[S.page];
      if (!f) { racine.innerHTML = '<div class="carte vide">Cet écran n’existe pas.</div>'; return; }
      try { await f(S); } catch (e) { racine.innerHTML = '<div class="carte"><span style="color:var(--danger)">' + esc(e.message || String(e)) + "</span></div>"; }
    };
    S.entetes = (titre, sous, actions) => '<div class="barre"><div class="titre" style="flex:1 1 260px;min-width:0"><h1>' + esc(titre) + "</h1><p>" + esc(sous || "") + "</p></div>" + (actions || "") + "</div>";
    const onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const a = onglet.classList.contains("active"); if (a && !etait && S.rechargeable !== false) S.rendre(); etait = a; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    racine.addEventListener("click", (ev) => { const a = ev.target.closest("[data-a]"); if (a && S.clic) S.clic(a.dataset.a, a, ev); });
    racine.addEventListener("input", (ev) => { if (S.saisie) S.saisie(ev); });
    racine.addEventListener("change", (ev) => { if (S.change) S.change(ev); });
    await S.rendre();
  };
  B.aides = { eur: eur, cts: cts, euroCourt: euroCourt, jour: jour, jourCourt: jourCourt, quand: quand, puce: puce, puceEvt: puceEvt, puceCmd: puceCmd, MOYENS: MOYENS, CSS: CSS, cellule: cellule };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
