// ═════════════════════════════════════════════════════════════════════
// TITRE      : Dolibarr : l'écran de gestion
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #e77c79
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : l'écran de gestion du module dolibarr : à faire, factures, devis, tiers, banque, dons, adhérents, projets, ma clé, requête libre
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.dolibarr) ; toutes les listes se lisent par dolibarr.lire_libre (une page de 100 lignes), tous les gestes passent par les capacités du module, après une confirmation sur place ; tout texte dynamique est échappé
// ═════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=e77c79 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const K = CASS.kit, esc = K.esc, pill = K.pill;
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const eur = (n) => Number(n || 0).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  const jour = (v) => { if (!v) return "—"; const d = /^\d+$/.test(String(v)) ? new Date(Number(v) * 1000 + 43200000) : new Date(v); return isNaN(d) ? esc(v) : d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }); };
  const iso = (v) => { if (!v) return ""; const d = /^\d+$/.test(String(v)) ? new Date(Number(v) * 1000 + 43200000) : new Date(v); return isNaN(d) ? "" : d.toISOString().slice(0, 10); };
  const retard = (f) => { const e = f.date_lim_reglement; if (!e) return 0; const d = /^\d+$/.test(String(e)) ? Number(e) * 1000 : new Date(e).getTime(); return Math.floor((Date.now() - d) / 864e5); };
  const AUJ = new Date().toISOString().slice(0, 10);
  const CSS = ".dlb .barre2{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.dlb .t{width:100%;border-collapse:collapse;font-size:13px}.dlb .t th{text-align:left;font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:6px 8px;border-bottom:1px solid var(--line)}" +
    ".dlb .t td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}.dlb .t tr.clk{cursor:pointer}.dlb .t tr.clk:hover td{background:color-mix(in srgb,var(--accent) 7%,transparent)}.dlb .t .num{font-family:ui-monospace,Menlo,monospace;white-space:nowrap}" +
    ".dlb .defil{overflow-x:auto}.dlb .fld{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--txt-faint);font-weight:600}.dlb .in,.kit-m .in{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 11px;font:500 13px 'Inter',sans-serif;min-width:0;max-width:100%}" +
    ".kit-m .fld{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--txt-faint);font-weight:600}.kit-m .grille2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kit-m textarea.in{width:100%;resize:vertical}.dlb .code{background:var(--surface);border:1px dashed var(--line-strong,var(--line));border-radius:10px;padding:10px 12px;font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}";

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.dolibarr = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("dolibarr", corps); return; }
    K.injecter();
    const anc = document.getElementById("dlb-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "dlb-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "kit dlb"; corps.appendChild(racine);
    const S = { v: {}, onglet: "afaire", d: {}, q: {}, f: { factures: "ouvertes" }, err: "", occupe: false, acces: null, libre: "", libreRep: null };

    async function lire(chemin, params) { return (await agir("dolibarr.lire_libre", { chemin: chemin, parametres: params || "" })).reponse || []; }
    const liste = (r) => (Array.isArray(r) ? r : []);
    const PAGE = "limit=100&sortfield=t.rowid&sortorder=DESC";
    const CHARGEURS = {
      tiers: async () => liste(await lire("/thirdparties", PAGE + "&properties=id,name,client,fournisseur,town")),
      factures: async () => liste(await lire("/invoices", PAGE + "&properties=id,ref,socid,date,date_lim_reglement,total_ttc,remaintopay,statut,paye,type")),
      devis: async () => liste(await lire("/proposals", PAGE + "&properties=id,ref,socid,date,total_ttc,statut")),
      projets: async () => liste(await lire("/projects", PAGE + "&properties=id,ref,title,statut,date_start,date_end")),
      produits: async () => liste(await lire("/products", PAGE + "&properties=id,ref,label,price,tva_tx")),
      dons: async () => liste(await lire("/donations", PAGE + "&properties=id,ref,amount,date,statut")),
      adherents: async () => liste(await lire("/members", PAGE + "&properties=id,firstname,lastname,typeid,statut,datefin")),
      cp: async () => liste((await agir("projets.lister")).projets),
      cc: async () => liste((await agir("contacts.lister", { limite: 200 })).contacts),
      liens: async () => liste(await agir("dolibarr.liens")),
      types: async () => liste(await lire("/members/types", "limit=100")),
      banques: async () => { const l = liste(await lire("/bankaccounts", "limit=100&properties=id,label,clos")); await Promise.all(l.map(async (b) => { try { b.solde = Number((await lire("/bankaccounts/" + b.id + "/balance")) || 0); } catch (e) { b.solde = null; } })); return l; },
    };
    const BESOIN = { afaire: ["factures", "devis", "dons", "tiers"], factures: ["factures", "tiers", "banques"], devis: ["devis", "tiers"], tiers: ["tiers", "factures"], banque: ["banques"], dons: ["dons"], adherents: ["adherents", "types"], projets: ["projets"], cprojets: ["cp", "liens", "projets"], ccontacts: ["cc", "liens", "tiers"] };
    async function charger(forcer) {
      S.err = ""; const vus = BESOIN[S.onglet] || [];
      await Promise.all(vus.filter((k) => forcer || !S.d[k]).map(async (k) => { try { S.d[k] = await CHARGEURS[k](); } catch (e) { S.err = e.message || String(e); S.d[k] = []; } }));
      if (S.onglet === "acces" && !S.acces) { try { S.acces = await agir("dolibarr.mon_acces"); } catch (e) { S.acces = { erreur: e.message || String(e) }; } }
      dessiner();
    }
    const nomTiers = (id) => { const t = (S.d.tiers || []).find((x) => String(x.id) === String(id)); return t ? t.name : "tiers " + id; };
    const filtrer = (l, k, f) => (l || []).filter((x) => !S.q[k] || JSON.stringify(x).toLowerCase().includes(S.q[k].toLowerCase()) || (f && f(x)));
    const barre = (k, droite) => '<div class="barre2"><input type="search" class="in" data-q="' + k + '" placeholder="Chercher…" value="' + esc(S.q[k] || "") + '" style="flex:1 1 220px"><span style="flex:1"></span>' + (droite || "") + "</div>";
    const seg = (k, opts) => '<div class="seg">' + opts.map((o) => '<button data-f="' + k + '|' + o[0] + '" class="' + ((S.f[k] || opts[0][0]) === o[0] ? "on" : "") + '">' + o[1] + "</button>").join("") + "</div>";
    const etatF = (f) => { const s = String(f.statut); if (s === "0") return pill("Brouillon"); if (s === "3") return pill("Abandonnée"); if (s === "2" || String(f.paye) === "1") return pill("Payée", "ok"); const r = retard(f); return r > 0 ? pill("En retard · " + r + " j", r > 365 ? "dg" : "al") : pill("À encaisser", "ac"); };
    const etiq = (o) => (o.venu ? pill("Venu de Dolibarr", "ac") : o.lien ? pill("Dolibarr · lié", "ok") + ' <span class="note">le ' + jour(o.lien.le) + "</span>" : pill("Cassandra seulement", ""));
    const ouverte = (f) => String(f.statut) === "1" && String(f.paye) !== "1" && Number(f.remaintopay) > 0.005;
    const table = (cols, rows) => '<div class="defil"><table class="t"><thead><tr>' + cols.map((c) => "<th>" + c + "</th>").join("") + "</tr></thead><tbody>" + (rows.join("") || '<tr><td colspan="' + cols.length + '" class="note">Rien ne correspond.</td></tr>') + "</tbody></table></div>";
    const btn = (t, a, p, c) => '<button class="btn mini ' + (c || "") + '" data-a="' + a + '" data-p="' + esc(p == null ? "" : p) + '">' + t + "</button>";

    // ───────── les onglets
    const VUES = {
      afaire() {
        const F = S.d.factures || [], ouv = F.filter(ouverte), ret = ouv.filter((f) => retard(f) > 0), rec = ret.filter((f) => retard(f) <= 365), vie = ret.filter((f) => retard(f) > 365);
        const bro = F.filter((f) => String(f.statut) === "0"), sig = (S.d.devis || []).filter((d) => String(d.statut) === "2"), dons = (S.d.dons || []).filter((d) => String(d.statut) === "0");
        const li = (t, d, b) => '<div class="li"><div class="sp"><b>' + t + '</b><div class="note">' + d + '</div></div><div style="display:flex;gap:6px;flex-wrap:wrap">' + b + "</div></div>";
        return '<div class="stats"><div class="stat"><b>' + eur(ouv.reduce((s, f) => s + Number(f.remaintopay || 0), 0)) + "</b><span>à encaisser · " + ouv.length + ' factures</span></div><div class="stat al"><b>' + ret.length + "</b><span>en retard</span></div><div class=\"stat\"><b>" + bro.length + "</b><span>brouillons</span></div><div class=\"stat\"><b>" + sig.length + "</b><span>devis signés à facturer</span></div></div>" +
          '<div class="carte"><h3>À traiter</h3><div class="liste">' +
          (rec.length ? li("Relancer " + rec.length + " factures en retard", eur(rec.reduce((s, f) => s + Number(f.remaintopay), 0)) + " dus. Chaque relance se relit avant d’être gardée.", btn("Voir les factures", "onglet", "factures")) : "") +
          (vie.length ? li(vie.length + " factures de plus d’un an", eur(vie.reduce((s, f) => s + Number(f.remaintopay), 0)) + " : à ne pas relancer par automatisme. Un avoir les solderait si l’expert-comptable décide la perte.", btn("Voir", "onglet", "factures")) : "") +
          bro.map((f) => li("Valider " + esc(f.ref) + " ?", esc(nomTiers(f.socid)) + " · " + eur(f.total_ttc), btn("Valider", "valider", f.id, "pri"))).join("") +
          sig.map((d) => li("Facturer le devis " + esc(d.ref), esc(nomTiers(d.socid)) + " · " + eur(d.total_ttc), btn("Préparer la facture", "facturer", d.id, "pri"))).join("") +
          dons.map((d) => li("Valider le don de " + eur(d.amount), jour(d.date) + " : promesse à valider, puis reçu fiscal", btn("Valider", "donvalider", d.id, "pri"))).join("") +
          ((rec.length || vie.length || bro.length || sig.length || dons.length) ? "" : '<div class="vide">Rien n’attend un geste.</div>') + "</div></div>";
      },
      factures() {
        const f = S.f.factures || "ouvertes", F = filtrer(S.d.factures, "factures", (x) => nomTiers(x.socid).toLowerCase().includes((S.q.factures || "~").toLowerCase())).filter((x) => f === "toutes" || (f === "ouvertes" && ouverte(x)) || (f === "retard" && ouverte(x) && retard(x) > 0) || (f === "brouillons" && String(x.statut) === "0") || (f === "payees" && String(x.paye) === "1"));
        return '<div class="carte">' + barre("factures", btn("+ Nouvelle facture", "nfacture", "", "pri")) + seg("factures", [["ouvertes", "Ouvertes"], ["retard", "En retard"], ["brouillons", "Brouillons"], ["payees", "Payées"], ["toutes", "Toutes"]]) +
          table(["Réf.", "Tiers", "Date", "Échéance", "Total", "Reste", "État"], F.map((x) => '<tr class="clk" data-a="fiche" data-p="' + x.id + '"><td class="num"><b>' + esc(x.ref) + "</b></td><td>" + esc(nomTiers(x.socid)) + "</td><td>" + jour(x.date) + "</td><td>" + (String(x.statut) === "1" ? jour(x.date_lim_reglement) : "—") + '</td><td class="num">' + eur(x.total_ttc) + '</td><td class="num">' + (ouverte(x) ? eur(x.remaintopay) : "—") + "</td><td>" + etatF(x) + "</td></tr>")) +
          (S.d.factures && S.d.factures.length >= 100 ? '<div class="note">100 lignes affichées : les plus récentes.</div>' : "") + "</div>";
      },
      devis() {
        const L = ["Brouillon", "Ouvert", "Signé", "Refusé", "Facturé"], D = filtrer(S.d.devis, "devis");
        return '<div class="carte">' + barre("devis", btn("+ Nouveau devis", "ndevis", "", "pri")) + table(["Réf.", "Tiers", "Date", "Total", "État", ""], D.map((d) => {
          const s = String(d.statut); const b = s === "0" ? btn("Valider", "devis", d.id + "|valider") : s === "1" ? btn("Marquer signé", "devis", d.id + "|signer") + btn("Refusé", "devis", d.id + "|refuser") : s === "2" ? btn("Facturer", "facturer", d.id, "pri") : "";
          return "<tr class=\"clk\" data-a=\"fichedevis\" data-p=\"" + d.id + "\"><td class=\"num\"><b>" + esc(d.ref) + "</b></td><td>" + esc(nomTiers(d.socid)) + "</td><td>" + jour(d.date) + '</td><td class="num">' + eur(d.total_ttc) + "</td><td>" + pill(L[Number(s)] || "Annulé", s === "2" ? "ok" : "") + "</td><td>" + b + "</td></tr>";
        })) + "</div>";
      },
      tiers() {
        const T = filtrer(S.d.tiers, "tiers");
        return '<div class="carte">' + barre("tiers", btn("+ Nouveau tiers", "ntiers", "", "pri")) + table(["Nom", "Type", "Ville", "Factures", "Dû"], T.map((t) => { const f = (S.d.factures || []).filter((x) => String(x.socid) === String(t.id)), du = f.filter(ouverte).reduce((s, x) => s + Number(x.remaintopay), 0); return '<tr class="clk" data-a="tiers" data-p="' + t.id + '"><td><b>' + esc(t.name) + "</b></td><td>" + (String(t.client) !== "0" ? pill("client", "ac") : "") + " " + (String(t.fournisseur) === "1" ? pill("fournisseur") : "") + "</td><td>" + esc(t.town || "") + '</td><td class="num">' + f.length + '</td><td class="num">' + (du ? eur(du) : "—") + "</td></tr>"; })) + "</div>";
      },
      banque() {
        const B = (S.d.banques || []).filter((b) => String(b.clos) !== "1");
        return '<div class="stats">' + B.map((b) => '<div class="stat"><b>' + (b.solde == null ? "?" : eur(b.solde)) + "</b><span>" + esc(b.label) + "</span></div>").join("") + '</div><div class="carte"><h3>Virement entre comptes</h3><div class="note">Le solde des deux comptes est relu après le virement ; un contre-virement le défait.</div><div>' + btn("Virer d’un compte à l’autre", "virement", "", "pri") + "</div></div>";
      },
      dons() {
        const D = S.d.dons || [];
        return '<div class="carte"><div class="barre2"><h3 style="flex:1">Dons</h3>' + btn("+ Nouveau don", "ndon", "", "pri") + "</div>" + table(["Réf.", "Date", "Montant", "État", ""], D.map((d) => "<tr><td class=\"num\">" + esc(d.ref || d.id) + "</td><td>" + jour(d.date) + '</td><td class="num">' + eur(d.amount) + "</td><td>" + (String(d.statut) === "0" ? pill("Promesse", "al") : pill("Validé", "ok")) + "</td><td>" + (String(d.statut) === "0" ? btn("Valider", "donvalider", d.id) : btn("Reçu fiscal", "donrecu", d.id, "pri")) + "</td></tr>")) + "</div>";
      },
      adherents() {
        const T = Object.fromEntries((S.d.types || []).map((t) => [String(t.id), t.label])), A = filtrer(S.d.adherents, "adherents");
        return '<div class="carte">' + barre("adherents", "") + table(["N°", "Adhérent", "Type", "État", "Fin", ""], A.map((a) => '<tr><td class="num">' + a.id + "</td><td><b>" + esc(((a.firstname || "") + " " + (a.lastname || a.name || "")).trim()) + "</b></td><td>" + esc(T[String(a.typeid)] || a.typeid) + "</td><td>" + (String(a.statut) === "1" ? pill("actif", "ok") : pill("à revoir", "al")) + "</td><td>" + jour(a.datefin) + "</td><td>" + btn("Cotisation", "cotis", a.id) + "</td></tr>")) + "</div>";
      },
      projets() {
        const P = filtrer(S.d.projets, "projets"), L = ["Brouillon", "Ouvert", "Clos"];
        return '<div class="carte">' + barre("projets", btn("+ Nouveau projet", "nprojet", "", "pri")) + table(["Réf.", "Projet", "Début", "Fin", "État", ""], P.map((p) => "<tr><td class=\"num\">" + esc(p.ref) + "</td><td><b>" + esc(p.title) + "</b></td><td>" + jour(p.date_start) + "</td><td>" + jour(p.date_end) + "</td><td>" + pill(L[Number(p.statut)] || p.statut, String(p.statut) === "1" ? "ok" : "") + "</td><td>" + (String(p.statut) === "0" ? btn("Valider", "projet", p.id + "|valider") : String(p.statut) === "1" ? btn("Clore", "projet", p.id + "|clore") : "") + "</td></tr>")) + "</div>";
      },
      cprojets() {
        const lie = (id) => (S.d.liens || []).find((l) => l.type === "projet" && String(l.id) === String(id)), f = S.f.cprojets || "tous";
        const liesDoli = new Set((S.d.liens || []).filter((l) => l.type === "projet").map((l) => String(l.id_doli)));
        const mien = (S.d.cp || []).map((p) => ({ cle: "p|" + p.id, id: p.id, titre: p.nom, d1: p.debut, d2: p.fin, lien: lie(p.id), venu: false }));
        const venus = (S.d.projets || []).filter((p) => String(p.statut) === "1" && !liesDoli.has(String(p.id))).slice(0, 8).map((p) => ({ cle: "v|" + p.id, id: p.id, titre: p.title, d1: p.date_start, d2: p.date_end, ref: p.ref, venu: true }));
        const L = mien.concat(venus).filter((o) => (f === "tous" || (f === "cass" && !o.lien && !o.venu) || (f === "lie" && o.lien) || (f === "venu" && o.venu)) && (!S.q.cprojets || o.titre.toLowerCase().includes(S.q.cprojets.toLowerCase())));
        return '<div class="carte">' + barre("cprojets", "") + seg("cprojets", [["tous", "Tous"], ["cass", "Cassandra seulement"], ["lie", "Dolibarr · lié"], ["venu", "Venu de Dolibarr"]]) +
          table(["Projet", "Dates", "Étiquette", ""], L.map((o) => '<tr class="clk" data-a="fichec" data-p="' + o.cle + '"><td><b>' + esc(o.titre) + '</b><div class="note">' + esc(o.venu ? o.ref : o.lien ? o.lien.ref : "") + "</div></td><td>" + (o.d1 ? jour(o.d1) : "—") + (o.d2 && o.d2 !== o.d1 ? " → " + jour(o.d2) : "") + "</td><td>" + etiq(o) + "</td><td>" + (!o.venu && !o.lien ? btn("Envoyer à Dolibarr", "envoyerp", o.id) : "") + "</td></tr>")) + '<div class="note">Un projet reste chez Cassandra tant que tu ne l’envoies pas. Envoyé, Dolibarr fait foi pour son titre, ses dates et sa description.</div></div>';
      },
      ccontacts() {
        const lie = (id) => (S.d.liens || []).find((l) => l.type === "contact" && String(l.id) === String(id)), f = S.f.ccontacts || "tous";
        const L = (S.d.cc || []).map((c) => ({ id: c.id, nom: c.display_name, orga: c.company, lien: lie(c.id) })).filter((o) => (f === "tous" || (f === "cass" && !o.lien) || (f === "lie" && o.lien)) && (!S.q.ccontacts || (o.nom + " " + o.orga).toLowerCase().includes(S.q.ccontacts.toLowerCase())));
        return '<div class="carte">' + barre("ccontacts", "") + seg("ccontacts", [["tous", "Tous"], ["cass", "Cassandra seulement"], ["lie", "Dolibarr · lié"]]) +
          table(["Contact", "Organisation", "Étiquette", ""], L.map((o) => '<tr class="clk" data-a="fichec" data-p="c|' + o.id + '"><td><b>' + esc(o.nom) + "</b></td><td>" + esc(o.orga || "—") + "</td><td>" + etiq(o) + (o.lien ? '<div class="note">rattaché au tiers ' + esc(nomTiers(o.lien.tiers)) + "</div>" : "") + "</td><td>" + (o.lien ? "" : btn("Envoyer à Dolibarr", "envoyerc", o.id)) + "</td></tr>")) + '<div class="note">Un contact Dolibarr est toujours rattaché à un tiers que tu choisis : il ne devient jamais un tiers tout seul.</div></div>';
      },
      acces() {
        const a = S.acces || {}, o = { compte: "ta clé propre", mandat: "la clé de mandat", fichier: "le fichier de clé" }[a.cle] || "";
        return '<div class="g2"><div class="carte"><h3>Ma clé d’API Dolibarr</h3><div class="note">Mon Itare et moi agissons dans Dolibarr sous le nom de son utilisateur, avec ses droits. La clé est chiffrée, jamais réaffichée ; personne d’autre ne la lit.</div>' +
          (a.erreur ? "<div class=\"alerte dg\">" + esc(a.erreur) + "</div>" : a.cle ? "<div>" + pill("Clé utilisée : " + o, a.cle === "compte" ? "ok" : "al") + " " + pill(a.peut_ecrire ? "peut écrire" : "lecture seule", a.peut_ecrire ? "ok" : "al") + "</div><div class=\"note\">Dolibarr te voit comme « " + esc(a.utilisateur) + " »" + (a.administrateur ? " (administrateur : tous les droits)" : "") + ", dans la société « " + esc(a.societe) + " ».</div>" : "") +
          '<label class="fld">Coller ma clé<input type="password" class="in" id="dlb-cle" autocomplete="off" placeholder="clé d’API"></label><div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Enregistrer dans mon coffre", "savecle", "", "pri") + btn("Retirer ma clé", "rmcle") + btn("Tester", "tester") + "</div></div>" +
          '<div class="carte"><h3>Ce que mon Itare peut faire seul</h3><div class="note">Chaque geste a un palier, réglé par l’administrateur : « raconter » (il prépare, tu approuves) ou « auto ». Aucun geste n’est interdit par le code.</div><div>' + btn("Régler les paliers", "paliers") + "</div></div></div>";
      },
      libre() {
        return '<div class="carte"><h3>Requête libre</h3><div class="note">Tout le catalogue de Dolibarr : par exemple <span class="mono">GET /thirdparties/12</span> ou <span class="mono">PUT /products/3 {"price": 12}</span>. Les secrets sont masqués ; une suppression passe par la corbeille du module.</div><div class="barre2"><input class="in mono" id="dlb-req" style="flex:1 1 320px" value="' + esc(S.libre || "GET /thirdparties?limit=5") + '"><button class="btn pri" data-a="libre">Lancer</button></div>' + (S.libreRep ? '<pre class="code">' + esc(typeof S.libreRep === "string" ? S.libreRep : JSON.stringify(S.libreRep, null, 1)) + "</pre>" : "") + "</div>";
      },
    };
    const ONGLETS = [["afaire", "À faire"], ["factures", "Factures"], ["devis", "Devis"], ["tiers", "Tiers"], ["banque", "Banque"], ["dons", "Dons"], ["adherents", "Adhérents"], ["projets", "Projets"], ["cprojets", "Projets de Cassandra"], ["ccontacts", "Contacts de Cassandra"], ["acces", "Mon accès"], ["libre", "Requête libre"]];
    function dessiner() {
      const foc = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.q : null, pos = foc ? document.activeElement.selectionStart : 0;
      racine.innerHTML = K.titre("Dolibarr", "Gestion complète : facturer, encaisser, relancer, donner un reçu, cotiser. Chaque geste est relu, journalisé et défaisable.") + '<div class="onglets">' + ONGLETS.map((o) => '<button data-o="' + o[0] + '" class="' + (S.onglet === o[0] ? "on" : "") + '">' + o[1] + "</button>").join("") + "</div>" +
        (S.err ? '<div class="alerte dg"><div class="sp">' + esc(S.err) + "</div></div>" : "") + VUES[S.onglet]();
      if (foc) { const n = racine.querySelector('[data-q="' + foc + '"]'); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }
    }

    // ───────── les gestes : une confirmation, puis la capacité
    const fait = async (cap, args, dit, recharge) => { try { await agir(cap, args); K.dire(dit); } catch (e) { K.dire(e.message || String(e), "err"); } if (recharge !== false) { S.d = {}; await charger(true); } };
    // Comme K.confirmer, mais rend aussi ce qui a été saisi : la fenêtre se retire avant que la promesse ne reprenne, on relève donc les champs au clic.
    const modale = (titre, corps, oui) => new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre);
      m.innerHTML = "<h2>" + esc(titre) + "</h2>" + corps + '<div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn pri" data-c="oui">' + esc(oui || "Envoyer à Dolibarr") + "</button></div>";
      const clore = (r) => { if (r) { S.v = {}; m.querySelectorAll("[id]").forEach((e) => { S.v[e.id] = e.type === "checkbox" ? e.checked : e.value; }); } v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(false)); m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) clore(b.dataset.c === "oui"); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(false); });
      document.body.appendChild(v); document.body.appendChild(m); const f = m.querySelector("input,textarea,select,[data-c=non]"); if (f) f.focus();
    });
    const champ = (id, lib, v, t, x) => '<label class="fld">' + lib + '<input class="in" id="' + id + '" type="' + (t || "text") + '" value="' + esc(v == null ? "" : v) + '" ' + (x || "") + "></label>";
    const sel = (id, lib, opts, v) => '<label class="fld">' + lib + '<select class="in" id="' + id + '">' + opts.map((o) => '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(v) ? " selected" : "") + ">" + esc(o[1]) + "</option>").join("") + "</select></label>";
    const val = (id) => { if (S.v && id in S.v) return S.v[id]; const e = document.getElementById(id); return e ? e.value : ""; };
    const banqueOpts = () => (S.d.banques || []).filter((b) => String(b.clos) !== "1").map((b) => [b.id, b.label]);
    const tiersOpts = () => (S.d.tiers || []).map((t) => [t.id, t.name]);
    const GESTES = {
      onglet: async (p) => { S.onglet = p; dessiner(); await charger(); },
      valider: async (p) => { if (await modale("Valider la facture", '<p>Elle prend son numéro légal. Cela se défait tant qu’elle n’est ni payée ni comptabilisée.</p>', "Valider")) await fait("dolibarr.valider_facture", { id: Number(p) }, "Facture validée"); },
      fiche: async (p) => {
        const f = (S.d.factures || []).find((x) => String(x.id) === String(p)); if (!f) return;
        const corpsF = '<div class="note">' + esc(nomTiers(f.socid)) + " · " + jour(f.date) + " · " + eur(f.total_ttc) + (ouverte(f) ? " · reste " + eur(f.remaintopay) : "") + "</div><div>" + etatF(f) + "</div><div style=\"display:flex;gap:6px;flex-wrap:wrap\">" +
          (String(f.statut) === "0" ? btn("Valider", "valider", f.id, "pri") : "") + (ouverte(f) ? btn("Encaisser", "encaisser", f.id, "pri") + btn("Relancer", "relancer", f.id) : "") + (String(f.statut) !== "0" ? btn("Créer un avoir", "avoir", f.id) : "") + (String(f.statut) !== "0" ? btn("Voir le PDF", "pdf", "factures|" + f.id) : "") + "</div>";
        modale("Facture " + f.ref, corpsF, "Fermer");
      },
      encaisser: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const f = (S.d.factures || []).find((x) => String(x.id) === String(p));
        const ok = await modale("Encaisser · " + f.ref, '<p class="note">Reste dû : ' + eur(f.remaintopay) + '</p><div class="grille2">' + champ("e-mt", "Montant", f.remaintopay, "number", 'step="0.01"') + sel("e-bk", "Compte", banqueOpts(), "") + sel("e-md", "Mode", [["VIR", "Virement"], ["CHQ", "Chèque"], ["LIQ", "Espèces"], ["CB", "Carte"]], "VIR") + champ("e-dt", "Date", AUJ, "date") + "</div>", "Encaisser");
        if (ok) await fait("dolibarr.encaisser", { id: Number(p), montant: val("e-mt"), banque: Number(val("e-bk")), mode: val("e-md"), date: val("e-dt") }, "Règlement enregistré");
      },
      relancer: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const f = (S.d.factures || []).find((x) => String(x.id) === String(p));
        const msg = "Bonjour,\n\nSauf erreur de notre part, la facture " + f.ref + " du " + jour(f.date) + ", d’un reste dû de " + eur(f.remaintopay) + ", est échue depuis " + retard(f) + " jours.\n\nPourriez-vous nous indiquer la date de règlement prévue ?\n\nBien cordialement,\nLa Maison Bohème";
        if (await modale("Relance · " + f.ref, '<p class="note">La relance est gardée dans l’agenda du tiers. Le courriel part par le module Mandats, qui seul résout l’adresse.</p><label class="fld">Message<textarea class="in" id="r-msg" rows="8">' + esc(msg) + "</textarea></label>", "Garder la relance")) await fait("dolibarr.relancer", { id: Number(p), message: val("r-msg") }, "Relance gardée");
      },
      avoir: async (p) => { document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove()); if (await modale("Créer un avoir", "<p>Un avoir en BROUILLON, relié à la facture, mêmes lignes en négatif. Rien n’est validé.</p>", "Créer le brouillon")) await fait("dolibarr.creer_avoir", { id: Number(p) }, "Avoir préparé"); },
      nfacture: async () => {
        const ok = await modale("Nouvelle facture (brouillon)", '<div class="grille2">' + sel("n-t", "Tiers", tiersOpts(), "") + champ("n-q", "Quantité", "1", "number") + "</div>" + champ("n-d", "Désignation", "") + champ("n-p", "Prix unitaire HT", "0", "number", 'step="0.01"'), "Créer le brouillon");
        if (ok) await fait("dolibarr.creer_brouillon", { objet: "factures", socid: Number(val("n-t")), lignes: [{ desc: val("n-d") || "Prestation", qty: Number(val("n-q")) || 1, subprice: Number(val("n-p")) || 0, tva_tx: 0 }] }, "Brouillon créé");
      },
      ndevis: async () => {
        const ok = await modale("Nouveau devis (brouillon)", '<div class="grille2">' + sel("n-t", "Tiers", tiersOpts(), "") + champ("n-p", "Montant HT", "0", "number", 'step="0.01"') + "</div>" + champ("n-d", "Désignation", ""), "Créer le brouillon");
        if (ok) await fait("dolibarr.creer_brouillon", { objet: "devis", socid: Number(val("n-t")), lignes: [{ desc: val("n-d") || "Prestation", qty: 1, subprice: Number(val("n-p")) || 0, tva_tx: 0 }] }, "Devis créé");
      },
      devis: async (p) => { const [id, action] = p.split("|"); if (await modale("Devis : " + action, "<p>Le statut du devis change ; cela se défait (retour en brouillon).</p>", "Faire")) await fait("dolibarr.devis", { id: Number(id), action: action }, "Devis mis à jour"); },
      facturer: async (p) => { if (await modale("Facturer le devis", "<p>Une facture en brouillon est préparée avec les lignes du devis. Rien n’est validé.</p>", "Préparer la facture")) await fait("dolibarr.facturer_devis", { id: Number(p) }, "Facture préparée"); },
      ntiers: async () => {
        const ok = await modale("Nouveau tiers", champ("n-n", "Nom", "") + '<div class="grille2">' + champ("n-v", "Ville", "") + sel("n-ty", "Type", [["cli", "Client"], ["fou", "Fournisseur"], ["les2", "Les deux"]], "cli") + "</div>", "Créer");
        if (ok && val("n-n")) { const t = val("n-ty"); await fait("dolibarr.creer", { objet: "tiers", champs: { name: val("n-n"), town: val("n-v"), client: t !== "fou" ? 1 : 0, fournisseur: t !== "cli" ? 1 : 0 } }, "Tiers créé"); }
      },
      fichedevis: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const d = (S.d.devis || []).find((x) => String(x.id) === String(p)); if (!d) return;
        let full = {}; try { full = (await agir("dolibarr.lire_libre", { chemin: "/proposals/" + p })).reponse || {}; } catch (e) { K.dire(e.message || String(e), "err"); }
        const L = ["Brouillon", "Ouvert", "Signé", "Refusé", "Facturé"], s = String(d.statut), nb = (n) => Number(n || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const lignes = (full.lines || []).map((l) => "<tr><td>" + esc(String(l.desc || l.description || l.product_label || "").replace(/<br\s*\/?>/gi, " ").replace(/\s+/g, " ").trim()) + '</td><td class="num">' + nb(l.qty) + '</td><td class="num">' + nb(l.subprice) + '</td><td class="num">' + nb(l.tva_tx) + ' %</td><td class="num">' + nb(l.total_ttc) + " €</td></tr>");
        const gestes = s === "0" ? btn("Valider", "devis", d.id + "|valider", "pri") : s === "1" ? btn("Marquer signé", "devis", d.id + "|signer", "pri") + btn("Refusé", "devis", d.id + "|refuser") : s === "2" ? btn("Facturer", "facturer", d.id, "pri") : "";
        await modale("Propale " + d.ref, '<div class="note">' + esc(nomTiers(d.socid)) + " · " + jour(d.date) + (full.fin_validite ? " · valable jusqu’au " + jour(full.fin_validite) : "") + "</div><div>" + pill(L[Number(s)] || "Annulé", s === "2" ? "ok" : "") + "</div>" +
          table(["Désignation", "Qté", "PU HT", "TVA", "Total"], lignes) + '<p class="num" style="text-align:right">Total HT ' + nb(full.total_ht || d.total_ttc) + " € · TVA " + nb(full.total_tva) + " € · <b>Total TTC " + nb(d.total_ttc) + " €</b></p>" +
          '<div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Voir le PDF", "pdf", "devis|" + d.id, "pri") + gestes + "</div>", "Fermer");
      },
      fichec: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [k, id] = p.split("|");
        if (k === "v") { const d = (S.d.projets || []).find((x) => String(x.id) === String(id)); return void modale(d.title, '<div>' + pill("Venu de Dolibarr", "ac") + ' <span class="mono">' + esc(d.ref) + '</span></div><p class="note">Ce projet est né dans Dolibarr : Cassandra le montre, il se modifie chez Dolibarr.</p>', "Fermer"); }
        const type = k === "p" ? "projet" : "contact", o = (k === "p" ? S.d.cp : S.d.cc || []).find((x) => String(x.id) === String(id)); if (!o) return;
        const lien = (S.d.liens || []).find((l) => l.type === type && String(l.id) === String(id)), nom = k === "p" ? o.nom : o.display_name;
        const corps = lien
          ? "<div>" + etiq({ lien: lien }) + ' <span class="mono">' + esc(lien.ref) + '</span></div><div class="alerte"><div class="sp"><b>Dolibarr fait foi</b> pour ' + (k === "p" ? "le titre, les dates et la description" : "le nom, le courriel, le téléphone et le tiers") + ". Modifier ici envoie la modification à Dolibarr. Restent dans Cassandra : " + (k === "p" ? "les notes, l’équipe, les jalons et les tâches." : "les notes.") + '</div></div><div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Modifier (part vers Dolibarr)", "modifl", type + "|" + id, "pri") + btn("Détacher", "detacher", type + "|" + id) + '</div><div class="note">« Détacher » rompt le lien et garde les deux copies : rien n’est supprimé, ni chez Dolibarr ni chez Cassandra.</div>'
          : "<div>" + etiq({}) + '</div><p class="note">Cette fiche n’existe que dans Cassandra. Rien ne part vers Dolibarr sans ton clic.</p><div>' + btn("Envoyer à Dolibarr…", k === "p" ? "envoyerp" : "envoyerc", id, "pri") + "</div>";
        await modale(nom, corps, "Fermer");
      },
      envoyerp: async (id) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const o = (S.d.cp || []).find((x) => String(x.id) === String(id));
        const ok = await modale("Envoyer le projet à Dolibarr", '<p class="note">Il y sera créé avec son titre « ' + esc(o.nom) + " », ses dates et sa description. Ses notes, son équipe, ses jalons et ses tâches restent dans Cassandra.</p>" + sel("e-t", "Tiers de rattachement (facultatif)", [["", "Aucun"]].concat(tiersOpts()), "") + '<label class="fld"><span><input type="checkbox" id="e-v"> Le valider tout de suite (il prend sa référence)</span></label>', "Envoyer");
        if (ok) await fait("dolibarr.envoyer_projet", { id: Number(id), tiers: val("e-t") === "" ? "" : Number(val("e-t")), valider: val("e-v") === true }, "Projet envoyé");
      },
      envoyerc: async (id) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const o = (S.d.cc || []).find((x) => String(x.id) === String(id));
        const ok = await modale("Envoyer le contact à Dolibarr", '<p class="note">Un contact Dolibarr est toujours rattaché à un tiers. Choisis-le, ou nomme celui à créer : le contact ne devient jamais un tiers.</p>' + sel("e-t", "Rattacher à un tiers existant", [["", "— en créer un —"]].concat(tiersOpts()), "") + champ("e-nt", "… ou créer ce tiers", o.company || ""), "Envoyer");
        if (ok) await fait("dolibarr.envoyer_contact", { id: Number(id), tiers: val("e-t") === "" ? "" : Number(val("e-t")), nouveau_tiers: val("e-t") === "" ? val("e-nt") : "" }, "Contact envoyé");
      },
      modifl: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [type, id] = p.split("|");
        const ok = await modale("Modifier chez Dolibarr", type === "projet" ? champ("m-a", "Titre", "") + champ("m-b", "Description", "") : champ("m-a", "Courriel", "") + champ("m-b", "Téléphone", ""), "Envoyer");
        if (!ok) return;
        const champs = type === "projet" ? { title: val("m-a"), description: val("m-b") } : { email: val("m-a"), phone_pro: val("m-b") };
        Object.keys(champs).forEach((k) => { if (champs[k] === "") delete champs[k]; });
        if (!Object.keys(champs).length) return K.dire("Rien à modifier", "err");
        await fait("dolibarr.modifier_lie", { type: type, id: Number(id), champs: champs }, "Modification envoyée à Dolibarr");
      },
      detacher: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [type, id] = p.split("|");
        if (await modale("Détacher de Dolibarr", "<p>Le lien est rompu, les deux copies restent. L’étiquette redevient « Cassandra seulement ».</p>", "Détacher")) await fait("dolibarr.detacher", { type: type, id: Number(id) }, "Fiche détachée");
      },
      pdf: async (p) => {
        const [objet, id] = p.split("|"); document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        let r; try { r = await agir("dolibarr.piece_pdf", { objet: objet, id: Number(id) }); }
        catch (e) {
          if (/pas de PDF/.test(e.message || "")) { if (await modale("Pas encore de PDF", "<p>Dolibarr n’a pas encore produit le PDF de cette pièce. Il peut le faire maintenant ; le geste se défait.</p>", "Produire le PDF")) { await fait("dolibarr.produire_pdf", { objet: objet, id: Number(id) }, "PDF produit", false); return GESTES.pdf(p); } return; }
          return K.dire(e.message || String(e), "err");
        }
        const oct = Uint8Array.from(atob(r.donnees_b64), (c) => c.charCodeAt(0)), url = URL.createObjectURL(new Blob([oct], { type: "application/pdf" }));
        // pas d'attribut sandbox : le lecteur PDF du navigateur a besoin de scripter son document (même choix que le visionneur de la GED)
        const fin = modale("PDF · " + r.nom, '<iframe id="dlb-pdf" title="' + esc(r.nom) + '" style="width:100%;height:70vh;border:0;border-radius:8px;background:#fff"></iframe><div class="note">' + esc(r.ref) + " · " + Math.round(r.taille / 1024) + " Ko · produit par Dolibarr</div>", "Fermer");
        const cadre = document.getElementById("dlb-pdf"); if (cadre) cadre.src = url; fin.then(() => URL.revokeObjectURL(url));
      },
      tiers: async (p) => { const t = (S.d.tiers || []).find((x) => String(x.id) === String(p)); const f = (S.d.factures || []).filter((x) => String(x.socid) === String(p)); modale(t.name, '<div class="note">' + f.length + " factures · dû " + eur(f.filter(ouverte).reduce((s, x) => s + Number(x.remaintopay), 0)) + "</div>" + f.slice(0, 8).map((x) => '<div class="li"><div class="sp mono">' + esc(x.ref) + '</div><div class="note">' + eur(x.total_ttc) + "</div>" + etatF(x) + "</div>").join(""), "Fermer"); },
      virement: async () => {
        const o = banqueOpts(); if (o.length < 2) return K.dire("Il faut deux comptes ouverts", "err");
        if (await modale("Virement entre comptes", '<div class="grille2">' + sel("v-de", "De", o, o[0][0]) + sel("v-vers", "Vers", o, o[1][0]) + champ("v-mt", "Montant", "100", "number", 'step="0.01"') + champ("v-dt", "Date", AUJ, "date") + "</div>" + champ("v-l", "Libellé", "Virement interne"), "Virer")) await fait("dolibarr.virement_interne", { de: Number(val("v-de")), vers: Number(val("v-vers")), montant: val("v-mt"), date: val("v-dt"), libelle: val("v-l") }, "Virement fait");
      },
      ndon: async () => { if (await modale("Nouveau don", champ("n-mt", "Montant", "50", "number", 'step="0.01"') + '<div class="grille2">' + champ("n-nom", "Nom", "") + champ("n-dt", "Date", AUJ, "date") + "</div>", "Saisir la promesse")) await fait("dolibarr.don_creer", { montant: val("n-mt"), nom: val("n-nom"), date: val("n-dt") }, "Promesse saisie"); },
      donvalider: async (p) => { if (await modale("Valider le don", "<p>Le don prend son numéro. Dolibarr ne le repasse pas en promesse par l’API.</p>", "Valider")) await fait("dolibarr.don_valider", { id: Number(p) }, "Don validé"); },
      donrecu: async (p) => { if (await modale("Reçu fiscal", "<p>Le PDF du reçu est produit par Dolibarr (modèle de l’association).</p>", "Éditer le reçu")) await fait("dolibarr.don_recu", { id: Number(p) }, "Reçu produit"); },
      cotis: async (p) => { if (await modale("Cotisation", '<div class="grille2">' + champ("c-mt", "Montant", "15", "number") + champ("c-d", "Du", AUJ, "date") + "</div>" + champ("c-f", "Au", String(new Date().getFullYear() + 1) + AUJ.slice(4), "date"), "Enregistrer")) await fait("dolibarr.cotisation", { membre: Number(p), montant: val("c-mt"), debut: val("c-d"), fin: val("c-f") }, "Cotisation enregistrée"); },
      nprojet: async () => { if (await modale("Nouveau projet", champ("n-t", "Titre", ""), "Créer")) await fait("dolibarr.creer", { objet: "projets", champs: { title: val("n-t") || "Nouveau projet" } }, "Projet créé"); },
      projet: async (p) => { const [id, action] = p.split("|"); if (await modale("Projet : " + action, "<p>Le statut du projet change ; cela se défait.</p>", "Faire")) await fait("dolibarr.projet", { id: Number(id), action: action }, "Projet mis à jour"); },
      savecle: async () => { const v = val("dlb-cle").trim(); if (!v) return K.dire("Colle d’abord ta clé", "err"); try { await agir("reglages.regler_secret", { cle: "dolibarr.cle_api", valeur: v }); K.dire("Clé enregistrée dans ton coffre"); S.acces = null; await charger(); } catch (e) { K.dire(e.message || String(e), "err"); } },
      rmcle: async () => { if (await modale("Retirer ma clé", "<p>Ni toi ni ton Itare n’écrirez plus dans Dolibarr sous ton nom.</p>", "Retirer")) { try { await agir("reglages.reinitialiser", { cle: "dolibarr.cle_api" }); K.dire("Clé retirée"); S.acces = null; await charger(); } catch (e) { K.dire(e.message || String(e), "err"); } } },
      tester: async () => { S.acces = null; await charger(); },
      paliers: () => { if (CASS.console) CASS.console("dolibarr", corps); },
      libre: async () => {
        S.libre = val("dlb-req").trim(); const m = S.libre.match(/^(GET|POST|PUT)\s+(\/[^\s?]*)(\?\S*)?\s*(\{[\s\S]*\})?$/i); if (!m) return K.dire("Format : GET /chemin  ou  PUT /chemin {json}", "err");
        try {
          if (m[1].toUpperCase() === "GET") S.libreRep = (await agir("dolibarr.lire_libre", { chemin: m[2], parametres: (m[3] || "").slice(1) })).reponse;
          else if (await modale(m[1].toUpperCase() + " " + m[2], '<div class="code">' + esc(m[4] || "{}") + "</div><p class=\"note\">Relu après l’écriture ; défaisable quand l’acte le permet.</p>")) S.libreRep = await agir("dolibarr.ecrire_libre", { methode: m[1].toUpperCase(), chemin: m[2], corps: m[4] ? JSON.parse(m[4]) : {} });
        } catch (e) { S.libreRep = "Erreur : " + (e.message || String(e)); }
        dessiner();
      },
    };
    // le tiroir de fiche (K.confirmer) ne porte pas nos boutons : on délègue sur tout le document pour ses data-a
    const clic = (e) => { const b = e.target.closest("[data-a]"); if (!b || !GESTES[b.dataset.a]) return; if (!racine.isConnected) { document.removeEventListener("click", clic); return; } e.preventDefault(); GESTES[b.dataset.a](b.dataset.p); };
    document.addEventListener("click", clic);
    racine.addEventListener("click", (e) => { const o = e.target.closest("[data-o]"); if (o) { GESTES.onglet(o.dataset.o); return; } const f = e.target.closest("[data-f]"); if (f) { const [k, v] = f.dataset.f.split("|"); S.f[k] = v; dessiner(); } });
    racine.addEventListener("input", (e) => { const k = e.target.dataset && e.target.dataset.q; if (k) { S.q[k] = e.target.value; dessiner(); } });
    racine.innerHTML = '<div class="vide">Lecture de Dolibarr…</div>';
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l'écran et ses gestes.
// EC : néant.
// LIEN : modules/dolibarr (le module et ses capacités), interface/CN_kit.js (les composants), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
