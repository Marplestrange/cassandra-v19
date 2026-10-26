// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de C
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #eacc04
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=eacc04 ▼▼▼
// La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux.
// Une page, des sections (Vue d'ensemble, Installés, Mises à jour, Boutique, Sources, Sécurité, Santé, Journal, Développeur, Réglages).
// Principe : Cassandra gère les modules SEULE ; l'utilisateur voit ce qu'elle fait (le récit, avec le pourquoi), peut tout défaire,
// la mettre en pause, verrouiller un module, ou lui demander. Les gestes directs (interrupteurs, retrait) sont derrière un « Mode avancé ».
(function () {
  "use strict";
  const CASS = window.CASS;
  const { esc, I, ic, pill, depuis, titre, agir, dire } = CASS.kit;                                   // le kit commun (CN_kit.js)

  const SECTIONS = [["vue", "Vue d’ensemble", "vue"], ["inst", "Installés", "inst"], ["maj", "Mises à jour", "maj"], ["shop", "Boutique", "shop"], ["src", "Sources", "src"],
    ["sec", "Sécurité et confiance", "sec"], ["sante", "Santé", "sante"], ["jour", "Journal et versions", "jour"], ["dev", "Développeur", "dev"], ["reg", "Réglages", "reg"]];


  const IMP = { vital: ["Vital", "vi"], important: ["Important", "al"], optionnel: ["Optionnel", ""] };
  const NIV = {
    observer: ["Observer", "Je regarde et je te raconte ce que je ferais. Je ne touche à rien."],
    entretien: ["Entretien", "Je retire ce qui est révoqué, je prends les mises à jour sans permission en plus, je mets en pause ce qui échoue."],
    reine: ["Reine", "Je gère tout : j’ajoute, je mets à jour, je retire, j’active. Tu n’as rien à faire."],
  };
  const FENETRES = { nuit: "La nuit, 02:00–05:00", dimanche: "Dimanche matin", hors_bureau: "Hors heures de bureau", tout: "À tout moment" };
  const GESTES = { active: "a activé", desactive: "a désactivé", installe: "a installé", retour: "a remis une version précédente de", desinstalle: "a retiré" };


  const S = { choix: new Set(), reg: null, regCharge: false, regErr: "", sante: {}, santeCharge: false, jfil: "tout", gere: true, cat: [], sections: [], act: { actes: [], verrous: [], autonomie: "reine", fenetre: "nuit", gel: false }, constats: null, rep: new Set(), q: "", fam: "toutes", etat: "tous", imp: "toutes", vue: "grille", ouvert: "", onglet: "apercu", occupe: false };
  let racine = null, corpsEl = null, sec = "vue", hooks = {}, escLie = false;
  const lire = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } };
  const ecrire = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const avance = () => lire("lg.avance", "0") === "1";

  const qui = (par) => { const p = String(par || ""); if (["cassandra", "itare"].includes(p)) return p.charAt(0).toUpperCase() + p.slice(1); if (p === "agent") return "Un agent"; if (p === "noyau") return "Le noyau"; if (!p || p === "utilisateur" || p === "humain") return "Un utilisateur"; return p.split("@")[0]; };
  const nomDe = (id) => { const m = S.cat.find((x) => x.id === id); return m ? m.nom : id; };
  const niveauMod = (m) => (m.etat === "refuse" ? pill("Refusé", "dg", "warn") : m.confiance === "interne" ? pill("Noyau", "ok", "shield") : m.confiance === "local" ? pill("Clé de l’administrateur", "") : pill("Installé", ""));
  const sectionDe = (id) => S.sections.find((s) => s.id === id) || { id: id, libelle: id, icone: "" };
  const famIcone = (id) => ((CASS.modulesUi && CASS.modulesUi.famIcone && CASS.modulesUi.famIcone(id)) || "box");
  const iconeMod = (m) => (CASS.modulesUi && CASS.modulesUi.trace && m.icone_trace && CASS.modulesUi.trace(m.icone_trace)) ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + CASS.modulesUi.trace(m.icone_trace) + "</svg>" : ic("box");

  async function charger() {
    const [l, a] = await Promise.all([agir("modules.lister"), agir("modules.activite", { limite: 60 }).catch(() => null)]);
    S.cat = l.modules || [];
    S.gere = l.gere !== false;
    if (!S.gere) S.cat.forEach((m) => { if (m.etat !== "refuse") m.etat = "actif"; });           // instance de développement : tout ce qui est chargé tourne
    S.sections = l.sections || [];
    if (a) S.act = a;
    else S.act = Object.assign({}, S.act, { autonomie: l.autonomie || S.act.autonomie });
  }
  async function chargerConstats() {
    if (S.constats !== null) return;
    S.constats = { chargement: true, liste: [] };
    try { const r = await agir("modules.entretien", { simuler: true }); S.constats = { chargement: false, liste: r.constats || [], erreurs: r.erreurs || [] }; }
    catch (e) { S.constats = { chargement: false, liste: [], erreurs: [e.message || String(e)] }; }
    if (sec === "vue") dessiner();
  }

  const banDev = () => S.gere ? "" : '<div class="alerte in" role="status"><div class="sp"><b>Instance de développement.</b> <span class="note">Tous les modules sont chargés : activer ou désactiver ne change rien ici, et Cassandra n’a rien à entretenir.</span></div></div>';
  const banAvance = () => avance() ? '<div class="alerte al avance" role="status"><div class="ico sm al">' + ic("warn") + '</div><div class="sp"><b>Mode avancé.</b> <span class="note">Tu as les vrais boutons (interrupteurs, retrait). Cassandra voit tout ce que tu fais, et chaque geste se défait.</span></div><button class="btn mini" data-a="avance">Quitter</button></div>' : "";

  // ── l'accueil d'une instance neuve : un point de départ à cocher (les ensembles se cumulent), ou Cassandra décide ───────
  const ENSEMBLES = [
    { id: "hebergeur", nom: "Hébergeur complet", d: "Sites, DNS, certificats, sauvegardes, sécurité, supervision.", mods: ["sites", "dns", "certificats", "sauvegardes", "securite", "sensorium", "fastpanel"] },
    { id: "bureau", nom: "Bureau personnel", d: "Courrier, agenda, notes, tâches, contacts, assistante.", mods: ["courrier", "agenda", "notes", "taches", "contacts", "agents"] },
  ];
  const ensembles = () => ENSEMBLES.map((e) => Object.assign({}, e, { mods: e.mods.filter((id) => S.cat.some((m) => m.id === id)) })).filter((e) => e.mods.length);
  const neuve = () => S.gere && lire("lg.accueil", "0") !== "1" && (S.act.actes || []).length === 0 && !S.cat.some((m) => m.etat === "actif" && m.importance !== "vital");
  function aActiver() {
    const ids = new Set(); ensembles().filter((e) => S.choix.has(e.id)).forEach((e) => e.mods.forEach((id) => { ids.add(id); atirer(id).forEach((d) => ids.add(d)); }));
    return [...ids].filter((id) => { const m = S.cat.find((x) => x.id === id); return m && m.etat !== "actif"; });
  }
  function accueil() {
    const E = ensembles(), tout = E.length && S.choix.size === E.length, vit = S.cat.filter((m) => m.importance === "vital" && m.etat === "actif").length;
    const nb = aActiver().length;
    return titre("Bienvenue", "Cette instance vient d’être installée. Cassandra a déjà mis en place les modules vitaux.") +
      '<div class="carte accueil"><h2>Que veux-tu faire de cette instance ?</h2><p class="note" style="max-width:60ch">Choisis un ou plusieurs points de départ (ils se cumulent), ou dis-moi simplement ce que tu veux. Rien n’est définitif : tout se défait.</p>' +
      '<div class="carte" style="flex-direction:row;gap:12px;align-items:center;box-shadow:none"><div class="ico sm">' + ic("check") + '</div><div><b>Déjà en place</b> <span class="note">' + vit + " modules vitaux : ils tiennent Cassandra debout, rien à choisir.</span></div></div>" +
      '<div class="g2">' + E.map((e) => '<button class="carte choix' + (S.choix.has(e.id) ? " on" : "") + '" data-a="ensemble" data-id="' + e.id + '" aria-pressed="' + S.choix.has(e.id) + '"><span class="coche">' + ic("check") + "</span><h4>" + esc(e.nom) + '</h4><span class="note">' + esc(e.d) + '</span><span class="chips">' + e.mods.map((id) => '<span class="p">' + esc(nomDe(id)) + "</span>").join("") + "</span></button>").join("") +
      (E.length > 1 ? '<button class="carte choix' + (tout ? " on" : "") + '" data-a="ensemble" data-id="tout" aria-pressed="' + !!tout + '"><span class="coche">' + ic("check") + '</span><h4>Tout installer</h4><span class="note">Tous les ensembles ci-dessus, bureau compris. Les modules en commun ne sont activés qu’une fois.</span></button>' : "") + "</div>" +
      (S.choix.size ? '<div class="alerte in" style="width:100%"><div class="sp"><b>' + S.choix.size + " ensemble" + (S.choix.size > 1 ? "s" : "") + " choisi" + (S.choix.size > 1 ? "s" : "") + " · " + nb + " module" + (nb > 1 ? "s" : "") + ' à activer</b><span class="note"> (dépendances comprises). Tout se défait ensuite.</span></div><button class="btn pri" data-a="mise-en-place"' + (S.occupe || !nb ? " disabled" : "") + ">Mettre en place</button></div>" : '<p class="note">Coche un ou plusieurs ensembles : ils se cumulent.</p>') +
      '<div class="demande" style="width:100%"><input id="lg-dem" placeholder="Ou dis-moi : « je veux héberger mes sites et gérer mon courrier »" aria-label="Dire à Cassandra ce qu’on veut"><button class="btn pri" data-a="demande">Dire</button></div>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-sug="Mets cette instance en place : choisis les modules utiles et active-les.">Laisse Cassandra décider</button><button class="btn" data-go="shop">Voir la boutique</button><button class="btn" data-a="plus-tard">Plus tard</button></div></div>' +
      '<div class="carte"><h3>Jusqu’où Cassandra va seule</h3><p class="note">Tu pourras le changer à tout moment.</p><div style="display:flex;flex-direction:column;gap:8px">' + Object.entries(NIV).map(([k, v]) => '<button class="radio' + (S.act.autonomie === k ? " on" : "") + '" data-a="autonomie" data-k="' + k + '" role="radio" aria-checked="' + (S.act.autonomie === k) + '"><i></i><div><b>' + v[0] + (k === "reine" ? ' <span class="p ok">recommandé</span>' : "") + '</b><span class="note" style="display:block">' + v[1] + "</span></div></button>").join("") + "</div></div>";
  }

  // ── la Vue d'ensemble ───────────────────────────────────────────────
  function recitLi(a, i) {
    const dep = a.detail && /^mise à jour/.test(a.detail), verbe = a.geste === "installe" && dep ? "a mis à jour" : (GESTES[a.geste] || a.geste);
    return '<div class="li"><div class="ico sm">' + ic("check") + '</div><div class="sp"><b>' + esc(qui(a.par)) + "</b> " + esc(verbe) + " <b>" + esc(nomDe(a.module)) + "</b>" + (a.detail ? '<span class="note">' + esc(a.detail) + "</span>" : "") +
      (a.pourquoi ? '<span class="pourquoi">' + ic("eye") + esc(a.pourquoi) + "</span>" : "") + '<span class="faint" style="font-size:11.5px">' + esc(depuis(a.ts)) + "</span></div>" +
      (a.defaire ? '<button class="btn mini" data-a="defaire" data-i="' + i + '">Défaire</button>' : "") + "</div>";
  }
  function vue() {
    if (neuve()) return accueil();
    const A = S.act, actifs = S.cat.filter((m) => m.etat === "actif").length, n = S.cat.length;
    const gel = !!A.gel, laisses = S.constats && S.constats.liste || [];
    const hero = '<div class="carte hero"><div class="l1"><div class="ico" style="width:46px;height:46px;border-radius:14px">' + ic(gel ? "warn" : "bot") + '</div><div style="flex:1;min-width:240px"><h2>' + (gel ? "Cassandra est en pause" : "Tout va bien") + '</h2><p class="note" style="margin-top:3px;max-width:62ch">' +
      (gel ? "Elle observe et raconte, elle n’agit plus. Reprends quand tu veux." : "Cassandra s’occupe des modules" + (A.actes && A.actes[0] ? " : dernier geste " + esc(depuis(A.actes[0].ts)) + "." : " : rien à signaler pour l’instant.")) + "</p></div>" +
      '<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-a="passe"' + (S.occupe ? " disabled" : "") + '>Lancer une passe</button><button class="btn' + (gel ? " pri" : "") + '" data-a="gel">' + (gel ? "Reprendre" : "Mettre en pause") + "</button></div></div>" +
      '<div class="demande"><input id="lg-dem" placeholder="Demander à Cassandra : « installe Sentinelle du disque », « qu’est-ce qui ne va pas ? »…" aria-label="Demander à Cassandra"><button class="btn pri" data-a="demande">Demander</button></div>' +
      '<div class="chips"><button class="chip" data-sug="Qu’est-ce qui ne va pas ?">Qu’est-ce qui ne va pas ?</button><button class="chip" data-sug="Qu’est-ce qui consomme le plus ?">Qu’est-ce qui consomme le plus ?</button><button class="chip" data-sug="Mets tout à jour">Mets tout à jour</button></div></div>';
    const stats = '<div class="stats"><div class="stat ok"><b>' + actifs + "/" + n + '</b><span>modules actifs</span></div><div class="stat"><b>' + S.cat.filter((m) => m.etat === "inactif").length + '</b><span>inactifs</span></div><div class="stat"><b>' + (A.verrous || []).length + "</b><span>verrouillés</span></div></div>";
    const recit = '<div class="carte"><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>Ce que Cassandra a fait</h3><span class="note">Chaque ligne se défait en un clic. Rien n’est effacé pour de bon : un module retiré reste 30 jours en corbeille.</span></div><div class="liste">' +
      ((A.actes || []).length ? A.actes.slice(0, 5).map(recitLi).join("") : '<div class="vide">Rien pour l’instant. Ce que Cassandra fait ou laisse de côté apparaîtra ici.</div>') + "</div></div>";
    const niveaux = '<div class="carte"><h3>Jusqu’où Cassandra va seule</h3><div style="display:flex;flex-direction:column;gap:8px">' + Object.entries(NIV).map(([k, v]) =>
      '<button class="radio' + (A.autonomie === k ? " on" : "") + '" data-a="autonomie" data-k="' + k + '" role="radio" aria-checked="' + (A.autonomie === k) + '"><i></i><div><b>' + v[0] + (k === "reine" ? ' <span class="p ok">défaut</span>' : "") + '</b><span class="note" style="display:block">' + v[1] + "</span></div></button>").join("") +
      '</div><p class="note">À tout niveau : elle n’installe que le registre officiel et les éditeurs vérifiés, jamais un module révoqué, jamais un module vital désactivé, jamais un module verrouillé. Ce niveau est un plafond ; l’autonomie qu’elle gagne par les preuves se suit dans Évolution.</p></div>';
    const cote = '<div class="carte"><h3>Ce que je n’ai pas fait seule, et pourquoi</h3>' + (!S.constats || S.constats.chargement ? '<p class="note">Je regarde le registre…</p>' :
      laisses.length ? '<div class="liste">' + laisses.map((c) => '<div class="li"><div class="sp"><span class="note" style="display:block;color:var(--txt)">' + esc(c) + "</span></div></div>").join("") + "</div>" : '<p class="note">Rien : tout ce que ma règle permet est fait.</p>') +
      '<p class="note">Ce n’est pas une file d’attente : je continue sans ton accord. Cette liste dit seulement ce que ma règle m’a fait laisser de côté.</p></div>';
    return titre("Vue d’ensemble", "Les modules de cette instance : Cassandra s’en occupe, tu vois ce qu’elle fait.") + banDev() + banAvance() + hero + stats + recit + '<div class="g2">' + niveaux + cote + "</div>";
  }

  // ── Installés ───────────────────────────────────────────────────────
  const filtres = () => S.cat.filter((m) => (S.fam === "toutes" || (m.famille || "autres") === S.fam) && (S.etat === "tous" || (S.etat === "actif" && m.etat === "actif") || (S.etat === "inactif" && m.etat !== "actif") || (S.etat === "verrou" && m.verrou)) &&
    (S.imp === "toutes" || m.importance === S.imp) && (!S.q || (m.nom + " " + m.id + " " + (m.description || "")).toLowerCase().indexOf(S.q.toLowerCase()) >= 0));
  function carteMod(m) {
    const on = m.etat === "actif", av = avance();
    const sw = av ? '<button class="sw' + (on ? " on" : "") + '" data-a="bascule" data-id="' + esc(m.id) + '"' + (m.importance === "vital" || m.etat === "refuse" || m.etat === "a_installer" || !S.gere ? " disabled" : "") + ' aria-label="Activer ' + esc(m.nom) + '" role="switch" aria-checked="' + on + '"></button>' : pill(on ? "actif" : m.etat === "a_installer" ? "à installer" : "inactif", on ? "ok" : "");
    return '<div class="carte mod' + (on ? "" : " off") + '" data-ouvrir="' + esc(m.id) + '" role="button" tabindex="0"><div class="l1"><div class="ico' + (on ? "" : " off") + '">' + iconeMod(m) + '</div><div class="sp"><h3>' + esc(m.nom) + '</h3><div class="mono note">' + esc(m.id) + " · v" + esc(m.version) + "</div></div>" + sw + "</div>" +
      '<div class="desc">' + esc(m.description) + '</div><div class="pied">' + niveauMod(m) + (IMP[m.importance] ? '<span class="faint" style="font:600 11px Inter,sans-serif">' + IMP[m.importance][0] + "</span>" : "") + (m.verrou ? pill("verrouillé", "", "lock") : "") + "</div></div>";
  }
  function inst() {
    const l = filtres(), n = (f) => S.cat.filter(f).length, sects = S.sections.filter((s) => S.cat.some((m) => (m.famille || "autres") === s.id));
    const filtre = S.fam !== "toutes" || S.imp !== "toutes" || S.etat !== "tous" || S.q;
    const bloc = sects.filter((s) => l.some((m) => (m.famille || "autres") === s.id)).map((s) => {
      const g = l.filter((m) => (m.famille || "autres") === s.id), ouv = !S.rep.has(s.id);
      return '<section class="rub"><button class="rub-t" data-a="rep" data-id="' + esc(s.id) + '" aria-expanded="' + ouv + '"><span class="ico sm">' + ic(famIcone(s.id)) + "</span><h3>" + esc(s.libelle) + '</h3><span class="p">' + g.length + '</span><span class="note">' + g.filter((m) => m.etat === "actif").length + ' actif(s)</span><svg class="chev' + (ouv ? "" : " ferme") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + I.chev + "</svg></button>" +
        (ouv ? '<div class="grille">' + g.map(carteMod).join("") + "</div>" : "") + "</section>";
    }).join("");
    return titre("Installés", "Tout ce qui tourne sur cette instance, avec ce qui s’arrête si on le coupe.", '<button class="btn' + (avance() ? " pri" : "") + '" data-a="avance" title="Affiche les interrupteurs. Cassandra sait tout ce que tu fais.">Mode avancé : ' + (avance() ? "oui" : "non") + "</button>") + banDev() + banAvance() +
      '<div class="barre"><input type="search" id="lg-q" placeholder="Rechercher parmi les modules installés…" value="' + esc(S.q) + '" aria-label="Rechercher un module"><select class="sel" data-sel="fam" aria-label="Section"><option value="toutes">Toutes les sections</option>' +
      S.sections.filter((s) => S.cat.some((m) => (m.famille || "autres") === s.id)).map((s) => '<option value="' + esc(s.id) + '"' + (S.fam === s.id ? " selected" : "") + ">" + esc(s.libelle) + "</option>").join("") + '</select><select class="sel" data-sel="imp" aria-label="Importance">' +
      [["toutes", "Toutes les importances"], ["vital", "Vital"], ["important", "Important"], ["optionnel", "Optionnel"]].map((c) => '<option value="' + c[0] + '"' + (S.imp === c[0] ? " selected" : "") + ">" + c[1] + "</option>").join("") + "</select>" + (filtre ? '<button class="btn mini" data-a="reset">Réinitialiser</button>' : "") + "</div>" +
      '<div class="seg">' + [["tous", "Tous", S.cat.length], ["actif", "Actifs", n((m) => m.etat === "actif")], ["inactif", "Inactifs", n((m) => m.etat !== "actif")], ["verrou", "Verrouillés", n((m) => m.verrou)]].map((c) => '<button class="' + (S.etat === c[0] ? "on" : "") + '" data-etat="' + c[0] + '">' + c[1] + ' <span class="cnt">' + c[2] + "</span></button>").join("") + "</div>" +
      (bloc || '<div class="carte vide">Aucun module ne correspond.</div>');
  }

  // ── le registre : lu à la demande (réseau), partagé par Mises à jour, Sources et Sécurité ───────
  async function chargerRegistre(force) {
    if ((S.reg || S.regErr) && !force) return;                               // une panne ne relance pas la lecture en boucle : « Réessayer » le fait
    if (S.regCharge) return;
    S.regCharge = true; S.regErr = "";
    try { S.reg = await agir("modules.registre"); } catch (e) { S.reg = null; S.regErr = e.message || String(e); }
    S.regCharge = false;
    if (["maj", "src", "sec"].includes(sec)) dessiner();
  }
  const jour = (ts) => new Date(ts * 1000).toLocaleDateString("fr-FR");
  const off = () => (S.reg && S.reg.officiel) || null;
  const regMuet = () => '<div class="alerte al"><div class="ico sm al">' + ic("src") + '</div><div class="sp"><b>Le registre officiel ne répond pas.</b> <span class="note">' + esc(S.regErr || (off() && off().erreur) || "Aucune réponse") + ' Rien n’est cassé : ce qui est installé tourne normalement, et Cassandra réessaie.</span></div><button class="btn mini" data-a="registre">Réessayer</button></div>';

  // ── Mises à jour ────────────────────────────────────────────────────
  function maj() {
    chargerRegistre(); chargerConstats();
    const o = off(), fen = S.act.fenetre || "nuit";
    const hors = !S.reg && !S.regCharge ? regMuet() : o && o.erreur ? regMuet() : "";
    const l = o && !o.erreur ? (o.modules || []).filter((m) => m.etat === "mise_a_jour" && !m.revoque) : [];
    const cote = (S.constats && S.constats.liste) || [];
    return titre("Mises à jour", "Cassandra prend seule celles que sa règle permet, dans ta fenêtre de maintenance. Tu vois ce qui vient, et ce qu’elle laisse de côté.", '<button class="btn" data-a="passe"' + (S.occupe ? " disabled" : "") + ">Lancer une passe maintenant</button>") + banDev() + hors +
      '<div class="carte"><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>Ce qui vient</h3><span class="note">Prochaine passe : ' + esc(FENETRES[fen] || fen).toLowerCase() + ".</span></div>" +
      (S.regCharge || !S.reg ? '<p class="note">Je regarde le registre…</p>' : l.length ? '<div class="liste">' + l.map((m) => '<div class="li"><div class="ico sm">' + ic("maj") + '</div><div class="sp"><b>' + esc(m.nom) + '</b> <span class="mono note">' + esc(m.version_en_place || "?") + " → " + esc(m.version) + "</span>" +
        '<span class="pourquoi">' + ic("eye") + esc(m.niveau === "officiel" ? "Registre officiel" : m.niveau === "verifie" ? "Éditeur vérifié (" + (m.editeur_id || "") + ")" : "Source non reconnue") + " : Cassandra la prend selon sa règle.</span></div>" +
        '<button class="btn mini" data-a="maintenant" data-id="' + esc(m.id) + '"' + (S.occupe ? " disabled" : "") + ">Maintenant</button></div>").join("") + "</div>" :
        '<div class="vide"><b>Tout est à jour.</b><br><span class="note">Dernière lecture du registre : à l’instant.</span></div>') + "</div>" +
      '<div class="g2"><div class="carte"><h3>Ce que je laisse de côté</h3>' + (!S.constats || S.constats.chargement ? '<p class="note">Je regarde…</p>' : cote.length ? '<div class="liste">' + cote.map((c) => '<div class="li"><div class="sp"><span class="note" style="color:var(--txt)">' + esc(c) + "</span></div></div>").join("") + "</div>" : '<p class="note">Rien : tout ce que ma règle permet est fait.</p>') + "</div>" +
      '<div class="carte"><h3>Quand</h3><div class="barre"><div style="flex:1;min-width:180px"><b>Fenêtre de maintenance</b><span class="note" style="display:block">Cassandra n’applique rien en dehors. Une urgence (module révoqué, module en échec) n’attend pas.</span></div><select class="sel" data-reglage="modules.fenetre" aria-label="Fenêtre de maintenance">' +
      Object.entries(FENETRES).map(([k, v]) => '<option value="' + k + '"' + (k === fen ? " selected" : "") + ">" + esc(v) + "</option>").join("") + "</select></div>" +
      '<p class="note">Après chaque mise à jour, la santé du module est surveillée ; si elle tourne mal, la version précédente est remise toute seule et la version fautive n’est jamais reprise.</p></div></div>';
  }

  // ── Sources ─────────────────────────────────────────────────────────
  function src() {
    chargerRegistre();
    const o = off(), a = S.reg && S.reg.autre;
    const jours = o && o.expire ? Math.floor((o.expire - Date.now() / 1000) / 86400) : null;
    const carte = !S.reg && S.regCharge ? '<div class="carte"><p class="note">Lecture du registre officiel…</p></div>' : !o || o.erreur ? regMuet() :
      '<div class="carte"><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><div class="ico">' + ic("shield") + '</div><div class="sp" style="flex:1;min-width:220px"><h3>Registre officiel de Cassandra ' + pill("verrouillé", "ok", "lock") + '</h3><div class="mono note">' + esc(o.url) + '</div></div><button class="btn mini" data-a="registre">Relire</button></div>' +
        '<div class="g2"><div><div class="lib">Signature</div><div>Clé racine « ' + esc(o.signe_par || "") + ' »</div></div><div><div class="lib">Fraîcheur de l’index</div><div>Émis le ' + jour(o.emis) + ", valable jusqu’au " + jour(o.expire) + (jours !== null ? ' <span class="p ' + (jours < 14 ? "al" : "ok") + '">' + jours + " j</span>" : "") + '</div></div><div><div class="lib">Contenu</div><div>' + (o.modules || []).length + " module(s) · " + (o.editeurs || []).length + " éditeur(s) vérifié(s) · " + (o.revocations || []).length + ' révocation(s)</div></div></div>' +
        '<p class="note">Intégré à l’application : il ne se retire pas et ne se modifie pas. C’est le seul dont la signature donne le niveau « Officiel ».</p></div>';
    const editeurs = o && !o.erreur ? '<div class="carte"><h3>Éditeurs vérifiés ' + pill("par le registre officiel", "ac", "shield") + '</h3>' + ((o.editeurs || []).length ? '<div class="liste">' + o.editeurs.map((e) => '<div class="li"><div class="sp"><b>' + esc(e.nom || e.id) + '</b><span class="note mono">ed_' + esc(e.id) + "</span></div>" + pill("vérifié", "ok") + "</div>").join("") + "</div>" : '<p class="note">Aucun pour l’instant.</p>') + '<p class="note">La liste vient de l’index signé : on la lit, on ne l’édite pas ici.</p></div>' : "";
    const autre = '<div class="carte"><h3>Un autre registre ' + pill("toujours non officiel", "al") + '</h3><p class="note">Le magasin d’un tiers. Chaque archive y est examinée comme une archive déposée ; il ne peut jamais donner le niveau « Officiel ».</p><div class="barre"><input type="text" id="lg-url" class="sel" style="flex:1 1 240px" placeholder="https://…/index.json" value="' + esc((a && a.url) || "") + '" aria-label="Adresse de l’autre registre"><button class="btn" data-a="url">Enregistrer</button></div>' +
      (a && a.erreur ? '<div class="alerte dg"><div class="sp">' + esc(a.erreur) + "</div></div>" : a && a.url ? '<p class="note">' + (a.modules || []).length + " module(s) proposé(s).</p>" : '<p class="note">Aucun. Vide = pas d’autre registre.</p>') + "</div>";
    return titre("Sources", "D’où viennent les modules : le registre officiel (fixe) et, si tu en ajoutes un, un autre registre.") + banDev() + carte + '<div class="g2">' + editeurs + autre + "</div>";
  }

  // ── Sécurité et confiance ───────────────────────────────────────────
  function sec_() {
    chargerRegistre();
    const o = off(), pol = (S.reg && S.reg.politique) || "signes";
    const rev = o && !o.erreur ? o.installes_revoques || [] : [];
    const perms = S.cat.filter((m) => { const p = m.permissions || {}; return m.confiance !== "interne" || (p.reseau || []).length + (p.ecritures || []).length + (p.privileges || []).length > 0; }).sort((a, b) => a.nom.localeCompare(b.nom));
    const verrous = S.cat.filter((m) => m.verrou);
    return titre("Sécurité et confiance", "Qui peut installer quoi, ce que chaque module a le droit de faire, et ce qui a été révoqué.") + banDev() +
      (rev.length ? '<div class="alerte dg"><div class="ico sm" style="background:color-mix(in srgb,var(--danger) 14%,transparent);color:var(--danger)">' + ic("warn") + '</div><div class="sp"><b>' + rev.length + " module(s) installé(s) révoqué(s) par le registre.</b> <span class=\"note\">" + rev.map((x) => esc(x.nom + " " + x.version + " : " + x.raison)).join(" · ") + ' Cassandra le retire dès qu’elle passe (niveau Entretien et au-dessus).</span></div></div>' : "") +
      '<div class="carte"><h3>Ce que Cassandra se refuse, quel que soit son niveau</h3><div class="liste">' + [["shield", "Installer ce qui n’est pas signé", "Seuls le registre officiel et les éditeurs vérifiés comptent pour elle."], ["warn", "Installer ou garder un module révoqué", "Elle le retire ; il reste 30 jours en corbeille."], ["lock", "Désactiver un module vital", "Le noyau le refuse de toute façon."], ["eye", "Prendre seule plus de permissions chez un éditeur tiers", "Une mise à jour qui demande plus reste à l’écart, et elle le dit."], ["lock", "Toucher à un module verrouillé", "Seul l’utilisateur pose et lève un verrou."]].map((x) => '<div class="li"><div class="ico sm">' + ic(x[0]) + '</div><div class="sp"><b>' + x[1] + "</b><span class=\"note\">" + x[2] + "</span></div></div>").join("") + "</div></div>" +
      '<div class="carte"><h3>Politique de confiance</h3><div style="display:flex;flex-direction:column;gap:8px">' + [["signes", "Paquets signés seulement", "Racine Cassandra, éditeur vérifié, ou clé que tu as posée. Recommandé."], ["tous", "Tout accepter", "Archives non signées comprises. Réservé à un module que tu écris toi-même."]].map((r) => '<button class="radio' + (pol === r[0] ? " on" : "") + '" data-a="politique" data-k="' + r[0] + '" role="radio" aria-checked="' + (pol === r[0]) + '"><i></i><div><b>' + r[1] + '</b><span class="note" style="display:block">' + r[2] + "</span></div></button>").join("") + "</div></div>" +
      '<div class="carte"><h3>Ce que chaque module demande</h3><p class="note">Déclaratives : le module tourne dans Cassandra. Les modules du noyau sans permission particulière ne sont pas listés.</p>' + (perms.length ? '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr>' + ["Module", "Niveau", "Réseau", "Écritures", "Privilèges"].map((h) => '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);font:600 11px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint)">' + h + "</th>").join("") + "</tr></thead><tbody>" +
        perms.map((m) => { const p = m.permissions || {}; return '<tr><td style="padding:8px 10px;border-bottom:1px solid var(--line)"><b>' + esc(m.nom) + '</b></td><td style="padding:8px 10px;border-bottom:1px solid var(--line)">' + niveauMod(m) + "</td>" + [(p.reseau || []).length, (p.ecritures || []).length, (p.privileges || []).length].map((n) => '<td style="padding:8px 10px;border-bottom:1px solid var(--line)" class="mono">' + n + "</td>").join("") + "</tr>"; }).join("") + "</tbody></table></div>" : '<p class="note">Rien à signaler.</p>') + "</div>" +
      '<div class="carte"><h3>Modules verrouillés</h3>' + (verrous.length ? '<div class="liste">' + verrous.map((m) => '<div class="li"><div class="sp"><b>' + esc(m.nom) + '</b><span class="note">Cassandra n’y touche pas.</span></div><button class="btn mini" data-a="deverrouiller" data-id="' + esc(m.id) + '">Déverrouiller</button></div>').join("") + "</div>" : '<p class="note">Aucun. Un verrou se pose depuis le tiroir d’un module.</p>') + "</div>";
  }

  // ── Santé ───────────────────────────────────────────────────────────
  async function chargerSante() {
    if (S.santeCharge) return;
    S.santeCharge = true;
    try { const r = await agir("modules.sante"); S.sante = r.modules || {}; }                       // tous les modules en une passe
    catch (e) { S.sante = {}; S.cat.forEach((m) => { S.sante[m.id] = { erreur: e.message || String(e) }; }); }
    S.santeCharge = false;
    if (sec === "sante") dessiner();
  }
  function sante() {
    if (!Object.keys(S.sante).length && !S.santeCharge) chargerSante();
    const V = { sain: ["sain", "ok", "check"], a_surveiller: ["à surveiller", "al", "eye"], en_echec: ["en échec", "dg", "warn"] };
    const lignes = S.cat.filter((m) => m.etat === "actif").map((m) => ({ m: m, s: S.sante[m.id] }));
    const mal = lignes.filter((x) => x.s && x.s.verdict && x.s.verdict !== "sain");
    const fait = lignes.filter((x) => x.s).length;
    return titre("Santé", "Chaque module est sondé : moteurs, échecs, refus. Cassandra suit et agit ; une panne n’arrête pas Cassandra.") + banDev() + banAvance() +
      (mal.length ? '<div class="alerte al"><div class="ico sm al">' + ic("eye") + '</div><div class="sp"><b>' + mal.length + " module(s) à surveiller.</b> <span class=\"note\">" + mal.map((x) => esc(x.m.nom)).join(", ") + ". Cassandra les suit ; s’ils échouent en boucle, elle les met en pause et te le dit.</span></div></div>" : "") +
      '<div class="carte"><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>Modules actifs</h3><span class="note">' + (S.santeCharge ? "Lecture… " + fait + "/" + lignes.length : lignes.length + " lus") + "</span></div>" +
      '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr>' + ["Module", "État", "Moteurs", "Actes 24 h", "Constats"].map((h) => '<th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);font:600 11px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint)">' + h + "</th>").join("") + "</tr></thead><tbody>" +
      lignes.map((x) => { const s = x.s, v = s && V[s.verdict]; const n24 = s && s.capacites_24h ? Object.values(s.capacites_24h).reduce((a, b) => a + b, 0) : 0; return '<tr><td style="padding:8px 10px;border-bottom:1px solid var(--line)"><b>' + esc(x.m.nom) + '</b></td><td style="padding:8px 10px;border-bottom:1px solid var(--line)">' + (s ? (s.erreur ? pill("illisible", "dg") : v ? pill(v[0], v[1], v[2]) : pill("—", "")) : '<span class="note">…</span>') + '</td><td class="mono" style="padding:8px 10px;border-bottom:1px solid var(--line)">' + (s && s.moteurs ? s.moteurs.length : "—") + '</td><td class="mono" style="padding:8px 10px;border-bottom:1px solid var(--line)">' + (s && !s.erreur ? n24 : "—") + '</td><td class="mono" style="padding:8px 10px;border-bottom:1px solid var(--line)">' + (s && s.constats_ouverts != null ? s.constats_ouverts : "—") + "</td></tr>"; }).join("") + "</tbody></table></div></div>" +
      '<div class="carte"><h3>Ce que Cassandra fait seule</h3><p class="note">Un module qui échoue en boucle est mis en pause (niveau Entretien et au-dessus) ; une mise à jour qui tourne mal est remise en arrière. Chaque geste est dans le journal, avec son « Défaire ».</p></div>';
  }

  // ── Journal et versions ─────────────────────────────────────────────
  function jour_() {
    const f = S.jfil, A = S.act.actes || [];
    const l = A.map((a, i) => [a, i]).filter(([a]) => f === "tout" || (f === "auto" && ["cassandra", "itare", "agent", "noyau"].includes(a.par)) || (f === "utilisateur" && !["cassandra", "itare", "agent", "noyau"].includes(a.par)));
    return titre("Journal et versions", "Tout ce qui est arrivé aux modules : qui l’a fait, pourquoi, et le geste qui le défait.") + banDev() +
      '<div class="carte"><div class="barre"><h3 style="flex:1">Récit</h3><div class="seg">' + [["tout", "Tout"], ["auto", "Cassandra"], ["utilisateur", "Utilisateurs"]].map((c) => '<button class="' + (f === c[0] ? "on" : "") + '" data-jfil="' + c[0] + '">' + c[1] + "</button>").join("") + '</div></div><div class="liste">' +
      (l.length ? l.map(([a, i]) => recitLi(a, i)).join("") : '<div class="vide"><b>Rien pour l’instant.</b><br><span class="note">Ce que Cassandra fait ou laisse de côté apparaîtra ici.</span></div>') + "</div></div>" +
      '<div class="carte"><h3>Versions</h3><p class="note">Les versions restaurables d’un module installé par archive se lisent dans son tiroir (onglet Versions) : la version courante part elle-même en sauvegarde à chaque remplacement.</p></div>';
  }

  // ── Développeur ─────────────────────────────────────────────────────
  function dev() {
    const code = (t) => '<pre style="margin:0;background:color-mix(in srgb,var(--txt-strong,#111) 6%,transparent);border-radius:10px;padding:11px 13px;font:12px/1.55 ui-monospace,Menlo,monospace;overflow-x:auto">' + esc(t) + "</pre>";
    return titre("Développeur", "Créer, tester et publier un module.") +
      '<div class="g2"><div class="carte"><h3>Nouveau module</h3><p class="note">Le générateur écrit un squelette valide : manifeste (section, importance, « sans »), module et banc.</p>' + code('python CN_main.py module nouveau mon_module --nom "Mon module" --famille gestion --importance optionnel --dest donnees/extensions') + '<p class="note">Une section nouvelle se déclare dans le manifeste : <span class="mono">[[sections]]</span> (nom, icône, ordre).</p></div>' +
      '<div class="carte"><h3>Publier</h3><p class="note">Construis l’archive, signe-la avec ta clé d’éditeur, puis propose-la au registre officiel (ou publie-la sur ton propre registre).</p>' + code("python outils/CN_paquet.py construire mon_module/\npython outils/CN_paquet.py signer --cle ed_moi.pem mon_module-0.1.0.cmod") + "</div></div>" +
      '<div class="carte"><h3>Documentation</h3><p class="note">Le contrat d’un module, son cycle de vie, la règle d’autonomie de Cassandra et le registre sont décrits dans <span class="mono">docs/CN_MODULES_DEVELOPPEUR.md</span>, <span class="mono">docs/CN_AUTONOMIE_MODULES.md</span> et <span class="mono">docs/CN_REGISTRE.md</span>.</p></div>';
  }

  // ── Réglages : ceux du module « modules » (autonomie, fenêtre, confiance, autre registre), avec l'enregistrement à la sortie du champ ───────
  function reg() { return titre("Réglages", "Le comportement général de la gestion des modules.") + '<div id="lg-reglages"><div class="carte vide">Lecture…</div></div>'; }
  async function monterReglages() {
    const z = racine.querySelector("#lg-reglages"), M = CASS.modulesUi; if (!z) return;
    if (!M) { z.innerHTML = '<div class="carte vide">Écran indisponible.</div>'; return; }
    try { await M.lire(); const m = M.catalogue().find((x) => x.id === "modules"); if (!m) throw new Error("module introuvable"); z.innerHTML = '<div class="carte">' + M.fiche(m, "global", false) + "</div>"; M.lierChamps(z, async () => { await rafraichir(); }); }
    catch (e) { z.innerHTML = '<div class="carte vide">Les réglages ne se lisent pas : ' + esc(e.message || e) + "</div>"; }
  }

  // ── le tiroir d'un module ───────────────────────────────────────────
  function fermerTiroir() { ["lg-tiroir", "lg-voile"].forEach((i) => { const e = document.getElementById(i); if (e) e.remove(); }); S.ouvert = ""; }
  function ouvrir(id, onglet) {
    const m = S.cat.find((x) => x.id === id); if (!m) return;
    S.ouvert = id; S.onglet = onglet || "apercu";
    fermerTiroir(); S.ouvert = id;
    const v = document.createElement("div"); v.className = "kit-v"; v.id = "lg-voile"; v.addEventListener("click", fermerTiroir);
    const t = document.createElement("aside"); t.className = "kit-t"; t.id = "lg-tiroir"; t.setAttribute("role", "dialog"); t.setAttribute("aria-modal", "true"); t.setAttribute("aria-label", "Détail du module " + m.nom);
    document.body.appendChild(v); document.body.appendChild(t);
    t.addEventListener("click", (e) => { const b = e.target.closest("[data-t]"); if (b) gesteTiroir(b, m); });
    dessinerTiroir(m, null);
    const f = t.querySelector("[data-t=fermer]"); if (f) f.focus();
    if (S.onglet === "sante" || S.onglet === "versions") chargerOnglet(m);
  }
  async function chargerOnglet(m) {
    let r = null; try { r = S.onglet === "sante" ? await agir("modules.sante", { module: m.id }) : await agir("modules.versions", { module: m.id }); } catch (e) { r = { erreur: e.message || String(e) }; }
    if (S.ouvert === m.id) dessinerTiroir(m, r);
  }
  function dessinerTiroir(m, extra) {
    const t = document.getElementById("lg-tiroir"); if (!t) return;
    const on = m.etat === "actif", av = avance(), reque = (m.requis_par || []).map(nomDe);
    const ONG = [["apercu", "Aperçu"], ["dep", "Dépendances"], ["perm", "Permissions"], ["sante", "Santé"], ["versions", "Versions"]];
    const p = m.permissions || {};
    const corps = {
      apercu: '<div class="carte"><div class="lib">Sans lui</div><p><b>' + esc(m.sans || "Non déclaré.") + "</b></p>" + (reque.length ? '<p class="note">Cela touche aussi : ' + reque.map(esc).join(", ") + ".</p>" : "") + "</div>" +
        '<div class="carte"><div class="reglage"><div class="sp"><b>Cassandra n’y touche pas</b><span class="note" style="display:block">Verrou : ni mise à jour, ni pause, ni retrait par elle. Utile pour un module que tu règles à la main.</span></div><button class="sw' + (m.verrou ? " on" : "") + '" data-t="verrou" aria-label="Verrouiller ' + esc(m.nom) + '" role="switch" aria-checked="' + !!m.verrou + '"' + (m.importance === "vital" ? " disabled" : "") + "></button></div></div>" +
        '<div class="carte"><div class="lib">Famille</div><div>' + esc(sectionDe(m.famille || "autres").libelle) + '</div><div class="lib">Auteur</div><div>' + esc(m.auteur || "—") + '</div><div class="lib">Licence</div><div>' + esc(m.licence || "—") + "</div></div>",
      dep: '<div class="carte"><div class="lib">Il a besoin de</div><div>' + ((m.requiert || []).map((x) => '<span class="p">' + esc(x) + "</span>").join(" ") || '<span class="note">rien</span>') + '</div><div class="lib">Ont besoin de lui</div><div>' + ((m.requis_par || []).map((x) => '<span class="p">' + esc(x) + "</span>").join(" ") || '<span class="note">personne</span>') + "</div></div>",
      perm: '<div class="carte"><div class="lib">Ce qu’il demande</div><div class="note">Réseau : ' + esc((p.reseau || []).join(", ") || "aucun") + "</div><div class=\"note\">Écritures : " + esc((p.ecritures || []).join(", ") || "aucune") + "</div><div class=\"note\">Privilèges : " + esc((p.privileges || []).join(", ") || "aucun") + "</div></div><p class=\"note\">Déclaratives : le module tourne dans Cassandra. Elles servent à décider, pas encore à contenir.</p>",
      sante: extra ? (extra.erreur ? '<div class="alerte dg"><div class="sp">' + esc(extra.erreur) + "</div></div>" : '<div class="carte"><div class="lib">Verdict</div><div>' + pill({ sain: "sain", a_surveiller: "à surveiller", en_echec: "en échec" }[extra.verdict] || extra.verdict || "—", extra.verdict === "sain" ? "ok" : extra.verdict === "en_echec" ? "dg" : "al") + '</div><div class="lib">Constats ouverts</div><div>' + esc(extra.constats_ouverts == null ? "—" : extra.constats_ouverts) + "</div></div>") : '<p class="note">Lecture…</p>',
      versions: extra ? (extra.erreur ? '<div class="alerte dg"><div class="sp">' + esc(extra.erreur) + "</div></div>" : '<div class="carte"><div class="lib">Versions restaurables</div>' + ((extra.sauvegardes || []).length ? extra.sauvegardes.map((s) => '<div class="note mono">' + esc(s.version) + " · " + esc(s.raison) + " · " + esc(depuis(s.ts)) + "</div>").join("") : '<p class="note">Aucune : ce module est livré avec le noyau, ou jamais remplacé.</p>') + "</div>") : '<p class="note">Lecture…</p>',
    }[S.onglet];
    t.innerHTML = '<div class="tete"><div style="display:flex;gap:12px;align-items:center"><div class="ico">' + iconeMod(m) + '</div><div style="flex:1;min-width:0"><h2>' + esc(m.nom) + '</h2><div class="mono note">' + esc(m.id) + " · v" + esc(m.version) + '</div></div><button class="btn mini" data-t="fermer">Fermer</button></div><div style="display:flex;gap:6px;flex-wrap:wrap">' +
      niveauMod(m) + pill((IMP[m.importance] || ["—"])[0], (IMP[m.importance] || [])[1]) + pill(on ? "actif" : "inactif", on ? "ok" : "") + '</div><div class="onglets" role="tablist">' + ONG.map((o) => '<button role="tab" class="' + (S.onglet === o[0] ? "on" : "") + '" data-t="onglet" data-o="' + o[0] + '">' + o[1] + "</button>").join("") + '</div></div><div class="corps">' + corps + "</div>" +
      '<div class="pied">' + (m.importance === "vital" ? '<span class="note">Vital : ne se désactive ni ne se désinstalle.</span>' : av ? '<button class="btn" data-t="bascule">' + (on ? "Désactiver" : "Activer") + "</button>" : '<button class="btn pri" data-t="demander">Demander à Cassandra de le ' + (on ? "désactiver" : "activer") + '</button><span class="note">Les boutons directs sont dans le « Mode avancé ».</span>') + "</div>";
  }
  async function gesteTiroir(b, m) {
    const g = b.dataset.t;
    if (g === "fermer") return fermerTiroir();
    if (g === "onglet") { S.onglet = b.dataset.o; dessinerTiroir(m, null); if (S.onglet === "sante" || S.onglet === "versions") chargerOnglet(m); return; }
    if (g === "demander") { fermerTiroir(); return demander((m.etat === "actif" ? "Désactive " : "Active ") + m.nom); }
    try {
      if (g === "verrou") { await agir("modules.verrouiller", { module: m.id, verrou: !m.verrou }); dire(m.verrou ? m.nom + " : Cassandra peut de nouveau s’en occuper." : m.nom + " : Cassandra n’y touchera plus.", "ok"); }
      else if (g === "bascule") { if (!await basculer(m)) return; }
      await rafraichir(); const n = S.cat.find((x) => x.id === m.id); if (n) dessinerTiroir(n, null);
    } catch (e) { dire(e.message || String(e), "err"); }
  }

  // ── l'impact d'un geste direct (Mode avancé) : on le dit AVANT, avec ce qui s'arrêterait ou s'activerait aussi ───────
  function dependants(id, vus) { vus = vus || new Set(); S.cat.forEach((x) => { if ((x.requiert || []).indexOf(id) >= 0 && x.etat === "actif" && !vus.has(x.id)) { vus.add(x.id); dependants(x.id, vus); } }); return vus; }
  function atirer(id, vus) { vus = vus || new Set(); const m = S.cat.find((x) => x.id === id); ((m && m.requiert) || []).forEach((r) => { const d = S.cat.find((x) => x.id === r); if (d && d.etat !== "actif" && !vus.has(r)) { vus.add(r); atirer(r, vus); } }); return vus; }
  const confirmer = CASS.kit.confirmer;
  async function basculer(m) {
    if (m.etat === "actif") {
      const dep = [...dependants(m.id)].map(nomDe);
      if (dep.length) { if (!await confirmer("Désactiver " + m.nom + " ?", '<p class="note">Cela arrêtera aussi, parce qu’ils en dépendent :</p><ul class="lst">' + dep.map((x) => "<li><b>" + esc(x) + "</b></li>").join("") + '</ul><p class="note">Leurs données restent.</p>', "Tout désactiver", true)) return false; await agir("modules.desactiver", { module: m.id, cascade: true }); }
      else await agir("modules.desactiver", { module: m.id });
      dire(m.nom + " désactivé.", "ok"); return true;
    }
    const tire = [...atirer(m.id)], bloque = tire.filter((id) => (S.cat.find((x) => x.id === id) || {}).etat === "a_installer");
    if (m.etat === "a_installer" || bloque.length) { dire("Il faut d’abord l’installer" + (bloque.length ? " : " + bloque.map(nomDe).join(", ") : "") + ".", "err"); return false; }
    if (tire.length) { if (!await confirmer("Activer " + m.nom + " ?", '<p class="note">Cela activera aussi, parce qu’il en a besoin :</p><ul class="lst">' + tire.map((x) => "<li><b>" + esc(nomDe(x)) + "</b></li>").join("") + "</ul>", "Tout activer", false)) return false; }
    await agir("modules.activer", { module: m.id, avec_dependances: true });
    dire(m.nom + " activé.", "ok"); return true;
  }

  // ── les gestes de la page ────────────────────────────────────────────
  function demander(texte) {
    if (CASS.disposition && CASS.disposition.demander) CASS.disposition.demander(texte);
    else dire("L’assistant n’est pas disponible sur cet écran.", "err");
  }
  async function rafraichir() { await charger(); dessiner(); }
  async function geste(b) {
    const a = b.dataset.a;
    try {
      if (a === "avance") { ecrire("lg.avance", avance() ? "0" : "1"); dessiner(); return; }
      if (a === "rep") { S.rep.has(b.dataset.id) ? S.rep.delete(b.dataset.id) : S.rep.add(b.dataset.id); dessiner(); return; }
      if (a === "reset") { S.fam = "toutes"; S.imp = "toutes"; S.etat = "tous"; S.q = ""; dessiner(); return; }
      if (a === "demande") { const d = racine.querySelector("#lg-dem"), v = d ? d.value.trim() : ""; if (d) d.value = ""; if (v) demander(v); else dire("Dis-lui ce que tu veux.", ""); return; }
      if (a === "gel") { await agir("urgence.geler", { actif: !S.act.gel }); dire(S.act.gel ? "Cassandra reprend." : "Cassandra est en pause : elle observe, elle n’agit plus.", "ok"); await rafraichir(); return; }
      if (a === "passe") { S.occupe = true; dessiner(); const r = await agir("modules.entretien", { forcer: true }); S.occupe = false; S.constats = null; dire((r.actions || []).length ? (r.actions.length + " geste(s) fait(s).") : "Passe faite : rien à faire pour l’instant.", "ok"); await rafraichir(); return; }
      if (a === "autonomie") { await agir("reglages.regler", { cle: "modules.autonomie", valeur: b.dataset.k }); dire("Autonomie : " + NIV[b.dataset.k][0] + ".", "ok"); S.constats = null; await rafraichir(); return; }
      if (a === "defaire") { const l = S.act.actes[+b.dataset.i]; if (!l) return; await agir("modules.annuler", { module: l.module, geste: l.geste }); dire("C’est défait. Cassandra en prend note.", "ok"); await rafraichir(); return; }
      if (a === "ensemble") { const E = ensembles(); if (b.dataset.id === "tout") S.choix = S.choix.size === E.length ? new Set() : new Set(E.map((e) => e.id)); else S.choix.has(b.dataset.id) ? S.choix.delete(b.dataset.id) : S.choix.add(b.dataset.id); dessiner(); return; }
      if (a === "plus-tard") { ecrire("lg.accueil", "1"); dessiner(); return; }
      if (a === "mise-en-place") {
        const ids = aActiver(); S.occupe = true; dessiner(); let fait = 0; const rates = [];
        for (const id of ids) { const m = S.cat.find((x) => x.id === id); if (!m || m.etat === "actif") continue; if (m.etat === "a_installer") { rates.push(m.nom + " (à installer d’abord)"); continue; }
          try { await agir("modules.activer", { module: id, avec_dependances: true, pourquoi: "Mise en place de l'instance : ensembles choisis à l'accueil." }); fait++; } catch (e) { rates.push(m.nom + " (" + (e.message || e) + ")"); } }
        S.occupe = false; S.choix = new Set(); ecrire("lg.accueil", "1");
        dire(fait + " module(s) activé(s)" + (rates.length ? ". Pas activés : " + rates.join(" ; ") : "."), rates.length ? "" : "ok"); await rafraichir(); return;
      }
      if (a === "registre") { S.reg = null; await chargerRegistre(true); return; }
      if (a === "maintenant") { S.occupe = true; dessiner(); const r = await agir("modules.ajouter", { module: b.dataset.id, pourquoi: "Mise à jour demandée tout de suite par l'utilisateur." }); S.occupe = false; S.reg = null; S.constats = null; dire(r && r.refuse ? r.refuse : nomDe(b.dataset.id) + " est à jour.", r && r.refuse ? "" : "ok"); await rafraichir(); chargerRegistre(true); return; }
      if (a === "url") { const v = (racine.querySelector("#lg-url") || {}).value || ""; await agir("reglages.regler", { cle: "modules.registre_url", valeur: v.trim() }); dire(v.trim() ? "Autre registre enregistré." : "Autre registre retiré.", "ok"); S.reg = null; await chargerRegistre(true); return; }
      if (a === "politique") { await agir("reglages.regler", { cle: "modules.politique_confiance", valeur: b.dataset.k }); dire("Politique : " + (b.dataset.k === "signes" ? "paquets signés seulement." : "tout accepter."), "ok"); S.reg = null; await chargerRegistre(true); dessiner(); return; }
      if (a === "deverrouiller") { await agir("modules.verrouiller", { module: b.dataset.id, verrou: false }); dire(nomDe(b.dataset.id) + " : Cassandra peut de nouveau s’en occuper.", "ok"); await rafraichir(); return; }
      if (a === "bascule") { const m = S.cat.find((x) => x.id === b.dataset.id); if (!m) return; await basculer(m); await rafraichir(); return; }
    } catch (e) { S.occupe = false; dire(e.message || String(e), "err"); dessiner(); }
  }

  // ── le montage ──────────────────────────────────────────────────────
  function dessiner() {
    if (!racine) return;
    const focus = document.activeElement && document.activeElement.id;
    let h;
    if (sec === "vue") h = vue();
    else if (sec === "inst") h = inst();
    else if (sec === "shop") h = '<div id="lg-boutique"></div>';
    else if (sec === "maj") h = maj();
    else if (sec === "src") h = src();
    else if (sec === "sec") h = sec_();
    else if (sec === "sante") h = sante();
    else if (sec === "jour") h = jour_();
    else if (sec === "dev") h = dev();
    else if (sec === "reg") h = reg();
    else h = vue();
    racine.innerHTML = h;
    if (sec === "shop" && CASS.pageAppStore) { const z = racine.querySelector("#lg-boutique"); CASS.pageAppStore(z); }
    if (focus === "lg-q") { const q = racine.querySelector("#lg-q"); if (q) { q.focus(); q.setSelectionRange(99, 99); } }
    if (sec === "vue") chargerConstats();
    if (sec === "reg") monterReglages();
  }
  const compteCourant = async () => { if (CASS.moi && CASS.moi.compte) return CASS.moi.compte; try { const m = await (await fetch("/api/moi")).json(); return m.compte || ""; } catch (e) { return ""; } };
  CASS.pageMesApplications = async function (corps, h) {
    CASS.kit.injecter();
    corps.innerHTML = ""; const z = document.createElement("div"); z.className = "kit"; corps.appendChild(z);
    let liste = [];
    const dessin = () => {
      z.innerHTML = '<div class="grille">' + (liste.length ? liste.map((e) => '<div class="carte mod' + (e.masque ? " off" : "") + '"><div class="l1"><div class="ico' + (e.masque ? " off" : "") + '">' + ic("box") + '</div><div class="sp"><h3>' + esc(e.libelle) + '</h3></div></div><div class="pied"><button class="btn mini pri" data-ouvrir="' + esc(e.id) + '">Ouvrir</button><label class="note" style="margin-left:auto;display:flex;gap:8px;align-items:center">Dans mon menu <button class="sw' + (e.masque ? "" : " on") + '" data-menu="' + esc(e.id) + '" role="switch" aria-checked="' + !e.masque + '" aria-label="Dans mon menu : ' + esc(e.libelle) + '"></button></label></div></div>').join("") :
        '<div class="carte vide">Aucune application pour l’instant.</div>') + "</div>" +
        '<div class="carte"><h3>Il te manque quelque chose ?</h3><p class="note">Dis-le à Cassandra, avec tes mots. Elle décide et te répond : tu n’as rien à valider.</p><div class="demande"><input id="lg-dem" placeholder="« Je voudrais gérer mes factures »" aria-label="Demander une application à Cassandra"><button class="btn pri" data-a="demande">Demander</button></div></div>';
    };
    const lireTout = async () => { try { liste = (((await agir("menus.mes_entrees")) || {}).entrees || []).filter((e) => e.ecran !== "menus:vue_mes_applications"); } catch (e) { liste = []; } dessin(); };
    z.addEventListener("click", async (e) => {
      const o = e.target.closest("[data-ouvrir]"); if (o) { const x = liste.find((y) => y.id === o.dataset.ouvrir); if (x && CASS.ouvrirEcran) CASS.ouvrirEcran(x.ecran, x.libelle); return; }
      const sw = e.target.closest("[data-menu]"); if (sw) { const x = liste.find((y) => y.id === sw.dataset.menu); if (!x) return;
        try { await agir("menus.personnaliser_entree", { entree: x.id, masque: !x.masque, compte: await compteCourant() }); dire(x.masque ? "Remise dans ton menu." : "Retirée de ton menu.", "ok"); await lireTout(); if (h && h.rafraichir) h.rafraichir(); } catch (er) { dire(er.message || String(er), "err"); } return; }
      const d = e.target.closest('[data-a="demande"]'); if (d) { const i = z.querySelector("#lg-dem"), v = i ? i.value.trim() : ""; if (i) i.value = ""; if (v && h && h.demander) h.demander(v); else if (!v) dire("Dis-lui ce que tu veux.", ""); }
    });
    z.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "lg-dem") { e.preventDefault(); const v = e.target.value.trim(); e.target.value = ""; if (v && h && h.demander) h.demander(v); } });
    z.innerHTML = '<div class="carte vide">Lecture…</div>'; await lireTout();
  };
  CASS.logitheque = { sections: SECTIONS };
  CASS.pageLogitheque = async function (corps, section, h) {
    hooks = h || {}; sec = SECTIONS.some((x) => x[0] === section) ? section : "vue";
    CASS.kit.injecter();
    fermerTiroir();
    corps.innerHTML = ""; racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine); corpsEl = corps;
    racine.innerHTML = '<div class="carte vide">Lecture des modules…</div>';
    racine.addEventListener("click", (e) => {
      const go = e.target.closest("[data-go]"); if (go) { if (hooks.aller) hooks.aller(go.dataset.go); return; }
      const sug = e.target.closest("[data-sug]"); if (sug) { demander(sug.dataset.sug); return; }
      const jf = e.target.closest("[data-jfil]"); if (jf) { S.jfil = jf.dataset.jfil; dessiner(); return; }
      const et = e.target.closest("[data-etat]"); if (et) { S.etat = et.dataset.etat; dessiner(); return; }
      const b = e.target.closest("[data-a]"); if (b) { e.stopPropagation(); geste(b); return; }
      const m = e.target.closest("[data-ouvrir]"); if (m) ouvrir(m.dataset.ouvrir);
    });
    racine.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-ouvrir]")) { e.preventDefault(); ouvrir(e.target.dataset.ouvrir); } if (e.key === "Enter" && e.target.id === "lg-dem") { e.preventDefault(); const v = e.target.value.trim(); e.target.value = ""; if (v) demander(v); } });
    racine.addEventListener("input", (e) => { if (e.target.id === "lg-q") { S.q = e.target.value; dessiner(); } });
    racine.addEventListener("change", (e) => {
      const k = e.target.dataset && e.target.dataset.sel; if (k) { S[k] = e.target.value; dessiner(); return; }
      const r = e.target.dataset && e.target.dataset.reglage;
      if (r) agir("reglages.regler", { cle: r, valeur: e.target.value }).then(async () => { dire("Enregistré.", "ok"); await rafraichir(); }).catch((x) => dire(x.message || String(x), "err"));
    });
    if (!escLie) { escLie = true; document.addEventListener("keydown", (e) => { if (e.key === "Escape" && document.getElementById("lg-tiroir")) fermerTiroir(); }); }
    try { await charger(); } catch (e) { racine.innerHTML = '<div class="carte vide">Les modules ne se lisent pas : ' + esc(e.message || e) + "</div>"; return; }
    dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
