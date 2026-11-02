// ═════════════════════════════════════════════════════════════════
// TITRE      : Modèles : l’écran des modèles et des clés
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #542c69
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l’écran « Modèles et clés » du module modeles : les modèles en ligne (fournisseur, clé d’API, essai), le catalogue des modèles locaux (Ollama : installer, déclarer, supprimer) et les rôles.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.modeles) ; tout passe par les capacités modeles.* ; une clé saisie part au noyau et n’est jamais relue ni réaffichée.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=542c69 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };

  // Des suggestions, pas une liste fermée : le nom se tape librement (les fournisseurs en ajoutent chaque mois).
  const SUGGEST = {
    deepseek: ["deepseek-chat", "deepseek-reasoner"],
    openrouter: ["google/gemini-2.5-flash", "anthropic/claude-sonnet-4.5", "openai/gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-chat"],
    openai: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    google: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"],
    ollama: ["qwen2.5:3b", "qwen3:4b-instruct", "llama3.2:3b"],
  };
  const LIENS = { deepseek: "platform.deepseek.com", openrouter: "openrouter.ai/keys", openai: "platform.openai.com/api-keys", google: "aistudio.google.com/apikey", groq: "console.groq.com/keys" };
  const CATALOGUE_LOCAL = [
    ["qwen2.5:3b", "1,9 Go", "léger, bon en français : le choix par défaut"], ["qwen3:4b-instruct", "2,5 Go", "plus fin, répond sans réfléchir à voix haute"],
    ["llama3.2:3b", "2,0 Go", "polyvalent et rapide"], ["gemma2:2b", "1,6 Go", "très léger, pour une petite machine"],
    ["qwen2.5:7b", "4,7 Go", "nettement meilleur, demande 8 Go de mémoire"], ["mistral:7b", "4,1 Go", "français correct, 8 Go de mémoire"],
    ["phi3.5", "2,2 Go", "petit et bon en raisonnement court"], ["nomic-embed-text", "0,3 Go", "recherche par le sens (pas de conversation)"],
  ];

  const CSS = ".md{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.md *{box-sizing:border-box}.md h1,.md h2,.md h3,.md p{margin:0}.md .mono{font-family:" + MONO + "}" +
    ".md .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:12px}" +
    ".md .tete h1{font:650 22px/1.2 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}.md .sous,.md .note{color:var(--txt-soft);font-size:12.5px}.md .sous{font-size:13px;margin-top:3px;max-width:68ch}" +
    ".md h2{font:650 16px 'Inter',system-ui,sans-serif}.md .acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.md .bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}" +
    ".md .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 13px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer}" +
    ".md .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.md .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.md .btn.pri:hover:not([disabled]){filter:brightness(1.08);color:var(--on-accent,#fff)}" +
    ".md .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.md .btn[disabled]{opacity:.45;cursor:not-allowed}.md .btn.mini{padding:4px 9px;font-size:11.5px}" +
    ".md .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;white-space:nowrap;border:1px solid var(--line)}.md .pastille::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}" +
    ".md .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)}.md .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}.md .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent)}.md .pastille.mu{color:var(--txt-soft)}" +
    ".md .rang{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1.4fr) auto;gap:8px 14px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}.md .rang .nom{font:600 13px " + MONO + ";overflow-wrap:anywhere}" +
    ".md .champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px 16px}.md label.ch{display:flex;flex-direction:column;gap:5px}.md label.ch b{font-weight:650;font-size:12.5px}" +
    ".md input[type=text],.md input[type=password],.md select{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:8px 12px;font:13px " + MONO + ";min-width:0;width:100%}" +
    ".md input:focus,.md select:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}" +
    ".md .puces{display:flex;gap:8px;flex-wrap:wrap}.md .puce{border:1px solid var(--line);border-radius:12px;padding:8px 12px;background:var(--surface-solid,transparent);display:flex;flex-direction:column;gap:3px;min-width:170px;max-width:240px}" +
    ".md .puce b{font:650 12.5px " + MONO + "}.md .barre{height:5px;border-radius:99px;background:var(--line);overflow:hidden}.md .barre i{display:block;height:100%;background:var(--accent)}" +
    ".md .attente{padding:30px;text-align:center;color:var(--txt-soft)}.md .confirme{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px}.md .err{color:var(--danger)}" +
    ".sh-scene:has(>.sh-corps>.md)>.sh-titre{display:none}@media (max-width:820px){.md .rang{grid-template-columns:minmax(0,1fr) auto}.md .rang .m{grid-column:1 / -1}}";

  const octets = (n) => n >= 1e9 ? (n / 1e9).toFixed(1).replace(".", ",") + " Go" : Math.round((n || 0) / 1e6) + " Mo";
  const RANG = { principal: "le modèle principal de Cassandra", itare_citadelle: "Itare, la passerelle", vision: "la lecture d’images", relecteur: "la relecture", second_avis: "le second avis" };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.modeles = async function (corps, ctx) {
    const anc = document.getElementById("md-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "md-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "md"; corps.appendChild(racine);

    const S = { l: null, f: [], loc: null, occupe: false, erreur: "", prov: "", retirer: "", suppr: "", essais: {}, form: { nom: "", cle: "", base: "" }, mini: "" };
    let minuterie = null;

    async function charger(tout) {
      try {
        const [l, f, loc] = await Promise.all([agir("modeles.lister"), S.f.length && !tout ? Promise.resolve({ fournisseurs: S.f, roles: S.roles }) : agir("modeles.fournisseurs"), agir("modeles.locaux").catch((e) => ({ repond: false, raison: e.message, modeles: [], telechargements: [] }))]);
        S.l = l; S.f = f.fournisseurs || []; S.roles = f.roles || {}; S.loc = loc; S.erreur = "";
        if (!S.prov && S.f.length) S.prov = S.f[0].id;
      } catch (e) { S.erreur = e.message || String(e); }
      dessiner(); armer();
    }
    function armer() {
      if (minuterie) { clearTimeout(minuterie); minuterie = null; }
      const actifs = S.loc && (S.loc.telechargements || []).some((p) => p.etat === "attente" || p.etat === "en cours");
      if (actifs && document.body.contains(racine)) minuterie = setTimeout(() => { if (document.body.contains(racine) && !S.occupe) charger(); }, 3000);
    }
    const faire = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; dessiner();
      try { const r = await f(); if (ok) dire(typeof ok === "function" ? ok(r) : ok); } catch (e) { dire(e.message || String(e), "err"); }
      finally { S.occupe = false; S.retirer = ""; S.suppr = ""; await charger(); }
    };
    // L’administrateur déclare pour l’instance ; un compte ordinaire pour lui seul.
    const ajouterModele = async (a) => { try { return await agir("modeles.instance_ajouter", a); } catch (e) { if (/droit|autoris/i.test(e.message || "")) return agir("modeles.ajouter", a); throw e; } };
    const essayer = async (id) => { try { return await agir("modeles.instance_essayer", { id }); } catch (e) { if (/droit|autoris/i.test(e.message || "")) return agir("modeles.essayer", { id }); throw e; } };
    const retirerModele = async (id) => { try { return await agir("modeles.instance_retirer", { id }); } catch (e) { if (/droit|autoris/i.test(e.message || "")) return agir("modeles.retirer", { id }); throw e; } };

    const prov = () => S.f.find((x) => x.id === S.prov) || {};
    const declares = () => (S.l.modeles || []);
    const enLigne = () => declares().filter((m) => m.en_ligne);
    const localDecl = () => declares().filter((m) => !m.en_ligne);

    function ligneModele(m) {
      const e = m.essai || S.essais[m.id];
      const essai = e ? (e.ok ? '<span class="pastille ok">a répondu en ' + esc(e.secondes) + " s</span>" : '<span class="pastille dg" title="' + esc(e.message || e.erreur) + '">a échoué</span>') + ' <span class="note">' + esc(e.quand || "") + "</span>" : '<span class="pastille mu">pas encore essayé</span>';
      return '<div class="rang"><div><span class="nom">' + esc(m.nom) + '</span><br><span class="note">' + esc((S.f.find((x) => x.id === m.fournisseur) || {}).nom || m.fournisseur) + (m.base_url ? " · " + esc(m.base_url) : "") + "</span></div>" +
        '<div class="m">' + (m.a_cle ? '<span class="pastille ok">clé enregistrée</span> ' : '<span class="pastille mu">sans clé</span> ') + (m.roles || []).map((r) => '<span class="pastille al">' + esc(r) + "</span>").join(" ") + "<br>" + essai + "</div>" +
        '<div class="acts"><button class="btn mini" data-a="essayer" data-id="' + esc(m.id) + '"' + (S.occupe ? " disabled" : "") + ">Essayer</button>" +
        (S.retirer === m.id ? '<span class="confirme">Retirer ? <button class="btn mini dng" data-a="retirer-oui" data-id="' + esc(m.id) + '">Oui</button><button class="btn mini" data-a="retirer-non">Non</button></span>' : '<button class="btn mini dng" data-a="retirer" data-id="' + esc(m.id) + '">Retirer</button>') + "</div></div>";
    }

    function carteLigne() {
      const l = enLigne();
      return '<div class="carte"><div class="bar"><h2>Modèles en ligne</h2></div>' + (l.length ? l.map(ligneModele).join("") : '<p class="note">Aucun modèle en ligne déclaré. Ajoute-en un ci-dessous : fournisseur, nom du modèle, clé d’API.</p>') + "</div>";
    }

    function carteAjout() {
      const p = prov(), sug = SUGGEST[S.prov] || [], besoin = p.cle !== "aucune", perso = S.prov === "personnalise";
      return '<div class="carte"><h2>Ajouter un modèle</h2><p class="note">La clé est chiffrée dans le coffre du noyau dès l’envoi ; elle n’est jamais relue ni réaffichée, ni écrite dans le journal.</p>' +
        '<div class="champs"><label class="ch"><b>Fournisseur</b><select id="md-prov">' + S.f.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === S.prov ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + "</select>" +
        (LIENS[S.prov] ? '<span class="note">Créer une clé : ' + esc(LIENS[S.prov]) + "</span>" : "") + "</label>" +
        '<label class="ch"><b>Nom du modèle</b><input type="text" id="md-nom" list="md-sug" value="' + esc(S.form.nom) + '" placeholder="' + esc(p.defaut || "nom du modèle") + '" autocomplete="off" spellcheck="false"><datalist id="md-sug">' + sug.map((x) => '<option value="' + esc(x) + '">').join("") + "</datalist><span class=\"note\">Vide : " + esc(p.defaut || "à saisir") + "</span></label>" +
        (besoin ? '<label class="ch"><b>Clé d’API' + (p.cle === "optionnelle" ? " (facultative)" : "") + '</b><input type="password" id="md-cle" value="" placeholder="sk-…" autocomplete="off" spellcheck="false"></label>' : "") +
        (perso ? '<label class="ch"><b>Adresse de l’API</b><input type="text" id="md-base" value="' + esc(S.form.base) + '" placeholder="https://… ou http://127.0.0.1:8000/v1" autocomplete="off" spellcheck="false"></label>' : "") + "</div>" +
        '<div class="acts"><button class="btn pri" data-a="ajouter"' + (S.occupe ? " disabled" : "") + ">" + (S.occupe ? "Un instant…" : "Ajouter et essayer") + "</button></div></div>";
    }

    function carteLocale() {
      const loc = S.loc || {}, inst = loc.modeles || [], decl = new Set(localDecl().map((m) => m.nom)), pulls = (loc.telechargements || []).filter((p) => p.etat === "attente" || p.etat === "en cours");
      const noms = new Set(inst.map((m) => m.name));
      let h = '<div class="carte"><div class="bar"><h2>Modèles locaux (Ollama)</h2>' + (loc.repond ? '<span class="pastille ok">Ollama répond</span>' : '<span class="pastille dg" title="' + esc(loc.raison || "") + '">Ollama ne répond pas</span>') + "</div>";
      if (!loc.repond) h += '<p class="note err">' + esc(loc.raison || "Ollama est arrêté") + ' — sur la machine : <span class="mono">systemctl start ollama</span> (ou relancer l’installateur avec WITH_OLLAMA=1).</p>';
      h += inst.length ? inst.map((m) => '<div class="rang"><div><span class="nom">' + esc(m.name) + '</span><br><span class="note">' + octets(m.taille) + " sur le disque</span></div><div class=\"m\">" + (decl.has(m.name) ? '<span class="pastille ok">déclaré</span>' : '<span class="pastille mu">installé, pas déclaré</span>') + '</div><div class="acts">' +
        (decl.has(m.name) ? "" : '<button class="btn mini pri" data-a="declarer" data-n="' + esc(m.name) + '"' + (S.occupe ? " disabled" : "") + ">Utiliser</button>") +
        (S.suppr === m.name ? '<span class="confirme">Supprimer ? <button class="btn mini dng" data-a="suppr-oui" data-n="' + esc(m.name) + '">Oui</button><button class="btn mini" data-a="suppr-non">Non</button></span>' : '<button class="btn mini dng" data-a="suppr" data-n="' + esc(m.name) + '">Supprimer</button>') + "</div></div>").join("")
        : (loc.repond ? '<p class="note">Aucun modèle installé.</p>' : "");
      if (pulls.length) h += '<h3 style="font:650 13px Inter,sans-serif;margin-top:6px">Téléchargements en cours</h3>' + pulls.map((p) => '<div><span class="mono">' + esc(p.nom) + '</span> <span class="note">' + esc(p.detail || p.etat) + '</span><div class="barre"><i style="width:' + Math.max(3, Math.min(100, p.pourcent || 3)) + '%"></i></div></div>').join("");
      h += '<h3 style="font:650 13px Inter,sans-serif;margin-top:6px">Catalogue : à installer en un clic</h3><div class="puces">' + CATALOGUE_LOCAL.map((c) => '<div class="puce"><b>' + esc(c[0]) + '</b><span class="note">' + esc(c[1]) + " · " + esc(c[2]) + "</span>" +
        (noms.has(c[0]) ? '<span class="pastille ok">installé</span>' : '<button class="btn mini" data-a="installer" data-n="' + esc(c[0]) + '"' + (S.occupe || !loc.repond ? " disabled" : "") + ">Installer</button>") + "</div>").join("") + "</div>" +
        '<div class="acts" style="margin-top:4px"><input type="text" id="md-pull" value="' + esc(S.mini) + '" placeholder="un autre nom du catalogue ollama.com/library, ex. llama3.1:8b" style="flex:1 1 280px;width:auto" autocomplete="off" spellcheck="false"><button class="btn" data-a="installer-libre"' + (S.occupe || !loc.repond ? " disabled" : "") + ">Installer</button></div></div>";
      return h;
    }

    function carteRoles() {
      const ms = declares().filter((m) => m.portee === "instance"), roles = (S.l.roles || {}), dico = Object.assign({}, RANG, S.roles || {}), noms = Object.keys(dico);
      if (!Object.prototype.hasOwnProperty.call(S.l, "roles") || !ms.length) return "";
      return '<div class="carte"><h2>Qui parle avec quoi</h2><p class="note">Chaque agent et chaque service cherche son modèle par son rôle. Un rôle sans modèle prend celui de la maison (le modèle local).</p>' +
        noms.map((r) => '<div class="rang"><div><span class="nom">' + esc(r) + '</span><br><span class="note">' + esc(dico[r] || "") + '</span></div><div class="m"><select data-role="' + esc(r) + '"><option value="">— celui de la maison —</option>' +
          ms.map((m) => '<option value="' + esc(m.id) + '"' + (roles[r] === m.id ? " selected" : "") + ">" + esc(m.nom) + " (" + esc(m.fournisseur) + ")</option>").join("") + '</select></div><div></div></div>').join("") + "</div>";
    }

    function dessiner() {
      let h = '<div class="tete"><div class="bar"><h1>Modèles et clés</h1><div class="acts"><button class="btn mini" data-a="console" title="La console technique du module (réglages, gestes, journal)">Console technique</button></div></div>' +
        '<p class="sous">Les modèles de langage qui font parler Cassandra, Itare et les autres : ceux des fournisseurs en ligne (avec ta clé d’API) et ceux que la machine fait tourner elle-même.</p></div>';
      if (S.erreur) h += '<div class="carte err">' + esc(S.erreur) + "</div>";
      if (!S.l) { racine.innerHTML = h + '<div class="attente">Lecture des modèles…</div>'; return; }
      h += carteLigne() + carteAjout() + carteLocale() + carteRoles();
      // on garde ce qui se tape pendant qu’on redessine
      const foc = document.activeElement && document.activeElement.id, val = foc ? document.activeElement.value : "";
      racine.innerHTML = h;
      if (foc && racine.querySelector("#" + foc) && foc !== "md-cle") { const e = racine.querySelector("#" + foc); if (e.tagName === "INPUT") e.value = val; }
      lier();
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
      const p = racine.querySelector("#md-prov"); if (p) p.addEventListener("change", () => { S.prov = p.value; S.form = { nom: "", cle: "", base: "" }; dessiner(); });
      const n = racine.querySelector("#md-nom"); if (n) n.addEventListener("input", () => { S.form.nom = n.value; });
      const b = racine.querySelector("#md-base"); if (b) b.addEventListener("input", () => { S.form.base = b.value; });
      const m = racine.querySelector("#md-pull"); if (m) m.addEventListener("input", () => { S.mini = m.value; });
      racine.querySelectorAll("[data-role]").forEach((s) => s.addEventListener("change", () => faire(() => agir("modeles.role_lier", { role: s.dataset.role, modele_id: s.value }), "Rôle mis à jour : " + s.dataset.role)));
    }

    async function geste(b) {
      const a = b.dataset.a;
      if (a === "console") { racine.remove(); if (CASS.console) CASS.console("modeles", corps); return; }
      if (a === "retirer") { S.retirer = b.dataset.id; dessiner(); return; }
      if (a === "retirer-non") { S.retirer = ""; dessiner(); return; }
      if (a === "retirer-oui") return faire(() => retirerModele(b.dataset.id), "Modèle retiré.");
      if (a === "suppr") { S.suppr = b.dataset.n; dessiner(); return; }
      if (a === "suppr-non") { S.suppr = ""; dessiner(); return; }
      if (a === "suppr-oui") return faire(() => agir("modeles.ollama_supprimer", { nom: b.dataset.n }), "Modèle local supprimé.");
      if (a === "essayer") return faire(async () => { const r = await essayer(b.dataset.id); S.essais[b.dataset.id] = r.essai || r; return r; }, (r) => ((r.essai || r).ok === false ? "Le modèle n’a pas répondu." : "Le modèle a répondu."));
      if (a === "declarer") return faire(() => ajouterModele({ fournisseur: "ollama", nom: b.dataset.n }), "Modèle local déclaré : " + b.dataset.n);
      if (a === "installer") return faire(() => agir("modeles.ollama_telecharger", { nom: b.dataset.n }), "Téléchargement demandé : " + b.dataset.n);
      if (a === "installer-libre") {
        const n = String((racine.querySelector("#md-pull") || {}).value || "").trim();
        if (!n) { dire("Un nom de modèle, comme llama3.1:8b", "err"); return; }
        S.mini = ""; return faire(() => agir("modeles.ollama_telecharger", { nom: n }), "Téléchargement demandé : " + n);
      }
      if (a === "ajouter") {
        const nom = String((racine.querySelector("#md-nom") || {}).value || "").trim() || prov().defaut || "";
        const cle = String((racine.querySelector("#md-cle") || {}).value || "").trim();
        const base = String((racine.querySelector("#md-base") || {}).value || "").trim();
        if (!nom) { dire("Le nom du modèle est obligatoire.", "err"); return; }
        if (prov().cle === "requise" && !cle) { dire("Ce fournisseur demande une clé d’API.", "err"); return; }
        return faire(async () => {
          const r = await ajouterModele({ fournisseur: S.prov, nom, cle, base_url: base });
          S.form = { nom: "", cle: "", base: "" };
          const id = (r && (r.id || (r.modele && r.modele.id))) || "";
          if (id) { try { const e = await essayer(id); S.essais[id] = e.essai || e; } catch (e) { S.essais[id] = { ok: false, erreur: e.message }; } }
          return r;
        }, "Modèle ajouté : " + nom);
      }
    }

    racine.innerHTML = '<div class="attente">Lecture des modèles…</div>';
    await charger(true);
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l’écran et ses gestes.
// EC : néant.
// LIEN : modules/modeles (le module et ses capacités), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
