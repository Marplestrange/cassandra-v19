// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran « Journaux » du module journal : ce qui s'est passé (le flux unifié), une source e
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d1ccfc
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran « Journaux » du module journal : ce qui s'est passé (le flux unifié), une source en détail, chercher partout, les veilles sur motif, le poids de chaque journal.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d1ccfc ▼▼▼
// L'écran « Journaux » du module journal : ce qui s'est passé (le flux unifié), une source en détail, chercher partout, les veilles sur motif, le poids de chaque journal.
// Les données viennent des capacités du module (journal.resume, flux, sources, lire, chercher, silences, timeline, veilles, stats).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, ic = K.ic, pill = K.pill, agir = K.agir, dire = K.dire;
  const SCENES = [["flux", "Ce qui s’est passé"], ["source", "Une source"], ["chercher", "Chercher partout"], ["veilles", "Veilles"], ["poids", "Poids"]];
  const NIV = { critique: ["critique", "dg", "warn"], erreur: ["erreur", "dg", "warn"], avertissement: ["avertissement", "al", "eye"], info: ["info", "", ""] };
  const PERIODES = [["", "Tout"], ["1", "1 h"], ["24", "24 h"], ["168", "7 j"]];
  const niv = (n) => { const x = NIV[n] || NIV.info; return pill(x[0], x[1], x[2]); };
  const court = (ts) => String(ts || "").replace("T", " ").slice(0, 19);
  const octets = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " Mo" : n >= 1024 ? Math.round(n / 1024) + " Ko" : n + " o");
  const depuisH = (h) => { if (!h) return ""; const d = new Date(Date.now() - (+h) * 3600000); return d.toISOString().slice(0, 19).replace("T", " "); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.journal = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("journal", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "flux", resume: null, flux: null, niveau: "", q: "", h: "", sources: null, src: "", lire: null, offset: 0, qs: "", chercher: null, qc: "", veilles: null, stats: null, silences: null, charge: false, erreur: "" };

    async function lire(cap, args) { try { return await agir(cap, args); } catch (e) { S.erreur = e.message || String(e); return null; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0]) + '">' + s[1] + "</button>").join("") + "</div>";

    function ligneFlux(e) {
      const det = e.detail && Object.keys(e.detail).length ? '<details><summary class="note" style="cursor:pointer">détail</summary><pre class="mono note" style="white-space:pre-wrap;margin:4px 0 0">' + esc(JSON.stringify(e.detail, null, 1)) + "</pre></details>" : "";
      return '<div class="li"><div class="sp"><b>' + esc(e.action || "") + "</b>" + (e.sujet ? '<span class="note">' + esc(e.sujet) + "</span>" : "") + det + '<span class="faint mono" style="font-size:11.5px">' + esc(court(e.ts)) + " · " + esc(e.label || e.source || "") + (e.acteur ? " · " + esc(e.acteur) : "") + "</span></div>" + niv(e.niveau) + "</div>";
    }
    function flux() {
      const r = S.resume, f = S.flux;
      const haut = r ? '<div class="carte"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h3 style="flex:1;min-width:200px">' + esc(r.titre || "") + "</h3>" + pill(r.niveau || "stable", r.niveau === "stable" ? "ok" : "al") + "</div>" +
        '<div class="chips">' + ["critique", "erreur", "avertissement", "info"].map((k) => '<span class="p ' + (NIV[k][1]) + '">' + esc(k) + " " + ((r.compte || {})[k] || 0) + "</span>").join("") + '<span class="note">' + esc(r.sous_titre || "") + "</span></div>" +
        ((r.marquants || []).length ? '<div class="liste">' + r.marquants.map((m) => '<div class="li"><div class="sp"><b>' + esc(m.action) + '</b><span class="faint mono" style="font-size:11.5px">' + esc(court(m.ts)) + " · " + esc(m.label || m.source || "") + "</span></div>" + niv(m.niveau) + "</div>").join("") + "</div>" : "") + "</div>" : '<div class="carte vide">Lecture…</div>';
      const filtres = '<div class="barre"><input type="search" id="jr-q" placeholder="Filtrer (Entrée)…" value="' + esc(S.q) + '" aria-label="Filtrer le flux"><select class="sel" data-a="niveau" aria-label="Niveau">' + [["", "Tous les niveaux"], ["erreur+", "Erreurs"], ["avertissement", "Avertissements"], ["info", "Infos"]].map((x) => '<option value="' + x[0] + '"' + (S.niveau === x[0] ? " selected" : "") + ">" + x[1] + "</option>").join("") + '</select><div class="seg" role="group" aria-label="Période">' + PERIODES.map((p) => '<button class="' + (S.h === p[0] ? "on" : "") + '" data-a="h" data-v="' + p[0] + '">' + p[1] + "</button>").join("") + "</div></div>";
      const liste = S.charge ? '<div class="carte vide">Lecture…</div>' : f ? '<div class="carte"><div class="liste">' + ((f.entrees || []).length ? f.entrees.map(ligneFlux).join("") : '<div class="vide"><b>Rien à afficher.</b><br><span class="note">Aucune ligne ne correspond, ou les journaux sont vides.</span></div>') + "</div>" + ((f.en_defaut || []).length ? '<p class="note">Sources illisibles : ' + esc(f.en_defaut.join(" ; ")) + "</p>" : "") + "</div>" : "";
      return haut + filtres + liste;
    }
    function source() {
      const ss = S.sources || [];
      const groupes = {}; ss.forEach((s) => { (groupes[s.group || "Autres"] = groupes[s.group || "Autres"] || []).push(s); });
      const choix = '<select class="sel" data-a="src" aria-label="Journal">' + '<option value="">Choisis un journal…</option>' + Object.keys(groupes).map((g) => '<optgroup label="' + esc(g) + '">' + groupes[g].map((s) => '<option value="' + esc(s.key) + '"' + (s.key === S.src ? " selected" : "") + (s.available ? "" : " disabled") + ">" + esc(s.label) + (s.available ? " (" + s.count + ")" : " (absent)") + "</option>").join("") + "</optgroup>").join("") + "</select>";
      const L = S.lire;
      let c = '<div class="carte vide">Choisis un journal.</div>';
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (L) {
        const cols = (L.columns || []).filter((x) => x !== L.ts_col);
        c = '<div class="carte"><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>' + esc(L.label || S.src) + '</h3><span class="note">' + esc(L.total) + " ligne(s)" + (S.qs ? ' pour « ' + esc(S.qs) + " »" : "") + "</span></div>" +
          (L.kind === "table" ? ((L.rows || []).length ? '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px"><thead><tr>' + [L.ts_col].concat(cols).filter(Boolean).map((h) => '<th style="text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);font:600 11px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint)">' + esc(h) + "</th>").join("") + "</tr></thead><tbody>" +
            L.rows.map((r) => "<tr>" + [L.ts_col].concat(cols).filter(Boolean).map((h) => '<td style="padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top;max-width:340px;overflow-wrap:anywhere">' + esc(String(r[h] == null ? "" : r[h]).slice(0, 400)) + "</td>").join("") + "</tr>").join("") + "</tbody></table></div>" : '<div class="vide">Aucune ligne.</div>') :
            ((L.lines || []).length ? '<pre class="mono" style="margin:0;white-space:pre-wrap;font-size:12px;overflow-x:auto;max-height:60vh;overflow-y:auto">' + esc(L.lines.join("\n")) + "</pre>" : '<div class="vide">Aucune ligne.</div>')) +
          (L.has_more ? '<div><button class="btn mini" data-a="plus">Plus ancien</button></div>' : "") + "</div>";
      }
      return '<div class="barre">' + choix + '<input type="search" id="jr-qs" placeholder="Filtrer dans ce journal (Entrée)…" value="' + esc(S.qs) + '" aria-label="Filtrer dans ce journal"></div>' + c;
    }
    function chercher() {
      const r = S.chercher;
      return '<div class="barre"><input type="search" id="jr-qc" placeholder="Chercher dans tous les journaux (Entrée)…" value="' + esc(S.qc) + '" aria-label="Chercher partout"></div>' +
        (S.charge ? '<div class="carte vide">Lecture…</div>' : r ? '<div class="carte"><h3>' + esc(r.total) + " résultat(s) pour « " + esc(r.query) + " »</h3>" + ((r.results || []).length ? '<div class="liste">' + r.results.map((x) => '<div class="li"><div class="sp"><b>' + esc(x.label) + '</b><span class="note">' + esc(x.total) + " ligne(s)</span></div><button class=\"btn mini\" data-a=\"ouvrir-source\" data-k=\"" + esc(x.key) + '">Ouvrir</button></div>').join("") + "</div>" : '<div class="vide"><b>Rien trouvé.</b></div>') + "</div>" : '<div class="carte vide">Tape un terme : je le cherche dans chaque journal.</div>');
    }
    function veilles() {
      const v = S.veilles, ss = S.sources || [];
      return '<div class="carte"><h3>Veilles sur motif</h3><p class="note">Une veille cherche une expression régulière dans un journal (ou tous) : elle te prévient quand elle la voit.</p>' + (v === null ? '<div class="vide">Lecture…</div>' : v.length ? '<div class="liste">' + v.map((w) => '<div class="li"><div class="sp"><b>' + esc(w.label || w.pattern) + '</b><span class="note mono">' + esc(w.pattern) + " · " + esc(w.source || "tous les journaux") + "</span></div>" + pill(w.enabled ? "active" : "en pause", w.enabled ? "ok" : "") + '<button class="btn mini" data-a="veille-bascule" data-id="' + w.id + '">' + (w.enabled ? "Mettre en pause" : "Reprendre") + '</button><button class="btn mini dng" data-a="veille-retire" data-id="' + w.id + '">Retirer</button></div>').join("") + "</div>" : '<div class="vide">Aucune veille.</div>') +
        '<div class="barre"><input type="text" id="vl-motif" class="sel" style="flex:1 1 200px" placeholder="motif (expression régulière)" aria-label="Motif"><input type="text" id="vl-nom" class="sel" style="flex:1 1 160px" placeholder="nom (facultatif)" aria-label="Nom"><select class="sel" id="vl-src" aria-label="Journal"><option value="">Tous les journaux</option>' + ss.filter((s) => s.available).map((s) => '<option value="' + esc(s.key) + '">' + esc(s.label) + "</option>").join("") + '</select><button class="btn pri" data-a="veille-pose">Poser</button></div></div>';
    }
    function poids() {
      const st = S.stats, si = S.silences;
      return '<div class="carte"><h3>Poids de chaque journal</h3><p class="note">Un journal qui enfle finit par gêner le disque.</p>' + (st ? '<div class="liste">' + (st.journals || []).filter((j) => j.rows || j.bytes).map((j) => '<div class="li"><div class="sp"><b>' + esc(j.label) + '</b><span class="note">' + esc(j.kind === "table" ? j.rows + " ligne(s)" : "fichier") + "</span></div>" + pill(octets(j.bytes || 0), j.bytes > 104857600 ? "al" : "") + "</div>").join("") + (((st.journals || []).some((j) => j.rows || j.bytes)) ? "" : '<div class="vide">Tous les journaux sont vides.</div>') + '</div><p class="note">Total : ' + octets(st.bytes || 0) + "</p>" : '<div class="vide">Lecture…</div>') + "</div>" +
        '<div class="carte"><h3>Journaux qui se taisent</h3><p class="note">Un journal qui écrivait régulièrement et ne dit plus rien depuis plus de trois fois son rythme habituel.</p>' + (si ? ((si.silences || []).length ? '<div class="liste">' + si.silences.map((s) => '<div class="li"><div class="sp"><b>' + esc(s.label) + '</b><span class="note">dernière ligne ' + esc(court(s.last)) + " ; d’habitude toutes les " + Math.round(s.attendu_s / 60) + " min</span></div>" + pill("silence", "al") + "</div>").join("") + "</div>" : '<div class="vide"><b>Aucun silence anormal.</b></div>') : '<div class="vide">Lecture…</div>') + "</div>";
    }
    function dessiner() {
      const c = S.scene === "flux" ? flux() : S.scene === "source" ? source() : S.scene === "chercher" ? chercher() : S.scene === "veilles" ? veilles() : poids();
      const foc = document.activeElement && document.activeElement.id;
      racine.innerHTML = '<p class="note">Tout ce que les journaux ont dit : le flux, une source, une recherche, des veilles.</p>' + (S.erreur ? '<div class="alerte dg"><div class="sp">' + esc(S.erreur) + "</div></div>" : "") + barre() + c;
      if (foc && racine.querySelector("#" + foc)) { const x = racine.querySelector("#" + foc); x.focus(); if (x.setSelectionRange) try { x.setSelectionRange(99, 99); } catch (e) {} }
    }
    async function chargerFlux() {
      S.charge = true; dessiner();
      const [r, f] = await Promise.all([lire("journal.resume", { heures: 24 }), lire("journal.flux", { sources: [], limit: 200, niveau: S.niveau, query: S.q, since: depuisH(S.h), equilibre: true })]);
      S.resume = r; S.flux = f; S.charge = false; dessiner();
    }
    async function chargerSource() {
      if (!S.sources) { const r = await lire("journal.sources"); S.sources = (r && r.sources) || []; }
      if (S.src) { S.charge = true; dessiner(); S.lire = await lire("journal.lire", { source: S.src, limit: 100, offset: S.offset, query: S.qs, since: "" }); S.charge = false; }
      dessiner();
    }
    async function aller(scene) {
      S.scene = scene; S.erreur = ""; dessiner();
      if (scene === "flux") await chargerFlux();
      else if (scene === "source") await chargerSource();
      else if (scene === "chercher") { dessiner(); }
      else if (scene === "veilles") { if (!S.sources) { const r = await lire("journal.sources"); S.sources = (r && r.sources) || []; } const v = await lire("journal.veilles"); S.veilles = v ? v.veilles || [] : []; dessiner(); }
      else { const [st, si] = await Promise.all([lire("journal.stats"), lire("journal.silences")]); S.stats = st; S.silences = si; dessiner(); }
    }
    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a;
      if (k === "h") { S.h = a.dataset.v; chargerFlux(); }
      else if (k === "plus") { S.offset += 100; const L = S.lire; const n = await lire("journal.lire", { source: S.src, limit: 100, offset: S.offset, query: S.qs, since: "" }); if (n) { n.rows = (L.rows || []).concat(n.rows || []); n.lines = (L.lines || []).concat(n.lines || []); S.lire = n; } dessiner(); }
      else if (k === "ouvrir-source") { S.src = a.dataset.k; S.qs = S.qc; S.offset = 0; S.lire = null; aller("source"); }
      else if (k === "veille-retire") { try { await agir("journal.veille_retirer", { wid: +a.dataset.id }); dire("Veille retirée.", "ok"); aller("veilles"); } catch (x) { dire(x.message || String(x), "err"); } }
      else if (k === "veille-bascule") { const w = (S.veilles || []).find((y) => String(y.id) === a.dataset.id); if (w) { try { await agir("journal.veille_poser", { wid: w.id, source: w.source || "", pattern: w.pattern, label: w.label || "", enabled: !w.enabled }); aller("veilles"); } catch (x) { dire(x.message || String(x), "err"); } } }
      else if (k === "veille-pose") { const m = (racine.querySelector("#vl-motif") || {}).value || ""; if (!m.trim()) { dire("Il faut un motif.", "err"); return; } try { await agir("journal.veille_poser", { source: (racine.querySelector("#vl-src") || {}).value || "", pattern: m.trim(), label: ((racine.querySelector("#vl-nom") || {}).value || "").trim(), enabled: true }); dire("Veille posée.", "ok"); aller("veilles"); } catch (x) { dire(x.message || String(x), "err"); } }
    });
    racine.addEventListener("change", (e) => {
      const k = e.target.dataset && e.target.dataset.a;
      if (k === "niveau") { S.niveau = e.target.value; chargerFlux(); }
      else if (k === "src") { S.src = e.target.value; S.offset = 0; S.lire = null; chargerSource(); }
    });
    racine.addEventListener("keydown", async (e) => {
      if (e.key !== "Enter") return;
      if (e.target.id === "jr-q") { e.preventDefault(); S.q = e.target.value.trim(); chargerFlux(); }
      else if (e.target.id === "jr-qs") { e.preventDefault(); S.qs = e.target.value.trim(); S.offset = 0; chargerSource(); }
      else if (e.target.id === "jr-qc") { e.preventDefault(); S.qc = e.target.value.trim(); if (!S.qc) return; S.charge = true; dessiner(); S.chercher = await lire("journal.chercher", { question: S.qc, per_source: 5 }); S.charge = false; dessiner(); }
    });
    dessiner(); await chargerFlux();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
