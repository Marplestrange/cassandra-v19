// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, c
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #83f507
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, ce qui attend l'utilisateur, le journal, les modèles.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=83f507 ▼▼▼
// L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, ce qui attend l'utilisateur, le journal, les modèles.
// Les données viennent du module agents (equipe, agent, paliers, couts, conversations, conversation, converser, propositions) ; le journal vient du module journal.
// Un propriétaire par donnée : Mémoire, Journaux, Canaux, Voix et Proactivité restent chez eux, la fiche les ouvre (jamais de copie).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, ic = K.ic, pill = K.pill, dire = K.dire, confirmer = K.confirmer;

  // ── la couche d'appels : tout ce que l'écran demande au module passe ici (un contrat qui change se corrige ici seulement) ──
  // une lecture récente n'est pas redemandée au serveur (mono-fil à l'essai, chargé en service) : un seul appel en vol, la même réponse quelques secondes, vidée à la moindre écriture
  const LECT = new Map(), LISIBLES = { equipe: 8, agent: 8, regles: 8, propositions: 8, couts: 8, retenus_refuses: 8, rapport_matin: 8, passations: 8, taches: 8, conversations: 8, auditer: 8, paliers: 8, confiance: 60 };
  const A = (c, a) => {
    if (!LISIBLES[c]) { LECT.clear(); return K.agir("agents." + c, a); }
    const k = c + "|" + JSON.stringify(a || {}), h = LECT.get(k);
    if (h && Date.now() - h.t < LISIBLES[c] * 1000) return h.p;
    const p = K.agir("agents." + c, a); LECT.set(k, { p: p, t: Date.now() }); p.catch(() => LECT.delete(k)); return p;
  };
  const API = {
    equipe: () => A("equipe"),
    agent: (id) => A("agent", { id: id }),
    paliers: (id) => A("paliers", { id: id }),
    couts: (id, jours) => A("couts", { id: id || "", jours: jours || 14 }),
    regler: (id, champs) => A("agent_regler", { id: id, champs: champs }),
    niveau: (agent, niveau) => A("niveau_regler", { agent: agent, niveau: niveau }),
    palier: (agent, outil, palier, confirmerFlag) => A("palier_regler", { agent: agent, outil: outil, palier: palier || "", confirmer: confirmerFlag }),
    plafond: (portee, euros, action, accorder) => A("plafond_regler", { portee: portee, euros: euros, action: action || "secours", accorder: !!accorder }),
    conversations: () => A("conversations"),
    conversation: (id) => A("conversation", { id: id }),
    creer: (agent, titre) => A("conversation_creer", { agent: agent, titre: titre || "" }),
    renommer: (id, titre) => A("conversation_renommer", { id: id, titre: titre }),
    supprimer: (id) => A("conversation_supprimer", { id: id }),
    converser: (cid, message, agent) => A("converser", { conversation_id: cid || 0, message: message, agent: agent }),
    propositions: (etat, agent) => A("propositions", { etat: etat || "a_valider", agent: agent || "", limite: 100 }),
    decider: (id, decision, jusqu) => A("proposition_decider", { id: id, decision: decision, jusqu_a: jusqu || "" }),
    confiance: (agent) => A("confiance", { agent: agent }),
    pourquoi: (acte) => A("pourquoi", { acte: acte, detail: true }),
    epreuvesLancer: (modele) => A("epreuves_lancer", { modele: modele }),
    epreuvesResultats: (modele) => A("epreuves_resultats", { modele: modele || "" }),
    sentinelle: () => A("sentinelle_etat"),
    registre: () => K.agir("modeles.lister", {}),
    regles: () => A("regles"),
    reglesRegler: (a) => A("regles_regler", a),
    passations: () => A("passations", { limite: 30 }),
    taches: () => A("taches"),
    tacheConfier: (a) => A("tache_confier", a),
    tacheRetirer: (id) => A("tache_retirer", { id: id }),
    tacheLancer: (id) => A("tache_lancer", { id: id }),
    retenus: (jours) => A("retenus_refuses", { jours: jours || 1 }),
    rapport: () => A("rapport_matin", {}),
    mauvaisJour: (h) => A("mauvais_jour", { duree_h: h }),
    mauvaisJourLever: () => A("mauvais_jour_lever"),
    defaire: (acte, raison) => A("defaire", { acte: acte, raison: raison || "" }),
    auditer: (jours) => A("auditer", { jours: jours || 7 }),
    journal: (acteur, n) => K.agir("journal.flux", { acteur: acteur || "", limit: n || 60, bruit: false }),
  };
  const RISQUE = { faible: "ok", moyen: "al", eleve: "dg", haut: "dg", fort: "dg" };
  const ETAT = { attend: "en attente", acceptee: "acceptée", refusee: "refusée", reportee: "reportée", perimee: "périmée" };
  const ISSUE = { faite: "fait", racontee: "raconté seulement", simulee: "simulé", echec: "échoué" };
  const tx = (v) => (v && typeof v === "object" ? JSON.stringify(v) : String(v == null ? "" : v));
  const btnPq = (acte) => (acte ? '<div><button class="btn mini" data-pq="' + esc(acte) + '">Pourquoi ?</button></div><div class="ag-pq" id="pq-' + esc(acte) + '"></div>' : "");
  const manque = (e) => /inconnu|introuvable|n'existe pas|not found|404|capacit/i.test(String((e && e.message) || e));

  const COUL = { cassandra: "#0b7c74", itare: "#6d3fd1", amizo: "#1d6fb8", relecteur: "#b45309", vision: "#be123c", auditeur: "#5b6b8c" };
  const NIVEAUX = [["observer", "Observer", "Elle constate et raconte ce qu'elle ferait. Rien n'est touché."], ["entretien", "Entretien", "Elle fait le petit et le sûr : lectures, rangement, ce qui se défait."], ["reine", "Pleine autonomie", "Elle conduit seule dans ses paliers ; chaque geste garde sa preuve et son retour."]];
  const ACTIONS = [["secours", "bascule sur le modèle de secours"], ["arret", "arrête les agents (sauf Cassandra) et te prévient"], ["accord", "demande ton accord"]];
  const VOC = { palier: "Palier", outils: { auto: "Automatique", raconter: "À raconter", retire: "Retiré" } };      // les libellés viennent d'agents.regles().vocabulaire ; les codes ne changent pas
  const appliquerVoc = (r) => { const v = (r && r.vocabulaire) || {}; if (v.palier_agent) VOC.palier = v.palier_agent; if (v.niveaux) NIVEAUX.forEach((n) => { if (v.niveaux[n[0]]) n[1] = v.niveaux[n[0]]; }); if (v.paliers_outil) Object.assign(VOC.outils, v.paliers_outil); };
  const RISQUES = ["lecture", "faible", "moyen", "élevé"];
  const REGLES = [
    ["Aucun outil de secret pour Itare, Amizo, ni les services", "Seule Cassandra gère le Coffre. La valeur d'un secret n'entre jamais dans le contexte d'un modèle."],
    ["Un compte ne règle que son Itare", "L'administrateur règle Cassandra, Amizo et les services. Administrer n'est pas voir : il ne lit pas le bureau d'un autre compte."],
    ["Un agent ne monte pas son propre palier", "Les capacités de réglage refusent un agent pour acteur."],
    ["Chaque geste a sa preuve et son retour", "Un acte se relit après coup et se défait ; ce qui ne se défait pas attend ton mot."],
    ["Le plafond le plus bas s'applique", "Plafond d'agent et plafond global : le plus bas retient, avec son action."],
  ];
  const G = (g) => '<span aria-hidden="true">' + g + "</span> ";                                   // un pictogramme décoratif, devant un texte qui dit déjà tout
  const pg = (g, t, c) => '<span class="p ' + (c || "") + '">' + G(g) + esc(t) + "</span>";
  const ETG = { attend: "⏳", reportee: "⏳", acceptee: "✓", refusee: "✕" };
  const etatTxt = (e) => (ETG[e] ? G(ETG[e]) : "") + esc(ETAT[e] || e);
  const SQ = '<div class="sq" role="status" aria-label="Ouverture de l\'écran"><div class="r"><i style="height:64px"></i><i style="height:64px"></i><i style="height:64px"></i><i style="height:64px"></i></div><i style="height:130px"></i><i style="height:190px"></i></div>';
  const SQ_PETIT = '<div class="sq" aria-hidden="true"><i style="height:14px;width:55%"></i><i style="height:14px"></i><i style="height:14px;width:80%"></i></div>';
  const eur = (x) => (x == null ? "—" : Number(x).toLocaleString("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: x < 1 && x > 0 ? 2 : 0, maximumFractionDigits: 4 }));
  const initiale = (n) => String(n || "?").trim().slice(0, 1).toUpperCase();
  const av = (a, g) => '<span class="ag-av' + (g ? " g" : "") + '" style="background:' + (COUL[a.id] || "#5b6b8c") + '" aria-hidden="true">' + esc(initiale(a.nom)) + "</span>";
  const dateFr = (ts) => { try { return new Date(ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

  const CSS = ".ag{--ag-doux:color-mix(in srgb,var(--accent) 9%,transparent)}.sh-scene:has(>.sh-corps>.ag){width:100%}" +
    ".ag .ag-nav{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:thin}.ag .ag-nav button{border:0;background:transparent;padding:9px 14px;font:600 13px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;display:inline-flex;gap:6px;align-items:center}" +
    ".ag .ag-nav button.on{color:var(--accent);border-bottom-color:var(--accent)}.ag .ag-n{background:var(--accent);color:var(--on-accent,#fff);border-radius:99px;font:700 10.5px/1 'Inter',sans-serif;padding:3px 6px}" +
    ".ag .ag-av{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;color:#fff;font:700 17px 'Inter',sans-serif;flex:none}.ag .ag-av.g{width:48px;height:48px;font-size:20px}" +
    ".ag .ag-cartes{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}.ag button.carte.clic{text-align:left;color:inherit;font:inherit;cursor:pointer}.ag button.carte.clic:hover{border-color:var(--accent)}" +
    ".ag .ag-tete{display:flex;gap:12px;align-items:center;min-width:0}.ag .ag-tete>div{min-width:0}.ag .ag-ligne{display:flex;justify-content:space-between;gap:10px;align-items:baseline;font-size:12.5px}.ag .ag-ligne .g{color:var(--txt-soft)}" +
    ".ag .ag-ligne b{font-weight:600;text-align:right;overflow-wrap:anywhere}.ag .ag-puces{display:flex;gap:6px;flex-wrap:wrap}.ag .ag-etat{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.ag .ag-etat .sp{flex:1;min-width:220px}" +
    ".ag .ag-rond{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok);flex:none}.ag .ag-rond.al{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}.ag .ag-rond svg{width:22px;height:22px}.ag .ag-rond{font-size:20px;line-height:1}" +
    ".ag .ag-outil{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}.ag .ag-outil .n{font:600 12.5px ui-monospace,Menlo,Consolas,monospace;overflow-wrap:anywhere}.ag .ag-outil .d{font-size:12px;color:var(--txt-soft)}" +
    ".ag .ag-ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.ag label.ag-conf{display:inline-flex;gap:5px;align-items:center;font-size:12px;color:var(--txt-soft);cursor:pointer}" +
    ".ag .ag-fam{border:1px solid var(--line);border-radius:12px;margin:6px 0;background:var(--surface-2,transparent)}.ag .ag-fam>summary{cursor:pointer;padding:9px 12px;list-style:none;font-size:13px}.ag .ag-fam>summary::-webkit-details-marker{display:none}.ag .ag-fam>summary::before{content:'▸ ';color:var(--txt-faint)}.ag .ag-fam[open]>summary::before{content:'▾ '}.ag .ag-fam-c{padding:0 10px 8px}.ag .ag-fam>summary:focus-visible{outline:2px solid var(--accent,#0b7c74);border-radius:12px}" +
    ".ag .ag-mod{font:650 11px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:14px 0 2px}.ag .ag-barres{display:flex;align-items:flex-end;gap:4px;height:84px}.ag .ag-barres i{flex:1;min-width:6px;background:var(--accent);border-radius:4px 4px 0 0;opacity:.8;min-height:2px}" +
    ".ag table{border-collapse:collapse;width:100%;font-size:13px}.ag th{text-align:left;font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:6px 10px}.ag td{padding:8px 10px;border-top:1px solid var(--line)}.ag .ag-tw{overflow-x:auto}" +
    ".ag input[type=text],.ag input[type=number],.ag textarea,.ag select{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:8px 11px;min-width:0;max-width:100%}.ag textarea{width:100%;min-height:92px;resize:vertical}" +
    ".ag .ag-f{display:flex;flex-direction:column;gap:4px;min-width:0}.ag .ag-f>span{font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint)}.ag .ag-champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}" +
    ".ag .ag-conv{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:12px;align-items:start}.ag .ag-fil{display:flex;flex-direction:column;gap:8px;max-height:56vh;overflow:auto;padding:2px}" +
    ".ag .ag-m{max-width:85%;padding:9px 12px;border-radius:14px;font-size:13.5px;white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid var(--line);background:var(--surface)}.ag .ag-m.moi{align-self:flex-end;background:var(--ag-doux);border-color:transparent}.ag .ag-m small{display:block;color:var(--txt-faint);margin-top:3px}" +
    ".ag .ag-m.outil{font:12px ui-monospace,Menlo,monospace;color:var(--txt-soft);max-width:100%}.ag .ag-sel{display:flex;gap:10px;align-items:center;padding:9px 10px;border:1px solid var(--line);border-radius:12px;background:var(--surface);cursor:pointer;text-align:left;color:inherit;font:inherit;width:100%}" +
    ".ag .ag-sel.on{border-color:var(--accent)}.ag .ag-sel .sp{flex:1;min-width:0}.ag .ag-sel b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ag .ag-ecrire{display:flex;gap:8px}.ag .ag-ecrire textarea{min-height:44px;height:44px}" +
    ".ag .ag-nb{font:600 9.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;border:1px dashed var(--line-strong,var(--line));border-radius:99px;padding:2px 8px;color:var(--txt-faint);white-space:nowrap}" +
    ".ag .ag-prop{border-top:1px solid var(--line);padding:11px 0;display:flex;flex-direction:column;gap:6px}.ag .ag-prop:first-of-type{border-top:0}.ag .ag-mandat{border:1px solid var(--line);border-radius:12px;padding:8px 11px;background:var(--ag-doux)}.ag .ag-mandat pre{margin:4px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace,Menlo,monospace;color:var(--txt-soft)}" +
    ".ag .ag-pq{border:1px dashed var(--line);border-radius:12px;padding:8px 11px;margin-top:6px}.ag .ag-pq:empty{display:none}.ag .ag-jauge{display:inline-block;width:90px;height:7px;border-radius:99px;background:var(--line);overflow:hidden;vertical-align:middle}.ag .ag-jauge i{display:block;height:100%;background:var(--accent)}.ag td .ag-puces{margin:0}" +
    ".ag .sq{display:flex;flex-direction:column;gap:12px}.ag .sq .r{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.ag .sq i{display:block;border-radius:14px;background:linear-gradient(90deg,var(--line) 0%,color-mix(in srgb,var(--line) 35%,transparent) 50%,var(--line) 100%);background-size:200% 100%;animation:ag-sq 1.3s linear infinite;opacity:.75}@keyframes ag-sq{to{background-position:-200% 0}}@media (prefers-reduced-motion:reduce){.ag .sq i{animation:none}}" +
    "@media (max-width:760px){.ag .ag-conv{grid-template-columns:1fr}.ag .ag-outil{grid-template-columns:1fr}.ag .ag-ctl{justify-content:flex-start}.ag .ag-m{max-width:100%}.ag .ag-ecrire{flex-direction:column}.ag .ag-ecrire textarea{height:70px}.ag table{min-width:420px}}";

  // ── l'état de l'écran (une scène, des vues) ────────────────────────────────
  const MEM = { eq: null, t: 0 };                                // l'équipe lue il y a moins de 30 s survit au changement de page du menu (l'écran est remonté à chaque clic)
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.agents = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("ag-css")) { const st = document.createElement("style"); st.id = "ag-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit ag"; corps.appendChild(racine);
    const S = { props: {}, vue: "", agent: "", onglet: "apercu", eq: null, admin: false, filtre: { q: "", risque: "tous" }, conv: { id: 0, liste: null, fil: null, agent: "itare", occupe: false }, jours: 14 };

    const erreur = (e) => dire(String((e && e.message) || e), "err");
    // l'identifiant de la page dans le menu de gauche (sous-entrées d'« Agents IA ») et sa traduction en vue de l'écran
    const pageMenu = () => (S.vue === "fiche" ? (S.admin ? S.agent : "itare") : S.vue);
    const depuisMenu = (id) => {
      if (["cassandra", "itare", "amizo", "relecteur", "vision"].includes(id)) { S.vue = "fiche"; if (S.agent !== id) S.essaiId = 0; S.agent = id; S.onglet = "apercu"; }
      else if (["equipe", "conv", "boite", "journal", "modeles", "auditeur", "maison"].includes(id)) S.vue = id;
      if (S.vue === "conv") S.conv.liste = null;
    };
    const nonBranche = (titre, texte) => '<section class="carte"><div class="barre"><h3 style="flex:1">' + esc(titre) + '</h3><span class="ag-nb">non branché</span></div><p class="note">' + esc(texte) + "</p></section>";
    const chez = (onglet, q) => {                                       // ouvrir l'écran d'un autre module, filtré quand il sait l'être
      if (typeof window.switchTab === "function") window.switchTab(onglet);
      if (q) setTimeout(() => { const i = document.querySelector("#tab-" + onglet + " input[type=search],#tab-" + onglet + " input[type=text]"); if (i) { i.value = q; i.dispatchEvent(new Event("input", { bubbles: true })); } }, 250);
    };
    const lien = (onglet, texte, q) => '<button class="btn mini" data-chez="' + esc(onglet) + '" data-q="' + esc(q || "") + '">' + esc(texte) + " ↗</button>";

    // ── la maison de l'équipe ────────────────────────────────────────────────
    function carteAgent(a) {
      const n = a.outils || {}; const pc = a.plafond_atteint;
      return '<button class="carte clic" data-agent="' + esc(a.id) + '"><div class="ag-tete">' + av(a) + '<div><h3>' + esc(a.nom) + '</h3><div class="note">' + esc(a.role) + "</div></div></div>" +
        '<div class="ag-puces">' + pill((n.auto || 0) + " en auto", "ok") + pill((n.raconter || 0) + " racontés", "al") + (n.retire ? pill(n.retire + " retirés") : "") + pill((n.lecture || 0) + " lectures") + "</div>" +
        '<div class="ag-ligne"><span class="g">' + esc(VOC.palier) + '</span><b>' + esc((NIVEAUX.find((x) => x[0] === a.niveau) || [0, a.niveau])[1]) + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle</span><b>' + esc(a.modele || "par défaut") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Aujourd\'hui</span><b>' + (a.cout_jour && a.cout_jour.euros ? eur(a.cout_jour.euros) : "gratuit") + ' <span class="note">· ' + ((a.cout_jour || {}).appels || 0) + " appels</span></b></div>" +
        (pc ? pg("⚠", "plafond atteint", "dg") : "") + "</button>";
    }
    const nomAg = (id) => ((S.eq.equipe || []).find((a) => a.id === id) || {}).nom || id;
    async function carteRapport() {
      let r; try { r = await API.rapport(); } catch (e) { return nonBranche("Le rapport du matin", String((e && e.message) || e)); }
      const long = !!S.rapLong;
      const corps = (r.agents || []).map((a) => { const p = a.phrases || [], aff = long ? p : p.slice(0, 3);
        return '<div class="li"><div class="sp"><b>' + esc(a.nom) + "</b>" + (aff.length ? aff.map((x) => '<div class="note">' + esc(x.phrase) + (x.journal ? ' <span class="mono">· ligne ' + esc(x.journal) + "</span>" : "") + "</div>").join("") : '<div class="note">Rien à signaler.</div>') + "</div></div>"; }).join("");
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Le rapport du matin</h3><div class="seg" role="group" aria-label="Longueur du rapport"><button data-rap="court" class="' + (long ? "" : "on") + '">En bref</button><button data-rap="long" class="' + (long ? "on" : "") + '">Détaillé</button></div></div><div class="liste">' + corps + "</div>" +
        '<p class="note">Chaque matin, chaque agent écrit ce qu\'il a fait, ce qu\'il a refusé et ce qui reste — tiré du journal, jamais inventé : chaque phrase renvoie à une ligne du journal.</p></section>';
    }
    async function cartePassations() {
      let r; try { r = await API.passations(); } catch (e) { return nonBranche("Passations", String((e && e.message) || e)); }
      const l = r.passations || [];
      return '<section class="carte"><h3>Passations : qui demande quoi à qui</h3>' + (l.length ? '<div class="liste">' + l.map((p) => '<div class="li"><div class="sp"><b>' + esc(nomAg(p.de)) + " → " + esc(nomAg(p.vers)) + '</b><div class="note">' + esc(p.demande || "") + " · " + esc(p.etat || "") + " · " + esc(dateFr(p.cree)) + "</div></div></div>").join("") + "</div>" : '<p class="note">Aucune passation pour le moment.</p>') +
        '<p class="note">Itare tient le bureau, Cassandra la machine, Amizo la connaissance : quand l\'un n\'a pas l\'outil, il le dit et passe la main. La passation est visible au lieu d\'être un secret entre agents. Tout ce qui vient du dehors passe par Amizo, qui n\'a aucun outil qui sort.</p></section>';
    }
    const FREQ = { horaire: "toutes les heures", quotidien: "chaque jour", hebdomadaire: "chaque semaine" };
    async function carteTaches() {
      let r; try { r = await API.taches(); } catch (e) { return nonBranche("Tâches récurrentes", String((e && e.message) || e)); }
      const l = r.taches || [], F = S.tForm;
      const choix = (S.eq.equipe || []).filter((a) => a.genre === "agent" && a.id !== "amizo").filter((a) => S.admin || a.portee === "compte");
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Tâches récurrentes</h3><button class="btn pri mini" id="ag-t-new">' + (F ? "Fermer" : "Confier une tâche récurrente") + "</button></div>" +
        '<p class="note">Une consigne qui revient, confiée à l\'un des agents. Pas un agent de plus : la tâche utilise ses outils, sa mémoire et son palier, et reste lisible dans son journal.</p>' +
        (F ? '<div class="ag-champs"><label class="ag-f"><span>Confiée à</span><select id="ag-t-ag">' + choix.map((a) => '<option value="' + esc(a.id) + '">' + esc(a.nom) + "</option>").join("") + "</select></label>" +
          '<label class="ag-f"><span>Fréquence</span><select id="ag-t-fr">' + Object.keys(FREQ).map((k) => '<option value="' + k + '"' + (k === "quotidien" ? " selected" : "") + ">" + FREQ[k] + "</option>").join("") + "</select></label>" +
          '<label class="ag-f"><span>Heure</span><input type="time" id="ag-t-h" value="08:00"></label>' +
          '<label class="ag-f"><span>Jour (si chaque semaine)</span><select id="ag-t-j">' + ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"].map((j) => "<option>" + j + "</option>").join("") + "</select></label></div>" +
          '<label class="ag-f"><span>La consigne</span><textarea id="ag-t-c" rows="3" placeholder="Ex. : range mes notes de la semaine et dis-moi ce qui reste."></textarea></label><div class="ag-puces"><button class="btn pri" id="ag-t-go">Confier la tâche</button></div>' : "") +
        (l.length ? '<div class="liste">' + l.map((t) => '<div class="li"><div class="sp"><b>' + esc(nomAg(t.agent)) + " · " + esc(FREQ[t.frequence] || t.frequence) + " à " + esc(t.heure) + (t.jour ? " (" + esc(t.jour) + ")" : "") + '</b><div class="note">' + esc(t.consigne) + (t.prochaine ? " · prochaine : " + esc(dateFr(t.prochaine)) : "") + (t.derniere ? " · dernière : " + esc(dateFr(t.derniere)) : "") + '</div></div><button class="btn mini" data-tl="' + t.id + '">' + G("↻") + 'Lancer maintenant</button><button class="btn mini dng" data-tr="' + t.id + '">' + G("✕") + 'Retirer</button></div>').join("") + "</div>" : '<p class="note">Aucune tâche récurrente.</p>') +
        (r.declenchement_automatique ? "" : '<p class="note">Pas de déclenchement automatique pour l\'instant : « Lancer maintenant » joue un tour de l\'agent.</p>') + "</section>";
    }
    async function vEquipe() {
      const eq = S.eq.equipe, agents = eq.filter((a) => a.genre === "agent"), services = eq.filter((a) => a.genre === "service");
      const pR = carteRapport(), pP = cartePassations(), pT = carteTaches();
      const [cout, ret] = await Promise.all([API.couts("", 1).catch(() => null), API.retenus(1).catch(() => null)]);
      const glob = cout && cout.plafonds && cout.plafonds.global;
      const auj = cout ? cout.aujourdhui_euros : null;
      const retenu = eq.some((a) => a.plafond_atteint);
      const pct = glob && glob.euros ? Math.min(100, (auj || 0) / glob.euros * 100) : 0;
      return '<section class="carte"><div class="ag-etat"><div class="ag-rond' + (retenu ? " al" : "") + '">' + (retenu ? "⚠" : "✓") + '</div><div class="sp"><h3>' + (retenu ? "Un plafond de coût retient un agent" : "Tout va bien") + "</h3>" +
        '<p class="note">' + (retenu ? "Voir « Coût » dans la fiche de l'agent concerné pour lever, relever ou accorder pour aujourd'hui." : "Les agents agissent seuls dans leurs paliers ; chaque geste garde sa preuve et son retour.") + '</p></div><button class="btn pri" data-agent="cassandra" data-onglet="essai">Demander à un agent…</button></div></section>' +
        '<section class="stats"><div class="stat"><b>' + eq.length + "</b><span>agents et services</span></div>" +
        '<div class="stat ' + (pct > 85 ? "al" : "") + '"><b>' + eur(auj) + "</b><span>dépensé aujourd'hui" + (glob ? " sur " + eur(glob.euros) + " de plafond global" : " · aucun plafond global") + "</span>" + (glob ? '<div class="jauge"><i style="width:' + pct + '%"></i></div>' : "") + "</div>" +
        '<div class="stat"><b>' + (ret ? ret.retenus + ret.refuses : "—") + "</b><span>retenus ou refusés aujourd\'hui · par la règle, pas par oubli</span></div>" +
        '<div class="stat"><b>' + (S.attente == null ? "—" : S.attente) + "</b><span>à valider</span></div></section>" +
        (await pR) +
        '<div><div class="note" style="margin:0 2px 8px"><b>L\'équipe</b></div><div class="ag-cartes">' + agents.map(carteAgent).join("") + "</div></div>" +
        '<div><div class="note" style="margin:0 2px 2px"><b>Services agentiques</b></div><div class="note" style="margin:0 2px 8px">Des fonctions, pas des décideurs : une tâche précise, pas de mémoire propre, pas d\'initiative.</div><div class="ag-cartes">' + services.map(carteAgent).join("") + "</div></div>" +
        (await pP) + (await pT);
    }

    // ── la fiche ─────────────────────────────────────────────────────────────
    const ONGLETS = [["apercu", "Aperçu"], ["outils", "Outils & palier"], ["journal", "Journal"], ["essai", "Essai en direct"], ["propose", "Fait & proposé"], ["cout", "Coût"], ["sur", "Sûr & refusé"], ["memoire", "Mémoire"], ["reglages", "Réglages"]];
    const ONGLETS_USER = ["apercu", "outils", "journal", "propose", "memoire", "reglages"];
    async function vFiche() {
      if (!S.admin) S.agent = "itare";
      const f = await API.agent(S.agent), a = f.agent;
      S.fiche = f;
      const service = a.genre === "service";
      let tabs = ONGLETS.filter((t) => (S.admin || ONGLETS_USER.includes(t[0])) && !(service && t[0] === "memoire"));
      if (!tabs.some((t) => t[0] === S.onglet)) S.onglet = "apercu";
      const n = f.decompte || {};
      const tete = '<section class="carte"><div class="ag-tete">' + av(a, 1) + '<div style="flex:1"><h2 style="font:650 20px \'Inter\',sans-serif;margin:0">' + esc(S.admin ? a.nom : "Mon Itare") + '</h2><div class="note">' + esc(S.admin ? a.role : "Ton agent du bureau : lui seul voit ton bureau, personne d'autre.") + "</div></div>" +
        (S.admin ? '<select class="sel" id="ag-chg" aria-label="Changer d\'agent">' + S.eq.equipe.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === a.id ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + "</select>" : "") + "</div>" +
        '<div class="ag-puces">' + (service ? pill("service agentique") : "") + pill((NIVEAUX.find((x) => x[0] === a.niveau) || [0, a.niveau])[1], "ac") + pill(a.modele || "modèle par défaut") + (f.plafond_atteint ? pg("⚠", "plafond atteint : " + f.plafond_atteint.action, "dg") : "") + pill((n.auto || 0) + " en auto", "ok") + pill((n.raconter || 0) + " racontés", "al") + "</div></section>";
      const ong = '<div class="ag-nav" role="tablist" id="ag-ong">' + tabs.map(([k, l]) => '<button role="tab" data-o="' + k + '" class="' + (S.onglet === k ? "on" : "") + '">' + esc(l) + "</button>").join("") + "</div>";
      const fn = { apercu: oApercu, outils: oOutils, journal: oJournal, essai: oEssai, propose: oPropose, cout: oCout, sur: oSur, memoire: oMemoire, reglages: oReglages }[S.onglet];
      return tete + ong + '<div id="ag-fiche" style="display:flex;flex-direction:column;gap:12px">' + await fn(f) + "</div>";
    }
    async function oApercu(f) {
      const a = f.agent, n = f.decompte || {};
      S.gestes = null; S.conf = null;
      const mo = dessin;                                                                    // la carte de confiance est la lecture la plus longue du module : elle part après les gestes, et seulement si on est encore là
      setTimeout(() => { if (mo !== dessin) return; API.confiance(a.id).then((c) => { S.conf = carteConfiance(c); peindreGestes(); }).catch((e) => { S.conf = nonBranche("Carte de confiance", String((e && e.message) || e)); peindreGestes(); }); }, 900);
      dernierGestes(a).catch(() => null).then((d) => { S.gestes = d && d.length ? d.slice(0, 5).map((x) => '<div class="ag-ligne" style="padding:4px 0"><span>' + esc(x.action) + '</span><span class="g">' + esc(x.ts) + "</span></div>").join("") : '<p class="note">Rien à montrer pour le moment.</p>'; peindreGestes(); });
      return '<div class="g2"><section class="carte"><h3>Qui est ' + esc(a.nom) + '</h3><p class="note">' + esc(a.role) + "</p>" +
        '<div class="ag-ligne"><span class="g">Ton</span><b style="max-width:62%">' + esc(a.ton || "le ton d'origine") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle principal</span><b>' + esc(a.modele || "par défaut") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle de secours</span><b>' + esc(a.secours || "aucun") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Porte</span><b>' + (a.portee === "compte" ? "le bureau d'un compte, le sien" : "toute l'instance") + "</b></div>" +
        '<div class="ag-puces"><button class="btn" data-onglet-vers="reglages">Modifier le ton et le modèle</button>' + ((f.agent.id !== "amizo" || S.admin) && f.agent.genre === "agent" ? '<button class="btn" data-onglet-vers="essai">L\'essayer</button>' : "") + "</div></section>" +
        '<section class="carte"><h3>Son ' + esc(VOC.palier.toLowerCase()) + '</h3><div id="ag-niv" style="display:flex;flex-direction:column;gap:8px">' +
        NIVEAUX.map(([k, l, t]) => '<button class="radio' + (a.niveau === k ? " on" : "") + '" data-niveau="' + k + '"><i></i><span><b>' + l + '</b><br><span class="note">' + t + "</span></span></button>").join("") + "</div>" +
        '<div class="ag-puces">' + pill((n.auto || 0) + " outils en auto", "ok") + pill((n.raconter || 0) + " racontés", "al") + pill((n.retire || 0) + " retirés") + "</div>" +
        '<p class="note">Le palier est un réglage, pas un interdit codé : il se précise outil par outil (onglet « Outils & palier »). La sûreté vient de la preuve et du retour arrière.</p></section></div>' +
        '<section class="carte"><h3>Ses derniers gestes</h3><div id="ag-gestes">' + SQ_PETIT + '</div>' +
        '<div><button class="btn mini" data-onglet-vers="journal">Tout le journal</button></div></section>' +
        '<section class="carte" id="ag-conf"><h3>Carte de confiance</h3>' + SQ_PETIT + '</section>';
    }
    function peindreGestes() {
      const z = racine.querySelector("#ag-gestes"); if (z && S.gestes) z.innerHTML = S.gestes;
      const c = racine.querySelector("#ag-conf"); if (c && S.conf) c.outerHTML = S.conf;
    }
    function carteConfiance(c) {
      const o = c.outils || [], seuil = c.seuil || 8;
      const lignes = o.map((x) => '<tr><td class="mono">' + esc(x.cle) + "</td><td><span class=\"ag-jauge\" title=\"" + (x.validations || 0) + " validations de suite sur " + seuil + "\"><i style=\"width:" + Math.min(100, Math.round(100 * (x.validations || 0) / seuil)) + "%\"></i></span> " + (x.validations || 0) + "/" + seuil + "</td><td>" +
        '<div class="ag-puces">' + pill(x.risque || "", RISQUE[x.risque] || "") + (x.refus ? pill(x.refus + " refus", "al") : "") + (x.essai ? pill("à l'essai" + (x.essai_jusqua ? " jusqu'au " + dateFr(x.essai_jusqua) : "")) : "") + "</div></td><td>" +
        (x.propose_auto ? '<button class="btn pri mini" data-auto="' + esc(x.cle) + '">Passer en auto</button>' : '<span class="note">' + (x.essai ? "période d'essai" : "encore " + (x.manque == null ? Math.max(0, seuil - (x.validations || 0)) : x.manque) + " à valider") + "</span>") + "</td></tr>").join("");
      return '<section class="carte" id="ag-conf"><div class="barre"><h3 style="flex:1">Carte de confiance</h3>' + ((c.propose_auto || []).length ? pill((c.propose_auto || []).length + " à passer en auto", "ok") : "") + "</div>" +
        '<p class="note">Un outil raconté qui a ' + seuil + " validations de suite, hors période d'essai (" + (c.essai_jours || 7) + " jours), est proposé en auto. La carte ne passe jamais rien toute seule.</p>" +
        (o.length ? '<div class="ag-tw"><table><tr><th>Outil</th><th>Validations</th><th>État</th><th></th></tr>' + lignes + "</table></div>" : '<p class="note">Aucune décision à compter pour l\'instant : un outil raconté apparaît ici dès qu\'il a été validé ou refusé.</p>') + "</section>";
    }
    async function dernierGestes(a) {
      if (!S.admin) return (await actes(a.id)).slice(0, 8).map((x) => ({ action: x.titre || x.capacite, ts: dateFr(x.decidee || x.cree) }));   // le flux du journal n'est pas cloisonné : un compte ordinaire lit ses actes par les propositions
      const r = await API.journal(a.id === "itare" ? "itare" : a.id, 8);
      return (r.entrees || []).filter(mien).map((e) => ({ action: String(e.action || e.sujet || ""), ts: String(e.ts || "").replace("T", " ").slice(0, 16) }));
    }
    // un compte ordinaire ne lit que ses propres lignes : on écarte ce que le journal rattache à un autre compte
    function mien(e) {
      if (S.admin) return true;
      const moi = String((ctx.moi && ctx.moi.compte) || ""), qui = String(e.compte || e.utilisateur || "");
      return !qui || qui === moi || qui === "itare";
    }

    // les outils par famille (module) repliable : les lignes ne se dessinent qu'à l'ouverture d'une famille (des centaines de contrôles sinon)
    function famille(groupes, filtre, n, total) {
      S.ouv = S.ouv || new Set();
      const noms = Object.keys(groupes).sort();
      const sec = (m) => { const l = groupes[m], c = (k) => l.filter((o) => (o.retire ? "retire" : o.palier) === k).length;
        const ouvert = filtre || S.ouv.has(m);
        return '<details class="ag-fam" data-fam="' + esc(m) + '"' + (ouvert ? " open" : "") + '><summary><b>' + esc(m) + "</b> <span class=\"note\">· " + l.length + " outil" + (l.length > 1 ? "s" : "") + (c("auto") ? " · " + c("auto") + " en auto" : "") + (c("raconter") ? " · " + c("raconter") + " racontés" : "") + (c("retire") ? " · " + c("retire") + " retirés" : "") + '</span></summary><div class="ag-fam-c">' + (ouvert ? l.map(S.ligne).join("") : "") + "</div></details>"; };
      return '<div class="note" style="margin:2px 2px 6px">' + (n === total ? total + " outils" : n + " sur " + total + " outils") + " en " + noms.length + ' famille' + (noms.length > 1 ? "s" : "") + ' <button class="btn mini" data-fam-tout="1">' + (S.ouv.size ? "Tout replier" : "Tout déplier") + "</button></div>" + noms.map(sec).join("");
    }
    async function oOutils(f) {
      const a = f.agent, p = await API.paliers(a.id);
      const q = S.filtre.q.toLowerCase(), r = S.filtre.risque;
      const liste = p.paliers.filter((o) => (r === "tous" || o.risque === r) && (!q || (o.cle + " " + (o.description || "")).toLowerCase().includes(q)));
      const groupes = {}; liste.forEach((o) => { const m = o.cle.includes("__") ? o.cle.split("__")[0] : (o.cle.split(".")[0] || "divers"); (groupes[m] = groupes[m] || []).push(o); });
      const ligne = (o) => {
        const lect = o.risque === "lecture";
        const cur = o.retire ? "retire" : o.palier;
        const seg = lect ? [["lecture", "Lecture"], ["retire", "Retirer"]] : [["auto", VOC.outils.auto], ["raconter", VOC.outils.raconter], ["retire", VOC.outils.retire]];
        return '<div class="ag-outil"><div><div class="n">' + esc(o.cle) + '</div><div class="d">' + esc(o.description || "") + '</div><div class="ag-puces" style="margin-top:3px">' + pill(o.risque, o.risque === "moyen" ? "al" : o.risque === "élevé" ? "dg" : "") + (o.pose ? pill("réglé par toi", "ac") : "") + (o.defaut && o.pose ? pill("catalogue : " + o.defaut) : "") + "</div></div>" +
          '<div class="ag-ctl"><div class="seg" role="group" aria-label="Palier de ' + esc(o.cle) + '">' + seg.map(([k, l]) => '<button data-outil="' + esc(o.cle) + '" data-p="' + k + '" class="' + (cur === k ? "on" : "") + '">' + l + "</button>").join("") + "</div>" +
          (lect ? "" : '<label class="ag-conf"><input type="checkbox" data-conf="' + esc(o.cle) + '"' + (o.confirmer ? " checked" : "") + (o.retire ? " disabled" : "") + '> demander</label>') +
          (o.pose ? '<button class="btn mini" data-outil="' + esc(o.cle) + '" data-p="defaut">Rétablir</button>' : "") + "</div></div>";
      };
      return '<section class="carte"><h3>Les outils de ' + esc(a.nom) + ' <span class="note">· dérivés du catalogue des capacités</span></h3>' +
        (p.paliers.length ? '<div class="barre"><input type="search" id="ag-q" placeholder="Chercher un outil…" value="' + esc(S.filtre.q) + '"><select class="sel" id="ag-r"><option value="tous">Tous les risques</option>' + RISQUES.map((x) => '<option' + (r === x ? " selected" : "") + ">" + x + "</option>").join("") + "</select></div>" +
          '<p class="note">« Demander » n\'est pas un palier : c\'est une confirmation posée sur « auto ». Une lecture n\'a pas de palier, on peut seulement la retirer.</p>' +
          (liste.length ? (S.grp = groupes, S.ligne = ligne, famille(groupes, !!(q || r !== "tous"), liste.length, p.paliers.length)) : '<div class="vide">Aucun outil ne correspond.</div>') :
          '<p class="note">' + esc(a.nom) + " n'a pas d'outils à régler" + (a.id === "amizo" ? " : il cherche, lit et informe, il n'agit jamais." : ".") + "</p>") + "</section>";
    }
    async function actes(agent) { const p = await API.propositions("toutes", agent || ""); return (p.propositions || []).filter((x) => x.acte); }
    function ligneActes(l) {
      return l.length ? '<div class="liste">' + l.map((x) => '<div class="li"><div class="sp"><b>' + esc(x.titre || x.capacite) + '</b><div class="note">' + esc(x.nom || x.agent) + " · " + etatTxt(x.etat) + (x.par ? " par " + esc(x.par) : "") + " · " + esc(dateFr(x.decidee || x.cree)) + "</div>" + btnPq(x.acte) + "</div></div>").join("") + "</div>"
        : '<p class="note">Aucun acte décidé pour le moment : ce que l\'agent fait après ton accord apparaît ici, avec son « Pourquoi ? ».</p>';
    }
    function vPourquoi(r) {
      const d = r.declencheur || {};
      const decl = d.phrase ? d.phrase : d.type === "tour" ? "un message dans une conversation" + (d.extrait ? " : « " + d.extrait + " »" : "") : d.type === "proposition" ? "une proposition acceptée" + (d.accepte_par ? " par " + d.accepte_par : "") : "—";
      const mem = (r.memoire || []).map((m) => '<button class="btn mini" data-chez="memory" data-q="' + esc(m.ref) + '" title="' + esc(m.valeur ? tx(m.valeur) : "Ouvrir la Mémoire") + '">' + esc(m.libelle || (m.cle ? String(m.cle).replace(/_/g, " ") : "souvenir n° " + String(m.ref).replace(/^\D+/, ""))) + "</button>").join(" ") || "aucun souvenir consulté";
      const preuve = r.preuve === true ? "prouvé" : r.preuve === false ? "preuve manquante" : "sans objet";
      const retour = r.retour_texte ? r.retour_texte : r.retour === "annulee" ? "annulé par le noyau" : r.retour === "annulation_impossible" ? "annulation impossible" : "aucun retour nécessaire";
      const l = (k, v) => '<div class="ag-ligne"><span class="g">' + k + "</span><b>" + v + "</b></div>";
      const phrases = (r.phrases || []).length ? '<div style="margin:2px 0 8px">' + r.phrases.map((x) => '<p style="margin:3px 0">' + esc(x) + "</p>").join("") + "</div>" : "";
      const issueT = r.issue === "inconnue" && !r.issue_texte ? "" : (r.issue_texte || ISSUE[r.issue] || "");
      const defais = r.defaisable !== undefined ? !!r.defaisable : r.issue === "faite" && r.retour !== "annulee";
      return phrases + l("Déclencheur", esc(decl)) + l("Mémoire consultée", mem) + l("Outil", esc((r.outil && r.outil.cle) || r.capacite || "")) + l(esc(VOC.palier), esc(VOC.outils[r.palier] || r.palier || "") + (r.confirmer ? " · à confirmer" : "") + (r.niveau ? " · " + esc((NIVEAUX.find((x) => x[0] === r.niveau) || [0, r.niveau])[1]) : "")) +
        (issueT ? l("Issue", pill(issueT, r.issue === "echec" ? "dg" : r.issue === "faite" ? "ok" : "al")) : "") + l("Preuve", esc(preuve)) + l("Retour", esc(retour)) + ((r.journal || []).length ? l("Lignes du journal", (r.journal || []).length) : "") +
        (defais ? '<div class="barre" style="margin-top:8px"><button class="btn mini" data-df="' + esc(r.acte) + '" title="Rejoue le retour arrière de ce geste, une seule fois">' + G("↺") + 'Défaire</button><span class="note">Rejoue le retour arrière de ce geste, une seule fois.</span></div>' : '<p class="note">' + (r.issue === "faite" || r.defaisable === false ? "Ce geste ne se défait pas (ou l'a déjà été)." : "Ce geste n'a rien fait : il n'y a rien à défaire.") + "</p>");
    }
    // « Règles communes » : ce qui vaut pour tous les agents, et les deux réglages qui valent pour tous (le plafond global ; le reste attend son module)
    const bilanMJ = (l) => ((l || []).length ? '<div class="liste">' + l.map((x) => '<div class="li"><div class="sp"><b>' + esc(nomAg(x.agent)) + '</b><div class="note">' + esc(x.capacite) + " · " + x.fois + " fois racontée" + (x.fois > 1 ? "s" : "") + " au lieu d\'être faite" + (x.fois > 1 ? "s" : "") + "</div></div></div>").join("") + "</div>" : '<p class="note">Rien n\'a été raconté à la place d\'un geste.</p>');
    function mauvaisJourCarte(rg) {
      const mj = (rg && rg.mauvais_jour) || {}, bil = S.bilanMJ;
      return '<section class="carte"><h3>' + G("⏸") + 'Le mauvais jour</h3><p class="note">Un seul bouton quand quelque chose te semble bizarre : tous les agents passent en « ' + esc(VOC.outils.raconter) + " » pendant une durée choisie, puis reviennent seuls à leurs réglages. Le bilan dit ce qu\'ils ont raconté au lieu de faire.</p>" +
        (mj.actif ? '<div class="ag-ligne"><span class="g">En cours</span><b>depuis ' + esc(dateFr(mj.depuis)) + (mj.jusqua ? " · jusqu\'à " + esc(dateFr(mj.jusqua)) : " · jusqu\'à la levée") + '</b></div><div class="note" style="margin:6px 2px 2px"><b>Ce qu\'ils ont raconté depuis</b></div>' + bilanMJ(mj.raconte) + '<div class="ag-puces"><button class="btn" data-mj-lever="1">Lever le mauvais jour</button></div>' :
          '<div class="ag-puces"><button class="btn" data-mj="1">1 heure</button><button class="btn" data-mj="24">24 heures</button><button class="btn" data-mj="0">Jusqu\'à ce que je lève</button></div>') +
        (bil ? '<div class="note" style="margin:8px 2px 2px"><b>Bilan du dernier mauvais jour</b></div>' + bilanMJ(bil) : "") + "</section>";
    }
    async function vMaison() {
      let c = null; try { c = await API.couts("", 1); } catch (e) { c = null; }
      let rg = null; try { rg = await API.regles(); } catch (e) { rg = null; }
      const glob = c && c.plafonds && c.plafonds.global, auj = c ? c.aujourdhui_euros : null, pct = glob && auj != null ? Math.min(100, Math.round(auj / glob.euros * 100)) : 0;
      const somme = (S.eq.equipe || []).reduce((t, a) => t + ((c && c.plafonds && c.plafonds[a.id] && c.plafonds[a.id].euros) || 0), 0);
      return '<section class="carte"><h3>Les règles communes</h3><p class="note">Valent pour tous les agents. Ce ne sont pas des interdits de plus : ce sont les garanties qui permettent de les laisser agir.</p><div class="liste">' +
        REGLES.map((r, i) => '<div class="li"><div class="sp"><b>' + (i + 1) + ". " + esc(r[0]) + '</b><div class="note">' + esc(r[1]) + "</div></div></div>").join("") + "</div></section>" +
        '<section class="carte"><h3>Le plafond global de coût</h3><p class="note">En plus du plafond de chaque agent : une limite pour tout ce que les agents dépensent en une journée. Le plus bas des deux s\'applique.</p>' +
        '<div class="ag-ligne"><span class="g">Plafond global</span><b>' + (glob ? eur(glob.euros) + " par jour · " + esc((ACTIONS.find((x) => x[0] === glob.action) || [0, glob.action])[1]) : "aucun") + "</b></div>" +
        (glob ? '<div class="ag-barres" style="height:14px" role="img" aria-label="' + pct + ' % du plafond global"><i style="height:100%;width:' + pct + '%;background:var(--accent,#0b7c74);border-radius:99px"></i></div><p class="note">Aujourd\'hui : <b>' + eur(auj) + "</b> sur " + eur(glob.euros) + " (" + pct + " %).</p>" : "") +
        (glob && somme > glob.euros ? '<p class="note">La somme des plafonds par agent (' + eur(somme) + ") dépasse le plafond global : c\'est le global qui gagne.</p>" : "") +
        '<div class="ag-champs"><label class="ag-f"><span>Montant par jour (€)</span><input type="number" min="0.01" step="0.01" id="ag-gl-e" value="' + (glob ? glob.euros : "") + '"></label>' +
        '<label class="ag-f"><span>À l\'atteinte</span><select id="ag-gl-a">' + ACTIONS.map(([k, l]) => '<option value="' + k + '"' + (glob && glob.action === k ? " selected" : "") + ">" + esc(l) + "</option>").join("") + "</select></label></div>" +
        '<div class="ag-puces"><button class="btn pri" id="ag-gl-poser">Poser le plafond global</button>' + (glob ? '<button class="btn dng" id="ag-gl-lever">Lever</button>' : "") + "</div></section>" +
        mauvaisJourCarte(rg) + (rg ? '<section class="carte"><h3>Le ' + esc(VOC.palier.toLowerCase()) + ' par défaut</h3><p class="note">Le point de départ de tout outil qu\'un agent n\'a pas réglé. Chaque agent se règle ensuite outil par outil.</p><div class="seg" id="ag-rg-p" role="radiogroup" aria-label="Palier par défaut">' +
          ["auto", "raconter"].map((k) => '<button data-rgp="' + k + '" role="radio" aria-checked="' + (rg.palier_defaut === k) + '" class="' + (rg.palier_defaut === k ? "on" : "") + '">' + esc(VOC.outils[k]) + "</button>").join("") + '</div><p class="note">« ' + esc(VOC.outils.raconter) + " » : l\'agent dit ce qu\'il ferait, sans le faire, tant que tu n\'as pas réglé l\'outil. Défaut prudent, capacité complète : rien n\'est interdit, tout est réglable.</p></section>" +
          '<section class="carte"><h3>Le dehors passe par un seul agent</h3><label class="ag-conf"><input type="checkbox" id="ag-rg-d"' + (rg.dehors_par_amizo ? " checked" : "") + '> Seul Amizo lit le dehors</label><p class="note">Seul Amizo lit le web, et il n\'a aucun outil qui sort. Cassandra et Itare, qui agissent, ne lisent jamais le dehors eux-mêmes : ils le lui demandent et reçoivent un résumé étiqueté « externe ». Une page piégée n\'atteint donc jamais un agent capable d\'agir.</p></section>' +
          '<section class="carte"><h3>L\'ordre du journal</h3><p class="note">Le journal des agents s\'ouvre sur le plus récent, ou sur le plus ancien pour relire une journée depuis son début.</p><div class="seg" id="ag-rg-o" role="radiogroup" aria-label="Ordre du journal">' +
          [["recent", "Le plus récent d\'abord"], ["ancien", "Le plus ancien d\'abord"]].map(([k, l]) => '<button data-rgo="' + k + '" role="radio" aria-checked="' + (rg.ordre_journal === k) + '" class="' + (rg.ordre_journal === k ? "on" : "") + '">' + l + "</button>").join("") + "</div></section>" :
          nonBranche("Les règles réglables", "Le module n\'a pas répondu : palier par défaut, dehors par Amizo et ordre du journal sont indisponibles.")) +
        "";
    }
    async function vAuditeur() {
      const jours = S.jauditeur || 7;
      let r; try { r = await API.auditer(jours); } catch (e) { return nonBranche("Auditeur", String((e && e.message) || e)); }
      let fiche = null; try { fiche = await API.agent("auditeur"); } catch (e) { fiche = null; }
      const ag = (fiche && fiche.agent) || {}, cj = (fiche && fiche.cout_jour) || {};
      const TYPE = { cout_derive: "Un coût qui dérive", palier_large: "Un palier trop généreux", injection_repetee: "Des tentatives d\'injection répétées" };
      const sg = r.signaux || [];
      return '<section class="carte"><div class="ag-tete">' + av({ id: "auditeur", nom: "Auditeur" }) + '<div><h3>Auditeur</h3><div class="note">Relit le journal et signale les dérives. Indépendant des agents qu\'il regarde ; il signale, il ne corrige pas.</div></div></div>' +
        '<div class="ag-puces">' + pill("lecture seule") + pill("sans palier : aucun outil qui agit") + pill(sg.length + (sg.length > 1 ? " signaux" : " signal"), sg.length ? "al" : "ok") + "</div></section>" +
        '<section class="carte"><h3>Sa fiche</h3>' +
        '<div class="ag-ligne"><span class="g">' + esc(VOC.palier) + '</span><b>' + esc((NIVEAUX.find((x) => x[0] === ag.niveau) || [0, ag.niveau || "observer"])[1]) + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle</span><b>' + esc(ag.modele || "par défaut") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Palier</span><b>aucun : il lit, il signale</b></div>' +
        '<div class="ag-ligne"><span class="g">Aujourd\'hui</span><b>' + (cj.euros ? eur(cj.euros) : "gratuit") + ' <span class="note">· ' + (cj.appels || 0) + " appels</span></b></div>" +
        '<div class="ag-ligne"><span class="g">Carte de confiance</span><b>rien à promouvoir : aucun outil à régler</b></div></section>' +
        '<section class="carte"><div class="barre"><h3 style="flex:1">Ce qu\'il a vu</h3><div class="seg" id="ag-ja" role="group" aria-label="Période">' + [7, 30].map((j) => '<button data-ja="' + j + '" class="' + (jours === j ? "on" : "") + '">' + j + " j</button>").join("") + "</div></div>" + (sg.length ? '<div class="liste">' + sg.map((x) => '<div class="li"><div class="sp"><b>' + esc(TYPE[x.type] || x.type) + (x.agent ? " · " + esc(x.agent) : "") + '</b><div class="note">' + esc(x.phrase || "") + (x.ref ? " · " + esc(x.ref) : "") + "</div></div></div>").join("") + "</div>" : '<p class="note">' + G("🛡") + 'Rien à signaler : ni coût qui dérive, ni palier trop large, ni tentative répétée.</p>') +
        '<p class="note">Il regarde : ' + (r.regards || []).map((g) => esc((TYPE[g] || g).toLowerCase())).join(", ") + ". Le geste reste à l\'administrateur.</p></section>";
    }
    async function oJournal(f) {
      const a = f.agent; let l = [], ac = "";
      try { ac = ligneActes(await actes(a.id)); } catch (e) { ac = nonBranche("Actes", String((e && e.message) || e)); }
      if (!S.admin) return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(a.nom) + " a fait</h3></div>" + ac + "</section>";
      try { l = (await API.journal(a.id === "itare" ? "itare" : a.id, 40)).entrees.filter(mien); } catch (e) { return nonBranche("Journal de " + a.nom, String(e.message || e)); }
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(a.nom) + " a fait</h3>" + lien("journal", "Ouvrir les Journaux", a.id) + "</div>" + ac + '<div class="note" style="margin:10px 2px 2px"><b>Dans le journal du noyau</b></div>' + ligneJournal(l) + "</section>";
    }
    function ligneJournal(l) {
      return l.length ? '<div class="liste">' + l.map((e) => '<div class="li"><div class="sp"><b>' + esc(e.action || e.sujet || "") + '</b><div class="note">' + esc(e.label || e.source || "") + (e.sujet && e.action ? " · " + esc(e.sujet) : "") + '</div></div>' + pill(e.niveau || "info", e.niveau === "erreur" || e.niveau === "critique" ? "dg" : e.niveau === "alerte" ? "al" : "") + '<span class="note">' + esc(String(e.ts || "").replace("T", " ").slice(0, 16)) + "</span></div>").join("") + "</div>" : '<div class="vide">Rien pour l\'instant.</div>';
    }
    async function oEssai(f) {
      const a = f.agent;
      if (!["cassandra", "itare"].concat(S.admin ? ["amizo"] : []).includes(a.id)) return nonBranche("Essai en direct", a.nom + " ne converse pas directement : on l'essaie par les services qui l'emploient.");
      return '<section class="carte"><h3>Essayer ' + esc(a.nom) + '</h3><p class="note">Une vraie conversation : chaque outil que l\'agent appelle traverse l\'exécuteur (droits, palier, preuve, retour, journal).</p><div class="ag-fil" id="ag-essai-fil" aria-live="polite"><div class="vide">Écris-lui pour commencer.</div></div>' +
        '<div class="ag-ecrire"><textarea id="ag-essai-t" placeholder="Demande-lui quelque chose…" aria-label="Message"></textarea><button class="btn pri" id="ag-essai-go">Envoyer</button></div></section>';
    }
    async function oPropose(f) {
      let p; try { p = await API.propositions("toutes", f.agent.id); } catch (e) { return nonBranche("Fait & proposé", String((e && e.message) || e)); }
      const l = p.propositions || [], att = l.filter((x) => x.etat === "attend" || x.etat === "reportee"), fait = l.filter((x) => !(x.etat === "attend" || x.etat === "reportee"));
      return '<section class="carte"><h3>Ce que ' + esc(f.agent.nom) + " propose</h3>" + (att.length ? att.map((x) => carteProp(x)).join("") : '<p class="note">Rien n\'attend ton mot.</p>') + "</section>" +
        '<section class="carte"><h3>Ce qui a été décidé</h3>' + (fait.length ? fait.map((x) => carteProp(x)).join("") : '<p class="note">Aucune décision pour le moment.</p>') + "</section>";
    }
    function carteProp(p) {
      S.props[p.id] = p;
      const m = p.mandat && p.mandat.id ? p.mandat : null, a = p.args || {};
      const k = ["corps", "texte", "message", "body", "brouillon"].find((x) => a[x]), brouillon = k ? tx(a[k]) : "";
      const attend = p.etat === "attend" || p.etat === "reportee", l = (t, v) => '<div class="ag-ligne"><span class="g">' + t + "</span><b>" + esc(v) + "</b></div>";
      return '<div class="ag-prop"><div class="barre"><b style="flex:1;min-width:0;overflow-wrap:anywhere">' + esc(p.titre || p.capacite || "Proposition") + "</b>" + pill(p.nom || p.agent, "ac") + pill(p.risque || "risque ?", RISQUE[p.risque] || "") + (attend ? "" : pg(ETG[p.etat] || "", ETAT[p.etat] || p.etat, p.etat === "acceptee" ? "ok" : "")) + "</div>" +
        (p.resume ? '<p class="note">' + esc(p.resume) + "</p>" : "") + (p.pourquoi ? l("Pourquoi", p.pourquoi) : "") + (p.impact ? l("Impact", p.impact) : "") +
        (m ? '<div class="ag-mandat"><div class="ag-mod">Mandat d\'envoi</div>' + l("Mandat", m.nom || "") + l("De", m.de || (S.eq && S.eq.compte) || "") + l("À", m.a || "") + l("Objet", m.objet || "") + l("Validité", tx(m.validite)) + (brouillon ? '<div class="note">Brouillon</div><pre>' + esc(brouillon) + "</pre>" : "") + "</div>" : "") +
        (p.blocage ? '<p class="note" style="color:var(--danger)">' + esc(p.blocage) + "</p>" : "") +
        (p.etat === "reportee" && p.reporte_jusqua && Number(p.reporte_jusqua) > Date.now() / 1000 ? '<p class="note">Reportée jusqu\'au ' + esc(dateFr(p.reporte_jusqua)) + ".</p>" : "") +
        (attend ? '<div class="ag-puces"><button class="btn pri mini" data-prop="' + esc(p.id) + '" data-d="accepter"' + (p.executable === false ? ' disabled title="' + esc(p.blocage || "Cette proposition ne peut pas être exécutée") + '"' : "") + '>Accepter</button><button class="btn mini" data-prop="' + esc(p.id) + '" data-d="refuser">' + G("✕") + 'Refuser</button><button class="btn mini" data-prop="' + esc(p.id) + '" data-d="reporter">Plus tard</button><button class="btn mini" data-prop="' + esc(p.id) + '" data-d="reporter" data-jusqu="demain">Demain</button></div>' : (p.resultat ? '<p class="note">' + esc(tx(p.resultat).slice(0, 220)) + "</p>" : "")) +
        btnPq(p.acte) + "</div>";
    }
    async function decider(id, d, jusqu) {
      const p = S.props[id] || {};
      try { await API.decider(id, d, jusqu); }
      catch (e) {
        if (!(d === "accepter" && /palier/i.test(String((e && e.message) || e)))) throw e;
        if (!(await confirmer("Passer cette capacité en auto ?", '<p class="note">Le palier « raconter » de <span class="mono">' + esc(p.capacite || "") + "</span> ne se contourne pas par un accord : pour que " + esc(p.nom || p.agent || "l'agent") + " l'exécute, elle doit passer en « auto ». Tu peux la remettre en « raconter » dans l'onglet « Outils & palier ».</p>", "Passer en auto"))) return;
        await API.palier(p.agent, p.capacite, "auto"); await API.decider(id, d, jusqu);
      }
      S.attente = undefined; dire({ accepter: "Accepté : l'agent l'exécute", refuser: "Refusé : il s'en souviendra", reporter: "Reporté" }[d] || "C'est noté", "ok"); await dessiner();
    }
    async function oCout(f) {
      const a = f.agent, c = await API.couts(a.id, S.jours), jours = {};
      c.jours.forEach((x) => { jours[x.jour] = (jours[x.jour] || 0) + x.euros; });
      const cles = Object.keys(jours).sort(), max = Math.max.apply(null, [0.0001].concat(cles.map((k) => jours[k])));
      const pl = (c.plafonds || {})[a.id], glob = (c.plafonds || {}).global;
      const carteP = (portee, p, lib) => '<div class="ag-ligne"><span class="g">' + lib + "</span><b>" + (p ? eur(p.euros) + " par jour · " + esc((ACTIONS.find((x) => x[0] === p.action) || [0, p.action])[1]) : "aucun") + "</b></div>";
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(a.nom) + " dépense</h3>" + '<div class="seg" id="ag-jours">' + [7, 14, 30].map((j) => '<button data-j="' + j + '" class="' + (S.jours === j ? "on" : "") + '">' + j + " j</button>").join("") + "</div></div>" +
        '<div class="stats"><div class="stat"><b>' + eur(c.aujourdhui_euros) + "</b><span>aujourd'hui</span></div><div class=\"stat\"><b>" + eur(c.total_euros) + "</b><span>sur " + S.jours + " jours</span></div></div>" +
        (cles.length ? '<div class="ag-barres" role="img" aria-label="Coût par jour">' + cles.map((k) => '<i title="' + esc(k) + " : " + eur(jours[k]) + '" style="height:' + Math.max(3, jours[k] / max * 100) + '%"></i>').join("") + "</div>" : '<p class="note">Aucune dépense sur la période' + (a.id === "itare" ? " (un modèle local ne coûte rien)." : ".") + "</p>") + "</section>" +
        (S.admin ? '<section class="carte"><h3>Le plafond du jour</h3>' + carteP(a.id, pl, "Plafond de " + esc(a.nom)) + carteP("global", glob, "Plafond global") +
          '<p class="note">Le plus bas s\'applique. À l\'atteinte : secours, arrêt (Cassandra ne s\'arrête jamais) ou demande d\'accord.</p>' +
          '<div class="ag-champs"><label class="ag-f"><span>Montant par jour (€)</span><input type="number" min="0.01" step="0.01" id="ag-pl-e" value="' + (pl ? pl.euros : "") + '"></label>' +
          '<label class="ag-f"><span>À l\'atteinte</span><select id="ag-pl-a">' + ACTIONS.map(([k, l]) => '<option value="' + k + '"' + (pl && pl.action === k ? " selected" : "") + ">" + esc(l) + "</option>").join("") + "</select></label></div>" +
          '<div class="ag-puces"><button class="btn pri" id="ag-pl-poser">Poser le plafond de ' + esc(a.nom) + '</button><button class="btn" id="ag-pl-g">Poser le plafond global</button>' + (pl ? '<button class="btn" data-plaf="accorder">Accorder pour aujourd\'hui</button><button class="btn dng" data-plaf="lever">Lever</button>' : "") + "</div></section>" :
          '<section class="carte"><h3>Ton plafond</h3><p class="note">Les plafonds de coût se posent depuis l\'administration. Si l\'un retient Itare, la fiche te le dit.</p></section>');
    }
    const MATRICE = [
      ["Cassandra", "la machine, ses sites, ses certificats", "gère le Coffre (jamais la valeur dans un modèle)", "non", "non"],
      ["Itare", "non", "aucun outil de secret", "son bureau, lui seul", "non"],
      ["Amizo", "non", "aucun outil de secret", "non", "ce qui est partagé ; écrit sa bibliothèque seule"],
      ["Relecteur", "non", "reconnaît un secret par son empreinte, ne le garde pas", "relit chaque réponse finale", "non"],
      ["Vision", "non", "aucun outil de secret", "📎 pièces jointes (pas encore branché)", "non"],
    ];
    function vEpreuve(r) {
      const cas = (r.cas || []).map((c) => '<div class="li"><div class="sp"><b>' + esc(c.titre || c.id) + '</b><div class="note">' + esc(c.detail || "") + "</div></div>" + pill(c.reussi ? "réussi" : "échoué", c.reussi ? "ok" : "dg") + "</div>").join("");
      return '<div class="ag-puces">' + pill(r.reussies + "/" + r.total + " réussies", r.ok ? "ok" : "dg") + (r.injoignable ? pill("modèle injoignable : rien n'a été éprouvé", "dg") : r.deconseille ? pill("modèle déconseillé", "dg") : r.sert ? pill("peut servir", "ok") : "") + '<span class="note">' + esc(r.modele || "") + (r.quand ? " · " + esc(dateFr(r.quand)) : "") + "</span></div>" + (cas ? '<div class="liste">' + cas + "</div>" : "");
    }
    async function oSur(f) {
      let res = null, cor = [], sen = null, err = "";
      if (S.admin) {
        try { const r = await API.epreuvesResultats(); res = r.resultats || []; cor = r.corpus || []; } catch (e) { err = String((e && e.message) || e); }
        try { sen = await API.sentinelle(); } catch (e) { sen = null; }
      }
      const regles = '<section class="carte"><h3>' + G("🛡") + 'Les règles non négociables</h3>' + REGLES.map((r) => '<details style="border-top:1px solid var(--line);padding:7px 0"><summary style="cursor:pointer;font-weight:600">' + esc(r[0]) + '</summary><p class="note" style="margin-top:6px">' + esc(r[1]) + "</p></details>").join("") + "</section>";
      const matrice = '<section class="carte"><h3>Qui voit quoi</h3><div class="ag-tw"><table><tr><th>Agent</th><th>La machine</th><th>Les secrets</th><th>Un bureau</th><th>La connaissance</th></tr>' + MATRICE.map((r) => "<tr>" + r.map((c, i) => (i ? "<td>" : "<td><b>") + esc(c) + (i ? "</td>" : "</b></td>")).join("") + "</tr>").join("") + "</table></div>" +
        '<p class="note">Un compte ne règle et ne lit que son Itare ; administrer n\'est pas voir le bureau d\'un autre.</p></section>';
      if (!S.admin) return regles + matrice;
      if (err) return regles + matrice + nonBranche("Les épreuves de sûreté", err);
      const modele = f && f.agent ? f.agent.modele || "" : "";
      const hist = res.length ? '<div class="liste">' + res.map((r) => '<div class="li"><div class="sp"><b>' + esc(r.modele) + '</b><div class="note">' + esc(dateFr(r.quand || r.ts)) + "</div></div>" + pill(r.reussies + "/" + r.total, r.ok ? "ok" : "dg") + (r.injoignable ? pill("injoignable", "dg") : r.deconseille ? pill("déconseillé", "dg") : "") + "</div>").join("") + "</div>" : '<p class="note">Aucun modèle n\'a encore passé les épreuves.</p>';
      const epr = '<section class="carte"><h3>Les épreuves de sûreté</h3><p class="note">Huit pièges rejoués à blanc, avec des outils-bouchons : rien n\'est touché. À faire avant de confier un agent à un autre modèle.</p>' +
        '<div class="ag-ecrire"><input type="text" id="ag-ep-m" value="' + esc(modele) + '" placeholder="rôle ou nom du modèle" aria-label="Modèle à éprouver"><button class="btn pri" id="ag-ep-go">Lancer les épreuves</button></div><div id="ag-ep-r" style="margin-top:8px"></div>' +
        '<div class="note" style="margin:10px 2px 2px"><b>Derniers passages</b></div>' + hist +
        '<details style="border-top:1px solid var(--line);padding:7px 0;margin-top:8px"><summary style="cursor:pointer;font-weight:600">Les huit cas</summary>' + cor.map((c) => '<p class="note"><b>' + esc(c.titre) + "</b><br>" + esc(c.attendu || "") + "</p>").join("") + "</details></section>";
      const sent = sen ? '<section class="carte"><h3>La sentinelle anti-fuite</h3><p class="note">Le Relecteur retient toute réponse qui contient un secret connu ou un ordre caché. Seules l\'étiquette et la longueur d\'un secret sont gardées, jamais sa valeur.</p><div class="ag-puces">' + pill((sen.secrets || []).length + " secrets connus") + pill((sen.relectures_retenues || 0) + " réponses retenues", sen.relectures_retenues ? "al" : "") + "</div>" +
        ((sen.secrets || []).length ? '<div class="liste">' + sen.secrets.map((x) => '<div class="li"><div class="sp"><b>' + esc(x.etiquette) + '</b></div><span class="note">' + esc(x.longueur) + " caractères</span></div>").join("") + "</div>" : "") + "</section>" : "";
      return regles + matrice + epr + sent;
    }
    async function oMemoire(f) {
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(f.agent.nom) + ' sait</h3>' + lien("memory", "Ouvrir la Mémoire") + '</div><p class="note">La mémoire vit dans son module : un seul propriétaire par donnée. Rien n\'est copié ici ; le bouton ouvre l\'écran Mémoire.</p></section>';
    }
    async function oReglages(f) {
      const a = f.agent, L = a.limites || {};
      let declares = []; try { declares = (await CASS.agir("modeles.lister")).modeles || []; } catch (e) { /* le registre est lent ou fermé : la liste de suggestions se réduit aux rôles */ }
      const sug = '<datalist id="ag-sugg">' + ["principal", "itare_citadelle", "vision", "relecteur", "second_avis"].map((r) => '<option value="' + r + '">rôle</option>').join("") + declares.map((m) => '<option value="' + esc(m.id) + '">' + esc(m.nom + " (" + m.fournisseur + ")") + "</option>").join("") + "</datalist>";
      const num = (k, lib, def) => '<label class="ag-f"><span>' + lib + '</span><input type="number" data-lim="' + k + '" value="' + (L[k] != null ? L[k] : "") + '" placeholder="' + def + '"></label>';
      return '<section class="carte"><h3>Nom, ton et modèle</h3><div class="ag-champs"><label class="ag-f"><span>Nom affiché</span><input type="text" id="ag-nom" maxlength="40" value="' + esc(a.nom) + '"></label>' +
        '<label class="ag-f"><span>Modèle principal</span><input type="text" id="ag-mod" list="ag-sugg" maxlength="80" value="' + esc(a.modele) + '" placeholder="rôle ou modèle"></label>' +
        '<label class="ag-f"><span>Modèle de secours</span><input type="text" id="ag-sec" list="ag-sugg" maxlength="80" value="' + esc(a.secours) + '" placeholder="aucun"></label></div>' + sug +
        '<p class="note">Un rôle (principal, vision…) ou un modèle déclaré. Les clés d’API et les modèles locaux se gèrent dans <button class="btn" id="ag-modeles" type="button" style="padding:3px 10px">Modèles et clés</button></p>' +
        '<label class="ag-f"><span>Ton</span><textarea id="ag-ton" maxlength="2000" placeholder="vide : le ton d\'origine">' + esc(a.ton) + "</textarea></label>" +
        '<div><button class="btn pri" id="ag-sauve">Enregistrer</button></div></section>' +
        '<section class="carte"><h3>Limites d\'un tour</h3><div class="ag-champs">' + num("max_tours", "Étapes d'outils", "défaut du module") + num("max_jetons", "Jetons par réponse", "défaut du module") + num("taille_fil", "Messages relus", "défaut du module") + num("tarif_entree_cts", "Tarif entrée (cts / M jetons)", String((a.tarifs_cts || [])[0])) + num("tarif_sortie_cts", "Tarif sortie (cts / M jetons)", String((a.tarifs_cts || [])[1])) + "</div>" +
        '<div><button class="btn pri" id="ag-lim">Enregistrer les limites</button></div></section>' +
        '<section class="carte"><h3>Ailleurs, chez leur propriétaire</h3><div class="ag-puces">' + lien("proactive", "Proactivité") + lien("settings", "Canaux et voix") + (S.admin ? lien("memory", "Mémoire") : "") + "</div><p class=\"note\">Ces réglages ne sont pas recopiés ici : chaque écran s'ouvre chez son module.</p></section>";
    }

    // ── conversations ────────────────────────────────────────────────────────
    async function vConv() {
      if (!S.conv.liste) S.conv.liste = (await API.conversations()).conversations || [];
      const L = S.conv.liste;
      const choix = (S.admin ? ["cassandra", "itare", "amizo"] : ["itare"]);
      const liste = '<section class="carte"><div class="barre"><h3 style="flex:1">Conversations</h3>' + (S.admin ? '<select class="sel" id="cv-ag">' + choix.map((x) => '<option value="' + x + '"' + (S.conv.agent === x ? " selected" : "") + ">avec " + x + "</option>").join("") + "</select>" : "") + '<button class="btn pri mini" id="cv-neuve">Nouvelle</button></div><input type="search" id="cv-q" placeholder="Chercher une conversation…" value="' + esc(S.conv.q || "") + '">' +
        (L.length ? L.filter((c) => !S.conv.q || (c.titre || "Sans titre").toLowerCase().includes(S.conv.q.toLowerCase())).map((c) => '<button class="ag-sel' + (S.conv.id === c.id ? " on" : "") + '" data-cv="' + c.id + '"><div class="sp"><b>' + esc(c.titre || "Sans titre") + '</b><div class="note">' + esc(c.agent) + " · " + c.n + " messages · " + esc(dateFr(c.maj)) + "</div></div></button>").join("") : '<div class="vide">Aucune conversation.</div>') + "</section>";
      let droite = '<section class="carte"><div class="vide">Choisis une conversation, ou ouvres-en une nouvelle.</div></section>';
      if (S.conv.id) {
        const d = await API.conversation(S.conv.id);
        const fil = d.messages.map((m) => {
          if (m.role === "tool") return '<div class="ag-m outil">' + G("⚙") + esc(m.nom || "outil") + (m.statut ? " · " + esc(m.statut) : "") + (m.evenement ? btnPq(m.evenement) : "") + "</div>";
          if (m.role === "panne") return '<div class="ag-m outil" style="color:var(--danger)">' + esc(m.contenu) + "</div>";
          if (!m.contenu && m.appels) return '<div class="ag-m outil">appelle ' + esc((m.appels || []).map((c) => (c.function && c.function.name) || c.nom || "outil").join(", ")) + "</div>";
          return '<div class="ag-m' + (m.role === "user" ? " moi" : "") + '">' + esc(m.contenu) + (m.actions || []).filter((x) => x && x.evenement).map((x) => '<div class="note">↳ ' + esc(x.outil || x.capacite || "geste") + btnPq(x.evenement) + "</div>").join("") + "</div>";
        }).join("");
        droite = '<section class="carte"><div class="barre"><h3 style="flex:1">' + esc(d.conversation.titre || "Sans titre") + " · " + esc(d.conversation.agent) + '</h3><button class="btn mini" id="cv-ren">Renommer</button><button class="btn mini dng" id="cv-sup">Supprimer</button></div>' +
          '<div class="ag-fil" id="cv-fil">' + (fil || '<div class="vide">Aucun message.</div>') + "</div>" + (d.en_cours ? '<p class="note">Un tour est en cours…</p>' : "") +
          '<div class="ag-ecrire"><textarea id="cv-t" placeholder="Écris un message…" aria-label="Message"></textarea><button class="btn pri" id="cv-go">Envoyer</button></div></section>';
      }
      return '<div class="ag-conv">' + liste + droite + "</div>";
    }

    // ── à valider ────────────────────────────────────────────────────────────
    async function vBoite() {
      let p;
      try { p = await API.propositions(); } catch (e) { S.attente = null; return nonBranche("À valider", String((e && e.message) || e)); }
      const l = (p.propositions || []).filter((x) => S.admin || x.agent === "itare");
      S.attente = l.length;
      return '<section class="carte"><h3>À valider</h3><p class="note">Seulement ce qui part vers l\'extérieur, ne se défait pas ou sort du palier. L\'agent propose, tu décides.</p>' + (l.length ? l.map((x) => carteProp(x)).join("") : '<div class="vide">Rien n\'attend ton mot. Quand un agent voudra faire quelque chose qui sort du cadre, ce sera ici.</div>') + "</section>";
    }

    // ── journal ──────────────────────────────────────────────────────────────
    async function vJournal() {
      const ord = (x) => ((MEM.regles || {}).ordre_journal === "ancien" ? x.slice().reverse() : x);
      let l = []; const F = S.jf = S.jf || { ag: "tous", q: "", n: 8 }, q = F.q.toLowerCase();
      let ac; try {
        const tous = (await actes("")).filter((x) => (F.ag === "tous" || x.agent === F.ag) && (!q || ((x.titre || "") + " " + (x.resume || "") + " " + (x.pourquoi || "")).toLowerCase().includes(q)));
        if ((MEM.regles || {}).ordre_journal === "ancien") tous.reverse();
        ac = ligneActes(tous.slice(0, F.n)) + (tous.length > F.n ? '<div class="ag-puces"><span class="note">' + F.n + " sur " + tous.length + ' affichés</span><button class="btn mini" id="jf-plus">Voir plus</button></div>' : "");
      } catch (e) { ac = nonBranche("Actes", String((e && e.message) || e)); }
      const filtres = '<div class="barre">' + (S.admin ? '<select class="sel" id="jf-a"><option value="tous">Tous les agents</option>' + (S.eq.equipe || []).filter((a) => a.genre === "agent").map((a) => '<option value="' + esc(a.id) + '"' + (F.ag === a.id ? " selected" : "") + ">" + esc(a.nom) + "</option>").join("") + "</select>" : "") + '<input type="search" id="jf-q" placeholder="Chercher dans le journal…" value="' + esc(F.q) + '"></div>';
      // le flux du module journal n'est pas cloisonné par compte (journaux système compris) : un compte ordinaire lit ses actes par les propositions, jamais le flux
      if (!S.admin) return '<section class="carte"><h3>Ce que ton Itare a fait</h3>' + filtres + ac + "</section>";
      try { l = (await API.journal("", 80)).entrees.filter(mien); } catch (e) { return nonBranche("Journal", String(e.message || e)); }
      if (S.admin) l = l.filter((e) => /cassandra|itare|amizo|agent|relecteur|vision/i.test((e.acteur || "") + " " + (e.source || "") + " " + (e.label || "")));
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que les agents ont fait</h3>' + lien("journal", "Ouvrir les Journaux") + "</div>" + filtres + ac + '<div class="note" style="margin:10px 2px 2px"><b>Dans le journal du noyau</b></div>' + ligneJournal(ord(q ? l.filter((e) => ((e.action || "") + " " + (e.sujet || "") + " " + (e.label || "")).toLowerCase().includes(q)) : l)) + "</section>";
    }

    // ── modèles et clés ──────────────────────────────────────────────────────
    function registreHtml(reg) {
      const eq = S.eq.equipe;
      const ms = (reg && reg.modeles) || [], roles = (reg && reg.roles) || {}, nomM = (m) => esc(m.nom || m.id || m.modele || "modèle"), tm = (v) => (v && typeof v === "object" ? (v.modele || v.nom || v.id || "") : v || "");
      const chaine = eq.filter((a) => a.genre === "agent").map((a) => '<div class="ag-ligne"><span class="g">' + esc(a.nom) + "</span><b>" + esc(a.modele || tm(roles[a.id]) || "rôle par défaut") + ' <span class="note">→</span> ' + esc(a.secours || "pas de secours") + ' <span class="note">→</span> ' + (a.plafond_atteint ? "plafond atteint : le secours seul" : "arrêt propre, jamais un silence") + "</b></div>").join("");
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Le registre des modèles</h3><button class="btn" id="ag-reg">Ouvrir le registre des modèles</button></div>' +
        (reg ? (ms.length ? '<div class="liste">' + ms.map((m) => '<div class="li"><div class="sp"><b>' + nomM(m) + '</b><div class="note">' + esc([m.fournisseur, m.modele && m.modele !== m.nom ? m.modele : "", m.cle === false || m.cle_presente === false ? "clé manquante" : ""].filter(Boolean).join(" · ")) + "</div></div></div>").join("") + "</div>" : '<p class="note">Aucun modèle enregistré pour l\'instant : ajoute un fournisseur et sa clé dans le registre. Les clés sont des réglages « secret » du noyau, jamais relues ici.</p>') : '<p class="note">Le registre n\'a pas répondu.</p>') +
        (Object.keys(roles).length ? '<div class="note" style="margin:8px 2px 2px"><b>Rôles</b></div>' + Object.keys(roles).sort().map((k) => '<div class="ag-ligne"><span class="g">' + esc(k) + "</span><b>" + esc(tm(roles[k])) + "</b></div>").join("") : "") + "</section>" +
        '<section class="carte"><h3>La chaîne de secours</h3><p class="note">Ce que chaque agent essaie, dans l\'ordre. Un modèle déconseillé aux épreuves de sûreté n\'est pas employé quand l\'exigence est active.</p>' + chaine + "</section>";
    }
    // le registre des modèles est lent à lire (il sonde le serveur local) : la page s'ouvre sur ce qu'on sait déjà, il se peint dès qu'il arrive
    function peindreRegistre() {
      const z = racine.querySelector("#ag-mreg"); if (!z || typeof S.reg !== "string") return;
      z.innerHTML = S.reg; sur("#ag-reg", "click", () => { if (CASS.ouvrirConsole) CASS.ouvrirConsole("modeles", "Modèles"); });
    }
    async function vModeles() {
      const eq = S.eq.equipe; S.reg = null; const moi = dessin;
      API.registre().then((r) => r, () => null).then((reg) => { if (moi !== dessin) return; S.reg = registreHtml(reg); peindreRegistre(); });
      return '<div id="ag-mreg" style="display:flex;flex-direction:column;gap:12px"><section class="carte"><h3>Le registre des modèles</h3>' + SQ_PETIT + "</section></div>" + '<section class="carte"><div class="barre"><h3 style="flex:1">Quel modèle fait parler qui</h3></div>' +
        '<div class="ag-tw"><table><tr><th>Agent</th><th>Modèle</th><th>Secours</th><th>Coût du jour</th></tr>' + eq.map((a) => "<tr><td>" + esc(a.nom) + "</td><td>" + esc(a.modele || "par défaut") + "</td><td>" + esc(a.secours || "aucun") + "</td><td>" + (a.cout_jour && a.cout_jour.euros ? eur(a.cout_jour.euros) : "gratuit") + "</td></tr>").join("") + "</table></div>" +
        '<p class="note">Le registre (fournisseurs, clés, tarifs) reste dans le module Modèles ; les clés sont des réglages « secret » du noyau, jamais lues ici. Le modèle d\'un agent se règle dans sa fiche, onglet « Réglages ».</p></section>';
    }

    // ── le dessin et les gestes ──────────────────────────────────────────────
    // l'équipe se lit lentement à froid : un seul appel en vol pour tous ceux qui l'attendent, et seul le dernier dessin compte (ouverture + clic du menu + retour d'onglet arrivent ensemble)
    let eqEnVol = null, dessin = 0;
    const equipe = () => (MEM.eq && Date.now() - MEM.t < 30000 ? Promise.resolve(MEM.eq) : eqEnVol || (eqEnVol = API.equipe().then((r) => { MEM.eq = r; MEM.t = Date.now(); return r; }).finally(() => { eqEnVol = null; })));
    let enCours = null, cle = "";
    function dessiner() {                                          // la même page demandée deux fois de suite (ouverture + menu) ne se dessine qu'une fois
      const k = S.vue + "|" + S.agent + "|" + S.onglet;
      if (enCours && cle === k) return enCours;
      cle = k; const p = dessinerVraiment(); enCours = p; p.finally(() => { if (enCours === p) enCours = null; }); return p;
    }
    async function dessinerVraiment() {
      let html; const moi = ++dessin;
      const v0 = racine.querySelector("#ag-vue");
      if (v0) v0.style.opacity = ".5"; else racine.innerHTML = SQ;
      try {
        const pEq = S.eq ? Promise.resolve(S.eq) : equipe();
        const pRg = MEM.regles ? Promise.resolve() : API.regles().then((r) => { MEM.regles = r; }, () => { MEM.regles = {}; });
        const pAt = S.attente === undefined ? API.propositions().then((r) => (r && r.propositions) || [], () => null) : null;
        S.eq = S.eq || await pEq; S.lu = S.lu || Date.now();
        await pRg;
        appliquerVoc(MEM.regles);
        S.admin = !!S.eq.administrateur;
        if (!S.vue) S.vue = S.admin ? "equipe" : "fiche";
        if (!S.admin && !["fiche", "conv", "boite", "journal"].includes(S.vue)) S.vue = "fiche";
        if (pAt) { const l = await pAt; S.attente = l ? l.filter((x) => S.admin || x.agent === "itare").length : null; }
        const f = { equipe: vEquipe, fiche: vFiche, conv: vConv, boite: vBoite, journal: vJournal, auditeur: vAuditeur, maison: vMaison, modeles: vModeles }[S.vue];
        const mj = (MEM.regles || {}).mauvais_jour;
        html = '<div id="ag-vue" style="display:flex;flex-direction:column;gap:12px">' + (mj && mj.actif ? '<section class="carte" role="status" style="border-color:var(--warn,#b45309)"><div class="barre"><div class="sp"><b>' + G("⏸") + 'Mauvais jour en cours</b><div class="note">Tous les agents racontent au lieu de faire' + (mj.jusqua ? " jusqu\'à " + esc(dateFr(mj.jusqua)) : " jusqu\'à ce que tu lèves") + ".</div></div>" + (S.admin ? '<button class="btn" data-mj-lever="1">Lever</button>' : "") + "</div></section>" : "") + await f() + "</div>";
      } catch (e) { html = '<div class="vide">' + esc((e && e.message) || e) + "</div>"; }
      if (moi !== dessin) return;                                                     // un dessin plus récent est parti : il écrira seul
      racine.innerHTML = html; brancher();
      if (typeof window.agentsSuivre === "function") window.agentsSuivre(pageMenu(), S.attente == null ? 0 : S.attente);
      const sc = corps.closest(".sh-scene"), ti = sc && sc.querySelector(".sh-titre");           // le titre suit la page choisie dans le menu
      if (ti) ti.textContent = { equipe: "L’équipe", conv: "Conversations", boite: "À valider", journal: "Journal", auditeur: "Auditeur", maison: "Règles communes", modeles: "Modèles & clés" }[S.vue] || ((S.eq && S.eq.equipe.find((x) => x.id === S.agent) || {}).nom || "Agents IA");
    }
    const recharger = (eq) => { if (eq) { S.eq = null; S.lu = 0; MEM.eq = null; MEM.regles = null; } return dessiner(); };
    const aller = (v, agent, onglet) => { S.vue = v; if (agent) S.agent = agent; if (onglet) S.onglet = onglet; if (v === "conv") S.conv.liste = null; dessiner(); };
    const sur = (sel, ev, fn) => racine.querySelectorAll(sel).forEach((el) => el.addEventListener(ev, (e) => fn(el, e)));
    const b0 = (off) => { const b = racine.querySelector("#ag-ep-go"); if (b) b.disabled = off; };
    const lancer = async (fn, ok) => { try { await fn(); if (ok) dire(ok, "ok"); } catch (e) { erreur(e); } };
    // la carte de confiance se peint après coup : son bouton se lit par délégation
    racine.addEventListener("click", (ev) => { const b = ev.target.closest("[data-auto]"); if (!b) return;
      lancer(async () => {
        const o = b.dataset.auto; if (!(await confirmer("Passer « " + o + " » en auto ?", '<p class="note">Huit validations de suite l\'y autorisent. Elle recule d\'elle-même après deux échecs de suite (règle du noyau).</p>', "Passer en auto"))) return;
        await API.palier(S.agent, o, "auto"); await recharger(true);
      }, "Palier posé : auto");
    });

    function brancher() {
      peindreGestes(); peindreRegistre();
      sur("[data-agent]", "click", (b) => (b.dataset.agent === "auditeur" ? aller("auditeur") : aller("fiche", b.dataset.agent, b.dataset.onglet || "apercu")));
      sur("#ag-ong [data-o]", "click", (b) => { S.onglet = b.dataset.o; dessiner(); });
      sur("[data-onglet-vers]", "click", (b) => { S.onglet = b.getAttribute("data-onglet-vers"); dessiner(); });
      sur("[data-chez]", "click", (b) => chez(b.dataset.chez, b.dataset.q));
      sur("#ag-chg", "change", (s) => aller("fiche", s.value));
      sur("[data-niveau]", "click", (b) => lancer(async () => { const avant = S.fiche.agent.niveau; await API.niveau(S.agent, b.dataset.niveau); dire("Palier réglé : " + b.dataset.niveau + " (avant : " + avant + ")", "ok"); await recharger(true); }));
      if (!racine.__outils) { racine.__outils = 1; racine.addEventListener("click", (ev) => { const b = ev.target.closest("[data-outil]"); if (b) outilClic(b); const t = ev.target.closest("[data-fam-tout]"); if (t) { S.ouv = S.ouv.size ? new Set() : new Set(Object.keys(S.grp || {})); dessiner(); } });
        racine.addEventListener("change", (ev) => { const c = ev.target.closest("[data-conf]"); if (c) lancer(async () => { await API.palier(S.agent, c.dataset.conf, "", c.checked); await recharger(true); }); });
        racine.addEventListener("toggle", (ev) => { const d = ev.target; if (!d.matches || !d.matches("details[data-fam]")) return; const m = d.dataset.fam; S.ouv = S.ouv || new Set();
          if (d.open) { S.ouv.add(m); const c = d.querySelector(".ag-fam-c"); if (c && !c.firstChild && S.grp && S.grp[m]) c.innerHTML = S.grp[m].map(S.ligne).join(""); } else S.ouv.delete(m); }, true); }
      const outilClic = (b) => lancer(async () => {
        const p = b.dataset.p, o = b.dataset.outil, retirer = p === "retire", lect = p === "lecture";
        if (retirer) { const ok = await confirmer("Retirer cet outil ?", '<p class="note"><span class="mono">' + esc(o) + "</span> ne sera plus présenté à " + esc(S.fiche.agent.nom) + ". Tu pourras le rétablir.</p>", "Retirer", true); if (!ok) return; }
        await API.palier(S.agent, o, lect ? "defaut" : p, retirer ? false : undefined); await recharger(true);
      });
      sur("#ag-q", "input", (i) => { S.filtre.q = i.value; clearTimeout(S.tq); S.tq = setTimeout(async () => { const pos = i.selectionStart; await dessiner(); const n = racine.querySelector("#ag-q"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 250); });
      sur("#ag-r", "change", (s) => { S.filtre.risque = s.value; dessiner(); });
      sur("[data-rap]", "click", (b) => { S.rapLong = b.dataset.rap === "long"; dessiner(); });
      sur("#ag-t-new", "click", () => { S.tForm = !S.tForm; dessiner(); });
      sur("#ag-t-go", "click", () => lancer(async () => { const g = (id) => racine.querySelector(id).value; await API.tacheConfier({ agent: g("#ag-t-ag"), consigne: g("#ag-t-c"), frequence: g("#ag-t-fr"), heure: g("#ag-t-h"), jour: g("#ag-t-j") }); S.tForm = false; await dessiner(); }, "Tâche confiée"));
      sur("[data-tr]", "click", (b) => lancer(async () => { if (!(await confirmer("Retirer cette tâche ?", '<p class="note">Elle ne reviendra plus. Tu pourras la confier de nouveau.</p>', "Retirer", true))) return; await API.tacheRetirer(Number(b.dataset.tr)); await dessiner(); }, "Tâche retirée"));
      sur("[data-tl]", "click", (b) => lancer(async () => { b.disabled = true; const r = await API.tacheLancer(Number(b.dataset.tl)); dire("Tour joué" + (r && r.conversation_id ? " : la conversation " + r.conversation_id + " est dans Conversations" : ""), "ok"); await dessiner(); }));
      sur("#ag-ja [data-ja]", "click", (b) => { S.jauditeur = +b.dataset.ja; dessiner(); });
      sur("#ag-jours [data-j]", "click", (b) => { S.jours = +b.dataset.j; dessiner(); });
      sur("#ag-modeles", "click", () => { if (CASS.ouvrirConsole) CASS.ouvrirConsole("modeles", "Modèles"); });
      sur("#ag-sauve", "click", () => lancer(async () => {
        const g = (id) => racine.querySelector(id).value;
        await API.regler(S.agent, { nom_affiche: g("#ag-nom"), modele: g("#ag-mod"), secours: g("#ag-sec"), ton: g("#ag-ton") }); await recharger(true);
      }, "Réglages enregistrés"));
      sur("#ag-lim", "click", () => lancer(async () => {
        const lim = {}; racine.querySelectorAll("[data-lim]").forEach((i) => { lim[i.dataset.lim] = i.value === "" ? null : parseInt(i.value, 10); });
        await API.regler(S.agent, { limites: lim }); await recharger(true);
      }, "Limites enregistrées"));
      sur("#ag-pl-poser", "click", () => lancer(async () => { const e = parseFloat(racine.querySelector("#ag-pl-e").value); if (!(e > 0)) throw new Error("un montant positif est requis"); await API.plafond(S.agent, e, racine.querySelector("#ag-pl-a").value); await recharger(true); }, "Plafond posé"));
      sur("[data-mj]", "click", (b) => lancer(async () => { if (!(await confirmer("Passer en mauvais jour ?", '<p class="note">Tous les agents racontent au lieu de faire, ' + (b.dataset.mj === "0" ? "jusqu\'à ce que tu lèves." : "pendant " + b.dataset.mj + " h, puis reviennent seuls.") + "</p>", "Passer en mauvais jour", true))) return; await API.mauvaisJour(Number(b.dataset.mj)); MEM.regles = null; S.bilanMJ = null; await dessiner(); }, "Mauvais jour posé"));
      sur("[data-mj-lever]", "click", () => lancer(async () => { const r = await API.mauvaisJourLever(); S.bilanMJ = (r && (r.raconte || (r.mauvais_jour && r.mauvais_jour.raconte))) || []; MEM.regles = null; await dessiner(); }, "Mauvais jour levé"));
      sur("[data-rgp]", "click", (b) => lancer(async () => { await API.reglesRegler({ palier_defaut: b.dataset.rgp }); MEM.regles = null; await dessiner(); }, "Réglage posé"));
      sur("[data-rgo]", "click", (b) => lancer(async () => { await API.reglesRegler({ ordre_journal: b.dataset.rgo }); MEM.regles = null; await dessiner(); }, "Réglage posé"));
      sur("#ag-rg-d", "change", (c) => lancer(async () => { await API.reglesRegler({ dehors_par_amizo: c.checked }); MEM.regles = null; await dessiner(); }, "Réglage posé"));
      sur("#ag-gl-poser", "click", () => lancer(async () => { const e = parseFloat(racine.querySelector("#ag-gl-e").value); if (!(e > 0)) throw new Error("un montant positif est requis"); await API.plafond("global", e, racine.querySelector("#ag-gl-a").value); await recharger(true); }, "Plafond global posé"));
      sur("#ag-gl-lever", "click", () => lancer(async () => { if (!(await confirmer("Lever le plafond global ?", '<p class="note">Les agents ne seront plus retenus que par leur propre plafond.</p>', "Lever", true))) return; await API.plafond("global", null, "secours"); await recharger(true); }, "Plafond global levé"));
      sur("#ag-pl-g", "click", () => lancer(async () => { const e = parseFloat(racine.querySelector("#ag-pl-e").value); if (!(e > 0)) throw new Error("un montant positif est requis"); await API.plafond("global", e, racine.querySelector("#ag-pl-a").value); await recharger(true); }, "Plafond global posé"));
      sur("[data-plaf]", "click", (b) => lancer(async () => {
        if (b.dataset.plaf === "accorder") { await API.plafond(S.agent, null, "accord", true); }
        else { if (!(await confirmer("Lever le plafond ?", '<p class="note">' + esc(S.fiche.agent.nom) + " ne sera plus retenu par un plafond de coût.</p>", "Lever", true))) return; await API.plafond(S.agent, null, "secours"); }
        await recharger(true);
      }));
      sur("[data-prop]", "click", (b) => lancer(() => decider(Number(b.dataset.prop), b.dataset.d, b.dataset.jusqu)));
      sur("[data-pq]", "click", (b) => lancer(async () => {
        const z = racine.querySelector("#pq-" + b.dataset.pq); if (!z) return;
        if (z.innerHTML) { z.innerHTML = ""; return; }
        z.innerHTML = '<p class="note">Lecture…</p>'; z.innerHTML = vPourquoi(await API.pourquoi(Number(b.dataset.pq)));
        z.querySelectorAll("[data-chez]").forEach((x) => x.addEventListener("click", () => chez(x.dataset.chez, x.dataset.q)));
      }));
      if (!racine.__df) { racine.__df = 1; racine.addEventListener("click", (ev) => { const b = ev.target.closest("[data-df]"); if (!b) return; lancer(async () => {
        const acte = Number(b.dataset.df);
        if (!(await confirmer("Défaire ce geste ?", '<p class="note">Le retour arrière de la capacité est rejoué, une seule fois, et le journal le raconte. On ne peut pas le rejouer ensuite.</p>', "Défaire", true))) return;
        await API.defaire(acte, "demandé depuis l'écran"); dire("Geste défait", "ok");
        const z = racine.querySelector("#pq-" + acte); if (z) z.innerHTML = vPourquoi(await API.pourquoi(acte));
      }); }); }
      sur("#ag-ep-go", "click", () => lancer(async () => {
        const m = racine.querySelector("#ag-ep-m").value.trim(); if (!m) throw new Error("indique le modèle à éprouver");
        const z = racine.querySelector("#ag-ep-r"); z.innerHTML = '<p class="note" role="status">Épreuves en cours : huit cas, jusqu\'à une demi-minute…</p>'; b0(true);
        try { z.innerHTML = vEpreuve(await API.epreuvesLancer(m)); } finally { b0(false); }
      }));
      // essai en direct (une conversation à part, tenue dans la fiche)
      sur("#ag-essai-go", "click", () => lancer(async () => {
        const t = racine.querySelector("#ag-essai-t"), fil = racine.querySelector("#ag-essai-fil"), m = t.value.trim(); if (!m) return;
        t.value = ""; if (fil.querySelector(".vide")) fil.innerHTML = ""; fil.insertAdjacentHTML("beforeend", '<div class="ag-m moi">' + esc(m) + '</div><div class="ag-m outil" id="ag-att">…</div>');
        const r = await API.converser(S.essaiId || 0, m, S.agent); S.essaiId = r.conversation_id || r.id || S.essaiId;
        const att = racine.querySelector("#ag-att"); if (att) att.outerHTML = '<div class="ag-m">' + esc(r.texte || r.message || r.reponse || "(l'agent a répondu)") + "</div>";
      }));
      // conversations
      sur("[data-cv]", "click", (b) => { S.conv.id = +b.dataset.cv; dessiner(); });
      sur("#cv-ag", "change", (s) => { S.conv.agent = s.value; });
      sur("#jf-a", "change", (x) => { S.jf.ag = x.value; S.jf.n = 8; dessiner(); });
      sur("#jf-plus", "click", () => { S.jf.n += 8; dessiner(); });
      sur("#jf-q", "input", (i) => { S.jf.q = i.value; S.jf.n = 8; clearTimeout(S.tq); S.tq = setTimeout(async () => { const pos = i.selectionStart; await dessiner(); const n = racine.querySelector("#jf-q"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 250); });
      sur("#cv-q", "input", (i) => { S.conv.q = i.value; clearTimeout(S.tq); S.tq = setTimeout(async () => { const pos = i.selectionStart; await dessiner(); const n = racine.querySelector("#cv-q"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 200); });
      sur("#cv-neuve", "click", () => lancer(async () => { const r = await API.creer(S.conv.agent); S.conv.id = r.id; S.conv.liste = null; await dessiner(); }));
      sur("#cv-ren", "click", () => lancer(async () => { const ok = confirmer("Renommer la conversation", '<input type="text" id="cv-titre" maxlength="120" value="' + esc(((S.conv.liste || []).find((c) => c.id === S.conv.id) || {}).titre || "") + '" aria-label="Nouveau titre">', "Renommer"), champ = document.querySelector(".kit-m #cv-titre"); if (champ) champ.focus(); if (!(await ok) || !champ || !champ.value.trim()) return; await API.renommer(S.conv.id, champ.value.trim()); S.conv.liste = null; await dessiner(); }));
      sur("#cv-sup", "click", () => lancer(async () => { if (!(await confirmer("Supprimer la conversation ?", '<p class="note">Elle disparaît avec ses messages.</p>', "Supprimer", true))) return; await API.supprimer(S.conv.id); S.conv.id = 0; S.conv.liste = null; await dessiner(); }));
      sur("#cv-go", "click", () => lancer(async () => {
        const t = racine.querySelector("#cv-t"), m = t.value.trim(); if (!m || S.conv.occupe) return; S.conv.occupe = true; t.disabled = true;
        racine.querySelector("#cv-fil").insertAdjacentHTML("beforeend", '<div class="ag-m moi">' + esc(m) + '</div><div class="ag-m outil">…</div>');
        try { await API.converser(S.conv.id, m, undefined); } finally { S.conv.occupe = false; S.conv.liste = null; await dessiner(); const f = racine.querySelector("#cv-fil"); if (f) f.scrollTop = f.scrollHeight; }
      }));
      const f = racine.querySelector("#cv-fil"); if (f) f.scrollTop = f.scrollHeight;
    }

    // revenir sur l'onglet recharge l'écran (le compte a pu changer)
    const onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait && racine.isConnected) { if (Date.now() - (S.lu || 0) > 30000) { S.eq = null; S.lu = 0; MEM.eq = null; S.attente = undefined; } S.conv.liste = null; dessiner(); } etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    const cible = String((ctx && ctx.ecran) || "").split(":")[1] || "";
    if (cible && ["equipe", "conv", "boite", "journal", "modeles", "fiche"].includes(cible)) S.vue = cible;
    // le menu de gauche demande une page : à l'ouverture (window.__agentsVue) ou, l'écran étant déjà là, par agentsAller
    window.agentsAller = () => { const v = window.__agentsVue; window.__agentsVue = ""; if (!racine.isConnected) return; if (v) depuisMenu(v); dessiner(); };
    if (window.__agentsVue) { depuisMenu(window.__agentsVue); window.__agentsVue = ""; }
    await dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
