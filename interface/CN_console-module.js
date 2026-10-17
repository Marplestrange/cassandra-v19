// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La console d'un module : l'écran que reçoit d'office tout module qui n'a pas d'écran sur m
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ad013b
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La console d'un module : l'écran que reçoit d'office tout module qui n'a pas d'écran sur mesure.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ad013b ▼▼▼
/* La console d'un module : l'écran que reçoit d'office tout module qui n'a pas d'écran sur mesure.

   Elle est TIRÉE de ce que le module déclare, jamais écrite à la main :
     - « Lire »    : ses capacités de lecture, chacune avec ses paramètres, et le résultat rendu en tableau ;
     - « Agir »    : ses capacités d'écriture, un formulaire par capacité, avec son risque, sa preuve et son retour dits AVANT le geste ;
     - « Réglages »: ses réglages globaux, ceux de modules-ui.js ;
   et, au-dessus, les tuiles que le module a déclarées pour l'écran (s'il en a).
   Un module neuf a donc un écran utilisable dès qu'il est branché ; un écran sur mesure le remplace quand il existe (CASS.couvre). */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const SECRET = /(mot_de_passe|password|secret|jeton|token|cle_api|passphrase)/i;
  const RISQUES = { lecture: ["", ""], faible: ["faible", "ok"], moyen: ["moyen", "warn"], eleve: ["élevé", "bad"] };

  // ── rendre une valeur quelconque ────────────────────────────────────
  function cellule(v) {
    if (v == null || v === "") return '<span class="sh-muet">—</span>';
    if (typeof v === "boolean") return v ? "oui" : "non";
    if (typeof v === "number") return esc(Number.isInteger(v) ? v : v.toFixed(2));
    if (typeof v === "string") return esc(v.length > 140 ? v.slice(0, 137) + "…" : v);
    if (Array.isArray(v)) return v.every((x) => typeof x !== "object") ? esc(v.join(", ").slice(0, 140)) : '<span class="sh-muet">' + v.length + " élément(s)</span>";
    const k = Object.keys(v); return '<span class="sh-muet">' + esc(k.slice(0, 4).join(", ") + (k.length > 4 ? "…" : "")) + "</span>";
  }
  function table(lignes) {
    const cols = [];
    for (const l of lignes.slice(0, 50)) for (const k of Object.keys(l || {})) if (cols.indexOf(k) < 0) cols.push(k);
    const c = cols.slice(0, 8);
    return '<div style="overflow:auto;max-height:340px"><table class="cm-tab" style="border-collapse:collapse;font-size:11.5px;width:100%"><thead><tr>' +
      c.map((k) => '<th style="text-align:left;padding:3px 8px;border-bottom:1px solid var(--bd,rgba(0,0,0,.15));white-space:nowrap">' + esc(k) + "</th>").join("") + "</tr></thead><tbody>" +
      lignes.slice(0, 50).map((l) => "<tr>" + c.map((k) => '<td style="padding:3px 8px;border-bottom:1px solid var(--bd,rgba(0,0,0,.06));vertical-align:top">' + cellule(l && l[k]) + "</td>").join("") + "</tr>").join("") +
      "</tbody></table></div>" + (lignes.length > 50 ? '<div class="s-hint">' + (lignes.length - 50) + " ligne(s) de plus non montrées</div>" : "") + (cols.length > 8 ? '<div class="s-hint">' + (cols.length - 8) + " colonne(s) de plus non montrées</div>" : "");
  }
  function rendre(v, profondeur) {
    profondeur = profondeur || 0;
    if (v == null) return '<span class="sh-muet">rien</span>';
    if (Array.isArray(v)) {
      if (!v.length) return '<span class="sh-muet">liste vide</span>';
      return v.every((x) => x && typeof x === "object" && !Array.isArray(x)) ? table(v) : "<div>" + esc(v.map((x) => (typeof x === "object" ? JSON.stringify(x) : x)).join(", ").slice(0, 600)) + "</div>";
    }
    if (typeof v === "object") {
      const k = Object.keys(v);
      if (!k.length) return '<span class="sh-muet">vide</span>';
      return k.map((cle) => {
        const x = v[cle], gros = x && typeof x === "object";
        return '<div style="padding:3px 0;border-bottom:1px solid var(--bd,rgba(0,0,0,.06))"><span class="s-hint" style="display:inline-block;min-width:120px">' + esc(cle) + "</span> " +
               (gros && profondeur < 2 ? '<div style="margin:2px 0 4px 8px">' + rendre(x, profondeur + 1) + "</div>" : cellule(x)) + "</div>";
      }).join("");
    }
    return "<div>" + esc(v) + "</div>";
  }

  // ── un formulaire de paramètres ─────────────────────────────────────
  function champ(p, id) {
    const s = 'style="font-size:12px;padding:4px 8px;min-width:0;flex:1"';
    const nom = p.nom + (p.requis ? " *" : "");
    let c;
    if (p.type === "booleen") c = '<input type="checkbox" id="' + id + '" ' + (p.defaut ? "checked" : "") + ">";
    else if (p.type === "entier" || p.type === "nombre") c = '<input type="number" id="' + id + '" class="inp" ' + s + ' value="' + esc(p.defaut == null ? "" : p.defaut) + '">';
    else if (p.type === "liste" || p.type === "objet") c = '<input type="text" id="' + id + '" class="inp" ' + s + ' placeholder="JSON, ex. ' + (p.type === "liste" ? "[&quot;a&quot;]" : "{}") + '" value="' + esc(p.defaut ? JSON.stringify(p.defaut) : "") + '">';
    else c = '<input type="' + (SECRET.test(p.nom) ? "password" : "text") + '" id="' + id + '" class="inp" ' + s + ' autocomplete="off" value="' + esc(p.defaut == null ? "" : p.defaut) + '">';
    return '<label style="display:flex;gap:8px;align-items:center;font-size:11.5px;text-transform:none;letter-spacing:0;margin:3px 0"><span style="min-width:130px">' + esc(nom) + "</span>" + c + "</label>";
  }
  function valeursDe(racine, caps) {
    const a = {};
    for (const p of caps.parametres) {
      const e = racine.querySelector('[data-p="' + p.nom + '"]'); if (!e) continue;
      let v = p.type === "booleen" ? e.checked : e.value;
      if (p.type === "booleen") { a[p.nom] = v; continue; }
      if (v === "") { if (p.requis) throw new Error("« " + p.nom + " » est requis"); continue; }
      if (p.type === "entier" || p.type === "nombre") v = Number(v);
      else if (p.type === "liste" || p.type === "objet") { try { v = JSON.parse(v); } catch (e2) { throw new Error("« " + p.nom + " » : JSON invalide"); } }
      a[p.nom] = v;
    }
    return a;
  }

  function pastille(txt, cls) {
    const col = cls === "ok" ? "var(--ok,#1b7f5c)" : cls === "warn" ? "var(--warn,#a86400)" : cls === "bad" ? "var(--danger,#b3261e)" : "var(--txt-faint,#777)";
    return '<span style="font-size:10px;padding:1px 8px;border-radius:9px;border:1px solid ' + col + ";color:" + col + '">' + esc(txt) + "</span>";
  }

  function carte(c, lecture) {
    const [rl, rc] = RISQUES[c.risque] || [c.risque, ""];
    const parametres = c.parametres.length ? '<div style="margin:6px 0">' + c.parametres.map((p, i) => champ(p, "cm-" + c.id + "-" + i).replace(/<input /, '<input data-p="' + p.nom + '" ')).join("") + "</div>" : "";
    const garantie = !lecture ? '<div class="s-hint" style="margin:4px 0">' +
      (c.perimetre.length ? "<b>Portée</b> : " + esc(c.perimetre.join(" ; ")) + "<br>" : "") + (c.preuve ? "<b>Preuve</b> : " + esc(c.preuve) + "<br>" : "") +
      (c.retour ? "<b>Retour</b> : " + esc(c.retour) : "") + (c.reversible ? "" : " — <b>pas de retour automatique</b>") + "</div>" : "";
    return '<div class="cm-cap" data-cap="' + esc(c.cle) + '" style="padding:9px 0;border-top:1px solid var(--bd,rgba(0,0,0,.08))">' +
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b style="font-size:12.5px">' + esc(c.id) + "</b>" + (lecture ? "" : pastille("risque " + rl, rc)) + (c.droit ? pastille("droit " + c.droit, "") : "") +
      '<span style="flex:1"></span><button class="btn-x mini ' + (lecture ? "" : "pri") + '" data-go>' + (lecture ? "Lire" : "Exécuter") + "</button></div>" +
      '<div class="s-hint">' + esc(c.libelle) + "</div>" + garantie + parametres + '<div class="cm-res" style="margin-top:6px"></div></div>';
  }

  function lier(racine, caps) {
    let autos = 0;
    racine.querySelectorAll(".cm-cap").forEach((el) => {
      const c = caps.find((x) => x.cle === el.dataset.cap), btn = el.querySelector("[data-go]"), res = el.querySelector(".cm-res");
      let arme = false;
      btn.addEventListener("click", async () => {
        if (c.ecrit && c.risque !== "faible" && !arme) { arme = true; btn.textContent = "Confirmer ?"; setTimeout(() => { arme = false; btn.textContent = "Exécuter"; }, 4000); return; }
        arme = false; btn.disabled = true; const t0 = btn.textContent; btn.textContent = "…"; res.innerHTML = "";
        try {
          const r = await CASS.agir(c.cle, valeursDe(el, c));
          res.innerHTML = (c.ecrit ? '<div class="s-hint" style="color:var(--ok,#1b7f5c)">✓ fait</div>' : "") + '<div style="max-height:380px;overflow:auto">' + rendre(r) + "</div>";
        } catch (e) { res.innerHTML = '<div style="color:var(--danger,#b3261e);font-size:12px">' + esc(e.message) + "</div>"; }
        btn.disabled = false; btn.textContent = c.ecrit ? "Exécuter" : "Lire";
      });
      if (!c.ecrit && !c.parametres.length && autos++ < 3) btn.click();       // une lecture sans paramètre se lit d'elle-même (les trois premières : pas d'orage d'appels)
    });
  }

  // ── la console ──────────────────────────────────────────────────────
  CASS.console = async function (mid, hote) {
    hote.innerHTML = '<div class="s-hint">Chargement du module…</div>';
    let f;
    try { f = await CASS.agir("modules.fiche", { module: mid }); } catch (e) { hote.innerHTML = '<div class="empty-state">' + esc(e.message) + "</div>"; return; }
    const lect = f.capacites.filter((c) => !c.ecrit), ecr = f.capacites.filter((c) => c.ecrit);
    const onglets = [["lire", "Lire", lect.length], ["agir", "Agir", ecr.length], ["reglages", "Réglages", null]].filter((o) => o[2] !== 0);
    hote.innerHTML = '<div class="cm" style="margin-top:14px"><div role="tablist" style="display:flex;gap:6px;margin-bottom:8px">' +
      onglets.map((o, i) => '<button class="mx-scene' + (i ? "" : " on") + '" data-o="' + o[0] + '">' + o[1] + (o[2] != null ? " (" + o[2] + ")" : "") + "</button>").join("") + '</div><div class="cm-corps"></div></div>';
    const corps = hote.querySelector(".cm-corps");
    const montrer = async (o) => {
      hote.querySelectorAll("[data-o]").forEach((b) => b.classList.toggle("on", b.dataset.o === o));
      if (o === "lire") { corps.innerHTML = lect.map((c) => carte(c, true)).join(""); lier(corps, lect); }
      else if (o === "agir") { corps.innerHTML = '<div class="s-hint">Chaque geste dit ce qu\'il touche, comment il se prouve et comment il se défait avant d\'être lancé. Un geste de risque moyen ou élevé demande une confirmation.</div>' + ecr.map((c) => carte(c, false)).join(""); lier(corps, ecr); }
      else if (CASS.reglagesDe) await CASS.reglagesDe(mid, corps);
      else corps.innerHTML = '<div class="s-hint">Les réglages ne sont pas chargés.</div>';
    };
    hote.querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", () => montrer(b.dataset.o)));
    montrer(onglets[0] ? onglets[0][0] : "reglages");
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
