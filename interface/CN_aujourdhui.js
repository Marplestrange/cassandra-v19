// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La page « Aujourd'hui » : le cadran du jour
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #588eb4
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La page « Aujourd'hui » : le cadran du jour. Un coup d'œil dit où l'on en est (cadran, temps libre, tâches faites), ce qui vient
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=588eb4 ▼▼▼
/* La page « Aujourd'hui » : le cadran du jour. Un coup d'œil dit où l'on en est (cadran, temps libre, tâches faites), ce qui vient
   (la suite), et la journée se range à la main ou toute seule (la frise, les tâches à placer). Les données sont celles de l'ancienne
   interface (agenda, tâches, rappels, état du jour) ; seul le PLAN — où l'on a posé quoi — est écrit, par le module affichage
   (affichage.lire_plan / affichage.modifier_plan), pour le compte qui agit. */
(function () {
  "use strict";
  const CASS = window.CASS = window.CASS || {};
  const $ = (s, r) => (r || document).querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const p2 = (n) => String(n).padStart(2, "0");
  const hm = (m) => { m = Math.floor(m + 1e-9); return p2(Math.floor(m / 60)) + ":" + p2(m % 60); };
  const dur = (m) => (m = Math.max(0, Math.round(m)), m < 60 ? m + " min" : Math.floor(m / 60) + " h" + (m % 60 ? " " + p2(m % 60) : ""));
  const iso = (d) => d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
  const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
  const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  // l'agenda est bleu ici (et non turquoise comme dans le calendrier) : sur le cadran, le vert des tâches faites doit se distinguer
  const COULEURS = { event: "var(--info)", etape: "var(--accent)", task: "var(--violet)", reminder: "var(--warn)", ssl: "var(--danger)" };
  const DUREE_DEFAUT = 30;

  const A = { d0: null, evts: [], echs: [], jourEntier: [], taches: [], faitesVeille: 0, plan: [], planJour: "", alerte: null, tuiles: null, now: 0, focus: null, focusMin: 25, glisse: null, secondes: 0, suppr: null, h0: 8, h1: 20, charge: false, sauvegarde: null };

  // ── les durées retenues pour les tâches (le serveur ne connaît que la charge, qui est un poids) ────────────────
  const durees = () => { try { return JSON.parse(localStorage.getItem("aj_durees") || "{}"); } catch (e) { return {}; } };
  const retenirDuree = (id, m) => { try { const d = durees(); d[id] = m; localStorage.setItem("aj_durees", JSON.stringify(d)); } catch (e) {} };

  const dureeFocus = () => { try { const v = +localStorage.getItem("aj_focus"); return v >= 1 && v <= 240 ? v : 25; } catch (e) { return 25; } };
  const retenirFocus = (v) => { try { localStorage.setItem("aj_focus", String(v)); } catch (e) {} };
  const minutes = (s) => { const x = String(s || "").slice(11, 16); return x.length === 5 ? (+x.slice(0, 2)) * 60 + (+x.slice(3, 5)) : null; };

  // ── lecture ─────────────────────────────────────────────────────────────────────────────────────────────────
  function lireAgenda() {
    const E = (typeof ETAT !== "undefined" ? ETAT : { carnet: {} }), jour = iso(new Date());
    const tout = (E.carnet._calUpcoming || []).concat(E.carnet._calItems || []), vus = {};
    A.evts = []; A.echs = []; A.jourEntier = []; A.taches = []; A.faitesVeille = 0;
    tout.forEach((e) => {
      const quand = String(e.when || e.start_at || ""), d = quand.slice(0, 10), k = e.kind || "event";
      const cle = k + ":" + (e.id || "") + ":" + (e.summary || "") + ":" + quand;
      if (vus[cle]) return; vus[cle] = 1;
      if (k === "task") {
        const fait = e.status === "fait";
        if (d && d <= jour) A.taches.push({ id: +e.id, titre: e.summary || "", fait, retard: d < jour, projet: e.project_name || "", kind: k });
        return;
      }
      if (d !== jour || k === "cron") return;
      const deb = minutes(quand), ref = { k, id: e.ref || e.id || "", w: quand, t: e.summary || "" };
      if (e.all_day || deb == null) { A.jourEntier.push({ titre: e.summary || "", c: COULEURS[k] || COULEURS.event, ref }); return; }
      if (k === "reminder" || k === "ssl") { A.echs.push({ h: deb, titre: e.summary || "", c: COULEURS[k], ref }); return; }
      let fin = minutes(e.end_at); if (fin == null || fin <= deb) fin = deb + 60;
      A.evts.push({ d: deb, f: fin, titre: e.summary || "", c: COULEURS[k] || COULEURS.event, ref });
    });
    A.evts.sort((a, b) => a.d - b.d); A.echs.sort((a, b) => a.h - b.h);
    // l'amplitude se cale sur le contenu : un rendez-vous de 7 h ou de 21 h ne sort pas du cadre
    let h0 = 8, h1 = 20;
    A.evts.forEach((e) => { h0 = Math.min(h0, Math.floor(e.d / 60)); h1 = Math.max(h1, Math.ceil(e.f / 60)); });
    A.echs.forEach((e) => { h0 = Math.min(h0, Math.floor(e.h / 60)); h1 = Math.max(h1, Math.ceil((e.h + 1) / 60)); });
    A.plan.forEach((b) => { h0 = Math.min(h0, Math.floor(b.deb / 60)); h1 = Math.max(h1, Math.ceil((b.deb + b.duree) / 60)); });
    A.h0 = Math.max(0, h0); A.h1 = Math.min(24, Math.max(h1, A.h0 + 6));
  }
  async function chargerPlan() {
    const jour = iso(new Date());
    try { const r = await CASS.agir("affichage.lire_plan", { jour }); A.plan = r.blocs || []; A.planJour = jour; } catch (e) { A.plan = A.plan || []; }
  }
  async function chargerEtat() {
    try { const r = await window.apiPost("/api/bureau/jour", {}); recevoir(r); } catch (e) {}
  }
  function recevoir(r) {
    if (!r || !r.ok) return;
    A.tuiles = r.tuiles || null;
    const b = (r.bandes || []).find((x) => x.cle === "brule");
    const x = b && (b.items || [])[0];
    A.alerte = x ? { titre: x.titre, detail: x.detail || "", i: 0, geste: x.geste || null, quoi: x.quoi, nat: x.nat } : null;
    A.reste = (r.bandes || []).reduce((s, y) => s + ((y.items || []).length), 0);
    rendre();
  }

  // ── le plan : écrit par le serveur, une fois les gestes posés ────────────────────────────────────────────────
  function sauver() {
    clearTimeout(A.sauvegarde);
    A.sauvegarde = setTimeout(async () => {
      try { await CASS.agir("affichage.modifier_plan", { jour: A.planJour || iso(new Date()), blocs: A.plan.map((b) => ({ id: b.id, titre: b.titre, deb: b.deb, duree: b.duree, tache: b.tache == null ? null : b.tache, fait: !!b.fait, couleur: b.couleur || "" })) }); }
      catch (e) { if (typeof window.toast === "function") window.toast("Plan non enregistré : " + e.message, "err"); }
    }, 350);
  }

  // ── calculs ──────────────────────────────────────────────────────────────────────────────────────────────────
  const occupes = () => A.evts.map((e) => [e.d, e.f]).concat(A.plan.map((p) => [p.deb, p.deb + p.duree])).sort((a, b) => a[0] - b[0]);
  function libres(depuis) {
    const out = []; let cur = Math.max(depuis, A.h0 * 60);
    for (const [a, b] of occupes()) { if (b <= cur) continue; if (a > cur) out.push([cur, Math.min(a, A.h1 * 60)]); cur = Math.max(cur, b); }
    if (cur < A.h1 * 60) out.push([cur, A.h1 * 60]);
    return out.filter((x) => x[1] - x[0] >= 10);
  }
  const SPAN = () => (A.h1 - A.h0) * 60;
  const pos = (m) => ((m - A.h0 * 60) / SPAN()) * 100;
  const ang = (m) => ((m - A.h0 * 60) / SPAN()) * 360 - 90;
  const aPlacer = () => { const d = durees(), ids = new Set(A.plan.map((b) => b.tache)); return A.taches.filter((t) => !t.fait && !ids.has(t.id)).map((t) => Object.assign({ duree: d[t.id] || DUREE_DEFAUT }, t)); };
  function prochain() {
    const tout = A.evts.map((e) => ({ d: e.d, f: e.f, t: e.titre, s: "agenda", k: "ev" })).concat(A.plan.filter((p) => !p.fait).map((p) => ({ d: p.deb, f: p.deb + p.duree, t: p.titre, s: "tâche · " + dur(p.duree), k: "ta" }))).filter((x) => x.f > A.now).sort((a, b) => a.d - b.d);
    return tout;
  }

  // ── le cadran ────────────────────────────────────────────────────────────────────────────────────────────────
  function arc(cx, cy, r, a0, a1) { const pt = (a) => [cx + r * Math.cos(a * Math.PI / 180), cy + r * Math.sin(a * Math.PI / 180)]; const [x0, y0] = pt(a0), [x1, y1] = pt(a1); return "M" + x0.toFixed(2) + " " + y0.toFixed(2) + " A" + r + " " + r + " 0 " + ((a1 - a0) > 180 ? 1 : 0) + " 1 " + x1.toFixed(2) + " " + y1.toFixed(2); }
  function cadran() {
    const cx = 170, cy = 170, R = 128, pas = (A.h1 - A.h0) > 14 ? 3 : 2;
    let s = '<circle class="aj-fond" cx="' + cx + '" cy="' + cy + '" r="' + R + '"/>';
    for (let h = A.h0; h <= A.h1; h++) {
      const a = ang(h * 60) * Math.PI / 180, L = (h - A.h0) % pas ? 6 : 11;
      s += '<line class="aj-tic" x1="' + (cx + (R + 14) * Math.cos(a)) + '" y1="' + (cy + (R + 14) * Math.sin(a)) + '" x2="' + (cx + (R + 14 + L) * Math.cos(a)) + '" y2="' + (cy + (R + 14 + L) * Math.sin(a)) + '"/>';
      if ((h - A.h0) % pas === 0 && h < A.h1) s += '<text class="aj-hl" x="' + (cx + (R + 36) * Math.cos(a)) + '" y="' + (cy + (R + 36) * Math.sin(a)) + '">' + h + "</text>";
    }
    A.evts.forEach((e) => { s += '<path class="aj-arc" d="' + arc(cx, cy, R, ang(e.d), ang(e.f) - .4) + '" style="stroke:' + e.c + '"/>'; });
    A.plan.forEach((p) => { s += '<path class="aj-arc" d="' + arc(cx, cy, R, ang(p.deb), ang(p.deb + p.duree) - .4) + '" style="stroke:' + (p.fait ? "var(--ok)" : (p.couleur || "var(--violet)")) + '"/>'; });
    const n = Math.min(Math.max(A.now, A.h0 * 60), A.h1 * 60);
    if (n > A.h0 * 60 + 1) s += '<path class="aj-passe-arc" d="' + arc(cx, cy, R, ang(A.h0 * 60), ang(n) - .01) + '"/>';
    const tot = A.plan.length, fait = A.plan.filter((p) => p.fait).length, r2 = 96, circ = 2 * Math.PI * r2, part = tot ? fait / tot : 0;
    s += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r2 + '" class="aj-fond2"/><circle class="aj-prog" cx="' + cx + '" cy="' + cy + '" r="' + r2 + '" stroke-dasharray="' + (circ * part).toFixed(1) + " " + circ.toFixed(1) + '" transform="rotate(-90 ' + cx + " " + cy + ')"/>';
    // l'aiguille : tracée vers le haut, puis tournée — ce qui la laisse glisser d'un cran à l'autre au lieu de sauter
    s += '<g id="aj-aig" class="aj-tourne" style="transform:rotate(' + (ang(n) + 90).toFixed(3) + 'deg)"><line class="aj-main" x1="' + cx + '" y1="' + (cy - 60) + '" x2="' + cx + '" y2="' + (cy - R - 12) + '"/><circle class="aj-main-pt" cx="' + cx + '" cy="' + (cy - R - 12) + '" r="6"/></g>';
    // la trotteuse : un point qui fait le tour du cadran en une minute
    s += '<g id="aj-trot" class="aj-tourne aj-trot" style="transform:rotate(' + angTrot() + 'deg)"><circle cx="' + cx + '" cy="' + (cy - 112) + '" r="3"/></g>';
    return s;
  }

  // ── la frise ─────────────────────────────────────────────────────────────────────────────────────────────────
  function frise() {
    let heures = "";
    for (let h = A.h0; h <= A.h1; h += (A.h1 - A.h0) > 14 ? 3 : 2) heures += "<span>" + h + "h</span>";
    const libresHtml = libres(A.now).filter((x) => x[1] - x[0] >= 30).map((x) => '<div class="aj-libre" style="left:' + pos(x[0]) + "%;width:" + (pos(x[1]) - pos(x[0])) + '%">' + dur(x[1] - x[0]) + " libres</div>").join("");
    const ag = libresHtml + A.evts.map((e) => '<div class="aj-blk" data-ref="' + esc(JSON.stringify(e.ref)) + '" style="--c:' + e.c + ";left:" + pos(e.d) + "%;width:" + (pos(e.f) - pos(e.d)) + '%"><b>' + esc(e.titre) + "</b><small>" + hm(e.d) + " – " + hm(e.f) + "</small></div>").join("");
    const ta = A.plan.map((p) => '<div class="aj-blk aj-tache' + (p.fait ? " fait" : "") + (p.neuf ? " arrive" : "") + '" data-id="' + esc(p.id) + '" style="--c:' + (p.couleur || "var(--violet)") + ";left:" + pos(p.deb) + "%;width:" + Math.max(pos(p.deb + p.duree) - pos(p.deb), 4.5) + '%"><b>' + (p.fait ? "✓ " : "") + esc(p.titre) + "</b><small>" + hm(p.deb) + " · " + dur(p.duree) + '</small><button class="aj-x" data-x="' + esc(p.id) + '" aria-label="Remettre à placer" title="Remettre à placer">×</button></div>').join("");
    const ec = A.echs.map((e) => '<div class="aj-pin' + (pos(e.h) > 70 ? " g" : "") + '" data-ref="' + esc(JSON.stringify(e.ref)) + '" style="left:' + pos(e.h) + "%;--c:" + e.c + '"><i></i><em>' + hm(e.h) + " · " + esc(e.titre) + "</em></div>").join("");
    return { heures, ag, ta, ec };
  }

  // ── le dessin d'ensemble ─────────────────────────────────────────────────────────────────────────────────────
  function salut() { const h = Math.floor(A.now / 60), d = new Date(); return (h < 12 ? "Bonjour" : h < 18 ? "Bon après-midi" : "Bonsoir") + " · " + JOURS[d.getDay()] + " " + d.getDate() + " " + MOIS[d.getMonth()]; }
  function racine() {
    let r = $("#aj-racine");
    if (!r) { const v = $("#bu-v-today"); if (!v) return null; r = document.createElement("div"); r.id = "aj-racine"; v.insertBefore(r, v.firstChild); }
    return r;
  }
  function squelette(r) {
    r.innerHTML =
      '<div class="aj-tete"><span class="aj-salut" id="aj-salut"></span><span class="aj-sp"></span>' +
      '<span class="aj-duree" id="aj-duree" role="group" aria-label="Durée de concentration"></span><button class="aj-btn" id="aj-focus" type="button">◔ Se concentrer</button><button class="aj-btn pri" id="aj-org" type="button">✦ Organiser ma journée</button></div>' +
      '<div class="aj-ruban" id="aj-ruban" hidden></div><div class="aj-chips" id="aj-chips"></div>' +
      '<div class="aj-haut"><section class="aj-verre aj-cadran"><div class="aj-disque"><svg viewBox="0 0 340 340" role="img" aria-label="Cadran de la journée"><g id="aj-svg"></g></svg>' +
      '<div class="aj-centre"><div class="t" id="aj-c-heure"></div><div class="s" id="aj-c-sous"></div><div class="p" id="aj-c-pro"></div></div></div>' +
      '<div class="aj-legende"><span><i style="background:var(--info)"></i>Agenda</span><span><i style="background:var(--violet)"></i>Tâches placées</span><span><i style="background:var(--ok);border-radius:50%"></i>Faites</span></div></section>' +
      '<div class="aj-droite"><div class="aj-chiffres" id="aj-chiffres"></div><section class="aj-verre aj-suite" id="aj-suite"></section></div></div>' +
      '<section class="aj-verre aj-frise"><header><h3>Ma journée</h3><span class="aj-bilan" id="aj-bilan"></span><span class="aj-sp"></span><button class="aj-btn sm" id="aj-vider" type="button">Tout remettre à placer</button></header>' +
      '<div class="aj-entier" id="aj-entier"></div>' +
      '<div class="aj-plan" id="aj-plan"><div class="aj-heures" id="aj-heures"></div><div class="aj-passe" id="aj-passe"></div><div class="aj-curseur" id="aj-curseur"><span id="aj-cur-h"></span></div>' +
      '<div class="aj-voie"><div class="aj-nom">Agenda</div><div class="aj-piste" id="aj-p-ag"></div></div><div class="aj-voie"><div class="aj-nom">À faire</div><div class="aj-piste" id="aj-p-ta"></div></div><div class="aj-voie"><div class="aj-nom">Échéances</div><div class="aj-piste" id="aj-p-ec"></div></div></div></section>' +
      '<div class="aj-bas"><section class="aj-verre aj-carte"><header><h3>À placer</h3><span class="aj-n" id="aj-n-pl"></span></header>' +
      '<form class="aj-saisie" id="aj-f"><input id="aj-q" placeholder="Nouvelle tâche… « relire le contrat 40 min »" autocomplete="off"><button class="aj-btn pri" type="submit">Ajouter</button></form>' +
      '<div class="aj-plateau" id="aj-plateau"></div><p class="aj-aide">Glissez une tâche sur la voie « À faire », ou laissez Itare la poser dans vos temps libres. Cliquez un bloc pour le cocher.</p></section>' +
      '<section class="aj-verre aj-carte aj-courrier"><header><h3>Courrier non lu</h3><span class="aj-sp"></span><button class="aj-btn sm" type="button" data-seg="mail">Ouvrir</button></header>' +
      '<div class="bu-rows" id="bu-mail-apercu"><div class="empty-state" style="padding:20px">Lecture…</div></div></section></div>';
    r.dataset.pret = "1"; A.focusMin = dureeFocus(); dessinerDuree();
    pose(r);
  }
  function rendre() {
    const r = racine(); if (!r) return;
    if (!r.dataset.pret) { squelette(r); if (typeof window.buApercuMail === "function") window.buApercuMail(); }
    A.now = minutesNow();
    lireAgenda();
    $("#aj-salut").textContent = salut();
    // l'alerte : un ruban, pas un mur
    const ru = $("#aj-ruban");
    if (A.alerte) {
      ru.hidden = false;
      ru.innerHTML = '<i></i><b>' + esc(A.alerte.titre) + '</b>' + (A.alerte.detail ? "<span>— " + esc(A.alerte.detail) + "</span>" : "") + '<span class="aj-sp"></span>' +
        (A.alerte.geste ? '<button class="aj-btn sm pri" type="button" data-geste="1">' + esc(A.alerte.geste[0]) + "</button>" : "") + (A.reste > 1 ? '<span class="aj-plus">+ ' + (A.reste - 1) + " autre" + (A.reste > 2 ? "s" : "") + "</span>" : "");
    } else { ru.hidden = true; ru.innerHTML = ""; }
    // ce qui ne tient pas dans le cadran : les nombres de l'état du jour, un clic y conduit
    const t = A.tuiles || {}, defs = (typeof BJ_TUILES !== "undefined" ? BJ_TUILES : []);
    $("#aj-chips").innerHTML = defs.filter((x) => Number(t[x[0]] || 0) > 0 && x[0] !== "a_faire").map((x) => '<button class="aj-chip" type="button" data-seg="' + esc(x[2]) + '" style="--c:' + x[3] + '"><b>' + Number(t[x[0]]) + "</b> " + esc(x[1]) + "</button>").join("");
    $("#aj-svg").innerHTML = cadran();
    const suiv = prochain(), n0 = suiv[0];
    $("#aj-c-heure").innerHTML = A.focus ? A.focus.affiche : hm(Math.floor(A.now)) + "<sup>" + p2(A.secondes) + "</sup>";
    $("#aj-c-sous").textContent = A.focus ? "concentration" : (n0 ? (n0.d <= A.now ? "en cours" : "prochain") : "rien de prévu");
    $("#aj-c-pro").textContent = A.focus ? "pas de notification" : (n0 ? (n0.d > A.now ? "dans " + dur(n0.d - A.now) : "jusqu’à " + hm(n0.f)) : "");
    const libre = libres(A.now).reduce((s, x) => s + (x[1] - x[0]), 0), reste = Math.max(A.h1 * 60 - A.now, 0), pl = aPlacer();
    const faites = A.plan.filter((p) => p.fait).length + A.taches.filter((x) => x.fait && !A.plan.some((b) => b.tache === x.id)).length, total = A.plan.length + A.taches.filter((x) => (x.fait && !A.plan.some((b) => b.tache === x.id)) || (!x.fait && !A.plan.some((b) => b.tache === x.id))).length;
    const pc = Math.round(Math.min(Math.max((A.now - A.h0 * 60) / SPAN(), 0), 1) * 100);
    const k = (b, l, s, w, c) => '<div class="aj-chiffre aj-verre"><b>' + b + "</b><span>" + l + "</span><small>" + s + '</small><div class="aj-bar"><i style="width:' + w + "%;background:" + c + '"></i></div></div>';
    $("#aj-chiffres").innerHTML = k(dur(libre), "de temps libre", "jusqu’à " + A.h1 + " h", reste ? Math.min(100, libre / reste * 100) : 0, "var(--accent)") +
      k(faites + " / " + total, "tâches faites", pl.length ? pl.length + " encore à placer" : (total ? "tout est placé" : "rien à faire"), total ? faites / total * 100 : 0, "var(--ok)") +
      k(pc + " %", "de la journée passée", hm(A.now) + " sur " + A.h0 + " h – " + A.h1 + " h", pc, "var(--info)");
    $("#aj-suite").innerHTML = suiv.length ? suiv.slice(0, 4).map((x, i) => { const en = x.d <= A.now; return '<div class="aj-r' + (i === 0 && en ? " now" : "") + '"><div class="aj-quand">' + hm(x.d) + '</div><div class="aj-tx"><b>' + esc(x.t) + "</b><small>" + esc(x.s) + '</small></div><div class="aj-dans">' + (en ? "en cours" : "dans " + dur(x.d - A.now)) + "</div></div>"; }).join("")
      : '<div class="aj-r"><div class="aj-tx"><b>Plus rien de prévu aujourd’hui</b><small>' + (pl.length ? "Il reste " + pl.length + " tâche" + (pl.length > 1 ? "s" : "") + " à placer." : "Bonne fin de journée.") + "</small></div></div>";
    const f = frise();
    $("#aj-heures").innerHTML = f.heures; $("#aj-p-ag").innerHTML = f.ag; $("#aj-p-ta").innerHTML = f.ta || '<div class="aj-vide-voie">Déposez ici une tâche, ou cliquez « Organiser ma journée »</div>'; $("#aj-p-ec").innerHTML = f.ec || '<div class="aj-vide-voie">Aucune échéance aujourd’hui</div>';
    A.plan.forEach((p) => { delete p.neuf; });
    $("#aj-entier").innerHTML = A.jourEntier.length ? '<span class="aj-lab">Toute la journée</span>' + A.jourEntier.map((e) => '<button class="aj-ad" type="button" data-ref="' + esc(JSON.stringify(e.ref)) + '" style="--c:' + e.c + '">' + esc(e.titre) + "</button>").join("") : "";
    $("#aj-bilan").textContent = A.plan.length + " placée" + (A.plan.length > 1 ? "s" : "") + " · " + pl.length + " à placer";
    $("#aj-n-pl").textContent = pl.length ? pl.length + " en attente" : "";
    $("#aj-plateau").innerHTML = pl.length ? pl.map((p) => '<div class="aj-puce' + (p.retard ? " retard" : "") + '" draggable="true" data-tid="' + p.id + '"><span class="aj-t">' + esc(p.titre) + "</span><small>" + dur(p.duree) + '</small><button class="aj-go" type="button" data-go="' + p.id + '">placer →</button>' + (A.suppr === p.id ? '<button class="aj-sup on" type="button" data-sup="' + p.id + '">Supprimer ?</button>' : '<button class="aj-sup" type="button" data-sup="' + p.id + '" aria-label="Supprimer cette tâche" title="Supprimer cette tâche">×</button>') + "</div>").join("") : '<span class="aj-n" style="padding:10px 4px">' + (A.taches.length || A.plan.length ? "Tout est placé. Rien ne traîne." : "Aucune tâche pour aujourd’hui.") + "</span>";
    pose(r);
  }
  // la frise se cale sur la largeur réelle : le curseur et le passé, une fois les pistes en place
  function pose(r) {
    const plan = $("#aj-plan"); if (!plan) return;
    const larg = plan.clientWidth - 74, x = pos(Math.min(Math.max(A.now, A.h0 * 60), A.h1 * 60));
    $("#aj-curseur").style.left = (74 + larg * x / 100) + "px"; $("#aj-cur-h").textContent = hm(A.now);
    $("#aj-passe").style.width = (larg * x / 100) + "px";
    plan.querySelectorAll(".aj-blk").forEach((b) => b.classList.toggle("etroit", b.getBoundingClientRect().width < 96));
  }

  // ── les gestes ───────────────────────────────────────────────────────────────────────────────────────────────
  const bloc = (t, deb) => ({ id: "t" + t.id, titre: t.titre, deb, duree: t.duree, tache: t.id, fait: false, couleur: "", neuf: 1 });
  function premierLibre(d, apres) { return libres(Math.max(A.now, apres || 0)).find((x) => x[1] - x[0] >= d); }
  const arrondi5 = (m) => Math.ceil(m / 5) * 5;
  function placer(t, deb) { A.plan.push(bloc(t, deb)); A.plan.sort((a, b) => a.deb - b.deb); sauver(); rendre(); }
  function organiser() {
    const l = aPlacer(); let k = 0;
    l.forEach((t) => { const z = premierLibre(t.duree + 5); if (z) { setTimeout(() => { if (!premierLibre(t.duree + 5)) return; A.plan.push(bloc(t, arrondi5(premierLibre(t.duree + 5)[0]))); A.plan.sort((a, b) => a.deb - b.deb); sauver(); rendre(); }, k * 260); k++; } });
    if (!k && typeof window.toast === "function") window.toast(l.length ? "Aucun temps libre assez long." : "Rien à placer.");
  }
  function confetti(x, y) { const couleurs = ["#2dd4bf", "#fbbf24", "#7c5cd6", "#d02a50", "#2b78b5"]; for (let i = 0; i < 18; i++) { const e = document.createElement("i"); e.className = "aj-confetti"; e.style.left = x + "px"; e.style.top = y + "px"; e.style.background = couleurs[i % 5]; e.style.setProperty("--dx", (Math.random() * 160 - 80) + "px"); e.style.setProperty("--dy", (Math.random() * -120 - 20) + "px"); e.style.setProperty("--r", Math.random() * 540 + "deg"); document.body.appendChild(e); setTimeout(() => e.remove(), 1000); } }
  async function cocher(b, el) {
    b.fait = !b.fait; sauver();
    if (b.tache != null && typeof window.apiPost === "function") { try { await window.apiPost("/api/itare/task/save", { id: b.tache, status: b.fait ? "fait" : "todo" }); const t = A.taches.find((x) => x.id === b.tache); if (t) t.fait = b.fait; if (typeof window.calLoad === "function") await window.calLoad(); } catch (e) {} }
    rendre();
    if (b.fait && el) { const r = el.getBoundingClientRect(); confetti(r.left + r.width / 2, r.top); }
  }
  async function ajouter(texte) {
    let v = texte.trim(); if (!v) return;
    const m = v.match(/(\d+)\s*(min|h)\b/i); let d = DUREE_DEFAUT; if (m) { d = m[2].toLowerCase() === "h" ? +m[1] * 60 : +m[1]; v = v.replace(m[0], "").replace(/\s+/g, " ").trim() || v; }
    d = Math.max(5, Math.min(480, d));
    try {
      const r = await window.apiPost("/api/itare/task/save", { text: v, due: iso(new Date()) });
      const id = r && (r.id || (r.task && r.task.id));
      if (id) retenirDuree(id, d);
      if (typeof window.calLoad === "function") await window.calLoad(); else rendre();
    } catch (e) { if (typeof window.toast === "function") window.toast("Tâche non créée : " + e.message, "err"); }
  }
  async function supprimer(id) {
    if (A.suppr !== id) { A.suppr = id; rendre(); clearTimeout(A.supprT); A.supprT = setTimeout(() => { if (A.suppr === id) { A.suppr = null; rendre(); } }, 3500); return; }
    A.suppr = null; clearTimeout(A.supprT);
    try {
      await window.apiPost("/api/itare/task/delete", { id });
      A.plan = A.plan.filter((b) => b.tache !== id); sauver();
      if (typeof window.calLoad === "function") await window.calLoad(); else rendre();
    } catch (e) { if (typeof window.toast === "function") window.toast("Suppression refusée : " + e.message, "err"); rendre(); }
  }
  function dessinerDuree() {
    const z = $("#aj-duree"); if (!z) return;
    if (A.focus) { z.innerHTML = '<button class="aj-btn sm" type="button" data-plus="5">+ 5 min</button>'; return; }
    const v = A.focusMin;
    z.innerHTML = [15, 25, 45, 60, 90].map((m) => '<button type="button" class="aj-pre' + (m === v ? " on" : "") + '" data-min="' + m + '">' + m + "</button>").join("") +
      '<label class="aj-lib' + ([15, 25, 45, 60, 90].indexOf(v) < 0 ? " on" : "") + '"><input type="number" id="aj-min" min="1" max="240" value="' + v + '" aria-label="Minutes de concentration"><span>min</span></label>';
  }
  function basculerFocus() {
    const b = $("#aj-focus");
    if (A.focus) { clearInterval(A.focus.i); A.focus = null; b.textContent = "◔ Se concentrer"; b.classList.remove("pri"); dessinerDuree(); rendre(); return; }
    const min = Math.max(1, Math.min(240, Math.round(+($("#aj-min") || {}).value || A.focusMin)));
    A.focusMin = min; retenirFocus(min);
    A.focus = { reste: min * 60, affiche: p2(min) + ":00" };
    b.classList.add("pri"); dessinerDuree();
    const maj = () => { const r = A.focus.reste; A.focus.affiche = p2(Math.floor(r / 60)) + ":" + p2(r % 60); const c = $("#aj-c-heure"); if (c) c.textContent = A.focus.affiche; b.textContent = "■ Arrêter (" + Math.ceil(r / 60) + " min)"; };
    A.focus.i = setInterval(() => { A.focus.reste--; if (A.focus.reste <= 0) { basculerFocus(); if (typeof window.toast === "function") window.toast("Concentration terminée."); return; } maj(); }, 1000);
    rendre(); maj();
  }
  function ouvrirRef(txt) { try { const r = JSON.parse(txt); if (typeof window.buOuvrir === "function") window.buOuvrir(r.k, r.id, r.w, r.t); } catch (e) {} }

  function brancher() {
    document.addEventListener("click", (ev) => {
      const r = $("#aj-racine"); if (!r || !r.contains(ev.target)) return;
      let x;
      if ((x = ev.target.closest("[data-x]"))) { A.plan = A.plan.filter((b) => b.id !== x.dataset.x); sauver(); rendre(); return; }
      if ((x = ev.target.closest("[data-sup]"))) { supprimer(+x.dataset.sup); return; }
      if ((x = ev.target.closest("[data-go]"))) { const t = aPlacer().find((q) => q.id === +x.dataset.go), z = t && premierLibre(t.duree); if (z) placer(t, arrondi5(z[0])); else if (typeof window.toast === "function") window.toast("Aucun temps libre assez long."); return; }
      if ((x = ev.target.closest(".aj-tache"))) { const b = A.plan.find((q) => q.id === x.dataset.id); if (b) cocher(b, x); return; }
      if ((x = ev.target.closest("[data-ref]"))) { ouvrirRef(x.dataset.ref); return; }
      if (ev.target.closest("#aj-org")) { organiser(); return; }
      if (ev.target.closest("#aj-vider")) { A.plan = []; sauver(); rendre(); return; }
      if (ev.target.closest("#aj-focus")) { basculerFocus(); return; }
      if ((x = ev.target.closest("[data-min]"))) { A.focusMin = +x.dataset.min; retenirFocus(A.focusMin); dessinerDuree(); return; }
      if ((x = ev.target.closest("[data-plus]")) && A.focus) { A.focus.reste += 5 * 60; return; }
      if ((x = ev.target.closest("[data-seg]"))) { if (x.dataset.seg === "mandats" && typeof window.buAllerMandats === "function") window.buAllerMandats("attente"); else if (typeof window.buSeg === "function") window.buSeg(x.dataset.seg); return; }
      if (ev.target.closest("[data-geste]")) { if (A.alerte) ouvrirSignal(A.alerte); return; }
    });
    document.addEventListener("submit", (ev) => { if (ev.target.id === "aj-f") { ev.preventDefault(); const i = $("#aj-q"); const v = i.value; i.value = ""; ajouter(v); } });
    // glisser-déposer d'une tâche vers la voie « À faire »
    document.addEventListener("dragstart", (e) => { const p = e.target.closest && e.target.closest(".aj-puce"); if (!p) return; A.glisse = +p.dataset.tid; p.classList.add("glisse"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(A.glisse)); });
    document.addEventListener("dragend", () => { document.querySelectorAll(".aj-puce.glisse").forEach((x) => x.classList.remove("glisse")); const p = $("#aj-p-ta"); if (p) p.classList.remove("cible"); A.glisse = null; });
    document.addEventListener("dragover", (e) => { const p = e.target.closest && e.target.closest("#aj-p-ta"); if (p && A.glisse != null) { e.preventDefault(); p.classList.add("cible"); } });
    document.addEventListener("dragleave", (e) => { const p = e.target.closest && e.target.closest("#aj-p-ta"); if (p && !p.contains(e.relatedTarget)) p.classList.remove("cible"); });
    document.addEventListener("drop", (e) => {
      const p = e.target.closest && e.target.closest("#aj-p-ta"); if (!p || A.glisse == null) return;
      e.preventDefault(); p.classList.remove("cible");
      const t = aPlacer().find((q) => q.id === A.glisse); if (!t) return;
      const r = p.getBoundingClientRect(); let m = Math.round((A.h0 * 60 + ((e.clientX - r.left) / r.width) * SPAN()) / 5) * 5;
      m = Math.max(m, arrondi5(A.now));
      if (!occupes().every(([a, b]) => m + t.duree <= a || m >= b)) { const z = premierLibre(t.duree, m); if (!z) { if (typeof window.toast === "function") window.toast("Pas de place à cet endroit."); return; } m = arrondi5(z[0]); }
      placer(t, m);
    });
    window.addEventListener("resize", () => { const r = $("#aj-racine"); if (r && r.dataset.pret) pose(r); });
    // l'heure avance : on redessine chaque 30 s tant que la page est ouverte
    setInterval(tic, 1000);
    setInterval(() => { const v = $("#bu-v-today"); if (v && v.classList.contains("on") && !document.hidden && !A.focus) rendre(); }, 60000);
  }
  function ouvrirSignal(a) {
    const BJ = (typeof BJ_OU !== "undefined" ? BJ_OU : {}), d = BJ[a.quoi] || BJ[a.nat]; if (!d) return;
    if (d.cloche && typeof window.toggleAlertDropdown === "function") window.toggleAlertDropdown();
    else if (d.fn && typeof window[d.fn] === "function") window[d.fn](d.arg);
    else if (d.tab && typeof window.switchTab === "function") window.switchTab(d.tab);
    else if (d.seg && typeof window.buSeg === "function") window.buSeg(d.seg);
  }

  // la trotteuse ne revient jamais en arrière : l'angle croît sans fin (un tour par minute), il ne repasse pas par zéro
  const T0 = Date.now() - (new Date().getSeconds() * 1000);
  const angTrot = () => (((Date.now() - T0) / 1000) * 6).toFixed(1);
  function minutesNow() { const d = new Date(); A.secondes = d.getSeconds(); return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60; }
  function tic() {
    const v = $("#bu-v-today"); if (!v || !v.classList.contains("on") || document.hidden || !$("#aj-aig")) return;
    const m = minutesNow(), avant = Math.floor(A.now);
    A.now = m;
    const n = Math.min(Math.max(m, A.h0 * 60), A.h1 * 60);
    $("#aj-aig").style.transform = "rotate(" + (ang(n) + 90).toFixed(3) + "deg)";
    const tr = $("#aj-trot"); if (tr) tr.style.transform = "rotate(" + angTrot() + "deg)";
    const pa = $(".aj-passe-arc"); if (pa && n > A.h0 * 60 + 1) pa.setAttribute("d", arc(170, 170, 128, ang(A.h0 * 60), ang(n) - .01));
    const plan = $("#aj-plan"); if (plan) { const larg = plan.clientWidth - 74, x = pos(n); $("#aj-curseur").style.left = (74 + larg * x / 100) + "px"; $("#aj-cur-h").textContent = hm(Math.floor(m)); $("#aj-passe").style.width = (larg * x / 100) + "px"; }
    if (!A.focus) { const c = $("#aj-c-heure"); if (c) c.innerHTML = hm(Math.floor(m)) + "<sup>" + p2(A.secondes) + "</sup>"; }
    if (Math.floor(m) !== avant) rendre();                        // la minute change : la suite, les temps libres et les chiffres se recalculent
  }

  // ── le branchement sur l'ancienne interface : ses fonctions d'ouverture de la vue deviennent les nôtres ─────────
  async function ouvrir() { if (!A.charge) { A.charge = true; await chargerPlan(); } else await chargerPlan(); rendre(); chargerEtat(); }
  window.buAujourdhui = function () { rendre(); };               // calLoad l'appelle quand l'agenda est lu
  window.bjJour = function () { return ouvrir(); };              // buSeg('today') l'appelle à l'ouverture
  window.bjRecevoir = function (msg) { if (!msg || !msg.jour) return; if (msg.jour.ok) recevoir(msg.jour); };
  CASS.aujourdhui = { rendre, ouvrir, etat: A };
  brancher();
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
