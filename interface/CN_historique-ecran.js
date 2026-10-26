// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran « Historique » du module mesures : ce que les mesures disent à l'ouverture, une co
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #a5a6de
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran « Historique » du module mesures : ce que les mesures disent à l'ouverture, une courbe au choix, les écarts à l'habitude, la prévision de saturation, les mesures muettes.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=a5a6de ▼▼▼
// L'écran « Historique » du module mesures : ce que les mesures disent à l'ouverture, une courbe au choix, les écarts à l'habitude, la prévision de saturation, les mesures muettes.
// Aucune bibliothèque de graphiques : la courbe est un SVG du kit. Les données viennent des capacités du module (mesures.verdict, sources, serie, profil, ecarts, prevision).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, ic = K.ic, pill = K.pill, agir = K.agir, dire = K.dire;
  const SCENES = [["maintenant", "Maintenant"], ["courbes", "Courbes"], ["ecarts", "Écarts"], ["prevision", "Prévision"], ["vides", "Sans données"]];
  const PERIODES = [["1h", "1 h"], ["6h", "6 h"], ["24h", "24 h"], ["7d", "7 j"], ["30d", "30 j"]];
  const NIVEAUX = { panne: ["panne", "dg", "warn"], danger: ["danger", "dg", "warn"], alerte: ["à regarder", "al", "eye"], muet: ["sans nouvelles", "al", "eye"], pas_encore: ["pas encore d’habitude", "", "eye"], stable: ["stable", "ok", "check"], ok: ["tout va bien", "ok", "check"] };
  const niv = (n) => { const x = NIVEAUX[n] || [String(n || "—"), "", ""]; return pill(x[0], x[1], x[2]); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.mesures = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("mesures", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "maintenant", sources: [], verdict: null, cle: "", periode: "24h", serie: null, profil: null, ecarts: null, prevision: null, charge: false, erreur: "" };

    async function lire(cap, args) { try { return await agir(cap, args); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function chargerSources() { const r = await lire("mesures.sources"); S.sources = (r && r.metrics) || []; if (!S.cle) { const m = S.sources.find((x) => x.available && x.etat === "a_jour") || S.sources.find((x) => x.available); S.cle = m ? m.key : ""; } }

    const familles = () => { const f = {}; S.sources.forEach((m) => { (f[m.family || "Autres"] = f[m.family || "Autres"] || []).push(m); }); return f; };
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0]) + '">' + s[1] + "</button>").join("") + "</div>";

    function maintenant() {
      const v = S.verdict;
      if (!v) return '<div class="carte vide">Lecture…</div>';
      return '<div class="carte"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h3 style="flex:1;min-width:200px">' + esc(v.titre || "") + "</h3>" + niv(v.niveau) + "</div>" + (v.sous_titre ? '<p class="note">' + esc(v.sous_titre) + "</p>" : "") + "</div>" +
        '<div class="carte"><div class="liste">' + ((v.lignes || []).length ? v.lignes.map((l) => '<div class="li"><div class="ico sm' + (l.niveau === "panne" || l.niveau === "danger" ? " dg" : l.niveau === "ok" || l.niveau === "stable" ? "" : " al") + '">' + ic(l.niveau === "panne" ? "warn" : "eye") + '</div><div class="sp"><b>' + esc(l.titre) + '</b><span class="note">' + esc(l.detail || "") + "</span></div>" + niv(l.niveau) + "</div>").join("") : '<div class="vide">Rien à signaler.</div>') + "</div></div>";
    }
    function courbes() {
      const F = familles(), m = S.sources.find((x) => x.key === S.cle);
      const choix = '<select class="sel" data-a="cle" aria-label="Mesure">' + Object.keys(F).map((f) => '<optgroup label="' + esc(f) + '">' + F[f].map((x) => '<option value="' + esc(x.key) + '"' + (x.key === S.cle ? " selected" : "") + ">" + esc(x.label) + (x.available ? "" : " (absente)") + "</option>").join("") + "</optgroup>").join("") + "</select>";
      const per = '<div class="seg" role="group" aria-label="Période">' + PERIODES.map((p) => '<button class="' + (S.periode === p[0] ? "on" : "") + '" data-a="periode" data-p="' + p[0] + '">' + p[1] + "</button>").join("") + "</div>";
      const sr = S.serie, pr = S.profil;
      return '<div class="barre">' + choix + per + "</div>" +
        '<div class="carte">' + (m ? '<div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>' + esc(m.label) + "</h3>" + pill(m.etat_texte || m.etat || "", m.etat === "a_jour" ? "ok" : m.etat === "muette" ? "al" : "") + (m.unit ? '<span class="note">en ' + esc(m.unit) + "</span>" : "") + '</div><p class="note">' + esc(m.desc || "") + "</p>" : "") +
        (S.charge ? '<div class="vide">Lecture…</div>' : sr && sr.ok === false ? '<div class="alerte al"><div class="sp">' + esc(sr.reason || "Cette mesure n’a pas de courbe.") + "</div></div>" : sr ? K.courbe(sr.series, { unite: sr.unit, titre: m ? m.label : "Courbe" }) : '<div class="vide">Choisis une mesure.</div>') + "</div>" +
        (pr ? '<div class="carte"><h3>Ce qui est habituel</h3>' + (pr.enough ? '<p>' + esc(pr.slot_label || "") + " : habituellement <b>" + esc(K.nombre(pr.baseline)) + "</b>" + esc(m && m.unit ? " " + m.unit : "") + ", là <b>" + esc(K.nombre(pr.current)) + "</b>" + (pr.deviation_pct != null ? " (" + (pr.deviation_pct > 0 ? "+" : "") + Math.round(pr.deviation_pct) + " %)" : "") + ".</p>" : '<p class="note">' + esc(pr.reason || "Habitude encore inconnue.") + "</p>") + "</div>" : "");
    }
    function ecarts() {
      const e = S.ecarts; if (!e) return '<div class="carte vide">Lecture…</div>';
      return '<div class="carte"><h3>Ce qui sort de l’habitude</h3><p class="note">Au-delà de ' + esc(e.threshold) + " % d’écart avec ce qui est normal ce jour-là à cette heure.</p>" + ((e.deviations || []).length ? '<div class="liste">' + e.deviations.map((d) => '<div class="li"><div class="sp"><b>' + esc(d.label) + '</b><span class="note">' + esc(d.family || "") + " · habituel " + esc(K.nombre(d.baseline)) + " " + esc(d.unit || "") + ", maintenant " + esc(K.nombre(d.current)) + " " + esc(d.unit || "") + "</span></div>" + pill((d.deviation_pct > 0 ? "+" : "") + Math.round(d.deviation_pct) + " %", "al") + '<button class="btn mini" data-a="ouvrir" data-k="' + esc(d.key) + '">Voir la courbe</button></div>').join("") + "</div>" : '<div class="vide"><b>Rien ne sort de l’habitude.</b></div>') + "</div>";
    }
    function prevision() {
      const l = S.prevision; if (!l) return '<div class="carte vide">Lecture…</div>';
      return '<div class="carte"><h3>Quand ça sature</h3><p class="note">Tendance linéaire sur les quatorze derniers jours, pour les mesures qui peuvent saturer.</p>' + (l.length ? '<div class="liste">' + l.map((x) => { const p = x.p; return '<div class="li"><div class="sp"><b>' + esc(x.m.label) + '</b><span class="note">' + (p.enough ? (p.saturation_days != null ? "Saturation dans " + esc(p.saturation_days) + " jours (" + esc(p.saturation_date || "") + "), actuellement " + esc(K.nombre(p.current)) + " " + esc(x.m.unit || "") : esc(p.note || "Aucune saturation en vue.")) : esc(p.reason || "Pas assez de mesures.")) + "</span></div>" + (p.enough && p.saturation_days != null ? pill(p.saturation_days + " j", p.saturation_days < 14 ? "dg" : p.saturation_days < 45 ? "al" : "ok") : pill("—", "")) + "</div>"; }).join("") + "</div>" : '<div class="vide">Aucune mesure ne se prévoit.</div>') + "</div>";
    }
    function vides() {
      const l = S.sources.filter((m) => !m.available || m.etat === "aucune_donnee" || m.etat === "muette");
      return '<div class="carte"><h3>Mesures sans données</h3>' + (l.length ? '<div class="liste">' + l.map((m) => '<div class="li"><div class="sp"><b>' + esc(m.label) + '</b><span class="note">' + esc(m.family || "") + (m.desc ? " · " + esc(m.desc) : "") + "</span></div>" + pill(m.available ? (m.etat_texte || "muette") : "source absente", "al") + "</div>").join("") + "</div>" : '<div class="vide"><b>Toutes les mesures ont des données.</b></div>') + "</div>";
    }
    function dessiner() {
      const corpsScene = S.scene === "maintenant" ? maintenant() : S.scene === "courbes" ? courbes() : S.scene === "ecarts" ? ecarts() : S.scene === "prevision" ? prevision() : vides();
      racine.innerHTML = '<p class="note">Ce que les mesures racontent : où on en est, comment ça évolue, ce qui sort de l’ordinaire.</p>' + (S.erreur ? '<div class="alerte dg"><div class="sp">' + esc(S.erreur) + "</div></div>" : "") + barre() + corpsScene;
    }
    async function charger(scene) {
      S.scene = scene; S.erreur = ""; dessiner();
      if (scene === "maintenant" && !S.verdict) { S.verdict = await lire("mesures.verdict"); }
      else if (scene === "courbes") { S.charge = true; dessiner(); const [sr, pr] = await Promise.all([S.cle ? lire("mesures.serie", { cle: S.cle, periode: S.periode, top: 6 }) : null, S.cle ? lire("mesures.profil", { cle: S.cle }) : null]); S.serie = sr; S.profil = pr; S.charge = false; }
      else if (scene === "ecarts" && !S.ecarts) S.ecarts = await lire("mesures.ecarts", { seuil: 60 });
      else if (scene === "prevision" && !S.prevision) { const cand = S.sources.filter((m) => m.forecast && m.available); S.prevision = []; for (const m of cand) { const p = await lire("mesures.prevision", { cle: m.key }); if (p) S.prevision.push({ m: m, p: p }); } }
      dessiner();
    }
    racine.addEventListener("click", (e) => {
      const s = e.target.closest("[data-s]"); if (s) { charger(s.dataset.s); return; }
      const p = e.target.closest('[data-a="periode"]'); if (p) { S.periode = p.dataset.p; charger("courbes"); return; }
      const o = e.target.closest('[data-a="ouvrir"]'); if (o) { S.cle = o.dataset.k; charger("courbes"); }
    });
    racine.addEventListener("change", (e) => { if (e.target.dataset && e.target.dataset.a === "cle") { S.cle = e.target.value; charger("courbes"); } });
    dessiner();                                                                          // le squelette tout de suite : les onglets, puis les lectures (lentes : une seconde ou quatre) en parallèle
    const [, v] = await Promise.all([chargerSources(), lire("mesures.verdict")]);
    S.verdict = v; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
