// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : gestionmail-ecran.js
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #421b14
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : gestionmail-ecran.js
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=421b14 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir;
  // La feuille de style : celle de la maquette validée (docs/CN_maquette-panel-detect.html, page « Gestion e-mail »), réduite à ce que la page emploie, portée par .gm.
  const CSS = ".sh-scene:has(>.sh-corps>.gm){width:100%}.gm{color:var(--txt);font:15px/1.5 Inter,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:6px 4px 48px;max-width:1140px;margin:0 auto}.gm *{box-sizing:border-box}" +
    ".gm .mono{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace}.gm button{font:inherit;color:inherit;cursor:pointer}.gm .carte{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);backdrop-filter:blur(18px)}" +
    ".gm .fil{font-size:13px;color:var(--txt-faint);margin:2px 0 6px}.gm h1{font-size:26px;margin:0 0 4px;color:var(--txt-strong,var(--txt));letter-spacing:-.2px}.gm .tete{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}.gm .tete .meta{font-size:13px;color:var(--txt-faint);margin-right:auto;flex:1 1 320px}" +
    ".gm .btn{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:4px 10px;font-size:13px;color:var(--txt-strong,var(--txt))}.gm .btn:hover{border-color:var(--accent)}" +
    ".gm .sec{padding:16px 18px;margin-bottom:16px}.gm .sec h2{font-size:16px;margin:0;color:var(--txt-strong,var(--txt))}.gm .sh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}.gm .sh .meta{font-size:12.5px;color:var(--txt-faint)}.gm .sh .dr{margin-left:auto;display:flex;gap:6px;align-items:center}" +
    ".gm .verdict{display:flex;gap:14px;align-items:stretch}.gm .vm{width:5px;border-radius:4px;background:var(--ok);flex:none}.gm .vm.w{background:var(--warn)}.gm .vm.d{background:var(--danger)}.gm .vm.n{background:var(--line-strong,var(--line))}.gm .verdict p{margin:0}.gm .vt{font-size:19px;font-weight:700;color:var(--txt-strong,var(--txt))}.gm .vs{color:var(--txt-soft);font-size:14px;margin-top:2px!important}" +
    ".gm .pl{display:inline-flex;align-items:center;gap:5px;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--line);color:var(--txt-soft);white-space:nowrap}.gm .pl::before{content:\"\";width:6px;height:6px;border-radius:50%;background:currentColor}.gm .pl.ok{background:color-mix(in srgb,var(--ok) 12%,transparent);color:var(--ok)}.gm .pl.w{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.gm .pl.i{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent))}" +
    ".gm .rows{display:grid;gap:6px}.gm .row{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1.5fr) auto;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px 13px}.gm .row .nm{min-width:0}.gm .row .nm b{display:block;color:var(--txt-strong,var(--txt));font-weight:650}.gm .row .nm small{color:var(--txt-faint);font-size:12.5px;display:block}.gm .row .mil{font-size:13px;color:var(--txt-soft);min-width:0;overflow-wrap:anywhere}.gm .row .cote{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}" +
    "@media (max-width:760px){.gm .row{grid-template-columns:1fr}.gm .row .cote{justify-content:flex-start}}.gm .pv{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px}.gm .pv .ok{color:var(--ok);font-weight:700}.gm .pv .ko{color:var(--txt-faint)}.gm .pv small{color:var(--txt-faint);font-size:12.5px;display:block;overflow-wrap:anywhere}" +
    ".gm .note{font-size:12.5px;color:var(--txt-faint);margin:10px 0 0}.gm .vide{color:var(--txt-faint);font-size:14px;padding:6px 0}.gm .err{color:var(--danger)}" +
    ".gm .gm-bar{display:inline-block;width:120px;height:8px;border-radius:6px;background:var(--line);vertical-align:middle;overflow:hidden}.gm .gm-bar i{display:block;height:100%;background:var(--ok)}.gm .gm-bar i.w{background:var(--warn)}.gm .gm-bar i.d{background:var(--danger)}";

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.gestionmail = async function (corps) {
    K.injecter();
    if (!document.getElementById("gm-css")) { const st = document.createElement("style"); st.id = "gm-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "gm"; corps.appendChild(racine);
    const S = { d: null, erreur: "" };
    const sec = (titre, meta, corpsHtml) => '<section class="carte sec"><div class="sh"><h2>' + titre + '</h2><span class="meta">' + meta + '</span></div>' + corpsHtml + "</section>";
    const ligne = (nm, sous, mil, cote) => '<div class="row"><div class="nm"><b>' + nm + "</b><small>" + sous + '</small></div><div class="mil">' + mil + '</div><div class="cote">' + cote + "</div></div>";
    const taille = (mo) => (mo === null || mo === undefined || mo === "") ? "inconnue" : (Number(mo) >= 1024 ? (Number(mo) / 1024).toFixed(2).replace(".", ",") + " Go" : Number(mo).toFixed(0) + " Mo");
    const barre = (b) => b.pct === null || b.pct === undefined ? "" :
      '<span class="gm-bar" role="img" aria-label="' + esc(String(b.pct)) + ' % du quota"><i class="' + (b.pct >= 90 ? "d" : b.pct >= 75 ? "w" : "") + '" style="width:' + Math.min(100, b.pct) + '%"></i></span> ';

    function liste(d) {
      const L = d.boites || [];
      if (d.etat === "absent") return '<p class="vide">Aucun panneau d’hébergement ne sert les boîtes e-mail sur cette machine.</p><p class="note">Le panneau s’installe avant Cassandra ; Panel Detect (Paramètres) dit lequel est reconnu et si un module le pilote.</p>';
      if (d.etat === "muet") return '<p class="vide err">Le panneau ne répond pas : ce n’est pas « aucune boîte ». Réessaie, ou regarde Panel Detect.</p>';
      if (!L.length) return '<p class="vide">Aucune boîte e-mail sur le panneau · lecture réussie.</p>';
      return '<div class="rows">' + L.map((b) => {
        const place = b.quota_mo ? barre(b) + esc(taille(b.utilise_mo)) + " sur " + esc(taille(b.quota_mo)) : esc(taille(b.utilise_mo)) + " · sans quota connu";
        const pill = b.suspendue ? '<span class="pl w">suspendue</span>' : b.presque_pleine ? '<span class="pl d">presque pleine</span>' : "";
        return ligne('<span class="mono">' + esc(b.adresse) + "</span>", "boîte · " + esc(b.domaine || "domaine inconnu"), place, pill);
      }).join("") + "</div>";
    }
    function domaines(d) {
      const D = d.domaines || [];
      if (d.etat !== "ok" || !D.length) return "";
      return sec("Les domaines", D.length + "", '<div class="rows">' + D.map((x) => ligne('<span class="mono">' + esc(x.domaine || "domaine inconnu") + "</span>", x.boites + " boîte" + (x.boites > 1 ? "s" : ""), esc(taille(x.utilise_mo)) + " utilisés", "")).join("") + "</div>");
    }
    function dessiner() {
      const d = S.d;
      const tete = '<p class="fil">Parc › Gestion e-mail</p><div class="tete"><h1>Gestion e-mail</h1><span class="meta">via le panneau détecté · « Courrier » reste ta messagerie</span></div>';
      if (S.erreur) { racine.innerHTML = tete + '<section class="carte sec"><p class="err">' + esc(S.erreur) + "</p></section>"; return; }
      if (!d) { racine.innerHTML = tete + '<section class="carte sec"><p class="vide">Lecture…</p></section>'; return; }
      const n = (d.boites || []).length;
      const meta = d.etat === "ok" ? n + " boîte" + (n > 1 ? "s" : "") + " · " + taille(d.total_mo) + (d.pleines ? " · " + d.pleines + " presque pleine" + (d.pleines > 1 ? "s" : "") : "") + (d.suspendues ? " · " + d.suspendues + " suspendue" + (d.suspendues > 1 ? "s" : "") : "") : "";
      racine.innerHTML = tete + sec("Les boîtes", meta, liste(d)) + domaines(d) +
        '<p class="note">Lecture seule : le panneau ne sert pour l’instant ni la création de boîtes ni les renvois, et cette page n’en invente pas. SPF, DKIM et DMARC viendront à côté de chaque domaine, avec Zones DNS.</p>';
    }
    async function lire() {
      try { S.d = await agir("gestionmail.lister", {}); S.erreur = ""; } catch (e) { S.erreur = (e && e.message) || String(e); }
      dessiner();
    }
    dessiner(); await lire();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
