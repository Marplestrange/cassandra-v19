// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La console d'un module : l'écran que reçoit d'office tout module qui n'a pas d'écran sur mesure
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.2.0  #7ff38d
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La console d'un module : l'écran que reçoit d'office tout module qui n'a pas d'écran sur mesure, tiré de ce que le module déclare.
// MÉTHODE    : une fiche (modules.fiche, modules.lister) pour l'en-tête et l'aperçu ; les lectures et les gestes en cartes avec leurs paramètres, le résultat rendu en grille ou en tableau triable (ou en JSON) ; les réglages du module (reglages.lire/regler/reinitialiser/historique) avec leur état et leur histoire ; les points d'évolution du module (evolution.etat) ; tout texte dynamique est échappé
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.2.0 empreinte=7ff38d ▼▼▼
/* La console d'un module : TIRÉE de ce que le module déclare, jamais écrite à la main. Un module neuf a un écran utilisable dès qu'il est branché ;
   un écran sur mesure le remplace quand il existe (CASS.sceneSurMesure). Cinq onglets :
     - Aperçu    : ce que le module est, ce qu'il compte, ce qu'il peut faire hors de lui (réseau, écritures), ses gestes sensibles ;
     - Lectures  : chaque lecture, avec ses paramètres, et un résultat lisible (grille, tableau triable, JSON, copie) ;
     - Gestes    : chaque écriture, son risque, sa portée, sa preuve et son retour dits AVANT le geste, une confirmation pour les gestes qui comptent ;
     - Réglages  : les réglages du module, leur état (défaut ou posé), leur remise à zéro et leur historique ;
     - Évolution : les points d'évolution du module, s'il en a. */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const SECRET = /(mot_de_passe|password|secret|jeton|token|cle_api|passphrase)/i;
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const RISQUES = { lecture: ["lecture", ""], faible: ["risque faible", "ok"], moyen: ["risque moyen", "al"], eleve: ["risque élevé", "dg"] };
  const FAMILLES = { reseau: "réseau", socle: "socle", securite: "sécurité", bureau: "bureau", agents: "agents", donnees: "données" };
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };

  const CSS = ".cmx{display:flex;flex-direction:column;gap:14px;color:var(--txt);font-size:13px;line-height:1.5;margin-top:6px}.cmx *{box-sizing:border-box}.cmx h2,.cmx h3,.cmx p{margin:0}.cmx .mono{font-family:" + MONO + "}" +
    ".cmx .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass)}" +
    ".cmx .tete{padding:16px 18px;display:flex;flex-direction:column;gap:10px}.cmx .tete .l1{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}.cmx .tete h2{font:650 20px/1.2 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".cmx .tete .desc{color:var(--txt-soft);max-width:80ch}.cmx .meta{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--txt-faint)}.cmx .liens{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;font-size:12px;color:var(--txt-soft)}" +
    ".cmx .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;white-space:nowrap;background:var(--surface-solid,var(--surface));color:var(--txt-soft);border:1px solid var(--line)}" +
    ".cmx .pastille::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}.cmx .pastille.nu::before{display:none}" +
    ".cmx .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 28%,transparent)}.cmx .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}" +
    ".cmx .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent);border-color:color-mix(in srgb,var(--danger) 28%,transparent)}.cmx .pastille.ac{color:var(--accent);background:color-mix(in srgb,var(--accent) 11%,transparent);border-color:color-mix(in srgb,var(--accent) 26%,transparent)}" +
    ".cmx button.lien{display:inline;border:0;background:none;padding:0;color:var(--accent);font:inherit;font-weight:600;cursor:pointer}.cmx button.lien:hover{text-decoration:underline}" +
    ".cmx .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:6px 13px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}.cmx .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}" +
    ".cmx .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.cmx .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}.cmx .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.cmx .btn.arme{background:var(--danger);color:#fff;border-color:transparent}.cmx .btn[disabled]{opacity:.5;cursor:not-allowed}.cmx .btn.mini{padding:3px 9px;font-size:11.5px}" +
    ".cmx .onglets{display:flex;gap:2px;padding:0 6px;overflow-x:auto;border-bottom:1px solid var(--line)}.cmx .onglets button{border:0;background:transparent;padding:10px 14px;font:600 13px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}" +
    ".cmx .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}.cmx .onglets .n{margin-left:6px;font:600 10.5px 'Inter',sans-serif;background:var(--line);border-radius:99px;padding:1px 7px;color:var(--txt-soft)}" +
    ".cmx .corps{padding:16px 18px 18px;display:flex;flex-direction:column;gap:14px}.cmx .note{font-size:12px;color:var(--txt-soft)}.cmx .lib{font:600 10.5px 'Inter',system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}" +
    ".cmx .tuiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}.cmx .tuile{padding:12px 14px;border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;gap:2px;background:var(--surface-solid,transparent)}.cmx .tuile b{font:650 24px/1.1 " + MONO + ";color:var(--txt-strong,var(--txt))}" +
    ".cmx .tuile span{font-size:12px;color:var(--txt-soft)}.cmx button.tuile{cursor:pointer;text-align:left;font:inherit;color:inherit}.cmx button.tuile:hover{border-color:var(--accent)}" +
    ".cmx .bloc{display:flex;flex-direction:column;gap:8px}.cmx .liste{display:flex;flex-direction:column}.cmx .liste>div{padding:8px 0;border-top:1px solid var(--line);display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start;justify-content:space-between}.cmx .liste>div:first-child{border-top:0}" +
    ".cmx .cherche{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.cmx input[type=text],.cmx input[type=number],.cmx input[type=password],.cmx select{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:9px;padding:6px 10px;font:13px 'Inter',system-ui,sans-serif;min-width:0}" +
    ".cmx input:focus,.cmx select:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}.cmx .cherche input{flex:1 1 220px}" +
    ".cmx .cap{border:1px solid var(--line);border-left:3px solid var(--line-strong,var(--line));border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:8px;background:var(--surface-solid,transparent)}.cmx .cap.ok{border-left-color:var(--ok)}.cmx .cap.al{border-left-color:var(--warn)}.cmx .cap.dg{border-left-color:var(--danger)}.cmx .cap.lec{border-left-color:var(--accent)}" +
    ".cmx .cap .l1{display:flex;gap:8px 10px;align-items:center;flex-wrap:wrap}.cmx .cap .nom{font:650 13px " + MONO + "}.cmx .cap .sp{flex:1}.cmx .cap .lb{color:var(--txt-soft);font-size:12.5px}" +
    ".cmx .garde{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 14px;font-size:12px}.cmx .garde div{display:flex;flex-direction:column;gap:1px}.cmx .garde b{font:600 10.5px 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint)}" +
    ".cmx .params{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 12px}.cmx .p{display:flex;flex-direction:column;gap:3px;font-size:11.5px;color:var(--txt-soft)}.cmx .p input[type=text],.cmx .p input[type=number],.cmx .p input[type=password]{width:100%}" +
    ".cmx .res{display:flex;flex-direction:column;gap:6px}.cmx .res:empty{display:none}.cmx .rbar{display:flex;gap:6px 10px;align-items:center;flex-wrap:wrap;font-size:11.5px;color:var(--txt-faint)}.cmx .rbar .sp{flex:1}.cmx .rsor{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:var(--surface)}" +
    ".cmx .kv{display:grid;grid-template-columns:minmax(110px,max-content) minmax(0,1fr);gap:4px 14px;font-size:12.5px}.cmx .kv>span.k{color:var(--txt-faint);font:600 11.5px " + MONO + ";padding-top:1px}.cmx .kv>div{min-width:0;overflow-wrap:anywhere}.cmx .kv .sous{padding-left:10px;border-left:2px solid var(--line)}" +
    ".cmx table{border-collapse:collapse;width:100%;font-size:12px}.cmx th{position:sticky;top:0;background:var(--surface-solid,var(--surface));text-align:left;padding:5px 9px;border-bottom:1px solid var(--line-strong,var(--line));white-space:nowrap;cursor:pointer;font:600 11px " + MONO + ";color:var(--txt-soft)}.cmx th:hover{color:var(--accent)}" +
    ".cmx td{padding:5px 9px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere;max-width:340px}.cmx .muet{color:var(--txt-faint)}.cmx .oui{color:var(--ok);font-weight:600}.cmx .non{color:var(--txt-faint)}" +
    ".cmx pre{margin:0;font:12px/1.5 " + MONO + ";white-space:pre-wrap;overflow-wrap:anywhere}.cmx .err{color:var(--danger);font-size:12.5px}.cmx .okmsg{color:var(--ok);font-size:12.5px;font-weight:600}" +
    ".cmx .rg{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:8px 18px;padding:12px 0;border-top:1px solid var(--line);align-items:start}.cmx .rg:first-child{border-top:0}.cmx .rg .l b{font-weight:650}.cmx .rg .l .cle{font:11px " + MONO + ";color:var(--txt-faint)}" +
    ".cmx .rg .c{display:flex;flex-direction:column;gap:6px;min-width:0}.cmx .rg .c .li{display:flex;gap:6px;align-items:center}.cmx .rg .c .li input,.cmx .rg .c .li select{flex:1}.cmx .rg .etat{font-size:11.5px;color:var(--txt-faint);min-height:1.2em}" +
    ".cmx .inter{position:relative;display:inline-block;width:38px;height:22px;flex:none}.cmx .inter input{opacity:0;width:100%;height:100%;position:absolute;margin:0;cursor:pointer;z-index:1}.cmx .inter i{position:absolute;inset:0;background:var(--line-strong,#bbb);border-radius:99px;transition:.15s}.cmx .inter i::after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:.15s}" +
    ".cmx .inter input:checked+i{background:var(--accent)}.cmx .inter input:checked+i::after{left:19px}.cmx .hist{display:flex;flex-direction:column;gap:2px;font-size:11.5px;color:var(--txt-soft);padding:6px 10px;border-left:2px solid var(--line)}" +
    ".cmx .vide{padding:26px 10px;text-align:center;color:var(--txt-soft)}" +
    "@media (max-width:760px){.cmx .rg{grid-template-columns:minmax(0,1fr)}.cmx .kv{grid-template-columns:minmax(0,1fr)}}";

  // ── rendre une valeur quelconque ────────────────────────────────────────────
  const court = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
  function cellule(v) {
    if (v == null || v === "") return '<span class="muet">—</span>';
    if (typeof v === "boolean") return v ? '<span class="oui">oui</span>' : '<span class="non">non</span>';
    if (typeof v === "number") return esc(Number.isInteger(v) ? v : Math.round(v * 100) / 100);
    if (typeof v === "string") return esc(court(v, 220));
    if (Array.isArray(v) && !v.length) return '<span class="muet">liste vide</span>';
    if (Array.isArray(v)) return v.every((x) => x == null || typeof x !== "object") ? esc(court(v.join(", "), 220)) : '<span class="muet">' + v.length + " élément" + (v.length > 1 ? "s" : "") + "</span>";
    const k = Object.keys(v); return '<span class="muet">' + esc(court(k.slice(0, 5).join(", ") + (k.length > 5 ? "…" : ""), 80)) + "</span>";
  }
  function table(lignes, id) {
    const cols = [];
    for (const l of lignes.slice(0, 200)) for (const k of Object.keys(l || {})) if (cols.indexOf(k) < 0) cols.push(k);
    const c = cols.slice(0, 9);
    return '<table data-t="' + id + '"><thead><tr>' + c.map((k, i) => '<th data-c="' + i + '" title="Trier">' + esc(k) + "</th>").join("") + "</tr></thead><tbody>" +
      lignes.slice(0, 200).map((l) => "<tr>" + c.map((k) => '<td data-v="' + esc(typeof (l && l[k]) === "object" ? "" : (l && l[k] == null ? "" : l[k])) + '">' + cellule(l && l[k]) + "</td>").join("") + "</tr>").join("") + "</tbody></table>" +
      (lignes.length > 200 ? '<div class="note">' + (lignes.length - 200) + " ligne(s) de plus non montrées.</div>" : "") + (cols.length > 9 ? '<div class="note">' + (cols.length - 9) + " colonne(s) de plus : voir le JSON.</div>" : "");
  }
  let nTable = 0;
  function rendre(v, prof) {
    prof = prof || 0;
    if (v == null) return '<span class="muet">rien</span>';
    if (Array.isArray(v)) {
      if (!v.length) return '<span class="muet">liste vide</span>';
      return v.every((x) => x && typeof x === "object" && !Array.isArray(x)) ? table(v, ++nTable) : "<div>" + esc(court(v.map((x) => (x && typeof x === "object" ? JSON.stringify(x) : x)).join(", "), 900)) + "</div>";
    }
    if (typeof v === "object") {
      const k = Object.keys(v);
      if (!k.length) return '<span class="muet">vide</span>';
      return '<div class="kv">' + k.map((cle) => { const x = v[cle], gros = x && typeof x === "object" && (Array.isArray(x) ? x.length : Object.keys(x).length); return '<span class="k">' + esc(cle) + "</span><div>" + (gros && prof < 2 ? '<div class="sous">' + rendre(x, prof + 1) + "</div>" : cellule(x)) + "</div>"; }).join("") + "</div>";
    }
    return "<div>" + esc(v) + "</div>";
  }
  function brancherTris(zone) {
    zone.querySelectorAll("table[data-t]").forEach((t) => {
      t.querySelectorAll("th").forEach((th) => th.addEventListener("click", () => {
        const i = +th.dataset.c, sens = th.dataset.s === "a" ? -1 : 1, corps = t.tBodies[0], l = Array.from(corps.rows);
        t.querySelectorAll("th").forEach((x) => { x.dataset.s = ""; x.textContent = x.textContent.replace(/ [▲▼]$/, ""); });
        th.dataset.s = sens === 1 ? "a" : "d"; th.textContent += sens === 1 ? " ▲" : " ▼";
        const val = (r) => r.cells[i].dataset.v;
        l.sort((a, b) => { const x = val(a), y = val(b), nx = x !== "" && !isNaN(x), ny = y !== "" && !isNaN(y); return sens * (nx && ny ? x - y : x.localeCompare(y, "fr", { numeric: true })); }).forEach((r) => corps.appendChild(r));
      }));
    });
  }

  // ── un champ de paramètre ───────────────────────────────────────────────────
  function champ(p, id) {
    let c;
    if (p.type === "booleen") c = '<span class="inter"><input type="checkbox" id="' + id + '" data-p="' + esc(p.nom) + '"' + (p.defaut ? " checked" : "") + '><i></i></span>';
    else if (p.type === "entier" || p.type === "nombre") c = '<input type="number" id="' + id + '" data-p="' + esc(p.nom) + '" value="' + esc(p.defaut == null ? "" : p.defaut) + '">';
    else if (p.type === "liste" || p.type === "objet") c = '<input type="text" id="' + id + '" data-p="' + esc(p.nom) + '" placeholder="JSON, ex. ' + (p.type === "liste" ? "[&quot;a&quot;]" : "{}") + '" value="' + esc(p.defaut ? JSON.stringify(p.defaut) : "") + '" spellcheck="false">';
    else c = '<input type="' + (SECRET.test(p.nom) ? "password" : "text") + '" id="' + id + '" data-p="' + esc(p.nom) + '" autocomplete="off" spellcheck="false" value="' + esc(p.defaut == null ? "" : p.defaut) + '">';
    return '<label class="p" for="' + id + '"><span>' + esc(p.nom) + (p.requis ? ' <b style="color:var(--danger)">*</b>' : "") + "</span>" + c + "</label>";
  }
  function valeursDe(zone, c) {
    const a = {};
    for (const p of c.parametres) {
      const e = zone.querySelector('[data-p="' + p.nom + '"]'); if (!e) continue;
      let v = p.type === "booleen" ? e.checked : e.value;
      if (p.type === "booleen") { a[p.nom] = v; continue; }
      if (v === "") { if (p.requis) throw new Error("« " + p.nom + " » est requis"); continue; }
      if (p.type === "entier" || p.type === "nombre") v = Number(v);
      else if (p.type === "liste" || p.type === "objet") { try { v = JSON.parse(v); } catch (e2) { throw new Error("« " + p.nom + " » : JSON invalide"); } }
      a[p.nom] = v;
    }
    return a;
  }

  const pastille = (t, c) => '<span class="pastille ' + (c || "nu") + '">' + esc(t) + "</span>";
  function carte(c, lecture) {
    const [rl, rc] = RISQUES[c.risque] || [c.risque, ""];
    const garde = !lecture && (c.perimetre.length || c.preuve || c.retour) ? '<div class="garde">' +
      (c.perimetre.length ? "<div><b>Portée</b><span>" + esc(c.perimetre.join(" · ")) + "</span></div>" : "") + (c.preuve ? "<div><b>Preuve</b><span>" + esc(c.preuve) + "</span></div>" : "") +
      (c.retour ? "<div><b>Retour</b><span>" + esc(c.retour) + "</span></div>" : "") + (c.reversible ? "" : "<div><b>Retour</b><span>pas de retour automatique</span></div>") + "</div>" : "";
    return '<div class="cap ' + (lecture ? "lec" : rc) + '" data-cap="' + esc(c.cle) + '"><div class="l1"><span class="nom">' + esc(c.id) + "</span>" + (lecture ? "" : pastille(rl, rc)) + (c.droit ? pastille("droit : " + c.droit, "") : "") +
      '<span class="sp"></span><button class="btn mini ' + (lecture ? "" : "pri") + '" data-go>' + (lecture ? "Lire" : "Exécuter") + '</button></div><div class="lb">' + esc(c.libelle) + "</div>" + garde +
      (c.parametres.length ? '<div class="params">' + c.parametres.map((p, i) => champ(p, "cm-" + c.id + "-" + i)).join("") + "</div>" : "") + '<div class="res"></div></div>';
  }

  function lierCartes(zone, caps) {
    let autos = 0;
    zone.querySelectorAll(".cap").forEach((el) => {
      const c = caps.find((x) => x.cle === el.dataset.cap), btn = el.querySelector("[data-go]"), res = el.querySelector(".res");
      let arme = false, brut = null, json = false, duree = 0;
      const dessiner = () => {
        if (brut == null && !res.dataset.f) return;
        res.innerHTML = '<div class="rbar">' + (c.ecrit ? '<span class="okmsg">✓ fait</span>' : "") + '<span>' + duree + " ms · " + new Date().toLocaleTimeString("fr-FR") + '</span><span class="sp"></span>' +
          '<button class="btn mini" data-js>' + (json ? "Vue lisible" : "Voir le JSON") + '</button><button class="btn mini" data-cp>Copier</button></div><div class="rsor">' + (json ? "<pre>" + esc(JSON.stringify(brut, null, 2)) + "</pre>" : rendre(brut)) + "</div>";
        res.querySelector("[data-js]").addEventListener("click", () => { json = !json; dessiner(); });
        res.querySelector("[data-cp]").addEventListener("click", () => { try { navigator.clipboard.writeText(JSON.stringify(brut, null, 2)).then(() => dire("JSON copié"), () => dire("Copie refusée par le navigateur", "err")); } catch (e) { dire("Copie refusée par le navigateur", "err"); } });
        brancherTris(res);
      };
      btn.addEventListener("click", async () => {
        if (c.ecrit && c.risque !== "faible" && !arme) { arme = true; btn.textContent = "Confirmer ?"; btn.classList.add("arme"); setTimeout(() => { if (arme) { arme = false; btn.textContent = "Exécuter"; btn.classList.remove("arme"); } }, 4000); return; }
        arme = false; btn.classList.remove("arme"); btn.disabled = true; const t0 = btn.textContent; btn.textContent = "…"; res.innerHTML = ""; res.dataset.f = "";
        const d0 = performance.now();
        try { const a = valeursDe(el, c); brut = await CASS.agir(c.cle, a); duree = Math.round(performance.now() - d0); res.dataset.f = "1"; dessiner(); }
        catch (e) { brut = null; res.dataset.f = ""; res.innerHTML = '<div class="err">' + esc(e.message || e) + "</div>"; }
        btn.disabled = false; btn.textContent = c.ecrit ? "Exécuter" : "Lire";
      });
      if (!c.ecrit && !c.parametres.length && autos++ < 2) btn.click();      // une lecture sans paramètre se lit d'elle-même (les deux premières : pas d'orage d'appels)
    });
  }

  // ── les réglages ────────────────────────────────────────────────────────────
  const quand = (ts) => new Date(ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  const valTxt = (v) => (v == null ? "défaut" : typeof v === "string" && v === "" ? "vide" : String(v));
  async function reglages(mid, zone) {
    zone.innerHTML = '<div class="vide">Lecture des réglages…</div>';
    let l; try { l = ((await CASS.agir("reglages.lire", { module: mid })) || {}).reglages || []; } catch (e) { zone.innerHTML = '<div class="err">' + esc(e.message) + "</div>"; return; }
    l = l.filter((r) => r.module === mid);
    if (!l.length) { zone.innerHTML = '<div class="vide">Ce module ne déclare aucun réglage.</div>'; return; }
    const ligne = (r) => {
      const id = "rg-" + r.cle.replace(/[^a-z0-9]/gi, "_");
      let ctl;
      if (r.type === "booleen") ctl = '<span class="inter"><input type="checkbox" id="' + id + '"' + (r.valeur ? " checked" : "") + "><i></i></span>";
      else if (r.type === "choix") ctl = '<select id="' + id + '">' + (r.choix || []).map((c) => '<option value="' + esc(c) + '"' + (String(c) === String(r.valeur) ? " selected" : "") + ">" + esc(c) + "</option>").join("") + "</select>";
      else if (r.type === "secret") ctl = '<input type="password" id="' + id + '" autocomplete="new-password" placeholder="' + (r.pose ? "•••••• défini : saisir pour remplacer" : "non défini") + '">';
      else if (r.type === "entier") ctl = '<input type="number" id="' + id + '" value="' + esc(r.valeur) + '">';
      else ctl = '<input type="text" id="' + id + '" value="' + esc(r.valeur) + '" spellcheck="false">';
      return '<div class="rg" data-cle="' + esc(r.cle) + '" data-type="' + esc(r.type) + '"><div class="l"><b>' + esc(r.libelle) + "</b>" + (r.aide ? '<div class="note">' + esc(r.aide) + "</div>" : "") + '<div class="cle">' + esc(r.cle) + "</div></div>" +
        '<div class="c"><div class="li">' + ctl + (r.pose ? pastille(r.type === "secret" ? "défini" : "personnalisé", "ac") : pastille("défaut", "")) + '<button class="btn mini" data-rz title="Rendre le défaut" ' + (r.pose ? "" : "hidden") + '>↺</button><button class="btn mini" data-h title="Historique des changements">Historique</button></div>' +
        (r.type !== "secret" && r.defaut !== "" && r.defaut != null && r.pose ? '<div class="note">défaut : <span class="mono">' + esc(r.defaut) + "</span></div>" : "") + '<div class="etat"></div><div class="hist" hidden></div></div></div>';
    };
    zone.innerHTML = '<div class="note">Chaque champ s’enregistre dès que vous le quittez ; ↺ rend la valeur d’origine.</div>' + l.map(ligne).join("");
    zone.querySelectorAll(".rg").forEach((el) => {
      const cle = el.dataset.cle, type = el.dataset.type, ctl = el.querySelector("input,select"), etat = el.querySelector(".etat"), hist = el.querySelector(".hist");
      const msg = (t, bad) => { etat.textContent = t; etat.style.color = bad ? "var(--danger)" : ""; };
      ctl.addEventListener("change", async () => {
        const v = type === "booleen" ? ctl.checked : type === "entier" ? Number(ctl.value) : ctl.value;
        if (type === "secret" && !ctl.value) return;
        msg("…");
        try { await CASS.agir(type === "secret" ? "reglages.regler_secret" : "reglages.regler", { cle, valeur: v }); msg("✓ enregistré"); setTimeout(() => reglages(mid, zone), 600); }
        catch (e) { msg(e.message || String(e), true); }
      });
      el.querySelector("[data-rz]").addEventListener("click", async () => { msg("…"); try { await CASS.agir("reglages.reinitialiser", { cle }); reglages(mid, zone); } catch (e) { msg(e.message || String(e), true); } });
      el.querySelector("[data-h]").addEventListener("click", async () => {
        if (!hist.hidden) { hist.hidden = true; return; }
        hist.hidden = false; hist.textContent = "Lecture…";
        try {
          const h = ((await CASS.agir("reglages.historique", { cle, limite: 8 })) || {}).historique || [];
          hist.innerHTML = h.length ? h.map((x) => "<div>" + esc(quand(x.ts)) + " · " + esc(x.par || "—") + " : <span class=\"mono\">" + esc(type === "secret" ? "•••" : valTxt(x.avant)) + "</span> → <span class=\"mono\">" + esc(type === "secret" ? "•••" : valTxt(x.apres)) + "</span></div>").join("") : "Jamais modifié.";
        } catch (e) { hist.textContent = e.message || String(e); }
      });
    });
  }

  // ── la console ──────────────────────────────────────────────────────────────
  CASS.console = async function (mid, hote) {
    const anc = document.getElementById("cmx-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "cmx-css"; st.textContent = CSS; document.head.appendChild(st);
    hote.innerHTML = '<div class="cmx"><div class="carte"><div class="corps"><div class="vide">Chargement du module…</div></div></div></div>';
    let f, cat = {}, gere = false, evo = [];
    try { f = await CASS.agir("modules.fiche", { module: mid }); } catch (e) { hote.innerHTML = '<div class="empty-state">' + esc(e.message) + "</div>"; return; }
    try { const l = (await CASS.agir("modules.lister", {})) || {}; cat = (l.modules || []).find((m) => m.id === mid) || {}; gere = l.gere !== false; } catch (e) { cat = {}; }
    try { const e = (await CASS.agir("evolution.etat", {})) || {}; evo = (e.points || []).filter((p) => String(p.point || "").split(".")[0] === mid); } catch (e) { evo = []; }
    const m = Object.assign({}, cat, f.module || {});
    const caps = f.capacites || [], lect = caps.filter((c) => !c.ecrit), ecr = caps.filter((c) => c.ecrit), sens = ecr.filter((c) => c.risque === "moyen" || c.risque === "eleve");
    let nReg = 0; try { nReg = (((await CASS.agir("reglages.lire", { module: mid })) || {}).reglages || []).filter((r) => r.module === mid).length; } catch (e) {}
    const onglets = [["apercu", "Aperçu", null], ["lire", "Lectures", lect.length], ["agir", "Gestes", ecr.length], ["reglages", "Réglages", nReg], ["evo", "Évolution", evo.length]].filter((o) => o[2] !== 0);
    const actif = m.etat === "actif", eCls = actif ? "ok" : m.etat === "refuse" ? "dg" : "al";
    const lien = (id) => '<button type="button" class="lien" data-m="' + esc(id) + '">' + esc(id) + "</button>";
    const peutBasculer = gere && !m.essentiel && (actif ? (m.peut_desactiver || {}).ok : (m.peut_activer || {}).ok);

    hote.innerHTML = '<div class="cmx"><div class="carte"><div class="tete"><div class="l1"><h2>' + esc(m.nom || mid) + '</h2><span class="mono note">' + esc(mid) + "</span>" + (m.version ? pastille("v" + m.version, "ac") : "") +
      pastille(gere ? (m.etat || "—") : "actif (développement)", gere ? eCls : "ok") + (m.famille ? pastille(FAMILLES[m.famille] || m.famille, "") : "") + (m.essentiel ? pastille("essentiel", "") : "") + (m.confiance ? pastille("confiance " + m.confiance, "") : "") +
      '<span style="flex:1"></span>' + (peutBasculer ? '<button class="btn ' + (actif ? "dng" : "pri") + '" data-bascule>' + (actif ? "Désactiver" : "Activer") + "</button>" : "") + "</div>" +
      (m.description ? '<p class="desc">' + esc(m.description) + "</p>" : "") +
      ((m.requiert || []).length || (m.requis_par || []).length ? '<div class="liens">' + ((m.requiert || []).length ? "<span>Requiert : " + m.requiert.map(lien).join(", ") + "</span>" : "") + ((m.requis_par || []).length ? "<span>Utilisé par : " + m.requis_par.map(lien).join(", ") + "</span>" : "") + "</div>" : "") +
      '<div class="meta">' + (m.auteur ? "<span>auteur : " + esc(m.auteur) + "</span>" : "") + (m.licence ? "<span>licence : " + esc(m.licence) + "</span>" : "") + (m.api ? "<span>API " + esc(m.api) + "</span>" : "") + (m.par ? "<span>fourni par " + esc(m.par) + "</span>" : "") + "</div></div>" +
      '<div class="onglets" role="tablist">' + onglets.map((o, i) => '<button type="button" role="tab" data-o="' + o[0] + '" class="' + (i ? "" : "on") + '">' + o[1] + (o[2] != null ? '<span class="n">' + o[2] + "</span>" : "") + "</button>").join("") + '</div><div class="corps cm-corps"></div></div></div>';
    const corps = hote.querySelector(".cm-corps");

    hote.querySelectorAll("[data-m]").forEach((b) => b.addEventListener("click", () => { if (CASS.ouvrirConsole) CASS.ouvrirConsole(b.dataset.m, b.dataset.m); }));
    const bas = hote.querySelector("[data-bascule]");
    if (bas) { let arme = false; bas.addEventListener("click", async () => {
      if (!arme) { arme = true; bas.textContent = actif ? "Confirmer la désactivation ?" : "Confirmer l’activation ?"; setTimeout(() => { if (arme) { arme = false; bas.textContent = actif ? "Désactiver" : "Activer"; } }, 4000); return; }
      bas.disabled = true; bas.textContent = "…";
      try { await CASS.agir(actif ? "modules.desactiver" : "modules.activer", actif ? { module: mid, cascade: false } : { module: mid, avec_dependances: true }); dire((m.nom || mid) + (actif ? " désactivé" : " activé")); CASS.console(mid, hote); }
      catch (e) { dire(e.message || String(e), "err"); bas.disabled = false; arme = false; bas.textContent = actif ? "Désactiver" : "Activer"; }
    }); }

    const perm = m.permissions || {};
    const apercu = () => {
      const tuile = (n, lib, o) => '<' + (o ? 'button type="button" data-go-o="' + o + '"' : "div") + ' class="tuile"><b>' + n + "</b><span>" + lib + "</span></" + (o ? "button" : "div") + ">";
      const liste = (t, a) => (a && a.length ? '<div class="bloc"><span class="lib">' + t + '</span><div class="liste">' + a.map((x) => "<div><span>" + esc(x) + "</span></div>").join("") + "</div></div>" : "");
      const hors = liste("Parle au réseau", perm.reseau) + liste("Écrit sur le disque", perm.ecritures) + liste("Privilèges demandés", perm.privileges) + (perm.espace_utilisateur ? '<div class="bloc"><span class="lib">Espace utilisateur</span><div class="note">Ce module garde des données par compte.</div></div>' : "");
      corps.innerHTML = '<div class="tuiles">' + tuile(lect.length, "lecture" + (lect.length > 1 ? "s" : ""), lect.length ? "lire" : "") + tuile(ecr.length, "geste" + (ecr.length > 1 ? "s" : ""), ecr.length ? "agir" : "") + tuile(nReg, "réglage" + (nReg > 1 ? "s" : ""), nReg ? "reglages" : "") +
        tuile(m.detecteurs || 0, "détecteur" + (m.detecteurs > 1 ? "s" : "")) + tuile(m.moteurs || 0, "moteur" + (m.moteurs > 1 ? "s" : "")) + tuile(m.objets || 0, "type" + (m.objets > 1 ? "s" : "") + " d’objet") + tuile(m.ecrans || 0, "écran" + (m.ecrans > 1 ? "s" : "")) + (evo.length ? tuile(evo.length, "point" + (evo.length > 1 ? "s" : "") + " d’évolution", "evo") : "") + "</div>" +
        (sens.length ? '<div class="bloc"><span class="lib">Gestes qui comptent</span><div class="liste">' + sens.map((c) => "<div><span><b class=\"mono\">" + esc(c.id) + "</b> · " + esc(c.libelle) + "</span>" + pastille(RISQUES[c.risque][0], RISQUES[c.risque][1]) + "</div>").join("") + "</div></div>" : "") +
        (hors ? '<div class="bloc"><span class="lib">Ce que ce module peut faire hors de lui</span></div>' + hors : '<div class="note">Ce module ne sort pas de la maison : ni réseau, ni écriture déclarés.</div>');
      corps.querySelectorAll("[data-go-o]").forEach((b) => b.addEventListener("click", () => montrer(b.dataset.goO)));
    };
    const liste = (caps2, lecture, intro) => {
      corps.innerHTML = (intro ? '<div class="note">' + intro + "</div>" : "") + (caps2.length > 6 ? '<div class="cherche"><input type="text" id="cm-q" placeholder="Filtrer par nom ou description…" aria-label="Filtrer"><span class="note" id="cm-n"></span></div>' : "") + '<div class="bloc cm-l">' + caps2.map((c) => carte(c, lecture)).join("") + "</div>";
      lierCartes(corps, caps2);
      const q = corps.querySelector("#cm-q");
      if (q) q.addEventListener("input", () => { const t = q.value.trim().toLowerCase(); let n = 0; corps.querySelectorAll(".cap").forEach((el) => { const c = caps2.find((x) => x.cle === el.dataset.cap), ok = !t || (c.id + " " + c.libelle).toLowerCase().includes(t); el.hidden = !ok; if (ok) n++; }); corps.querySelector("#cm-n").textContent = t ? n + " sur " + caps2.length : ""; });
    };
    const evolution = () => {
      corps.innerHTML = '<div class="note">Un point d’évolution est une fonction que Cassandra peut améliorer d’elle-même, dans un cadre prouvé. Voici ceux de ce module.</div><div class="liste">' + evo.map((p) => "<div><span><b class=\"mono\">" + esc(p.point) + "</b>" + (p.libelle ? " · " + esc(p.libelle) : "") + "</span>" + (p.etat ? pastille(p.etat, "") : "") + "</div>").join("") + "</div>" +
        (CASS.ouvrirEcran ? '<div><button class="btn" data-evo>Ouvrir l’atelier d’évolution</button></div>' : "");
      const b = corps.querySelector("[data-evo]"); if (b) b.addEventListener("click", () => CASS.ouvrirEcran("evolution:cockpit", "Évolution"));
    };
    const montrer = async (o) => {
      hote.querySelectorAll(".onglets [data-o]").forEach((b) => b.classList.toggle("on", b.dataset.o === o));
      if (o === "apercu") apercu();
      else if (o === "lire") liste(lect, true, "Chaque lecture est sans effet. Celles sans paramètre se lisent d’elles-mêmes à l’ouverture (les deux premières).");
      else if (o === "agir") liste(ecr, false, "Chaque geste dit ce qu’il touche, comment il se prouve et comment il se défait avant d’être lancé. Un geste de risque moyen ou élevé demande une confirmation.");
      else if (o === "evo") evolution();
      else await reglages(mid, corps);
    };
    hote.querySelectorAll(".onglets [data-o]").forEach((b) => b.addEventListener("click", () => montrer(b.dataset.o)));
    montrer("apercu");
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de la console et ses gestes.
// EC : néant (aucun point d'évolution déclaré pour l'instant).
// LIEN : modules/modules (modules.fiche, modules.lister), modules/reglages, interface/CN_shell.js (qui l'ouvre), interface/CN_modules-ui.js (le catalogue qui y renvoie).
