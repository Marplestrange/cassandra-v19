// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran Mon coffre-fort
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #3b2e63
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Mon coffre-fort : mes espaces (le mien, puis ceux des sociétés où l'on m'a fait entrer), les secrets que j'ai le droit de voir, leur ajout, leur lecture, leur retrait.
// MÉTHODE    : une scène (CASS.sceneSurMesure.coffre) ; tout passe par les capacités coffre.* : l'isolement (qui voit quoi) est garanti par le module, jamais par l'écran.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=3b2e63 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const PAGES = { vue_coffre: "tableau", c_tableau: "tableau", c_secrets: "secrets", c_outils: "outils", c_rapport: "rapport" };
  const RC = { proprio: "Propriétaire", admin: "Administrateur du coffre", membre: "Membre", contrib: "Contributeur", lecture: "Lecture seule" };
  const CSS = ".sh-scene:has(>.sh-corps>.mc){width:100%}.mc{display:grid;gap:14px;color:var(--txt);font:13.5px/1.45 'Inter',system-ui,sans-serif}.mc *{box-sizing:border-box}.mc>*{min-width:0}.mc button{font:inherit;color:inherit;cursor:pointer}" +
    ".mc .carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}.mc h2{margin:0 0 3px;font-size:15px}.mc .sub{color:var(--txt-faint);font-size:12px;margin:0 0 12px}.mc .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.mc .row .sp{flex:1}" +
    ".mc .esp{display:flex;gap:8px;flex-wrap:wrap}.mc .esp button{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:12px;padding:8px 12px;text-align:left;min-width:170px}.mc .esp button.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent)}.mc .esp small{display:block;color:var(--txt-faint)}" +
    ".mc input[type=text],.mc input[type=search],.mc select,.mc textarea{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:7px 10px;min-width:0;width:100%}.mc textarea{min-height:90px;resize:vertical}" +
    ".mc .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:10px;padding:6px 12px;font-weight:600;font-size:12.5px}.mc .btn:hover{border-color:var(--accent)}.mc .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.mc .btn.sm{padding:3px 9px;font-size:12px}.mc .btn.dng{color:var(--danger)}" +
    ".mc .tw{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface)}.mc table{border-collapse:collapse;width:100%;font-size:13px}.mc th{font:600 10.5px 'JetBrains Mono',monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:9px 12px;white-space:nowrap}.mc td{padding:8px 12px;border-top:1px solid var(--line);vertical-align:middle}" +
    ".mc .chip{display:inline-flex;font-size:11px;font-weight:600;border-radius:99px;padding:2px 9px;background:var(--surface);color:var(--txt-soft);border:1px solid var(--line);white-space:nowrap}.mc .chip.acc{background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent);border-color:transparent}.mc .vide{color:var(--txt-faint);padding:16px;text-align:center}.mc .hint{font-size:11.5px;color:var(--txt-faint)}" +
    ".mc .gen{display:grid;gap:8px}.mc .gen output{font:13px 'JetBrains Mono',monospace;background:var(--surface-solid,var(--surface));border:1px dashed var(--line-strong,var(--line));border-radius:10px;padding:8px 10px;word-break:break-all}";
  const alea = (n) => { const a = new Uint32Array(n); (window.crypto || {}).getRandomValues ? window.crypto.getRandomValues(a) : a.forEach((_, i) => { a[i] = Math.floor(Math.random() * 4294967296); }); return a; };
  const mdp = (long) => { const U = "ABCDEFGHJKLMNPQRSTUVWXYZ", L = "abcdefghijkmnopqrstuvwxyz", C = "23456789", Y = "!?#@$%&*+-=", T = U + L + C + Y; const r = alea(long + 4); let o = [U[r[0] % U.length], L[r[1] % L.length], C[r[2] % C.length], Y[r[3] % Y.length]]; for (let i = 4; i < long; i++) o.push(T[r[i] % T.length]); const m = alea(o.length); for (let i = o.length - 1; i > 0; i--) { const j = m[i] % (i + 1); [o[i], o[j]] = [o[j], o[i]]; } return o.join(""); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.coffre = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("mc-css")) { const st = document.createElement("style"); st.id = "mc-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "mc"; corps.appendChild(racine);
    const S = { page: PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "secrets", espaces: [], actif: "", secrets: [], q: "", col: "", erreur: "", charge: true, dispo: true, mdp: mdp(20), journal: null };
    const $ = (s) => racine.querySelector(s);
    const lire = async (cap, args) => { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } };
    const geste = async (cap, args, ok) => { try { const r = await agir(cap, args); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } };
    const esp = () => S.espaces.find((e) => e.id === S.actif) || S.espaces[0] || null;
    const peutEcrire = (e) => !!e && (e.role === "proprio" || e.role === "membre" || e.role === "contrib" || (e.role === "admin" && e.collections && e.collections !== ""));
    const peutRetirer = (e, s) => !!e && (e.role === "proprio" || e.role === "membre" || e.role === "admin" || (e.role === "contrib"));

    async function chargerEspaces() { const r = await lire("coffre.espaces"); S.espaces = (r && r.espaces) || []; if (!S.espaces.some((e) => e.id === S.actif)) S.actif = (S.espaces[0] || {}).id || ""; }
    async function chargerSecrets() {
      const e = esp(); S.secrets = []; S.journal = null; if (!e) return;
      if (S.page === "secrets" || S.page === "tableau") { const r = await lire("coffre.list", { espace: e.id }); S.secrets = (r && r.secrets) || []; }
      if (S.page === "rapport" || S.page === "tableau") { const j = await lire("coffre.journal", { espace: e.id, limite: S.page === "rapport" ? 100 : 5 }); S.journal = (j && j.journal) || []; }
    }
    async function recharger() { S.erreur = ""; await chargerEspaces(); await chargerSecrets(); dessiner(); }

    const selecteur = (e) => '<div class="esp">' + S.espaces.map((x) => '<button data-a="esp" data-id="' + esc(x.id) + '" class="' + (e && x.id === e.id ? "on" : "") + '"><b>' + esc(x.nom) + "</b><small>" + x.secrets + " secret" + (x.secrets > 1 ? "s" : "") + " · " + esc(RC[x.role] || x.role) + (x.expire ? " · jusqu’au " + esc(x.expire) : "") + "</small></button>").join("") + "</div>";
    const tabJournal = (J) => '<div class="tw"><table><thead><tr><th>Quand</th><th>Qui</th><th>Geste</th><th>Secret</th></tr></thead><tbody>' + (J.length ? J.map((j) => "<tr><td>" + esc(j.ts) + "</td><td>" + esc(j.username) + "</td><td>" + esc(j.action) + "</td><td>" + esc(j.secret_name) + "</td></tr>").join("") : '<tr><td colspan="4" class="vide">Rien.</td></tr>') + "</tbody></table></div>";
    function pTableau(e) {
      return '<div class="carte"><h2>Tableau de bord</h2><p class="sub">Tu ne vois que tes espaces : le tien, et ceux des sociétés où l’on t’a fait entrer. Un espace dont tu n’es pas membre n’existe pas pour toi, même pour l’administrateur de l’instance.</p>' + selecteur(e) + "</div>" +
        (e ? '<div class="carte"><h2>' + esc(e.nom) + '</h2><p class="sub">' + esc(RC[e.role] || e.role) + " · " + e.secrets + " secret" + (e.secrets > 1 ? "s" : "") + " que tu peux voir" + (e.expire ? " · accès jusqu’au " + esc(e.expire) : "") + "</p>" +
          '<h3 style="margin:0 0 8px;font-size:13px">Derniers gestes</h3>' + tabJournal(S.journal || []) + "</div>" : "");
    }
    function pSecrets(e) {
      const q = S.q.toLowerCase(), cols = Array.from(new Set(S.secrets.map((x) => x.collection || "").filter(Boolean)));
      const lignes = S.secrets.filter((x) => (!q || x.nom.toLowerCase().indexOf(q) >= 0) && (!S.col || (x.collection || "") === S.col)), peut = peutEcrire(e);
      return '<div class="carte"><h2>Coffre</h2><p class="sub">Les secrets de l’espace choisi, selon ton rôle. Seuls les noms apparaissent dans la liste ; la valeur s’ouvre à la demande et l’accès est journalisé.</p>' + selecteur(e) + "</div>" +
        (e ? '<div class="carte"><div class="row"><input type="search" id="mc-q" placeholder="Chercher un secret…" value="' + esc(S.q) + '" style="max-width:260px">' +
          (cols.length ? '<select id="mc-col" style="max-width:200px" aria-label="Collection"><option value="">Toutes les collections</option>' + cols.map((c) => "<option" + (S.col === c ? " selected" : "") + ">" + esc(c) + "</option>").join("") + "</select>" : "") +
          '<span class="sp"></span>' + (peut ? '<button class="btn pri" data-a="nouveau">+ Nouveau secret</button>' : "") + "</div>" +
          '<div class="tw" style="margin-top:12px"><table><thead><tr><th>Secret</th>' + (e.genre === "societe" ? "<th>Collection</th><th>Auteur</th>" : "") + "<th></th></tr></thead><tbody>" +
          (lignes.length ? lignes.map((x) => "<tr><td><b>" + esc(x.nom) + "</b></td>" + (e.genre === "societe" ? "<td>" + (x.collection ? '<span class="chip acc">' + esc(x.collection) + "</span>" : '<span class="hint">—</span>') + "</td><td>" + esc(x.auteur) + "</td>" : "") +
            '<td style="text-align:right;white-space:nowrap"><button class="btn sm" data-a="voir" data-n="' + esc(x.nom) + '">Voir</button> ' + (peut ? '<button class="btn sm" data-a="modifier" data-n="' + esc(x.nom) + '" data-c="' + esc(x.collection || "") + '">Modifier</button> ' : "") + (peutRetirer(e, x) && peut ? '<button class="btn sm dng" data-a="retirer" data-n="' + esc(x.nom) + '">Retirer</button>' : "") + "</td></tr>").join("") : '<tr><td colspan="4" class="vide">' + (S.charge ? "Chargement…" : (S.secrets.length ? "Aucun secret ne correspond." : "Rien dans cet espace pour l’instant.")) + "</td></tr>") +
          "</tbody></table></div>" + (e.role === "contrib" ? '<p class="hint">Contributeur : tu ne vois que les secrets que tu as déposés.</p>' : "") + (e.role === "lecture" ? '<p class="hint">Lecture seule : tu peux consulter, pas modifier.</p>' : "") + "</div>" : "");
    }
    function pOutils() {
      return '<div class="carte gen"><h2>Générateur de mot de passe</h2><p class="sub">Tiré dans ton navigateur, avec le hasard du système : rien n’est envoyé ni enregistré.</p><output id="mc-mdp">' + esc(S.mdp) + '</output><div class="row"><button class="btn" data-a="regen">Autre</button><button class="btn" data-a="copier-mdp">Copier</button><label class="hint">Longueur <select id="mc-long" style="width:auto"><option>16</option><option selected>20</option><option>28</option><option>40</option></select></label></div></div>';
    }
    function pRapport(e) {
      return '<div class="carte"><h2>Rapport</h2><p class="sub">Qui a lu, écrit ou accordé, et quand. Les valeurs n’y sont jamais. Un membre ordinaire ne voit que ses propres gestes ; les administrateurs du coffre voient ceux de tout l’espace.</p>' + selecteur(e) + "</div>" +
        (e ? '<div class="carte"><h2>Journal de ' + esc(e.nom) + "</h2>" + tabJournal(S.journal || []) + "</div>" : "");
    }
    function dessiner() {
      const e = esp();
      racine.innerHTML = (S.erreur ? '<div class="carte"><span style="color:var(--danger)">' + esc(S.erreur) + "</span></div>" : "") + ({ tableau: pTableau, secrets: pSecrets, outils: pOutils, rapport: pRapport }[S.page] || pSecrets)(e);
    }
    const copier = async (t) => { try { await navigator.clipboard.writeText(t); dire("Copié.", "ok"); } catch (e) { dire("Copie refusée par le navigateur.", "err"); } };
    // La fenêtre se referme AVANT que la promesse ne rende la main : on relève les valeurs saisies au moment du clic, avant sa fermeture.
    async function saisie(titre, corps, oui, ids, danger) {
      const snap = {};
      const h = (ev) => { if (ev.target.closest && ev.target.closest(".kit-m [data-c='oui']")) ids.forEach((id) => { const n = document.getElementById(id); snap[id] = n ? n.value : ""; }); };
      document.addEventListener("click", h, true);
      const ok = await confirmer(titre, corps, oui, danger);
      document.removeEventListener("click", h, true);
      return ok ? snap : null;
    }
    async function formulaire(titre, nom, valeur, collection) {
      const e = esp(), neuf = !nom;
      const snap = await saisie(titre, '<div class="mc" style="gap:10px"><label>Nom<input type="text" id="mc-fn" value="' + esc(nom) + '"' + (neuf ? "" : " readonly") + '></label><label>Valeur<textarea id="mc-fv">' + esc(valeur) + "</textarea></label>" + (e.genre === "societe" ? '<label>Collection<input type="text" id="mc-fc" value="' + esc(collection || "") + '" placeholder="Comptabilité, Hébergement…"></label>' : "") + '<button type="button" class="btn sm" onclick="document.getElementById(\'mc-fv\').value=(window.__mcMdp?window.__mcMdp():\'\')">Générer un mot de passe</button></div>', "Enregistrer", ["mc-fn", "mc-fv", "mc-fc"]);
      if (!snap) return null;
      return { name: (snap["mc-fn"] || "").trim(), valeur: snap["mc-fv"] || "", collection: (snap["mc-fc"] || "").trim() };
    }
    window.__mcMdp = () => mdp(+((($("#mc-long") || {}).value) || 20));
    racine.addEventListener("click", async (ev) => {
      const a = ev.target.closest("[data-a]"); if (!a) return; const k = a.dataset.a, e = esp();
      if (k === "esp") { S.actif = a.dataset.id; S.q = ""; S.col = ""; S.charge = true; dessiner(); await chargerSecrets(); S.charge = false; dessiner(); }
      else if (k === "nouveau") { const f = await formulaire("Nouveau secret", "", "", ""); if (f && f.name && await geste("coffre.set", { name: f.name, valeur: f.valeur, espace: e.id, collection: f.collection }, "Secret enregistré.")) await recharger(); }
      else if (k === "modifier") { const r = await lire("coffre.get", { name: a.dataset.n, espace: e.id }); if (!r || r.valeur === null || r.valeur === undefined) { dire("Ce secret ne s’ouvre pas.", "err"); return; } const f = await formulaire("Modifier « " + a.dataset.n + " »", a.dataset.n, r.valeur, a.dataset.c); if (f && await geste("coffre.set", { name: f.name, valeur: f.valeur, espace: e.id, collection: f.collection }, "Secret enregistré.")) await recharger(); }
      else if (k === "voir") { const r = await lire("coffre.get", { name: a.dataset.n, espace: e.id }); if (!r || r.valeur === null || r.valeur === undefined) { dire("Ce secret ne s’ouvre pas.", "err"); return; } const v = String(r.valeur); await confirmer(a.dataset.n, '<div class="mc" style="gap:8px"><textarea readonly style="min-height:90px" id="mc-vv">' + esc(v) + '</textarea><button type="button" class="btn sm" onclick="navigator.clipboard&&navigator.clipboard.writeText(document.getElementById(\'mc-vv\').value)">Copier</button><p class="hint">Cet accès est inscrit au journal.</p></div>', "Fermer"); }
      else if (k === "retirer") { if (await confirmer("Retirer « " + a.dataset.n + " » ?", "<p>Le secret est retiré du coffre. L’action peut être défaite depuis le journal des gestes.</p>", "Retirer", true) && await geste("coffre.delete", { name: a.dataset.n, espace: e.id }, "Secret retiré.")) await recharger(); }
      else if (k === "regen") { S.mdp = mdp(+((($("#mc-long") || {}).value) || 20)); const o = $("#mc-mdp"); if (o) o.textContent = S.mdp; }
      else if (k === "copier-mdp") copier(S.mdp);
    });
    racine.addEventListener("input", (ev) => { if (ev.target.id === "mc-q") { S.q = ev.target.value; const p = ev.target.selectionStart; dessiner(); const n = $("#mc-q"); if (n) { n.focus(); n.setSelectionRange(p, p); } } });
    racine.addEventListener("change", (ev) => { if (ev.target.id === "mc-col") { S.col = ev.target.value; dessiner(); } });
    const onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait && !S.charge) recharger(); etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    dessiner(); await chargerEspaces(); await chargerSecrets(); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
