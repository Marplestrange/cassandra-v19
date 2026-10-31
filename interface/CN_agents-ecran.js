// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, c
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ef3639
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, ce qui attend l'utilisateur, le journal, les modèles.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ef3639 ▼▼▼
// L'écran « Agents IA » : l'équipe, la fiche d'un agent et ses onglets, les conversations, ce qui attend l'utilisateur, le journal, les modèles.
// Les données viennent du module agents (equipe, agent, paliers, couts, conversations, conversation, converser, propositions) ; le journal vient du module journal.
// Un propriétaire par donnée : Mémoire, Journaux, Canaux, Voix et Proactivité restent chez eux, la fiche les ouvre (jamais de copie).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, ic = K.ic, pill = K.pill, dire = K.dire, confirmer = K.confirmer;

  // ── la couche d'appels : tout ce que l'écran demande au module passe ici (un contrat qui change se corrige ici seulement) ──
  const A = (c, a) => K.agir("agents." + c, a);
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
    propositions: () => A("propositions"),                                  // lot 2 : tant qu'elle manque, l'écran le dit
    decider: (id, decision) => A("proposition_decider", { id: id, decision: decision }),
    journal: (acteur, n) => K.agir("journal.flux", { acteur: acteur || "", limit: n || 60, bruit: false }),
  };
  const manque = (e) => /inconnu|introuvable|n'existe pas|not found|404|capacit/i.test(String((e && e.message) || e));

  const COUL = { cassandra: "#0b7c74", itare: "#6d3fd1", amizo: "#1d6fb8", relecteur: "#b45309", vision: "#be185d" };
  const NIVEAUX = [["observer", "Observer", "Elle constate et raconte ce qu'elle ferait. Rien n'est touché."], ["entretien", "Entretien", "Elle fait le petit et le sûr : lectures, rangement, ce qui se défait."], ["reine", "Reine", "Elle conduit seule dans ses paliers ; chaque geste garde sa preuve et son retour."]];
  const ACTIONS = [["secours", "bascule sur le modèle de secours"], ["arret", "arrête les agents (sauf Cassandra) et te prévient"], ["accord", "demande ton accord"]];
  const RISQUES = ["lecture", "faible", "moyen", "élevé"];
  const REGLES = [
    ["Aucun outil de secret pour Itare, Amizo, ni les services", "Seule Cassandra gère le Coffre. La valeur d'un secret n'entre jamais dans le contexte d'un modèle."],
    ["Un compte ne règle que son Itare", "L'administrateur règle Cassandra, Amizo et les services. Administrer n'est pas voir : il ne lit pas le bureau d'un autre compte."],
    ["Un agent ne monte pas son propre palier", "Les capacités de réglage refusent un agent pour acteur."],
    ["Chaque geste a sa preuve et son retour", "Un acte se relit après coup et se défait ; ce qui ne se défait pas attend ton mot."],
    ["Le plafond le plus bas s'applique", "Plafond d'agent et plafond global : le plus bas retient, avec son action."],
  ];
  const eur = (x) => (x == null ? "—" : Number(x).toLocaleString("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: x < 1 && x > 0 ? 2 : 0, maximumFractionDigits: 4 }));
  const initiale = (n) => String(n || "?").trim().slice(0, 1).toUpperCase();
  const av = (a, g) => '<span class="ag-av' + (g ? " g" : "") + '" style="background:' + (COUL[a.id] || "#5b6b8c") + '" aria-hidden="true">' + esc(initiale(a.nom)) + "</span>";
  const dateFr = (ts) => { try { return new Date(ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

  const CSS = ".ag{--ag-doux:color-mix(in srgb,var(--accent) 9%,transparent)}.sh-scene:has(>.sh-corps>.ag){width:100%}" +
    ".ag .ag-nav{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:thin}.ag .ag-nav button{border:0;background:transparent;padding:9px 14px;font:600 13px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;display:inline-flex;gap:6px;align-items:center}" +
    ".ag .ag-nav button.on{color:var(--accent);border-bottom-color:var(--accent)}.ag .ag-n{background:var(--accent);color:var(--on-accent,#fff);border-radius:99px;font:700 10.5px/1 'Inter',sans-serif;padding:3px 6px}" +
    ".ag .ag-av{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;color:#fff;font:700 17px 'Inter',sans-serif;flex:none}.ag .ag-av.g{width:48px;height:48px;font-size:20px}" +
    ".ag .ag-cartes{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}.ag button.carte.clic{text-align:left;color:inherit;font:inherit;cursor:pointer}.ag button.carte.clic:hover{border-color:var(--accent)}" +
    ".ag .ag-tete{display:flex;gap:12px;align-items:center;min-width:0}.ag .ag-tete>div{min-width:0}.ag .ag-ligne{display:flex;justify-content:space-between;gap:10px;align-items:baseline;font-size:12.5px}.ag .ag-ligne .g{color:var(--txt-faint)}" +
    ".ag .ag-ligne b{font-weight:600;text-align:right;overflow-wrap:anywhere}.ag .ag-puces{display:flex;gap:6px;flex-wrap:wrap}.ag .ag-etat{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.ag .ag-etat .sp{flex:1;min-width:220px}" +
    ".ag .ag-rond{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok);flex:none}.ag .ag-rond.al{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}.ag .ag-rond svg{width:22px;height:22px}" +
    ".ag .ag-outil{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}.ag .ag-outil .n{font:600 12.5px ui-monospace,Menlo,Consolas,monospace;overflow-wrap:anywhere}.ag .ag-outil .d{font-size:12px;color:var(--txt-soft)}" +
    ".ag .ag-ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.ag label.ag-conf{display:inline-flex;gap:5px;align-items:center;font-size:12px;color:var(--txt-soft);cursor:pointer}" +
    ".ag .ag-mod{font:650 11px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:14px 0 2px}.ag .ag-barres{display:flex;align-items:flex-end;gap:4px;height:84px}.ag .ag-barres i{flex:1;min-width:6px;background:var(--accent);border-radius:4px 4px 0 0;opacity:.8;min-height:2px}" +
    ".ag table{border-collapse:collapse;width:100%;font-size:13px}.ag th{text-align:left;font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:6px 10px}.ag td{padding:8px 10px;border-top:1px solid var(--line)}.ag .ag-tw{overflow-x:auto}" +
    ".ag input[type=text],.ag input[type=number],.ag textarea,.ag select{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:8px 11px;min-width:0;max-width:100%}.ag textarea{width:100%;min-height:92px;resize:vertical}" +
    ".ag .ag-f{display:flex;flex-direction:column;gap:4px;min-width:0}.ag .ag-f>span{font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint)}.ag .ag-champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}" +
    ".ag .ag-conv{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:12px;align-items:start}.ag .ag-fil{display:flex;flex-direction:column;gap:8px;max-height:56vh;overflow:auto;padding:2px}" +
    ".ag .ag-m{max-width:85%;padding:9px 12px;border-radius:14px;font-size:13.5px;white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid var(--line);background:var(--surface)}.ag .ag-m.moi{align-self:flex-end;background:var(--ag-doux);border-color:transparent}.ag .ag-m small{display:block;color:var(--txt-faint);margin-top:3px}" +
    ".ag .ag-m.outil{font:12px ui-monospace,Menlo,monospace;color:var(--txt-soft);max-width:100%}.ag .ag-sel{display:flex;gap:10px;align-items:center;padding:9px 10px;border:1px solid var(--line);border-radius:12px;background:var(--surface);cursor:pointer;text-align:left;color:inherit;font:inherit;width:100%}" +
    ".ag .ag-sel.on{border-color:var(--accent)}.ag .ag-sel .sp{flex:1;min-width:0}.ag .ag-sel b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ag .ag-ecrire{display:flex;gap:8px}.ag .ag-ecrire textarea{min-height:44px;height:44px}" +
    ".ag .ag-nb{font:600 9.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;border:1px dashed var(--line-strong,var(--line));border-radius:99px;padding:2px 8px;color:var(--txt-faint);white-space:nowrap}" +
    "@media (max-width:760px){.ag .ag-conv{grid-template-columns:1fr}.ag .ag-outil{grid-template-columns:1fr}.ag .ag-ctl{justify-content:flex-start}.ag .ag-m{max-width:100%}.ag .ag-ecrire{flex-direction:column}.ag .ag-ecrire textarea{height:70px}.ag table{min-width:420px}}";

  // ── l'état de l'écran (une scène, des vues) ────────────────────────────────
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.agents = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("ag-css")) { const st = document.createElement("style"); st.id = "ag-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit ag"; corps.appendChild(racine);
    const S = { vue: "", agent: "", onglet: "apercu", eq: null, admin: false, filtre: { q: "", risque: "tous" }, conv: { id: 0, liste: null, fil: null, agent: "itare", occupe: false }, jours: 14 };

    const erreur = (e) => dire(String((e && e.message) || e), "err");
    const nav = () => {
      const base = S.admin ? [["equipe", "L'équipe"], ["conv", "Conversations"], ["boite", "À valider"], ["journal", "Journal"], ["modeles", "Modèles & clés"]]
        : [["fiche", "Mon Itare"], ["conv", "Conversations"], ["boite", "À valider"], ["journal", "Journal"]];
      return '<div class="ag-nav" role="tablist">' + base.map(([k, l]) => '<button role="tab" data-v="' + k + '" class="' + (S.vue === k || (k === "equipe" && S.vue === "fiche" && S.admin) ? "on" : "") + '">' + esc(l) + (k === "boite" && S.attente ? '<span class="ag-n">' + S.attente + "</span>" : "") + "</button>").join("") + "</div>";
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
        '<div class="ag-ligne"><span class="g">Niveau</span><b>' + esc((NIVEAUX.find((x) => x[0] === a.niveau) || [0, a.niveau])[1]) + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle</span><b>' + esc(a.modele || "par défaut") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Aujourd\'hui</span><b>' + (a.cout_jour && a.cout_jour.euros ? eur(a.cout_jour.euros) : "gratuit") + ' <span class="note">· ' + ((a.cout_jour || {}).appels || 0) + " appels</span></b></div>" +
        (pc ? pill("plafond atteint", "dg", "warn") : "") + "</button>";
    }
    async function vEquipe() {
      const eq = S.eq.equipe, agents = eq.filter((a) => a.genre === "agent"), services = eq.filter((a) => a.genre === "service");
      let cout = null; try { cout = await API.couts("", 1); } catch (e) { cout = null; }
      const glob = cout && cout.plafonds && cout.plafonds.global;
      const auj = cout ? cout.aujourdhui_euros : null;
      const retenu = eq.some((a) => a.plafond_atteint);
      const pct = glob && glob.euros ? Math.min(100, (auj || 0) / glob.euros * 100) : 0;
      return '<section class="carte"><div class="ag-etat"><div class="ag-rond' + (retenu ? " al" : "") + '">' + ic(retenu ? "warn" : "check") + '</div><div class="sp"><h3>' + (retenu ? "Un plafond de coût retient un agent" : "Tout va bien") + "</h3>" +
        '<p class="note">' + (retenu ? "Voir « Coût » dans la fiche de l'agent concerné pour lever, relever ou accorder pour aujourd'hui." : "Les agents agissent seuls dans leurs paliers ; chaque geste garde sa preuve et son retour.") + '</p></div><button class="btn pri" data-agent="cassandra" data-onglet="essai">Demander à un agent…</button></div></section>' +
        '<section class="stats"><div class="stat"><b>' + eq.length + "</b><span>agents et services</span></div>" +
        '<div class="stat ' + (pct > 85 ? "al" : "") + '"><b>' + eur(auj) + "</b><span>dépensé aujourd'hui" + (glob ? " sur " + eur(glob.euros) + " de plafond global" : " · aucun plafond global") + "</span>" + (glob ? '<div class="jauge"><i style="width:' + pct + '%"></i></div>' : "") + "</div>" +
        '<div class="stat"><b>' + (S.attente == null ? "—" : S.attente) + "</b><span>à valider</span></div></section>" +
        '<div><div class="note" style="margin:0 2px 8px"><b>L\'équipe</b></div><div class="ag-cartes">' + agents.map(carteAgent).join("") + "</div></div>" +
        '<div><div class="note" style="margin:0 2px 2px"><b>Services agentiques</b></div><div class="note" style="margin:0 2px 8px">Des fonctions, pas des décideurs : une tâche précise, pas de mémoire propre, pas d\'initiative.</div><div class="ag-cartes">' + services.map(carteAgent).join("") + "</div></div>" +
        nonBranche("Le rapport du matin", "Chaque matin, ce que chaque agent a fait, refusé et laissé : trois phrases tirées du journal. Pas encore construit.");
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
        '<div class="ag-puces">' + (service ? pill("service agentique") : "") + pill((NIVEAUX.find((x) => x[0] === a.niveau) || [0, a.niveau])[1], "ac") + pill(a.modele || "modèle par défaut") + (f.plafond_atteint ? pill("plafond atteint : " + f.plafond_atteint.action, "dg", "warn") : "") + pill((n.auto || 0) + " en auto", "ok") + pill((n.raconter || 0) + " racontés", "al") + "</div></section>";
      const ong = '<div class="ag-nav" role="tablist" id="ag-ong">' + tabs.map(([k, l]) => '<button role="tab" data-o="' + k + '" class="' + (S.onglet === k ? "on" : "") + '">' + esc(l) + "</button>").join("") + "</div>";
      const fn = { apercu: oApercu, outils: oOutils, journal: oJournal, essai: oEssai, propose: oPropose, cout: oCout, sur: oSur, memoire: oMemoire, reglages: oReglages }[S.onglet];
      return tete + ong + '<div id="ag-fiche" style="display:flex;flex-direction:column;gap:12px">' + await fn(f) + "</div>";
    }
    async function oApercu(f) {
      const a = f.agent, n = f.decompte || {};
      const d = await dernierGestes(a).catch(() => null);
      return '<div class="g2"><section class="carte"><h3>Qui est ' + esc(a.nom) + '</h3><p class="note">' + esc(a.role) + "</p>" +
        '<div class="ag-ligne"><span class="g">Ton</span><b style="max-width:62%">' + esc(a.ton || "le ton d'origine") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle principal</span><b>' + esc(a.modele || "par défaut") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Modèle de secours</span><b>' + esc(a.secours || "aucun") + "</b></div>" +
        '<div class="ag-ligne"><span class="g">Porte</span><b>' + (a.portee === "compte" ? "le bureau d'un compte, le sien" : "toute l'instance") + "</b></div>" +
        '<div class="ag-puces"><button class="btn" data-onglet-vers="reglages">Modifier le ton et le modèle</button>' + (f.agent.id !== "amizo" && f.agent.genre === "agent" ? '<button class="btn" data-onglet-vers="essai">L\'essayer</button>' : "") + "</div></section>" +
        '<section class="carte"><h3>Son niveau d\'autonomie</h3><div id="ag-niv" style="display:flex;flex-direction:column;gap:8px">' +
        NIVEAUX.map(([k, l, t]) => '<button class="radio' + (a.niveau === k ? " on" : "") + '" data-niveau="' + k + '"><i></i><span><b>' + l + '</b><br><span class="note">' + t + "</span></span></button>").join("") + "</div>" +
        '<div class="ag-puces">' + pill((n.auto || 0) + " outils en auto", "ok") + pill((n.raconter || 0) + " racontés", "al") + pill((n.retire || 0) + " retirés") + "</div>" +
        '<p class="note">Le niveau est un réglage, pas un interdit codé : il se précise outil par outil (onglet « Outils & palier »). La sûreté vient de la preuve et du retour arrière.</p></section></div>' +
        '<section class="carte"><h3>Ses derniers gestes</h3>' + (d && d.length ? d.slice(0, 5).map((x) => '<div class="ag-ligne" style="padding:4px 0"><span>' + esc(x.action) + '</span><span class="g">' + esc(x.ts) + "</span></div>").join("") : '<p class="note">Rien à montrer pour l\'instant.</p>') +
        '<div><button class="btn mini" data-onglet-vers="journal">Tout le journal</button></div></section>' +
        nonBranche("Carte de confiance", "Un outil raconté qui a huit validations de suite sans refus est proposé en auto, jamais passé seul. Pas encore construit.");
    }
    async function dernierGestes(a) {
      const r = await API.journal(a.id === "itare" ? "itare" : a.id, 8);
      return (r.entrees || []).filter(mien).map((e) => ({ action: String(e.action || e.sujet || ""), ts: String(e.ts || "").replace("T", " ").slice(0, 16) }));
    }
    // un compte ordinaire ne lit que ses propres lignes : on écarte ce que le journal rattache à un autre compte
    function mien(e) {
      if (S.admin) return true;
      const moi = String((ctx.moi && ctx.moi.compte) || ""), qui = String(e.compte || e.utilisateur || "");
      return !qui || qui === moi || qui === "itare";
    }

    async function oOutils(f) {
      const a = f.agent, p = await API.paliers(a.id);
      const q = S.filtre.q.toLowerCase(), r = S.filtre.risque;
      const liste = p.paliers.filter((o) => (r === "tous" || o.risque === r) && (!q || (o.cle + " " + (o.description || "")).toLowerCase().includes(q)));
      const groupes = {}; liste.forEach((o) => { const m = o.cle.includes("__") ? o.cle.split("__")[0] : (o.cle.split(".")[0] || "divers"); (groupes[m] = groupes[m] || []).push(o); });
      const ligne = (o) => {
        const lect = o.risque === "lecture";
        const cur = o.retire ? "retire" : o.palier;
        const seg = lect ? [["lecture", "Lecture"], ["retire", "Retirer"]] : [["auto", "Auto"], ["raconter", "Raconter"], ["retire", "Retirer"]];
        return '<div class="ag-outil"><div><div class="n">' + esc(o.cle) + '</div><div class="d">' + esc(o.description || "") + '</div><div class="ag-puces" style="margin-top:3px">' + pill(o.risque, o.risque === "moyen" ? "al" : o.risque === "élevé" ? "dg" : "") + (o.pose ? pill("réglé par toi", "ac") : "") + (o.defaut && o.pose ? pill("catalogue : " + o.defaut) : "") + "</div></div>" +
          '<div class="ag-ctl"><div class="seg" role="group" aria-label="Palier de ' + esc(o.cle) + '">' + seg.map(([k, l]) => '<button data-outil="' + esc(o.cle) + '" data-p="' + k + '" class="' + (cur === k ? "on" : "") + '">' + l + "</button>").join("") + "</div>" +
          (lect ? "" : '<label class="ag-conf"><input type="checkbox" data-conf="' + esc(o.cle) + '"' + (o.confirmer ? " checked" : "") + (o.retire ? " disabled" : "") + '> demander</label>') +
          (o.pose ? '<button class="btn mini" data-outil="' + esc(o.cle) + '" data-p="defaut">Rétablir</button>' : "") + "</div></div>";
      };
      return '<section class="carte"><h3>Les outils de ' + esc(a.nom) + ' <span class="note">· dérivés du catalogue des capacités</span></h3>' +
        (p.paliers.length ? '<div class="barre"><input type="search" id="ag-q" placeholder="Chercher un outil…" value="' + esc(S.filtre.q) + '"><select class="sel" id="ag-r"><option value="tous">Tous les risques</option>' + RISQUES.map((x) => '<option' + (r === x ? " selected" : "") + ">" + x + "</option>").join("") + "</select></div>" +
          '<p class="note">« Demander » n\'est pas un palier : c\'est une confirmation posée sur « auto ». Une lecture n\'a pas de palier, on peut seulement la retirer.</p>' +
          (liste.length ? Object.keys(groupes).sort().map((m) => '<div class="ag-mod">module ' + esc(m) + " · " + groupes[m].length + " outil(s)</div>" + groupes[m].map(ligne).join("")).join("") : '<div class="vide">Aucun outil ne correspond.</div>') :
          '<p class="note">' + esc(a.nom) + " n'a pas d'outils à régler" + (a.id === "amizo" ? " : il cherche, lit et informe, il n'agit jamais." : ".") + "</p>") + "</section>";
    }
    async function oJournal(f) {
      const a = f.agent; let l = [];
      try { l = (await API.journal(a.id === "itare" ? "itare" : a.id, 40)).entrees.filter(mien); } catch (e) { return nonBranche("Journal de " + a.nom, String(e.message || e)); }
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(a.nom) + " a fait</h3>" + (S.admin ? lien("journal", "Ouvrir les Journaux", a.id) : "") + "</div>" + ligneJournal(l) + "</section>";
    }
    function ligneJournal(l) {
      return l.length ? '<div class="liste">' + l.map((e) => '<div class="li"><div class="sp"><b>' + esc(e.action || e.sujet || "") + '</b><div class="note">' + esc(e.label || e.source || "") + (e.sujet && e.action ? " · " + esc(e.sujet) : "") + '</div></div>' + pill(e.niveau || "info", e.niveau === "erreur" || e.niveau === "critique" ? "dg" : e.niveau === "alerte" ? "al" : "") + '<span class="note">' + esc(String(e.ts || "").replace("T", " ").slice(0, 16)) + "</span></div>").join("") + "</div>" : '<div class="vide">Rien pour l\'instant.</div>';
    }
    async function oEssai(f) {
      const a = f.agent;
      if (!["cassandra", "itare"].includes(a.id)) return nonBranche("Essai en direct", a.nom + " ne converse pas directement : on lui confie une tâche ou on l'essaie par les services qui l'emploient.");
      return '<section class="carte"><h3>Essayer ' + esc(a.nom) + '</h3><p class="note">Une vraie conversation : chaque outil que l\'agent appelle traverse l\'exécuteur (droits, palier, preuve, retour, journal).</p><div class="ag-fil" id="ag-essai-fil" aria-live="polite"><div class="vide">Écris-lui pour commencer.</div></div>' +
        '<div class="ag-ecrire"><textarea id="ag-essai-t" placeholder="Demande-lui quelque chose…" aria-label="Message"></textarea><button class="btn pri" id="ag-essai-go">Envoyer</button></div></section>';
    }
    async function oPropose(f) {
      let p; try { p = await API.propositions(); } catch (e) { return nonBranche("Fait & proposé", "Ce que " + f.agent.nom + " propose et ce qu'il a fait sans te demander. Cette lecture arrive avec les propositions du module."); }
      const mine = (p.propositions || []).filter((x) => x.agent === f.agent.id);
      return '<section class="carte"><h3>Ce que ' + esc(f.agent.nom) + " propose</h3>" + (mine.length ? mine.map(carteProp).join("") : '<p class="note">Rien n\'attend ton mot.</p>') + "</section>";
    }
    function carteProp(p) {
      return '<div class="alerte"><div class="sp"><b>' + esc(p.titre || p.outil || "Proposition") + '</b><div class="note">' + esc(p.sous || p.pourquoi || "") + '</div></div><button class="btn pri mini" data-prop="' + esc(p.id) + '" data-d="accepter">Accepter</button><button class="btn mini" data-prop="' + esc(p.id) + '" data-d="refuser">Refuser</button></div>';
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
    function oSur() {
      return '<section class="carte"><h3>Les règles non négociables</h3>' + REGLES.map((r) => '<details style="border-top:1px solid var(--line);padding:7px 0"><summary style="cursor:pointer;font-weight:600">' + esc(r[0]) + '</summary><p class="note" style="margin-top:6px">' + esc(r[1]) + "</p></details>").join("") + "</section>" +
        nonBranche("Les épreuves de sûreté", "Rejouer à blanc les pièges connus (ordre caché dans une page, envoi suspect, secret demandé) avant de changer de modèle. Pas encore construit.");
    }
    async function oMemoire(f) {
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que ' + esc(f.agent.nom) + ' sait</h3>' + lien("memory", "Ouvrir la Mémoire") + '</div><p class="note">La mémoire vit dans son module : un seul propriétaire par donnée. Rien n\'est copié ici ; le bouton ouvre l\'écran Mémoire.</p></section>';
    }
    async function oReglages(f) {
      const a = f.agent, L = a.limites || {};
      const num = (k, lib, def) => '<label class="ag-f"><span>' + lib + '</span><input type="number" data-lim="' + k + '" value="' + (L[k] != null ? L[k] : "") + '" placeholder="' + def + '"></label>';
      return '<section class="carte"><h3>Nom, ton et modèle</h3><div class="ag-champs"><label class="ag-f"><span>Nom affiché</span><input type="text" id="ag-nom" maxlength="40" value="' + esc(a.nom) + '"></label>' +
        '<label class="ag-f"><span>Modèle principal</span><input type="text" id="ag-mod" maxlength="80" value="' + esc(a.modele) + '" placeholder="rôle ou modèle"></label>' +
        '<label class="ag-f"><span>Modèle de secours</span><input type="text" id="ag-sec" maxlength="80" value="' + esc(a.secours) + '" placeholder="aucun"></label></div>' +
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
      const choix = (S.admin ? ["cassandra", "itare"] : ["itare"]);
      const liste = '<section class="carte"><div class="barre"><h3 style="flex:1">Conversations</h3>' + (S.admin ? '<select class="sel" id="cv-ag">' + choix.map((x) => '<option value="' + x + '"' + (S.conv.agent === x ? " selected" : "") + ">avec " + x + "</option>").join("") + "</select>" : "") + '<button class="btn pri mini" id="cv-neuve">Nouvelle</button></div>' +
        (L.length ? L.map((c) => '<button class="ag-sel' + (S.conv.id === c.id ? " on" : "") + '" data-cv="' + c.id + '"><div class="sp"><b>' + esc(c.titre || "Sans titre") + '</b><div class="note">' + esc(c.agent) + " · " + c.n + " messages · " + esc(dateFr(c.maj)) + "</div></div></button>").join("") : '<div class="vide">Aucune conversation.</div>') + "</section>";
      let droite = '<section class="carte"><div class="vide">Choisis une conversation, ou ouvres-en une nouvelle.</div></section>';
      if (S.conv.id) {
        const d = await API.conversation(S.conv.id);
        const fil = d.messages.filter((m) => m.role !== "tool" || true).map((m) => {
          if (m.role === "tool") return '<div class="ag-m outil">↳ ' + esc(m.nom || "outil") + (m.statut ? " · " + esc(m.statut) : "") + "</div>";
          if (m.role === "panne") return '<div class="ag-m outil" style="color:var(--danger)">' + esc(m.contenu) + "</div>";
          if (!m.contenu && m.appels) return '<div class="ag-m outil">appelle ' + esc((m.appels || []).map((c) => (c.function && c.function.name) || c.nom || "outil").join(", ")) + "</div>";
          return '<div class="ag-m' + (m.role === "user" ? " moi" : "") + '">' + esc(m.contenu) + "</div>";
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
      try { p = await API.propositions(); } catch (e) { S.attente = null; return nonBranche("À valider", "Seulement ce qui part vers l'extérieur ou ne se défait pas : l'agent propose, tu décides. Les propositions arrivent avec la prochaine étape du module ; rien n'attend ton mot pour l'instant.") ; }
      const l = (p.propositions || []).filter((x) => S.admin || x.agent === "itare");
      S.attente = l.length;
      return '<section class="carte"><h3>À valider</h3><p class="note">Seulement ce qui part vers l\'extérieur, ne se défait pas ou sort du palier.</p>' + (l.length ? l.map(carteProp).join("") : '<div class="vide">Rien n\'attend ton mot.</div>') + "</section>";
    }

    // ── journal ──────────────────────────────────────────────────────────────
    async function vJournal() {
      let l = [];
      try { l = (await API.journal(S.admin ? "" : "itare", 80)).entrees.filter(mien); } catch (e) { return nonBranche("Journal", String(e.message || e)); }
      if (S.admin) l = l.filter((e) => /cassandra|itare|amizo|agent|relecteur|vision/i.test((e.acteur || "") + " " + (e.source || "") + " " + (e.label || "")));
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Ce que les agents ont fait</h3>' + lien("journal", "Ouvrir les Journaux") + "</div>" + ligneJournal(l) + "</section>";
    }

    // ── modèles et clés ──────────────────────────────────────────────────────
    function vModeles() {
      const eq = S.eq.equipe;
      return '<section class="carte"><div class="barre"><h3 style="flex:1">Quel modèle fait parler qui</h3><button class="btn" id="ag-reg">Ouvrir le registre des modèles</button></div>' +
        '<div class="ag-tw"><table><tr><th>Agent</th><th>Modèle</th><th>Secours</th><th>Coût du jour</th></tr>' + eq.map((a) => "<tr><td>" + esc(a.nom) + "</td><td>" + esc(a.modele || "par défaut") + "</td><td>" + esc(a.secours || "aucun") + "</td><td>" + (a.cout_jour && a.cout_jour.euros ? eur(a.cout_jour.euros) : "gratuit") + "</td></tr>").join("") + "</table></div>" +
        '<p class="note">Le registre (fournisseurs, clés, tarifs) reste dans le module Modèles ; les clés sont des réglages « secret » du noyau, jamais lues ici. Le modèle d\'un agent se règle dans sa fiche, onglet « Réglages ».</p></section>';
    }

    // ── le dessin et les gestes ──────────────────────────────────────────────
    async function dessiner() {
      let html;
      const v0 = racine.querySelector("#ag-vue");
      if (v0) v0.style.opacity = ".5"; else racine.innerHTML = '<div class="vide" role="status">Chargement…</div>';
      try {
        S.eq = S.eq || await API.equipe();
        S.admin = !!S.eq.administrateur;
        if (!S.vue) S.vue = S.admin ? "equipe" : "fiche";
        if (!S.admin && !["fiche", "conv", "boite", "journal"].includes(S.vue)) S.vue = "fiche";
        if (S.attente === undefined) { try { S.attente = ((await API.propositions()).propositions || []).filter((x) => S.admin || x.agent === "itare").length; } catch (e) { S.attente = null; } }
        const f = { equipe: vEquipe, fiche: vFiche, conv: vConv, boite: vBoite, journal: vJournal, modeles: async () => vModeles() }[S.vue];
        html = nav() + '<div id="ag-vue" style="display:flex;flex-direction:column;gap:12px">' + await f() + "</div>";
      } catch (e) { html = '<div class="vide">' + esc((e && e.message) || e) + "</div>"; }
      racine.innerHTML = html; brancher();
    }
    const recharger = (eq) => { if (eq) S.eq = null; return dessiner(); };
    const aller = (v, agent, onglet) => { S.vue = v; if (agent) S.agent = agent; if (onglet) S.onglet = onglet; if (v === "conv") S.conv.liste = null; dessiner(); };
    const sur = (sel, ev, fn) => racine.querySelectorAll(sel).forEach((el) => el.addEventListener(ev, (e) => fn(el, e)));
    const lancer = async (fn, ok) => { try { await fn(); if (ok) dire(ok, "ok"); } catch (e) { erreur(e); } };

    function brancher() {
      sur(".ag-nav[role=tablist]:not(#ag-ong) [data-v]", "click", (b) => aller(b.dataset.v, b.dataset.v === "fiche" ? "itare" : ""));
      sur("[data-agent]", "click", (b) => aller("fiche", b.dataset.agent, b.dataset.onglet || "apercu"));
      sur("#ag-ong [data-o]", "click", (b) => { S.onglet = b.dataset.o; dessiner(); });
      sur("[data-onglet-vers]", "click", (b) => { S.onglet = b.getAttribute("data-onglet-vers"); dessiner(); });
      sur("[data-chez]", "click", (b) => chez(b.dataset.chez, b.dataset.q));
      sur("#ag-chg", "change", (s) => aller("fiche", s.value));
      sur("[data-niveau]", "click", (b) => lancer(async () => { const avant = S.fiche.agent.niveau; await API.niveau(S.agent, b.dataset.niveau); dire("Niveau réglé : " + b.dataset.niveau + " (avant : " + avant + ")", "ok"); await recharger(true); }));
      sur("[data-outil]", "click", (b) => lancer(async () => {
        const p = b.dataset.p, o = b.dataset.outil, retirer = p === "retire", lect = p === "lecture";
        if (retirer) { const ok = await confirmer("Retirer cet outil ?", '<p class="note"><span class="mono">' + esc(o) + "</span> ne sera plus présenté à " + esc(S.fiche.agent.nom) + ". Tu pourras le rétablir.</p>", "Retirer", true); if (!ok) return; }
        await API.palier(S.agent, o, lect ? "defaut" : p, retirer ? false : undefined); await recharger(true);
      }));
      sur("[data-conf]", "change", (c) => lancer(async () => { await API.palier(S.agent, c.dataset.conf, "", c.checked); await recharger(true); }));
      sur("#ag-q", "input", (i) => { S.filtre.q = i.value; clearTimeout(S.tq); S.tq = setTimeout(async () => { const pos = i.selectionStart; await dessiner(); const n = racine.querySelector("#ag-q"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 250); });
      sur("#ag-r", "change", (s) => { S.filtre.risque = s.value; dessiner(); });
      sur("#ag-jours [data-j]", "click", (b) => { S.jours = +b.dataset.j; dessiner(); });
      sur("#ag-sauve", "click", () => lancer(async () => {
        const g = (id) => racine.querySelector(id).value;
        await API.regler(S.agent, { nom_affiche: g("#ag-nom"), modele: g("#ag-mod"), secours: g("#ag-sec"), ton: g("#ag-ton") }); await recharger(true);
      }, "Réglages enregistrés"));
      sur("#ag-lim", "click", () => lancer(async () => {
        const lim = {}; racine.querySelectorAll("[data-lim]").forEach((i) => { lim[i.dataset.lim] = i.value === "" ? null : parseInt(i.value, 10); });
        await API.regler(S.agent, { limites: lim }); await recharger(true);
      }, "Limites enregistrées"));
      sur("#ag-pl-poser", "click", () => lancer(async () => { const e = parseFloat(racine.querySelector("#ag-pl-e").value); if (!(e > 0)) throw new Error("un montant positif est requis"); await API.plafond(S.agent, e, racine.querySelector("#ag-pl-a").value); await recharger(true); }, "Plafond posé"));
      sur("#ag-pl-g", "click", () => lancer(async () => { const e = parseFloat(racine.querySelector("#ag-pl-e").value); if (!(e > 0)) throw new Error("un montant positif est requis"); await API.plafond("global", e, racine.querySelector("#ag-pl-a").value); await recharger(true); }, "Plafond global posé"));
      sur("[data-plaf]", "click", (b) => lancer(async () => {
        if (b.dataset.plaf === "accorder") { await API.plafond(S.agent, null, "accord", true); }
        else { if (!(await confirmer("Lever le plafond ?", '<p class="note">' + esc(S.fiche.agent.nom) + " ne sera plus retenu par un plafond de coût.</p>", "Lever", true))) return; await API.plafond(S.agent, null, "secours"); }
        await recharger(true);
      }));
      sur("[data-prop]", "click", (b) => lancer(async () => { await API.decider(b.dataset.prop, b.dataset.d); S.attente = undefined; await recharger(); }, "C'est noté"));
      sur("#ag-reg", "click", () => { if (CASS.ouvrirConsole) CASS.ouvrirConsole("modeles", "Modèles"); });
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
      sur("#cv-neuve", "click", () => lancer(async () => { const r = await API.creer(S.conv.agent); S.conv.id = r.id; S.conv.liste = null; await dessiner(); }));
      sur("#cv-ren", "click", () => lancer(async () => { const t = window.prompt("Nouveau titre"); if (t == null) return; await API.renommer(S.conv.id, t); S.conv.liste = null; await dessiner(); }));
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
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait && racine.isConnected) { S.eq = null; S.attente = undefined; S.conv.liste = null; dessiner(); } etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    const cible = String((ctx && ctx.ecran) || "").split(":")[1] || "";
    if (cible && ["equipe", "conv", "boite", "journal", "modeles", "fiche"].includes(cible)) S.vue = cible;
    await dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
