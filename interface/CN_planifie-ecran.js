// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : ▼▼▼ BORNE CN version=0
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #7613f7
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=7613f7 ▼▼▼
// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Automatismes » du module planifie : les tâches planifiées du serveur (état, prochaine échéance), la fiche d'une tâche (historique, cibles, réglages, projets), une nouvelle tâche avec aperçu de l'horaire, l'audit et la maintenance.
// Les données viennent des capacités du module (planifie.unifiee, fiche, historique, apercu, audit, chevauchements, maintenance_etat, resume) ; les gestes : sauver, basculer, supprimer, executer, critique, lier, delier, reglages_poser, maintenance.
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, pill = K.pill, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const SCENES = [["taches", "Les tâches"], ["nouvelle", "Nouvelle tâche"], ["audit", "Audit"], ["maintenance", "Maintenance"]];
  const ETAT = { "cassé": ["cassée", "dg", "warn"], "échec": ["en échec", "dg", "warn"], "muet": ["muette", "al", "warn"], "inconnu": ["jamais vue", "", ""], "ok": ["ok", "", "check"], "désactivé": ["désactivée", "", ""] };
  const court = (t) => String(t || "").replace("T", " ").slice(0, 16);
  const dur = (ms) => (ms == null ? "" : ms >= 60000 ? (ms / 60000).toFixed(1) + " min" : ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : ms + " ms");
  const fiche = (titre, note, cote) => '<div class="li"><div class="sp"><b>' + titre + "</b>" + (note ? '<span class="note">' + note + "</span>" : "") + "</div>" + (cote || "") + "</div>";

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.planifie = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("planifie", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "taches", U: null, f: "", q: "", F: null, audit: null, chev: null, maint: null, apercu: null, charge: true, erreur: "" };
    const val = (id) => ((racine.querySelector(id) || {}).value || "").trim();

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { const r = await agir(cap, args); if (ok) dire(ok, "ok"); return r === undefined ? {} : r; } catch (e) { dire(e.message || String(e), "err"); return null; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] && !S.F ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0] && !S.F) + '">' + esc(s[1]) + "</button>").join("") + "</div>";

    function taches() {
      const U = S.U, c = U.compteurs || {};
      const q = S.q.toLowerCase();
      const l = U.taches.filter((t) => (!S.f || t.etat === S.f) && (!q || [t.commande, t.description, t.utilisateur, t.humain].some((x) => String(x || "").toLowerCase().indexOf(q) >= 0)));
      const puces = '<div class="chips"><button class="p ' + (!S.f ? "on" : "") + '" data-a="filtre" data-v="">Toutes ' + (c.total || 0) + "</button>" + Object.keys(ETAT).filter((e) => c[e]).map((e) => '<button class="p ' + (S.f === e ? "on" : ETAT[e][1]) + '" data-a="filtre" data-v="' + esc(e) + '">' + esc(ETAT[e][0]) + " " + c[e] + "</button>").join("") + "</div>";
      const src = U.source_systeme && !U.source_systeme.ok ? '<div class="carte"><p class="note">' + esc("La crontab du serveur n’a pas pu être lue : " + (U.source_systeme.erreur || "?")) + "</p></div>" : "";
      return src + '<div class="carte">' + puces + '<div class="barre"><input type="search" id="pl-q" placeholder="Chercher (Entrée)…" value="' + esc(S.q) + '" aria-label="Chercher"></div></div>' +
        '<div class="carte"><div class="liste">' + (l.length ? l.map((t) => { const e = ETAT[t.etat] || ETAT.inconnu; return fiche('<a href="#" data-a="fiche" data-k="' + esc(t.ref) + '">' + esc(t.description || t.commande) + "</a> " + pill(e[0], e[1], e[2]) + (t.critique ? " " + pill("critique", "al", "") : ""), esc([t.humain, t.utilisateur, t.prochaine ? "prochaine " + court(t.prochaine) : "", t.etat_detail].filter(Boolean).join(" · ")), '<span class="faint mono" style="font-size:11.5px">' + esc(court(t.derniere)) + "</span>"); }).join("") : '<div class="vide">Aucune tâche.</div>') + "</div></div>";
    }
    function detail() {
      const F = S.F, t = F.tache, e = ETAT[t.etat] || ETAT.inconnu, r = F.reglages || {};
      const gerable = t.id != null;
      const ex = (F.executions || []).slice().reverse().slice(0, 15).map((x) => fiche(esc(court(x.debut)) + " " + pill(x.code === 0 ? "ok" : "code " + x.code, x.code === 0 ? "" : "dg", ""), esc([x.declencheur, dur(x.duree_ms)].filter(Boolean).join(" · ")) + (x.sortie ? '<pre class="mono" style="white-space:pre-wrap;margin:4px 0 0;max-height:140px;overflow:auto">' + esc(String(x.sortie).slice(0, 800)) + "</pre>" : ""))).join("");
      const dernieres = K.courbe([{ name: "durée (s)", points: (F.executions || []).filter((x) => x.duree_ms > 0).map((x) => ({ ts: String(x.debut).slice(0, 19).replace("T", " "), v: Math.round(x.duree_ms / 100) / 10 })) }], { unite: "s", titre: "Durée des exécutions" });
      const avert = [F.destructive ? "Cette commande détruit des données." : "", F.lourde ? "Commande lourde." : "", F.chevauche ? "Une exécution dure plus longtemps que l’intervalle : elles se chevauchent." : "", (F.cibles || []).filter((x) => !x.present).map((x) => "Cible absente : " + x.chemin).join(" "), F.derive && F.derive.derive ? "Sa durée dérive." : ""].filter(Boolean);
      return '<div class="carte"><div class="barre"><h3 style="flex:1">' + esc(t.description || t.commande) + " " + pill(e[0], e[1], e[2]) + '</h3><button class="btn" data-a="retour">← Les tâches</button></div>' +
        '<p class="note mono" style="white-space:pre-wrap">' + esc(t.commande) + "</p>" + '<p class="note">' + esc([t.humain, t.horaire, t.utilisateur, t.etat_detail].filter(Boolean).join(" · ")) + "</p>" +
        (avert.length ? '<div class="alerte al"><div class="sp">' + avert.map(esc).join("<br>") + "</div></div>" : "") +
        '<div class="barre"><button class="btn pri" data-a="lancer" data-k="' + esc(t.ref) + '">Lancer maintenant</button><button class="btn" data-a="essai" data-k="' + esc(t.ref) + '">Essai à blanc</button>' +
        (gerable ? '<button class="btn" data-a="bascule" data-id="' + t.id + '" data-v="' + (t.actif ? 0 : 1) + '">' + (t.actif ? "Désactiver" : "Activer") + '</button><button class="btn dg" data-a="supprime" data-id="' + t.id + '">Supprimer</button>' : "") +
        '<button class="btn" data-a="critique" data-k="' + esc(t.ref) + '" data-v="' + (t.critique ? 0 : 1) + '">' + (t.critique ? "Ne plus la dire critique" : "La dire critique") + "</button></div>" +
        ((F.prochaines || []).length ? '<p class="note">Prochaines : ' + F.prochaines.map((p) => esc(court(typeof p === "string" ? p : p.at || p.quand || ""))).join(" · ") + "</p>" : "") + "</div>" +
        '<div class="carte"><h3>Les exécutions</h3>' + dernieres + '<div class="liste">' + (ex || '<div class="vide">Jamais lancée depuis Cassandra.</div>') + "</div></div>" +
        '<div class="carte"><h3>Réglages</h3><div class="barre"><label class="note">Essais <input id="pl-essais" type="number" min="0" max="5" value="' + (r.essais || 0) + '" style="max-width:70px"></label><label class="note">Fenêtre (min) <input id="pl-fen" type="number" min="0" value="' + (r.fenetre_min || 0) + '" style="max-width:80px"></label><label class="note"><input id="pl-verrou" type="checkbox"' + (r.verrou ? " checked" : "") + "> Un seul à la fois</label><button class=\"btn pri\" data-a=\"reglages\" data-k=\"" + esc(t.ref) + '">Enregistrer</button></div></div>' +
        '<div class="carte"><h3>Projets liés</h3><div class="liste">' + ((t.projets || []).length ? t.projets.map((p) => fiche(esc(p.nom), "", '<button class="p" data-a="delier" data-k="' + esc(t.ref) + '" data-p="' + p.id + '">Délier</button>')).join("") : '<div class="vide">Aucun projet.</div>') + '</div><div class="barre"><select class="sel" id="pl-proj" aria-label="Projet">' + (S.U.projets || []).map((p) => '<option value="' + p.id + '">' + esc(p.nom) + "</option>").join("") + '</select><button class="btn" data-a="lier" data-k="' + esc(t.ref) + '">Lier</button></div></div>' +
        ((F.modifs || []).length ? '<div class="carte"><h3>Modifications</h3><div class="liste">' + F.modifs.map((m) => fiche(esc(m.quoi), esc(m.acteur), '<span class="faint mono" style="font-size:11.5px">' + esc(court(m.ts)) + "</span>")).join("") + "</div></div>" : "");
    }
    function nouvelle() {
      const a = S.apercu;
      return '<div class="carte"><h3>Nouvelle tâche planifiée</h3><div class="barre"><input id="pl-desc" placeholder="À quoi elle sert" aria-label="Description"></div><div class="barre"><input id="pl-h" placeholder="0 4 * * *" class="mono" aria-label="Horaire cron"><button class="btn" data-a="apercu">Voir quand</button></div>' +
        (a ? '<p class="note">' + esc(a.humain || "") + "</p>" + ((a.prochaines || []).length ? '<p class="note">' + a.prochaines.map((p) => esc(court(typeof p === "string" ? p : p.at || p.quand || ""))).join(" · ") + "</p>" : "") : '<p class="note">Cinq champs : minute, heure, jour du mois, mois, jour de la semaine.</p>') +
        '<div class="barre"><input id="pl-cmd" placeholder="/chemin/vers/la/commande --option" class="mono" aria-label="Commande"></div><div class="barre"><button class="btn pri" data-a="creer">Créer</button></div><p class="note">La commande est écrite dans la crontab de root, une ligne à la fois ; si elle refuse, rien ne change.</p></div>';
    }
    function audit() {
      const A = S.audit || { collisions: [], sauvegardes_manquantes: [] }, C = (S.chev && S.chev.chevauchements) || [];
      return '<div class="carte"><h3>Tâches lourdes au même moment · ' + (A.collisions || []).length + '</h3><div class="liste">' + ((A.collisions || []).length ? A.collisions.map((x) => fiche(esc(x.at || x.quand || "collision"), esc(((x.taches || []).map((t) => t.libelle).join(", "))), pill("à répartir", "al", ""))).join("") : '<div class="vide">Aucune collision.</div>') + "</div></div>" +
        '<div class="carte"><h3>Qui dure plus que son intervalle · ' + C.length + '</h3><div class="liste">' + (C.length ? C.map((x) => fiche(esc(x.libelle), esc(x.duree_min + " min pour un intervalle de " + x.intervalle_min + " min"), x.verrou ? pill("verrouillée", "", "check") : pill("se chevauche", "al", "warn"))).join("") : '<div class="vide">Aucune ne se chevauche.</div>') + "</div></div>" +
        '<div class="carte"><h3>Projets sans sauvegarde planifiée · ' + (A.sauvegardes_manquantes || []).length + '</h3><div class="liste">' + ((A.sauvegardes_manquantes || []).length ? A.sauvegardes_manquantes.map((x) => fiche(esc(x.nom), esc(x.domaine || ""), pill("rien ne la sauvegarde", "dg", "warn"))).join("") : '<div class="vide"><b>Chaque projet d’infrastructure est sauvegardé.</b></div>') + "</div></div>";
    }
    function maintenance() {
      const m = S.maint || {};
      return '<div class="carte"><h3>Fenêtre de maintenance</h3><p class="note">Suspend toutes les tâches sauf les critiques, puis elles reprennent seules à l’heure dite.</p>' +
        (m.actif ? '<p>' + pill("en cours jusqu’à " + court(m.fin), "al", "warn") + '</p><div class="barre"><button class="btn pri" data-a="maint" data-v="0">Reprendre maintenant</button></div>' : '<div class="barre"><label class="note">Pendant <input id="pl-heures" type="number" min="1" max="24" value="4" style="max-width:70px"> h</label><button class="btn pri" data-a="maint" data-v="1">Suspendre</button></div>') + "</div>";
    }

    function dessiner() {
      let c;
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (!S.U) c = '<div class="carte"><h3>Les tâches ne répondent pas</h3><p class="note">' + esc(S.erreur || "Le module n’a rien rendu.") + "</p></div>";
      else if (S.F) c = detail();
      else c = ({ taches: taches, nouvelle: nouvelle, audit: audit, maintenance: maintenance }[S.scene] || taches)();
      racine.innerHTML = K.titre("Automatismes", "Les tâches planifiées du serveur : ce qui tourne, ce qui a cassé, ce qui va se lancer.") + barre() + c;
    }
    async function ouvrir(ref) { S.F = null; const F = await lire("planifie.fiche", { ref: ref }); if (F) S.F = F; else dire(S.erreur || "Tâche introuvable.", "err"); dessiner(); }
    async function recharger() { S.U = await lire("planifie.unifiee"); if (S.F) await ouvrir(S.F.tache.ref); else dessiner(); }
    async function aller(scene) {
      S.scene = scene; S.F = null; S.erreur = ""; dessiner();
      if (scene === "taches") S.U = await lire("planifie.unifiee");
      else if (scene === "audit") { const [a, c] = await Promise.all([lire("planifie.audit"), lire("planifie.chevauchements")]); S.audit = a; S.chev = c; }
      else if (scene === "maintenance") S.maint = await lire("planifie.maintenance_etat");
      dessiner();
    }

    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a; if (a.tagName === "A") e.preventDefault();
      const ref = a.dataset.k;
      if (k === "filtre") { S.f = a.dataset.v; dessiner(); }
      else if (k === "fiche") ouvrir(ref);
      else if (k === "retour") { S.F = null; dessiner(); }
      else if (k === "lancer" || k === "essai") {
        const essai = k === "essai";
        if (!essai && !await confirmer("Lancer cette tâche maintenant ?", '<p class="note">Ce que la commande fait ne se défait pas ; seule la ligne du journal se défait.</p>', "Lancer")) return;
        const r = await geste("planifie.executer", { ref: ref, essai: essai }, essai ? "Essai fait." : "Lancée."); if (r) ouvrir(ref);
      }
      else if (k === "bascule") { if (await geste("planifie.basculer", { id: +a.dataset.id, actif: a.dataset.v === "1" }, a.dataset.v === "1" ? "Tâche activée." : "Tâche désactivée.")) recharger(); }
      else if (k === "supprime") { if (!await confirmer("Supprimer cette tâche ?", '<p class="note">Elle sort de la crontab ; la ligne revient par « Défaire » dans le journal des gestes.</p>', "Supprimer", true)) return; if (await geste("planifie.supprimer", { id: +a.dataset.id }, "Tâche supprimée.")) { S.F = null; S.U = await lire("planifie.unifiee"); dessiner(); } }
      else if (k === "critique") { if (await geste("planifie.critique", { ref: ref, critique: a.dataset.v === "1" }, "Fait.")) recharger(); }
      else if (k === "reglages") { if (await geste("planifie.reglages_poser", { ref: ref, essais: +val("#pl-essais") || 0, fenetre_min: +val("#pl-fen") || 0, verrou: !!(racine.querySelector("#pl-verrou") || {}).checked }, "Réglages enregistrés.")) ouvrir(ref); }
      else if (k === "lier") { const p = +val("#pl-proj"); if (p && await geste("planifie.lier", { ref: ref, projet_id: p }, "Lien posé.")) recharger(); }
      else if (k === "delier") { if (await geste("planifie.delier", { ref: ref, projet_id: +a.dataset.p }, "Lien retiré.")) recharger(); }
      else if (k === "apercu") { const h = val("#pl-h"); if (!h) return; S.apercu = await lire("planifie.apercu", { expression: h, nombre: 5 }); dessiner(); const i = racine.querySelector("#pl-h"); if (i) i.value = h; }
      else if (k === "creer") {
        const d = val("#pl-desc"), h = val("#pl-h"), c = val("#pl-cmd"); if (!h || !c) { dire("Il faut un horaire et une commande.", "err"); return; }
        if (await geste("planifie.sauver", { description: d, horaire: h, commande: c }, "Tâche créée.")) { S.apercu = null; aller("taches"); }
      }
      else if (k === "maint") { if (await geste("planifie.maintenance", { actif: a.dataset.v === "1", heures: +val("#pl-heures") || 4 }, a.dataset.v === "1" ? "Tâches suspendues." : "Tâches reprises.")) aller("maintenance"); }
    });
    racine.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "pl-q") { e.preventDefault(); S.q = e.target.value.trim(); dessiner(); const i = racine.querySelector("#pl-q"); if (i) { i.focus(); i.setSelectionRange(S.q.length, S.q.length); } } });
    S.U = await lire("planifie.unifiee"); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
