// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : ▼▼▼ BORNE CN version=0
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #698197
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=698197 ▼▼▼
// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Sites » du module sites : les sites de la portée du compte (état, certificat, disponibilité, ce qui demande un geste), la fiche d'un site, la disponibilité, les demandes d'adossement et le journal.
// Les données viennent des capacités du module (sites.vue, fiche, historique, disponibilite, journal, demandes, declarer, retirer, attribuer, transferer, demander, repondre_demande, accorder, lier, delier).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, pill = K.pill, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const SCENES = [["sites", "Mes sites"], ["dispo", "Disponibilité"], ["demandes", "Demandes"], ["journal", "Journal"]];
  const NIV = { panne: ["panne", "dg", "warn"], regarder: ["à regarder", "al", "warn"], info: ["à savoir", "", ""] };
  const LIENS = [["project", "Projet"], ["contact", "Contact"], ["machine", "Machine"], ["note", "Note"]];
  const ts = (t) => (typeof t === "number" ? new Date(t * 1000).toISOString().slice(0, 19).replace("T", " ") : String(t || "").replace("T", " ").slice(0, 19));
  const court = (t) => ts(t).slice(0, 16);

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.sites = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("sites", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "sites", vue: null, fiche: null, heures: 24, jours: 30, dispo: null, demandes: null, journal: null, charge: true, erreur: "" };

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { await agir(cap, args); if (ok) dire(ok, "ok"); return true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const val = (id) => ((racine.querySelector(id) || {}).value || "").trim();
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] && !S.fiche ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0] && !S.fiche) + '">' + esc(s[1]) + (s[0] === "demandes" && S.vue && S.vue.vigilances.some((v) => v.geste === "repondre_demande") ? " ●" : "") + "</button>").join("") + "</div>";
    const admin = () => !!(S.vue && S.vue.portee && S.vue.portee.admin);

    function etatSite(x) {
      if (x.up === null) return pill("pas encore mesuré", "", "");
      return x.up ? pill("en ligne" + (x.ms != null ? " · " + x.ms + " ms" : ""), "", "check") : pill("hors ligne", "dg", "warn");
    }
    function ssl(x) {
      if (typeof x.ssl_jours !== "number") return "";
      return pill("certificat " + x.ssl_jours + " j", x.ssl_jours < 7 ? "dg" : x.ssl_jours < 21 ? "al" : "", x.ssl_jours < 21 ? "warn" : "");
    }
    function ligneSite(x) {
      return '<div class="li"><div class="sp"><b><a href="#" data-a="fiche" data-k="' + esc(x.domaine) + '">' + esc(x.domaine) + "</a> " + etatSite(x) + " " + ssl(x) + (x.source !== "panneau" ? " " + pill("hors panneau", "", "") : "") + (x.demande ? " " + pill("demande en cours", "al", "") : "") + "</b>" +
        '<span class="note">' + esc([x.dispo30 ? "disponibilité 30 j : " + x.dispo30.disponibilite + " %" : "", x.php ? "PHP " + x.php : "", admin() && x.comptes && x.comptes.length ? "à " + x.comptes.join(", ") : ""].filter(Boolean).join(" · ")) + "</span></div></div>";
    }
    function sites() {
      const v = S.vue, p = v.portee;
      const decl = '<div class="carte"><h3>Déclarer un site</h3><div class="barre"><input id="st-dom" placeholder="exemple.fr" aria-label="Domaine"><button class="btn pri" data-a="declarer">Déclarer</button></div><p class="note">Un site qu’on possède hors du panneau : la sonde le suivra.</p></div>';
      const vig = v.vigilances.length ? '<div class="carte"><h3>Ce qui demande un regard</h3><div class="liste">' + v.vigilances.map((g) => { const n = NIV[g.niveau] || NIV.info; return '<div class="li"><div class="sp"><b>' + esc(g.titre) + '</b><span class="note">' + esc(g.detail || "") + "</span>" + (g.geste === "demander" ? '<div class="chips"><button class="p" data-a="demander" data-k="' + esc(g.site) + '">Demander l’adossement</button></div>' : g.geste === "attribuer" ? '<div class="chips"><button class="p" data-a="fiche" data-k="' + esc(g.site) + '">Attribuer…</button></div>' : g.geste === "repondre_demande" ? '<div class="chips"><button class="p" data-s="demandes">Répondre</button></div>' : "") + "</div>" + pill(n[0], n[1], n[2]) + "</div>"; }).join("") + "</div></div>" : "";
      const tuiles = '<div class="grille-m">' + [["Sites", p.sites], ["Au panneau", p.panneau], ["Déclarés", p.declares]].map((x) => '<div class="carte"><span class="note">' + esc(x[0]) + '</span><div style="font-size:22px;font-weight:600">' + esc(x[1]) + "</div></div>").join("") + "</div>";
      return (p.panneau_lu ? "" : '<div class="carte"><p class="note">Le panneau d’hébergement ne répond pas : seuls les sites déclarés et les dernières mesures sont montrés.</p></div>') + vig + tuiles + '<div class="carte"><h3>Les sites</h3><div class="liste">' + (v.sites.length ? v.sites.map(ligneSite).join("") : '<div class="vide"><b>Aucun site pour l’instant.</b> Déclare-en un ci-dessous.</div>') + "</div></div>" + decl;
    }
    function dispo() {
      const d = S.dispo || { sites: [] };
      const barreJ = '<div class="chips">' + [7, 30, 90].map((j) => '<button class="p ' + (S.jours === j ? "on" : "") + '" data-a="jours" data-j="' + j + '">' + j + " j</button>").join("") + "</div>";
      const lignes = (d.sites || []).map((m) => '<div class="li"><div class="sp"><b>' + esc(m.domaine) + '</b><div class="jauge ' + (m.disponibilite < 95 ? "dg" : m.disponibilite < 99 ? "al" : "") + '"><i style="width:' + Math.max(0, Math.min(100, m.disponibilite)) + '%"></i></div><span class="note">' + esc((m.pannes || 0) + " panne(s)" + (m.indisponible ? " · " + m.indisponible + " d’indisponibilité" : "") + (m.reponse_moy_ms != null ? " · réponse moyenne " + m.reponse_moy_ms + " ms" : "")) + "</span></div><b>" + esc(m.disponibilite) + " %</b></div>").join("");
      return '<div class="carte"><h3>Disponibilité sur ' + S.jours + " jours</h3>" + barreJ + (lignes ? '<div class="liste">' + lignes + "</div>" : '<div class="vide">' + esc(d.raison || "Aucune mesure.") + "</div>") + "</div>";
    }
    function demandes() {
      const d = S.demandes || [];
      return '<div class="carte"><h3>Demandes d’adossement</h3><p class="note">Un site déclaré à la main peut demander à passer au panneau d’hébergement.</p><div class="liste">' + (d.length ? d.map((r) => '<div class="li"><div class="sp"><b>' + esc(r.domaine) + " " + pill(r.statut, r.statut === "ouverte" ? "al" : "", "") + '</b><span class="note">' + esc(r.compte + (r.message ? " — " + r.message : "") + (r.reponse ? " · réponse : " + r.reponse : "")) + "</span>" +
        (admin() && r.statut === "ouverte" ? '<div class="chips"><button class="p" data-a="repondre" data-id="' + r.id + '" data-d="fait">C’est fait</button><button class="p dg" data-a="repondre" data-id="' + r.id + '" data-d="refusee">Refuser</button></div>' : "") + '</div><span class="faint mono" style="font-size:11.5px">' + esc(court(r.ts)) + "</span></div>").join("") : '<div class="vide">Aucune demande.</div>') + "</div></div>";
    }
    function journal() {
      const j = S.journal || [];
      return '<div class="carte"><h3>Ce qui s’est passé sur les sites</h3><div class="liste">' + (j.length ? j.map((x) => '<div class="li"><div class="sp"><b>' + esc(x.verbe) + " " + pill(x.source === "veille" ? "sonde" : x.acteur || "geste", "", "") + '</b><span class="note">' + esc((x.domaine || "") + (x.detail ? " — " + x.detail : "")) + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(x.ts)) + "</span></div>").join("") : '<div class="vide">Rien pour l’instant.</div>') + "</div></div>";
    }
    function fiche() {
      const F = S.fiche, f = F.f;
      if (!f) return '<div class="carte vide">Lecture…</div>';
      const x = f.site, h = F.h || {}, g = f.gestes || {};
      const pts = (h.points || []).map((p) => ({ ts: ts(p.ts), v: p.up ? p.ms : null, d: p.up ? 100 : 0 }));
      const raccourcis = '<div class="chips">' + [[24, "24 h"], [168, "7 j"], [720, "30 j"]].map((r) => '<button class="p ' + (S.heures === r[0] ? "on" : "") + '" data-a="heures" data-h="' + r[0] + '">' + r[1] + "</button>").join("") + "</div>";
      const liens = (f.liens || []).map((l) => '<div class="li"><div class="sp"><b>' + esc(l.genre) + '</b><span class="note">' + esc(l.ref) + (l.note ? " — " + esc(l.note) : "") + '</span></div><button class="p" data-a="delier" data-g="' + esc(l.genre) + '" data-r="' + esc(l.ref) + '">Retirer</button></div>').join("");
      const jr = (f.journal || []).map((e) => '<div class="li"><div class="sp"><b>' + esc(e.verbe) + '</b><span class="note">' + esc(e.detail || "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(e.ts)) + "</span></div>").join("");
      const act = [g.demander ? '<button class="btn" data-a="demander" data-k="' + esc(f.domaine) + '">Demander l’adossement au panneau</button>' : "", g.accorder ? '<button class="btn" data-a="accorder">' + (f.accord ? "Renouveler l’accord de restauration" : "Autoriser l’administrateur à restaurer") + "</button>" : "", g.retirer ? '<button class="btn dg" data-a="retirer">Retirer ce site</button>' : ""].join("");
      const adm = g.attribuer ? '<div class="carte"><h3>Attribution</h3><div class="barre"><input id="st-compte" placeholder="compte" aria-label="Compte"><button class="btn pri" data-a="attribuer">Attribuer</button>' + (g.transferer ? '<button class="btn" data-a="transferer">Transférer à ce compte</button>' : "") + "</div></div>" : "";
      return '<div class="carte"><div class="barre"><h3 style="flex:1">' + esc(f.domaine) + " " + etatSite(x) + " " + ssl(x) + '</h3><button class="btn" data-a="retour">← Les sites</button></div>' +
        '<p class="note">' + esc([x.source === "panneau" ? "au panneau" : "déclaré à la main", x.php ? "PHP " + x.php : "", h.disponibilite != null ? "disponibilité " + h.disponibilite + " %" : "", h.reponse_moy_ms != null ? "réponse moyenne " + h.reponse_moy_ms + " ms" : "", f.accord ? "accord de restauration jusqu’au " + court(f.accord.jusqu_a) : ""].filter(Boolean).join(" · ")) + "</p>" + raccourcis +
        K.courbe([{ name: "temps de réponse", points: pts.filter((p) => p.v != null).map((p) => ({ ts: p.ts, v: p.v })) }], { unite: "ms", titre: "Temps de réponse" }) + (act ? '<div class="barre">' + act + "</div>" : "") + "</div>" + adm +
        '<div class="carte"><h3>Liens</h3><div class="liste">' + (liens || '<div class="vide">Aucun lien.</div>') + '</div><div class="barre"><select class="sel" id="st-genre" aria-label="Type">' + LIENS.map((l) => '<option value="' + l[0] + '">' + l[1] + "</option>").join("") + '</select><input id="st-ref" placeholder="référence" aria-label="Référence"><button class="btn pri" data-a="lier">Lier</button></div></div>' +
        '<div class="carte"><h3>Dernières nouvelles</h3><div class="liste">' + (jr || '<div class="vide">Rien pour l’instant.</div>') + "</div></div>";
    }

    function dessiner() {
      let c;
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (!S.vue) c = '<div class="carte"><h3>Les sites ne répondent pas</h3><p class="note">' + esc(S.erreur || "Le module n’a rien rendu.") + "</p></div>";
      else if (S.fiche) c = fiche();
      else c = ({ sites: sites, dispo: dispo, demandes: demandes, journal: journal }[S.scene] || sites)();
      racine.innerHTML = K.titre("Sites", "Les sites que tu suis : s’ils répondent, quand expire leur certificat, ce qui mérite un geste.") + barre() + c;
    }
    async function ouvrirFiche(d) {
      S.fiche = { d: d, f: null, h: null }; dessiner();
      const [f, h] = await Promise.all([lire("sites.fiche", { domaine: d }), lire("sites.historique", { domaine: d, heures: S.heures })]);
      if (!f) { S.fiche = null; dire(S.erreur || "Ce site n’est pas dans ta portée.", "err"); }
      else { S.fiche.f = f; S.fiche.h = h || {}; }
      dessiner();
    }
    async function rafraichir() { S.vue = await lire("sites.vue"); if (S.fiche) await ouvrirFiche(S.fiche.d); else await aller(S.scene); }
    async function aller(scene) {
      S.scene = scene; S.fiche = null; S.erreur = ""; dessiner();
      if (scene === "dispo") S.dispo = await lire("sites.disponibilite", { jours: S.jours });
      else if (scene === "demandes") { const d = await lire("sites.demandes", { statut: "" }); S.demandes = (d && d.demandes) || []; }
      else if (scene === "journal") { const j = await lire("sites.journal", { limite: 100 }); S.journal = (j && j.lignes) || []; }
      else S.vue = await lire("sites.vue");
      dessiner();
    }

    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a; if (a.tagName === "A") e.preventDefault();
      const d = S.fiche && S.fiche.d;
      if (k === "fiche") ouvrirFiche(a.dataset.k);
      else if (k === "retour") { S.fiche = null; dessiner(); }
      else if (k === "jours") { S.jours = +a.dataset.j; S.dispo = await lire("sites.disponibilite", { jours: S.jours }); dessiner(); }
      else if (k === "heures") { S.heures = +a.dataset.h; S.fiche.h = await lire("sites.historique", { domaine: d, heures: S.heures }) || {}; dessiner(); }
      else if (k === "declarer") { const dom = val("#st-dom"); if (!dom) { dire("Il faut un domaine.", "err"); return; } if (await geste("sites.declarer", { domaine: dom }, "Site déclaré : la sonde le suivra.")) rafraichir(); }
      else if (k === "demander") { const dom = a.dataset.k; if (!await confirmer("Demander l’adossement de « " + dom + " » ?", '<p class="note">L’administrateur verra la demande et passera ce site au panneau d’hébergement.</p>', "Demander")) return; if (await geste("sites.demander", { domaine: dom }, "Demande envoyée.")) rafraichir(); }
      else if (k === "repondre") { if (await geste("sites.repondre_demande", { id: +a.dataset.id, decision: a.dataset.d }, "Réponse enregistrée.")) { S.vue = await lire("sites.vue"); aller("demandes"); } }
      else if (k === "retirer") { if (!await confirmer("Retirer « " + d + " » ?", '<p class="note">Il sort de la liste de ce compte ; un site du panneau ne se retire jamais d’ici.</p>', "Retirer", true)) return; if (await geste("sites.retirer", { domaine: d }, "Site retiré.")) { S.fiche = null; S.vue = await lire("sites.vue"); aller("sites"); } }
      else if (k === "attribuer") { const c = val("#st-compte"); if (!c) { dire("Il faut un compte.", "err"); return; } if (await geste("sites.attribuer", { domaine: d, compte: c }, "Site attribué.")) rafraichir(); }
      else if (k === "transferer") { const c = val("#st-compte"); if (!c) { dire("Il faut un compte.", "err"); return; } if (!await confirmer("Transférer « " + d + " » à " + c + " ?", '<p class="note">Il quitte le compte actuel.</p>', "Transférer", true)) return; if (await geste("sites.transferer", { domaine: d, vers: c }, "Site transféré.")) rafraichir(); }
      else if (k === "accorder") { if (!await confirmer("Autoriser la restauration ?", '<p class="note">L’administrateur pourra restaurer ce site pendant 24 heures.</p>', "Autoriser")) return; if (await geste("sites.accorder", { domaine: d, geste: "restaurer", heures: 24 }, "Accord donné pour 24 h.")) ouvrirFiche(d); }
      else if (k === "lier") { const r = val("#st-ref"); if (!r) return; if (await geste("sites.lier", { domaine: d, genre: val("#st-genre") || "project", ref: r }, "Lien posé.")) ouvrirFiche(d); }
      else if (k === "delier") { if (await geste("sites.delier", { domaine: d, genre: a.dataset.g, ref: a.dataset.r }, "Lien retiré.")) ouvrirFiche(d); }
    });
    S.vue = await lire("sites.vue"); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
