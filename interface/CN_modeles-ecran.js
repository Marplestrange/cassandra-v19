// ═════════════════════════════════════════════════════════════════
// TITRE      : Modèles : l’écran des modèles et des clés
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.2.0  #95e522
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine la page « Modèles & clés » : la santé du cerveau, le choix d’un modèle par agent, les modèles en ligne (clé d’API), les modèles locaux (Ollama) avec ce que la machine supporte, les autres moteurs d’IA, un comparateur et l’usage par modèle.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.modeles) et CASS.monterModeles, monté aussi dans Agents IA ; les rôles du moteur restent cachés : choisir un modèle pour un agent crée le rôle « agent_<id> » qui le relie ; une clé saisie n’est jamais relue.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.2.0 empreinte=95e522 ▼▼▼
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
    google: ["gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.1-pro"],
    groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"],
    anthropic: ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"],
    mistral: ["mistral-small-latest", "mistral-large-latest", "codestral-latest"],
    xai: ["grok-4", "grok-3-mini"],
    together: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
    fireworks: ["accounts/fireworks/models/llama-v3p3-70b-instruct"],
    cerebras: ["llama-3.3-70b", "qwen-3-32b"],
    nvidia: ["meta/llama-3.3-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"],
    sambanova: ["Meta-Llama-3.3-70B-Instruct"],
    deepinfra: ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
    moonshot: ["kimi-k2-0905-preview"],
    zai: ["glm-4.6"],
    alibaba: ["qwen-plus", "qwen-max", "qwen-turbo"],
    perplexity: ["sonar", "sonar-pro", "sonar-reasoning"],
    github: ["openai/gpt-4.1", "meta/Llama-3.3-70B-Instruct", "deepseek/DeepSeek-V3-0324"],
    cohere: ["command-a-03-2025", "command-r-plus-08-2024"],
    ollama: ["qwen2.5:3b", "qwen3:4b-instruct", "llama3.2:3b"],
  };
  const EX_CLE = { openai: "sk-…", deepseek: "sk-…", openrouter: "sk-or-…", google: "AIza…", groq: "gsk_…", anthropic: "sk-ant-…", xai: "xai-…", perplexity: "pplx-…", github: "github_pat_… (droit « models »)", mistral: "clé Mistral", cohere: "clé Cohere" };   // un EXEMPLE de forme, jamais une règle : aucune clé n’est refusée pour son préfixe
  const LIENS = { deepseek: "platform.deepseek.com", openrouter: "openrouter.ai/keys", openai: "platform.openai.com/api-keys", google: "aistudio.google.com/apikey", groq: "console.groq.com/keys", perplexity: "perplexity.ai/settings/api", github: "github.com/settings/personal-access-tokens", cohere: "dashboard.cohere.com/api-keys", anthropic: "console.anthropic.com/settings/keys", mistral: "console.mistral.ai/api-keys", xai: "console.x.ai", together: "api.together.ai/settings/api-keys", fireworks: "fireworks.ai/account/api-keys", cerebras: "cloud.cerebras.ai", nvidia: "build.nvidia.com", sambanova: "cloud.sambanova.ai/apis", deepinfra: "deepinfra.com/dash/api_keys", moonshot: "platform.moonshot.ai", zai: "z.ai/manage-apikey/apikey-list", alibaba: "modelstudio.console.alibabacloud.com" };
  const DEFAUTS = ["principal", "itare_citadelle"];                      // les rôles que prennent Cassandra, Amizo et Itare quand on ne leur en donne pas d’autre

  const CSS = ".md{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.md *{box-sizing:border-box}.md h1,.md h2,.md h3,.md p{margin:0}.md .mono{font-family:" + MONO + "}" +
    ".md .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:12px;min-width:0}" +
    ".md .carte.al{border-left:4px solid var(--danger);background:color-mix(in srgb,var(--danger) 7%,var(--surface))}" +
    ".md .note{color:var(--txt-soft);font-size:12.5px}" +
    ".md h2{font:650 16px 'Inter',system-ui,sans-serif}.md h3{font:650 12.5px 'Inter',system-ui,sans-serif;margin-top:4px}.md .acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.md .bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}" +
    ".md .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 13px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer}" +
    ".md .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.md .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.md .btn.pri:hover:not([disabled]){filter:brightness(1.08);color:var(--on-accent,#fff)}" +
    ".md .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.md .btn[disabled]{opacity:.45;cursor:not-allowed}.md .btn.mini{padding:4px 9px;font-size:11.5px}" +
    ".md .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;white-space:nowrap;border:1px solid var(--line)}.md .pastille::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}" +
    ".md .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)}.md .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}.md .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent)}.md .pastille.mu{color:var(--txt-soft)}" +
    ".md .sante{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:16px;overflow:hidden}.md .sante>div{background:var(--surface-solid,var(--surface));padding:12px 14px;display:flex;flex-direction:column;gap:4px}" +
    ".md .sante b{font:600 19px/1.1 " + MONO + ";font-variant-numeric:tabular-nums}.md .lib{font:600 10px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}" +
    ".md .rang{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1.4fr) auto;gap:8px 14px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}.md .rang .nom{font:600 13px " + MONO + ";overflow-wrap:anywhere}" +
    ".md .sc{overflow-x:auto}.md table{border-collapse:collapse;width:100%;font-size:13px}.md th{font:600 10px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:6px 10px 8px;white-space:nowrap}.md td{padding:9px 10px;border-top:1px solid var(--line);vertical-align:middle}.md td.n{font-family:" + MONO + ";font-variant-numeric:tabular-nums;white-space:nowrap}" +
    ".md .champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px 16px}.md label.ch{display:flex;flex-direction:column;gap:5px}.md label.ch b{font-weight:650;font-size:12.5px}" +
    ".md input[type=text],.md input[type=password],.md select{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:7px 10px;font:12.5px " + MONO + ";min-width:0;width:100%}" +
    ".md input:focus,.md select:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}" +
    ".md .puces{display:flex;gap:8px;flex-wrap:wrap}.md .puce{border:1px solid var(--line);border-radius:12px;padding:8px 12px;background:var(--surface-solid,transparent);display:flex;flex-direction:column;gap:4px;min-width:170px;max-width:240px}" +
    ".md .puce b{font:650 12.5px " + MONO + "}.md .barre{height:6px;border-radius:99px;background:var(--line);overflow:hidden}.md .barre i{display:block;height:100%;background:var(--accent)}.md .barre i.al{background:var(--warn)}" +
    ".md .etapes{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}.md .etape{border:1px solid var(--line);border-radius:13px;padding:13px 14px;background:var(--surface-solid,transparent);display:flex;flex-direction:column;gap:8px}" +
    ".md .rep{border:1px solid var(--line);border-radius:11px;padding:11px 13px;background:var(--surface-solid,transparent);min-height:90px;font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}" +
    ".md .attente{padding:30px;text-align:center;color:var(--txt-soft)}.md .confirme{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px}.md .err{color:var(--danger)}.md .g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}" +
    ".md .seg{display:inline-flex;border:1px solid var(--line);border-radius:11px;padding:3px;gap:2px;background:var(--surface-solid,transparent)}.md .seg button{border:0;background:transparent;color:var(--txt-soft);border-radius:8px;padding:6px 12px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer}.md .seg button[aria-selected=true]{background:var(--accent);color:var(--on-accent,#fff)}.md .seg .n{font:600 10.5px " + MONO + ";opacity:.75;margin-left:3px}" +
    ".md .filtre{border:1px solid var(--line);background:var(--surface-solid,transparent);color:var(--txt-soft);border-radius:999px;padding:4px 11px;font:600 11.5px 'Inter',system-ui,sans-serif;cursor:pointer}.md .filtre:hover{border-color:var(--accent);color:var(--accent)}.md .filtre.on{background:var(--accent);border-color:transparent;color:var(--on-accent,#fff)}" +
    ".md .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}.md .fichette{border:1px solid var(--line);border-radius:14px;padding:13px 14px;background:var(--surface-solid,transparent);display:flex;flex-direction:column;gap:7px;min-width:0}.md .fichette:hover{border-color:var(--accent)}.md .fichette .puces{gap:5px}" +
    ".md .fr{font-size:9px;letter-spacing:1px;color:var(--accent)}.md .fr i{font-style:normal;color:var(--line-strong,var(--line))}" +
    ".md .fiche-fond{position:fixed;inset:0;background:rgba(10,16,24,.38);z-index:60}.md .fiche{position:fixed;top:0;right:0;bottom:0;width:min(540px,100vw);z-index:61;background:var(--surface-solid,#fff);border-left:1px solid var(--line);box-shadow:-18px 0 40px rgba(10,16,24,.18);padding:22px 24px 28px;overflow-y:auto;display:flex;flex-direction:column;gap:12px}" +
    ".md .fiche h2{font-size:19px}.md .fiche h3{margin-top:8px}.md .fiche ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px}.md .fiche ul.plus li::marker{color:var(--ok)}.md .fiche ul.moins li::marker{color:var(--warn)}" +
    ".md .verdict{border-radius:12px;padding:11px 14px;display:flex;flex-direction:column;gap:3px;border:1px solid var(--line)}.md .verdict.ok{background:color-mix(in srgb,var(--ok) 11%,transparent);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}.md .verdict.al{background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:color-mix(in srgb,var(--warn) 32%,transparent)}.md .verdict.dg{background:color-mix(in srgb,var(--danger) 10%,transparent);border-color:color-mix(in srgb,var(--danger) 30%,transparent)}.md .verdict b{font:650 11px " + MONO + ";text-transform:uppercase;letter-spacing:.07em}" +
    ".md .kvs{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden}.md .kv{background:var(--surface-solid,#fff);padding:8px 12px;display:flex;flex-direction:column;gap:1px}.md .kv span{font:600 10px " + MONO + ";text-transform:uppercase;letter-spacing:.07em;color:var(--txt-faint)}.md .kv b{font-weight:600;font-size:13px}.md .sel{user-select:all;background:var(--line);padding:6px 10px;border-radius:8px;overflow-wrap:anywhere}" +
    ".sh-scene:has(>.sh-corps>.md)>.sh-titre{display:none}@media (max-width:820px){.md .rang{grid-template-columns:minmax(0,1fr) auto}.md .rang .m{grid-column:1 / -1}}";

  const octets = (n) => n >= 1e9 ? (n / 1e9).toFixed(1).replace(".", ",") + " Go" : n >= 1e6 ? Math.round(n / 1e6) + " Mo" : n > 0 ? Math.round(n / 1e3) + " Ko" : "—";
  const go = (n) => String(n).replace(".", ",") + " Go";
  const entier = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

  async function monter(corps) {
    const anc = document.getElementById("md-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "md-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "md"; corps.appendChild(racine);

    const S = { l: null, f: [], loc: null, mo: null, us: null, eq: [], cv: null, ep: [], occupe: false, erreur: "", prov: "", retirer: "", suppr: "", essais: {}, dispo: {}, form: { nom: "", base: "" }, mini: "", cat: { onglet: "local", q: "", filtre: "tous" }, fiche: null, cmp: { a: "", b: "", q: "Pourquoi le disque de cette machine a-t-il autant d’espace libre ?", ra: "", rb: "" } };
    let minuterie = null;
    const vivant = () => document.body.contains(racine);

    async function charger(tout) {
      try {
        const [l, f, loc, cv] = await Promise.all([agir("modeles.lister"), S.f.length && !tout ? Promise.resolve({ fournisseurs: S.f }) : agir("modeles.fournisseurs"),
          agir("modeles.locaux").catch((e) => ({ repond: false, raison: e.message, modeles: [], telechargements: [] })), agir("agents.cerveau").catch(() => null)]);
        S.l = l; S.f = f.fournisseurs || []; S.loc = loc; S.cv = cv; S.erreur = "";
        if (!S.prov && S.f.length) S.prov = S.f[0].id;
      } catch (e) { S.erreur = e.message || String(e); }
      dessiner(); armer();
      // ce qui se lit lentement arrive ensuite : la page est déjà là
      const apres = (cap, cle, args) => agir(cap, args).then((r) => { S[cle] = r; if (vivant()) dessiner(); }).catch(() => {});
      apres("modeles.moteurs", "mo"); apres("modeles.usage", "us", { jours: 14 });
      agir("agents.equipe").then((r) => { S.eq = r.equipe || []; if (vivant()) dessiner(); }).catch(() => {});
      agir("agents.epreuves_resultats").then((r) => { S.ep = r.resultats || []; if (vivant()) dessiner(); }).catch(() => {});
    }
    function armer() {
      if (minuterie) { clearTimeout(minuterie); minuterie = null; }
      const actifs = S.loc && (S.loc.telechargements || []).some((p) => p.etat === "attente" || p.etat === "en cours");
      if (actifs && vivant()) minuterie = setTimeout(() => { if (vivant() && !S.occupe) charger(); }, 3000);
    }
    const faire = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; dessiner();
      try { const r = await f(); if (ok) dire(typeof ok === "function" ? ok(r) : ok); } catch (e) { dire(e.message || String(e), "err"); }
      finally { S.occupe = false; S.retirer = ""; S.suppr = ""; window.dispatchEvent(new Event("cassandra:agents-change")); await charger(); }
    };
    // L’administrateur déclare pour l’instance ; un compte ordinaire pour lui seul.
    const droit = (e) => /droit|autoris/i.test((e && e.message) || "");
    const ajouterModele = async (a) => { try { return await agir("modeles.instance_ajouter", a); } catch (e) { if (droit(e)) return agir("modeles.ajouter", a); throw e; } };
    const essayer = async (id) => { try { return await agir("modeles.instance_essayer", { id }); } catch (e) { if (droit(e)) return agir("modeles.essayer", { id }); throw e; } };
    const decouvrir = (a) => agir("modeles.decouvrir", a);
    const retirerModele = async (id) => { try { return await agir("modeles.instance_retirer", { id }); } catch (e) { if (droit(e)) return agir("modeles.retirer", { id }); throw e; } };
    // Un choix par agent : le moteur ne connaît que des rôles, on crée donc le rôle de cet agent et on le lie.
    async function choisirPourAgent(agent, champ, modeleId) {
      const role = (champ === "secours" ? "secours_" : "agent_") + agent;
      if (!modeleId) { await agir("agents.agent_regler", { id: agent, champs: { [champ]: "" } }); try { await agir("modeles.role_lier", { role, modele_id: "" }); } catch (e) { /* pas de rôle à délier */ } return; }
      await agir("modeles.role_lier", { role, modele_id: modeleId });
      await agir("agents.agent_regler", { id: agent, champs: { [champ]: role } });
    }
    // Un modèle local sur processeur lit lentement : avec les 60 outils décrits à chaque tour, un tour de Cassandra dépasse 2 minutes (mesuré sur Argos : 52 s avec 12 outils).
    // Les autres outils restent trouvables par « outil_cherche » : on en présente 12 d'emblée.
    const lierDefauts = async (modeleId, local) => {
      for (const r of DEFAUTS) await agir("modeles.role_lier", { role: r, modele_id: modeleId });
      if (local) await agir("reglages.regler", { cle: "agents.max_outils", valeur: 12 });
    };

    const declares = () => (S.l.modeles || []);
    const enLigne = () => declares().filter((m) => m.en_ligne);
    const locauxDecl = () => declares().filter((m) => !m.en_ligne);
    const prov = () => S.f.find((x) => x.id === S.prov) || {};
    const nomProv = (id) => (S.f.find((x) => x.id === id) || {}).nom || id;
    const eqDe = (id) => S.eq.find((a) => a.id === id) || {};
    const essaiDe = (m) => S.essais[m.id] || m.essai;
    function pastilleEssai(m) {
      const e = essaiDe(m);
      return e ? (e.ok ? '<span class="pastille ok">a répondu en ' + esc(e.secondes) + " s</span>" : '<span class="pastille dg" title="' + esc(e.message || e.erreur) + '">a échoué</span>') : '<span class="pastille mu">pas encore essayé</span>';
    }
    function epreuves(m) {
      const noms = [m.id].concat(m.roles || []), r = (S.ep || []).find((x) => noms.indexOf(x.modele) >= 0);
      return r ? ' <span class="pastille ' + (r.ok ? "ok" : "al") + '" title="Épreuves de sûreté">épreuves ' + r.reussies + "/" + r.total + "</span>" : "";
    }

    // ── la santé du cerveau ─────────────────────────────────────────────────
    function carteSante() {
      const cv = S.cv, ms = declares();
      if (cv && cv.sans && cv.sans.length) {
        const sans = cv.sans.join(", ");
        if (!ms.length) {
          const inst = (S.loc && S.loc.modeles) || [];
          return '<div class="carte al"><div class="bar"><div><h2>Cassandra ne peut pas penser pour l’instant</h2><p class="note">Aucun modèle n’est déclaré : ' + esc(sans) + ' répondent « aucun modèle ». Choisis un cerveau, deux minutes.</p></div><span class="pastille dg">0 agent sur ' + cv.total + " répond</span></div>" +
            '<div class="etapes"><div class="etape"><span class="lib">Sur la machine</span><b>Gratuit et privé</b>' +
            (inst.length ? '<p class="note">Ollama a déjà ' + (inst.length > 1 ? "des modèles installés" : "un modèle installé") + " : " + inst.map((m) => esc(m.name)).join(", ") + ".</p>" + inst.slice(0, 3).map((m) => '<button class="btn pri" data-a="brancher-local" data-n="' + esc(m.name) + '"' + (S.occupe ? " disabled" : "") + ">Utiliser " + esc(m.name) + " pour tous les agents</button>").join("") + '<p class="note">Sur processeur, un modèle local lit lentement : on présente alors 12 outils aux agents au lieu de 60 (les autres se trouvent à la demande), sinon un tour dépasse deux minutes.</p>'
              : '<p class="note">Aucun modèle installé. Le plus léger qui parle bien français pèse 1,9 Go.</p><button class="btn pri" data-a="installer" data-n="qwen2.5:3b"' + (S.occupe || !(S.loc || {}).repond ? " disabled" : "") + ">Installer qwen2.5:3b</button>") + "</div>" +
            '<div class="etape"><span class="lib">Chez un fournisseur</span><b>Plus fin, payant à l’usage</b><p class="note">Il faut une clé d’API. Le formulaire est juste en dessous : fournisseur, modèle, clé.</p><button class="btn" data-a="vers-ajout">Ajouter une clé</button></div></div></div>';
        }
        return '<div class="carte al"><div class="bar"><div><h2>' + esc(sans) + (cv.sans.length > 1 ? " ne peuvent pas répondre" : " ne peut pas répondre") + '</h2><p class="note">Un modèle est déclaré, mais ces agents n’y sont reliés par aucun rôle. Un clic suffit.</p></div><span class="pastille dg">' + cv.repondent + " agent(s) sur " + cv.total + " répondent</span></div>" +
          '<div class="acts"><select id="md-tout" style="width:auto;flex:1 1 220px">' + ms.map((m) => '<option value="' + esc(m.id) + '">' + esc(m.nom) + " (" + esc(nomProv(m.fournisseur)) + ")</option>").join("") + '</select><button class="btn pri" data-a="lier-defauts"' + (S.occupe ? " disabled" : "") + ">Relier Cassandra, Amizo et Itare à ce modèle</button></div></div>";
      }
      const us = S.us, lignes = (us && us.lignes) || [], aujourdhui = new Date().toISOString().slice(0, 10), jour = lignes.filter((x) => x.jour === aujourdhui);
      const appels = jour.reduce((n, x) => n + x.appels, 0), echecs = jour.reduce((n, x) => n + x.echecs, 0), secondes = jour.reduce((n, x) => n + x.secondes, 0);
      const locaux = new Set(locauxDecl().map((m) => m.id)), appelsLocaux = jour.filter((x) => locaux.has(x.modele_id)).reduce((n, x) => n + x.appels, 0);
      const cout = S.eq.reduce((n, a) => n + ((a.cout_jour || {}).euros || 0), 0);
      return '<div class="sante"><div><span class="lib">Agents qui répondent</span><b>' + (cv ? cv.repondent + " / " + cv.total : "…") + '</b><span class="pastille ok">tous reliés</span></div>' +
        '<div><span class="lib">Appels aujourd’hui</span><b>' + (us ? entier(appels) : "…") + '</b><span class="note">' + (us ? echecs + " échec(s)" + (appels ? " · " + (secondes / appels).toFixed(1).replace(".", ",") + " s en moyenne" : "") : "") + "</span></div>" +
        '<div><span class="lib">Coût du jour</span><b>' + (S.eq.length ? cout.toFixed(2).replace(".", ",") + " €" : "…") + '</b><span class="note">détail dans chaque fiche, onglet Coût</span></div>' +
        '<div><span class="lib">Resté sur la machine</span><b>' + (us && appels ? Math.round(100 * appelsLocaux / appels) + " %" : "—") + '</b><span class="note">des appels du jour</span></div></div>';
    }

    // ── un choix par agent ──────────────────────────────────────────────────
    function options(courant, vide) {
      return '<option value="">' + esc(vide) + "</option>" + declares().map((m) => '<option value="' + esc(m.id) + '"' + (m.id === courant ? " selected" : "") + ">" + esc(m.nom) + " (" + esc(nomProv(m.fournisseur)) + ")</option>").join("");
    }
    function carteAgents() {
      const cv = S.cv; if (!cv) return "";
      const rows = cv.agents.map((a) => {
        const e = eqDe(a.id), perso = a.chaine.length && /^(agent_|secours_)/.test(a.chaine[0]) ? a.modele_id : "", secours = a.chaine.length > 1 ? (declares().find((m) => m.nom === a.secours) || {}).id || "" : "";
        const defaut = a.modele ? "par défaut : " + a.modele : "— aucun —";
        const sante = a.peut === false ? '<span class="pastille dg" title="' + esc(a.raison) + '">ne répondra pas</span>' : a.peut === null ? '<span class="pastille mu" title="' + esc(a.raison) + '">règles internes</span>' : (a.essai ? (a.essai.ok ? '<span class="pastille ok">' + esc(a.essai.secondes) + " s</span>" : '<span class="pastille dg">dernier essai raté</span>') : '<span class="pastille mu">pas essayé</span>');
        const sort = a.peut ? '<span class="pastille ' + (a.en_ligne ? "al" : "mu") + '">' + (a.en_ligne ? "part chez un fournisseur" : "reste ici") + "</span>" : '<span class="pastille mu">—</span>';
        return "<tr><td><b>" + esc(a.nom) + '</b><br><span class="note">' + (a.genre === "agent" ? "agent" : "service agentique") + (e.niveau ? " · " + esc(e.niveau) : "") + '</span></td><td><select data-ag="' + esc(a.id) + '" data-champ="modele" aria-label="Modèle de ' + esc(a.nom) + '">' + options(perso, defaut) + '</select></td><td><select data-ag="' + esc(a.id) + '" data-champ="secours" aria-label="Secours de ' + esc(a.nom) + '">' + options(secours, "— aucun —") + "</select></td><td>" + sante + "</td><td>" + sort + '</td><td class="n">' + (e.cout_jour ? e.cout_jour.euros.toFixed(2).replace(".", ",") + " €" : "—") + '</td><td><button class="btn mini" data-a="essayer" data-id="' + esc(a.modele_id) + '"' + (!a.modele_id || S.occupe ? " disabled" : "") + ">Essayer</button></td></tr>";
      }).join("");
      return '<div class="carte"><div class="bar"><h2>Qui pense avec quoi</h2></div><div class="sc"><table><thead><tr><th>Agent</th><th>Modèle</th><th>Secours</th><th>Santé</th><th>Ce qui sort</th><th>Coût du jour</th><th></th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
        '<p class="note">Vide : l’agent prend le modèle par défaut de la maison. Un choix ici est propre à cet agent. Les services agentiques ont des règles internes : un modèle leur est facultatif.</p></div>';
    }

    // ── en ligne et local ──────────────────────────────────────────────────
    function ligneModele(m) {
      return '<div class="rang"><div><span class="nom">' + esc(m.nom) + '</span><br><span class="note">' + esc(nomProv(m.fournisseur)) + (m.base_url ? " · " + esc(m.base_url) : "") + "</span></div>" +
        '<div class="m">' + (m.a_cle ? '<span class="pastille ok">clé enregistrée</span> ' : '<span class="pastille mu">sans clé</span> ') + pastilleEssai(m) + epreuves(m) + "</div>" +
        '<div class="acts"><button class="btn mini" data-a="essayer" data-id="' + esc(m.id) + '"' + (S.occupe ? " disabled" : "") + ">Essayer</button>" +
        (S.retirer === m.id ? '<span class="confirme">Retirer ? <button class="btn mini dng" data-a="retirer-oui" data-id="' + esc(m.id) + '">Oui</button><button class="btn mini" data-a="retirer-non">Non</button></span>' : '<button class="btn mini dng" data-a="retirer" data-id="' + esc(m.id) + '">Retirer</button>') + "</div></div>";
    }
    function carteLigne() {
      const l = enLigne();
      return '<div class="carte"><h2>Modèles en ligne</h2>' + (l.length ? l.map(ligneModele).join("") : '<p class="note">Aucun modèle en ligne déclaré. Ajoute-en un ci-dessous : fournisseur, nom du modèle, clé d’API.</p>') + "</div>";
    }
    function carteAjout() {
      const p = prov(), sug = S.dispo[S.prov] || SUGGEST[S.prov] || [], besoin = p.cle !== "aucune", perso = S.prov === "personnalise" || S.prov === "omniroute";
      return '<div class="carte" id="md-ajout"><h2>Ajouter un modèle</h2><p class="note">La clé est chiffrée dans le coffre du noyau dès l’envoi ; elle n’est jamais relue ni réaffichée, ni écrite dans le journal.</p>' +
        '<div class="champs"><label class="ch"><b>Fournisseur</b><select id="md-prov">' + S.f.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === S.prov ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + "</select>" +
        (LIENS[S.prov] ? '<span class="note">Créer une clé : ' + esc(LIENS[S.prov]) + "</span>" : "") + "</label>" +
        '<label class="ch"><b>Nom du modèle</b><input type="text" id="md-nom" list="md-sug" value="' + esc(S.form.nom) + '" placeholder="' + esc(p.defaut || "nom du modèle") + '" autocomplete="off" spellcheck="false"><datalist id="md-sug">' + sug.map((x) => '<option value="' + esc(x) + '">').join("") + "</datalist><span class=\"note\">Vide : " + esc(p.defaut || "à saisir") + (S.dispo[S.prov] ? " · " + S.dispo[S.prov].length + " modèles listés par le fournisseur" : "") + '</span><button type="button" class="btn mini" data-a="decouvrir"' + (S.occupe ? " disabled" : "") + '>Lister ceux du fournisseur</button></label>' +
        (besoin ? '<label class="ch"><b>Clé d’API' + (p.cle === "optionnelle" ? " (facultative)" : "") + '</b><input type="password" id="md-cle" value="' + esc(S.form.cle || "") + '" placeholder="' + esc(EX_CLE[S.prov] || "clé d’API") + '" autocomplete="off" spellcheck="false"></label>' : "") +
        (perso ? '<label class="ch"><b>Adresse de l’API</b><input type="text" id="md-base" value="' + esc(S.form.base) + '" placeholder="' + (S.prov === "omniroute" ? "http://adresse-ou-ip:20128 ou https://passerelle.exemple.fr" : "https://… ou http://127.0.0.1:8000/v1") + '" autocomplete="off" spellcheck="false"></label>' : "") + "</div>" +
        '<div class="acts"><button class="btn pri" data-a="ajouter"' + (S.occupe ? " disabled" : "") + ">" + (S.occupe ? "Un instant…" : "Ajouter et essayer") + "</button></div></div>";
    }
    function ajustement(taille, total) {      // ce que la machine supporte : le modèle, son contexte, et de quoi laisser vivre le reste
      if (!total) return null;
      const besoin = taille * 1.25 + 0.5, t = total / 1e9;
      return besoin <= t * 0.5 ? ["ok", "tient"] : besoin <= t * 0.8 ? ["al", "juste, ralentit le reste"] : ["dg", "trop lourd"];
    }
    function carteLocale() {
      const loc = S.loc || {}, inst = loc.modeles || [], dm = {}, decl = new Set(locauxDecl().map((m) => { dm[m.nom] = m; return m.nom; })), pulls = (loc.telechargements || []).filter((p) => p.etat === "attente" || p.etat === "en cours");
      const noms = new Set(inst.map((m) => m.name)), total = S.mo && S.mo.machine ? S.mo.machine.total : 0, dispo = S.mo && S.mo.machine ? S.mo.machine.disponible : 0;
      let h = '<div class="carte"><div class="bar"><h2>Modèles sur cette machine (Ollama)</h2>' + (loc.repond ? '<span class="pastille ok">Ollama répond</span>' : '<span class="pastille dg" title="' + esc(loc.raison || "") + '">Ollama ne répond pas</span>') + "</div>";
      if (total) h += '<div><div class="bar note"><span class="mono">Mémoire de la machine : ' + go((total / 1e9).toFixed(1)) + "</span>" + (dispo ? "<span>" + go((dispo / 1e9).toFixed(1)) + " disponibles</span>" : "") + '</div>' + (dispo ? '<div class="barre" style="margin-top:6px"><i class="' + (dispo / total < 0.15 ? "al" : "") + '" style="width:' + Math.round(100 * (1 - dispo / total)) + '%"></i></div>' : "") + "</div>";
      if (!loc.repond) h += '<p class="note err">' + esc(loc.raison || "Ollama est arrêté") + ' — sur la machine : <span class="mono">systemctl start ollama</span> (ou relancer l’installateur avec WITH_OLLAMA=1).</p>';
      h += inst.length ? inst.map((m) => '<div class="rang"><div><span class="nom">' + esc(m.name) + '</span><br><span class="note">' + octets(m.taille) + " sur le disque</span></div><div class=\"m\">" + (decl.has(m.name) ? '<span class="pastille ok">déclaré</span> ' + pastilleEssai(dm[m.name]) + epreuves(dm[m.name]) : '<span class="pastille mu">installé, pas déclaré</span>') + '</div><div class="acts">' +
        (decl.has(m.name) ? '<button class="btn mini" data-a="essayer" data-id="' + esc(dm[m.name].id) + '"' + (S.occupe ? " disabled" : "") + ">Essayer</button>" : '<button class="btn mini pri" data-a="declarer" data-n="' + esc(m.name) + '"' + (S.occupe ? " disabled" : "") + ">Utiliser</button>") +
        (S.suppr === m.name ? '<span class="confirme">Supprimer ? <button class="btn mini dng" data-a="suppr-oui" data-n="' + esc(m.name) + '">Oui</button><button class="btn mini" data-a="suppr-non">Non</button></span>' : '<button class="btn mini dng" data-a="suppr" data-n="' + esc(m.name) + '">Supprimer</button>') + "</div></div>").join("")
        : (loc.repond ? '<p class="note">Aucun modèle installé.</p>' : "");
      if (pulls.length) h += "<h3>Téléchargements en cours</h3>" + pulls.map((p) => '<div><span class="mono">' + esc(p.nom) + '</span> <span class="note">' + esc(p.detail || p.etat) + '</span><div class="barre"><i style="width:' + Math.max(3, Math.min(100, p.pourcent || 3)) + '%"></i></div></div>').join("");
      return h + "</div>";
    }


    // ── le catalogue : des fiches ───────────────────────────────────────────
    const CATA = () => window.CASS_CATALOGUE_MODELES || { local: [], enligne: [] };
    const FILTRES = {
      local: [["tous", "Tous"], ["agents", "Pour les agents"], ["fr", "Bon français"], ["leger", "Légers"], ["tient", "Tiennent ici"], ["raisonne", "Raisonnement"], ["code", "Code"], ["vision", "Images"], ["gros", "Gros"]],
      enligne: [["tous", "Tous"], ["agents", "Pour les agents"], ["eco", "Économiques"], ["vision", "Images"], ["raisonne", "Raisonnement"], ["long", "Long contexte"]],
    };
    const installe = (nom) => { const n = ((S.loc || {}).modeles || []).map((m) => m.name); return n.indexOf(nom) >= 0 || n.indexOf(nom + ":latest") >= 0; };
    const besoin = (go) => Math.round((go * 1.25 + 0.5) * 10) / 10;
    function vitesse(go) { return go <= 2.5 ? ["ok", "rapide", "de l’ordre de la minute par tour d’agent sur processeur"] : go <= 5.5 ? ["al", "moyen", "plusieurs minutes par tour d’agent sur processeur"] : ["dg", "lent", "au-delà du délai d’un tour (2 min) sur processeur : réservé à une carte graphique"]; }
    function verdictLocal(m, total) {
      if (m.embed) return ["mu", "Ne converse pas : il sert à la recherche par le sens, pas aux agents."];
      if (!m.outils) return ["dg", "Ne convient pas à un agent : il ne sait pas appeler d’outils. Il peut lire ou rédiger, pas agir."];
      const aj = ajustement(m.go, total);
      if (aj && aj[0] === "dg") return ["dg", "Trop lourd pour cette machine (" + go((total / 1e9).toFixed(1)) + " de mémoire, il en faut environ " + go(besoin(m.go)) + ")."];
      const v = vitesse(m.go);
      if (v[0] === "dg") return ["dg", "Appelle des outils, mais " + v[2] + "."];
      if (aj && aj[0] === "al") return ["al", "Appelle des outils, mais la mémoire sera juste : le reste de la machine ralentira."];
      return v[0] === "al" ? ["al", "Appelle des outils ; " + v[2] + "."] : ["ok", "Convient à un agent ; " + v[2] + "."];
    }
    function passe(m, f, total, enligne) {
      if (f === "tous") return true;
      if (enligne) return f === "agents" ? m.outils : f === "eco" ? m.prix === "€" : f === "vision" ? m.vision : f === "raisonne" ? m.raisonne : f === "long" ? m.ctx >= 1000 : true;
      if (f === "agents") return m.outils;
      if (f === "fr") return m.fr >= 3;
      if (f === "leger") return m.go <= 3;
      if (f === "tient") { const a = ajustement(m.go, total); return !!a && a[0] === "ok"; }
      if (f === "raisonne") return m.raisonne;
      if (f === "code") return m.code;
      if (f === "vision") return m.vision;
      if (f === "gros") return m.go >= 8;
      return true;
    }
    const pointsFr = (n) => '<span class="fr" title="Appréciation du français : ' + n + ' sur 3">' + "●".repeat(n) + '<i>' + "●".repeat(3 - n) + "</i></span>";
    function carteLocaleCatalogue(m, total) {
      const ok = installe(m.nom), aj = ajustement(m.go, total), v = vitesse(m.go);
      return '<div class="fichette"><div class="bar"><b class="mono">' + esc(m.nom) + '</b>' + (ok ? '<span class="pastille ok">installé</span>' : "") + '</div><span class="note">' + esc(m.famille) + " · " + esc(m.editeur) + " · " + esc(m.params) + " · " + go(m.go) + (m.ctx ? " · " + m.ctx + " k" : "") + "</span>" +
        '<div class="puces">' + (m.embed ? '<span class="pastille mu">recherche</span>' : m.outils ? '<span class="pastille ok">outils</span>' : '<span class="pastille dg">sans outils</span>') + (m.vision ? '<span class="pastille mu">images</span>' : "") + (m.raisonne ? '<span class="pastille mu">raisonne</span>' : "") + (m.code ? '<span class="pastille mu">code</span>' : "") + (aj ? '<span class="pastille ' + aj[0] + '">' + aj[1] + "</span>" : "") + (m.embed || !m.outils ? "" : '<span class="pastille ' + v[0] + '" title="' + esc(v[2]) + '">' + v[1] + "</span>") + "</div>" +
        '<p class="note" style="min-height:2.6em">' + esc(m.desc) + '</p><div class="bar"><span class="note">FR ' + pointsFr(m.fr) + '</span><div class="acts"><button class="btn mini" data-a="fiche" data-k="local" data-n="' + esc(m.nom) + '">Fiche</button>' +
        (ok ? "" : '<button class="btn mini pri" data-a="installer" data-n="' + esc(m.nom) + '"' + (S.occupe || !(S.loc || {}).repond || (aj && aj[0] === "dg") ? " disabled" : "") + ">Installer</button>") + "</div></div></div>";
    }
    function carteEnLigneCatalogue(m) {
      const deja = declares().some((x) => x.nom === m.nom && x.fournisseur === m.fournisseur);
      return '<div class="fichette"><div class="bar"><b class="mono">' + esc(m.nom) + '</b>' + (deja ? '<span class="pastille ok">déclaré</span>' : "") + '</div><span class="note">' + esc(nomProv(m.fournisseur)) + " · " + (m.ctx >= 1000 ? Math.round(m.ctx / 1000) + " M" : m.ctx + " k") + " de contexte · " + m.prix + "</span>" +
        '<div class="puces">' + (m.outils ? '<span class="pastille ok">outils</span>' : '<span class="pastille dg">outils peu fiables</span>') + (m.vision ? '<span class="pastille mu">images</span>' : "") + (m.raisonne ? '<span class="pastille mu">raisonne</span>' : "") + '<span class="pastille al" title="Ce modèle est chez un fournisseur : tes données y partent">en ligne</span></div>' +
        '<p class="note" style="min-height:2.6em">' + esc(m.desc) + '</p><div class="bar"><span class="note">FR ' + pointsFr(m.fr) + '</span><div class="acts"><button class="btn mini" data-a="fiche" data-k="enligne" data-n="' + esc(m.fournisseur + "|" + m.nom) + '">Fiche</button><button class="btn mini pri" data-a="ajouter-ce" data-p="' + esc(m.fournisseur) + '" data-n="' + esc(m.nom) + '">Ajouter</button></div></div></div>';
    }
    function carteCatalogue() {
      const cat = CATA(), c = S.cat, total = S.mo && S.mo.machine ? S.mo.machine.total : 0, enl = c.onglet === "enligne", q = c.q.trim().toLowerCase();
      const liste = (enl ? cat.enligne : cat.local).filter((m) => passe(m, c.filtre, total, enl) && (!q || (m.nom + " " + (m.famille || "") + " " + (m.fournisseur || "") + " " + (m.editeur || "") + " " + m.desc).toLowerCase().indexOf(q) >= 0));
      const loc = S.loc || {};
      return '<div class="carte"><div class="bar"><div><h2>Catalogue des modèles</h2><p class="note">' + (enl ? "Les modèles des fournisseurs : tes données partent chez eux, l’appel se paie." : "Ceux qu’Ollama installe sur la machine : gratuits, privés, mais limités par la mémoire et le processeur.") + '</p></div>' +
        '<div class="seg" role="tablist"><button role="tab" aria-selected="' + !enl + '" data-a="cat-onglet" data-o="local">Sur la machine <span class="n">' + cat.local.length + '</span></button><button role="tab" aria-selected="' + enl + '" data-a="cat-onglet" data-o="enligne">En ligne <span class="n">' + cat.enligne.length + "</span></button></div></div>" +
        '<div class="acts"><input type="text" id="md-cat-q" value="' + esc(c.q) + '" placeholder="Chercher un modèle, une famille, un éditeur…" aria-label="Chercher dans le catalogue" style="flex:1 1 240px;width:auto" autocomplete="off" spellcheck="false"></div>' +
        '<div class="puces">' + FILTRES[enl ? "enligne" : "local"].map((f) => '<button class="filtre' + (c.filtre === f[0] ? " on" : "") + '" data-a="cat-filtre" data-f="' + f[0] + '">' + f[1] + "</button>").join("") + "</div>" +
        '<p class="note">' + liste.length + " modèle(s)" + (!enl && !total ? " · la mémoire de la machine se lit : les indications « tient » arrivent dans un instant" : "") + (!enl ? ' · <span class="mono">outils</span> = sait appeler des outils, indispensable pour un agent' : "") + "</p>" +
        (liste.length ? '<div class="grille">' + liste.map((m) => (enl ? carteEnLigneCatalogue(m) : carteLocaleCatalogue(m, total))).join("") + "</div>" : '<div class="attente">Aucun modèle ne correspond. Essaie un autre filtre.</div>') +
        (enl ? "" : '<div class="acts" style="margin-top:4px"><input type="text" id="md-pull" value="' + esc(S.mini) + '" placeholder="un autre nom du catalogue ollama.com/library, ex. llama3.1:8b" style="flex:1 1 280px;width:auto" autocomplete="off" spellcheck="false" aria-label="Un autre modèle Ollama"><button class="btn" data-a="installer-libre"' + (S.occupe || !loc.repond ? " disabled" : "") + ">Installer</button></div>") + "</div>";
    }
    function ficheHtml() {
      const f = S.fiche; if (!f) return "";
      const cat = CATA(), total = S.mo && S.mo.machine ? S.mo.machine.total : 0;
      const ligne = (k, v) => '<div class="kv"><span>' + k + "</span><b>" + v + "</b></div>";
      const liste = (t, a, cls) => a && a.length ? "<h3>" + t + '</h3><ul class="' + cls + '">' + a.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>" : "";
      let h;
      if (f.k === "local") {
        const m = cat.local.find((x) => x.nom === f.n); if (!m) return "";
        const v = verdictLocal(m, total), ok = installe(m.nom), aj = ajustement(m.go, total);
        h = '<div class="bar"><div><span class="lib">' + esc(m.famille) + " · " + esc(m.editeur) + '</span><h2 class="mono">' + esc(m.nom) + '</h2></div><button class="btn mini" data-a="fiche-fermer" aria-label="Fermer la fiche">Fermer</button></div>' +
          '<p>' + esc(m.desc) + '</p><div class="verdict ' + v[0] + '"><b>Pour tes agents</b><span>' + esc(v[1]) + "</span></div>" +
          '<div class="kvs">' + ligne("Paramètres", esc(m.params)) + ligne("Taille sur le disque", go(m.go)) + ligne("Mémoire vive conseillée", m.embed ? "faible" : "environ " + go(besoin(m.go))) + ligne("Contexte maximal", m.ctx ? m.ctx + " k jetons" : "—") + ligne("Licence", esc(m.licence)) + ligne("Français", pointsFr(m.fr) + " (appréciation)") +
          ligne("Appels d’outils", m.outils ? "oui" : "non") + ligne("Images", m.vision ? "oui" : "non") + ligne("Raisonnement", m.raisonne ? "oui" : "non") + (total ? ligne("Sur cette machine", aj ? aj[1] : "—") : "") + "</div>" +
          liste("Ses forces", m.forces, "plus") + liste("Ses limites", m.limites, "moins") + (m.usage ? "<h3>À qui il convient</h3><p>" + esc(m.usage) + "</p>" : "") +
          '<h3>En ligne de commande</h3><p class="mono sel">ollama pull ' + esc(m.nom) + "</p>" +
          '<div class="acts">' + (ok ? '<button class="btn pri" data-a="brancher-local" data-n="' + esc(m.nom) + '"' + (S.occupe || !m.outils ? " disabled" : "") + ">Utiliser pour tous les agents</button>" + (m.outils ? "" : '<span class="note">Sans outils, il ne peut pas servir d’agent.</span>') : '<button class="btn pri" data-a="installer" data-n="' + esc(m.nom) + '"' + (S.occupe || !(S.loc || {}).repond || (aj && aj[0] === "dg") ? " disabled" : "") + ">Installer (" + go(m.go) + ")</button><span class=\"note\">Une fois installé, reviens ici : « Utiliser pour tous les agents ».</span>") + "</div>";
      } else {
        const [fo, no] = f.n.split("|"), m = cat.enligne.find((x) => x.fournisseur === fo && x.nom === no); if (!m) return "";
        h = '<div class="bar"><div><span class="lib">' + esc(nomProv(m.fournisseur)) + '</span><h2 class="mono">' + esc(m.nom) + '</h2></div><button class="btn mini" data-a="fiche-fermer" aria-label="Fermer la fiche">Fermer</button></div>' +
          "<p>" + esc(m.desc) + '</p><div class="verdict ' + (m.outils ? "al" : "dg") + '"><b>Pour tes agents</b><span>' + (m.outils ? "Appelle des outils. Chaque échange part chez le fournisseur et se paie : le coût du jour le montre." : "Ses appels d’outils ne sont pas fiables : à éviter pour un agent.") + "</span></div>" +
          '<div class="kvs">' + ligne("Fournisseur", esc(nomProv(m.fournisseur))) + ligne("Contexte", (m.ctx >= 1000 ? Math.round(m.ctx / 1000) + " M" : m.ctx + " k") + " jetons") + ligne("Prix (ordre de grandeur)", m.prix + " — à vérifier chez le fournisseur") + ligne("Français", pointsFr(m.fr) + " (appréciation)") +
          ligne("Appels d’outils", m.outils ? "oui" : "peu fiables") + ligne("Images", m.vision ? "oui" : "non") + ligne("Raisonnement", m.raisonne ? "oui" : "non") + ligne("Données", "partent chez le fournisseur") + "</div>" +
          liste("Ses forces", m.forces, "plus") + liste("Ses limites", m.limites, "moins") + (m.usage ? "<h3>À qui il convient</h3><p>" + esc(m.usage) + "</p>" : "") +
          (LIENS[m.fournisseur] ? '<h3>Clé d’API</h3><p class="mono sel">' + esc(LIENS[m.fournisseur]) + "</p>" : "") +
          '<div class="acts"><button class="btn pri" data-a="ajouter-ce" data-p="' + esc(m.fournisseur) + '" data-n="' + esc(m.nom) + '">Ajouter ce modèle</button><span class="note">Le formulaire s’ouvre prérempli : il reste à coller ta clé.</span></div>';
      }
      return '<div class="fiche-fond" data-a="fiche-fermer"></div><aside class="fiche" role="dialog" aria-label="Fiche du modèle">' + h + "</aside>";
    }

    // ── les autres moteurs d’IA ─────────────────────────────────────────────
    function carteMoteurs() {
      const mo = S.mo; if (!mo) return '<div class="carte"><h2>Les autres moteurs d’IA de la machine</h2><div class="attente">Lecture…</div></div>';
      const ms = declares().filter((m) => m.portee === "instance");
      const rows = mo.moteurs.map((x) => '<tr><td><b class="mono">' + esc(x.nom) + "</b></td><td>" + esc(x.role) + '</td><td><span class="pastille ' + (x.etat === "pose" ? "ok" : x.etat === "partiel" ? "al" : x.id === "vision" ? "mu" : "dg") + '">' + (x.etat === "pose" ? "prêt" : x.etat === "partiel" ? "incomplet" : x.id === "vision" ? "facultatif" : "absent") + '</span><br><span class="note">' + esc(x.detail) + '</span></td><td class="n">' + octets(x.octets) + '</td><td class="note">' + esc(x.utilise_par) + "</td><td>" +
        (x.id === "vision" ? '<select data-vision="1" aria-label="Modèle de vision" style="width:auto"><option value="">— aucun —</option>' + ms.map((m) => '<option value="' + esc(m.id) + '"' + ((m.roles || []).indexOf("vision") >= 0 ? " selected" : "") + ">" + esc(m.nom) + "</option>").join("") + "</select>" : "") + "</td></tr>").join("");
      return '<div class="carte"><div><h2>Les autres moteurs d’IA de la machine</h2><p class="note">Posés par l’installateur : la bibliothèque, la mémoire, la voix et les pièces jointes en dépendent. Rien n’est chargé pour afficher cette liste.</p></div><div class="sc"><table><thead><tr><th>Moteur</th><th>Rôle</th><th>État</th><th>Poids</th><th>Utilisé par</th><th></th></tr></thead><tbody>' + rows + "</tbody></table></div></div>";
    }

    // ── comparateur et usage ────────────────────────────────────────────────
    function carteComparateur() {
      const ms = declares().filter((m) => m.portee === "instance"); if (ms.length < 1) return "";
      if (!S.cmp.a || !ms.some((m) => m.id === S.cmp.a)) S.cmp.a = ms[0].id;
      if (!S.cmp.b || !ms.some((m) => m.id === S.cmp.b)) S.cmp.b = (ms[1] || ms[0]).id;
      const sel = (id, cle) => '<select data-cmp="' + cle + '" aria-label="Modèle ' + cle.toUpperCase() + '">' + ms.map((m) => '<option value="' + esc(m.id) + '"' + (m.id === id ? " selected" : "") + ">" + esc(m.nom) + (m.en_ligne ? "" : " (local)") + "</option>").join("") + "</select>";
      return '<div class="carte"><div><h2>Deux modèles, la même question</h2><p class="note">Avant de confier un agent à un modèle, voir comment il répond comparé à l’autre. Aucun outil ne s’exécute : c’est une conversation, rien d’autre.</p></div>' +
        '<div class="g2" style="gap:10px">' + sel(S.cmp.a, "a") + sel(S.cmp.b, "b") + '</div><input type="text" id="md-cq" value="' + esc(S.cmp.q) + '" aria-label="La question" autocomplete="off">' +
        '<div class="acts"><button class="btn pri" data-a="comparer"' + (S.occupe ? " disabled" : "") + ">Comparer</button></div>" +
        '<div class="g2" style="gap:10px"><div class="rep" id="md-ra">' + esc(S.cmp.ra || "…") + '</div><div class="rep" id="md-rb">' + esc(S.cmp.rb || "…") + "</div></div></div>";
    }
    function carteUsage() {
      const us = S.us; if (!us) return "";
      const par = {};
      us.lignes.forEach((x) => { const o = par[x.modele_id] = par[x.modele_id] || { appels: 0, echecs: 0, e: 0, s: 0, sec: 0 }; o.appels += x.appels; o.echecs += x.echecs; o.e += x.entrees; o.s += x.sorties; o.sec += x.secondes; });
      const ids = Object.keys(par); if (!ids.length) return '<div class="carte"><h2>Ce que chaque modèle a fait</h2><p class="note">Aucun appel en 14 jours.</p></div>';
      return '<div class="carte"><h2>Ce que chaque modèle a fait <span class="note">(14 jours)</span></h2><div class="sc"><table><thead><tr><th>Modèle</th><th>Appels</th><th>Échecs</th><th>Jetons entrée</th><th>Jetons sortie</th><th>Durée moyenne</th></tr></thead><tbody>' + ids.map((id) => {
        const m = declares().find((x) => x.id === id), o = par[id];
        return '<tr><td><b class="mono">' + esc(m ? m.nom : id) + "</b> " + (m ? '<span class="pastille ' + (m.en_ligne ? "al" : "mu") + '">' + (m.en_ligne ? "en ligne" : "local") + "</span>" : '<span class="pastille mu">retiré</span>') + '</td><td class="n">' + entier(o.appels) + '</td><td class="n">' + entier(o.echecs) + '</td><td class="n">' + entier(o.e) + '</td><td class="n">' + entier(o.s) + '</td><td class="n">' + (o.appels ? (o.sec / o.appels).toFixed(1).replace(".", ",") + " s" : "—") + "</td></tr>";
      }).join("") + "</tbody></table></div></div>";
    }

    function dessiner() {
      let h = '<div class="pg-tete"><div class="bar"><h1>Modèles &amp; clés</h1><div class="acts"><button class="btn mini" data-a="console" title="La console technique du module (réglages, gestes, journal)">Console technique</button></div></div>' +
        '<p class="sous">Les modèles de langage qui font parler Cassandra, Itare et les autres : ceux des fournisseurs en ligne (avec ta clé d’API) et ceux que la machine fait tourner elle-même. Sans modèle, un agent ne répond pas.</p></div>';
      if (S.erreur) h += '<div class="carte err">' + esc(S.erreur) + "</div>";
      if (!S.l) { racine.innerHTML = h + '<div class="attente">Lecture des modèles…</div>'; return; }
      h += carteSante() + carteAgents() + carteLigne() + carteAjout() + carteLocale() + carteCatalogue() + carteMoteurs() + carteComparateur() + carteUsage() + ficheHtml();
      const foc = document.activeElement && document.activeElement.id, val = foc ? document.activeElement.value : "";
      racine.innerHTML = h;
      if (foc && racine.querySelector("#" + foc) && foc !== "md-cle") { const e = racine.querySelector("#" + foc); if (e.tagName === "INPUT") { e.value = val; if (foc === "md-cat-q") { e.focus(); e.setSelectionRange(val.length, val.length); } } }
      lier();
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
      const p = racine.querySelector("#md-prov"); if (p) p.addEventListener("change", () => { S.prov = p.value; S.form = { nom: "", base: "" }; dessiner(); });
      const n = racine.querySelector("#md-nom"); if (n) n.addEventListener("input", () => { S.form.nom = n.value; });
      const b = racine.querySelector("#md-base"); if (b) b.addEventListener("input", () => { S.form.base = b.value; });
      const kk = racine.querySelector("#md-cle"); if (kk) kk.addEventListener("input", () => { S.form.cle = kk.value; });   // en mémoire de la page seulement, le temps de lister puis d’ajouter
      const m = racine.querySelector("#md-pull"); if (m) m.addEventListener("input", () => { S.mini = m.value; });
      const cq = racine.querySelector("#md-cat-q"); if (cq) cq.addEventListener("input", () => { S.cat.q = cq.value; dessiner(); });
      const q = racine.querySelector("#md-cq"); if (q) q.addEventListener("input", () => { S.cmp.q = q.value; });
      racine.querySelectorAll("[data-cmp]").forEach((x) => x.addEventListener("change", () => { S.cmp[x.dataset.cmp] = x.value; }));
      racine.querySelectorAll("[data-ag]").forEach((x) => x.addEventListener("change", () => faire(() => choisirPourAgent(x.dataset.ag, x.dataset.champ, x.value), "Réglé : " + x.dataset.ag)));
      racine.querySelectorAll("[data-vision]").forEach((x) => x.addEventListener("change", () => faire(() => agir("modeles.role_lier", { role: "vision", modele_id: x.value }), "Rôle vision mis à jour.")));
    }

    async function comparer() {
      const q = String((racine.querySelector("#md-cq") || {}).value || S.cmp.q || "").trim(); if (!q) { dire("Une question à poser aux deux modèles.", "err"); return; }
      S.cmp.q = q; S.cmp.ra = S.cmp.rb = "Réponse en cours…"; S.occupe = true; dessiner();
      const un = async (id) => {
        const m = declares().find((x) => x.id === id), t = Date.now();
        try { const r = await agir("modeles.question_libre", { modele_id: id, question: q, max_tokens: 500 }); return (m ? m.nom + "\n\n" : "") + (r.ok ? (r.texte || "(réponse vide)") + "\n\n— " + ((Date.now() - t) / 1000).toFixed(1).replace(".", ",") + " s" : "Échec : " + (r.erreur || "aucune réponse")); }
        catch (e) { return (m ? m.nom + "\n\n" : "") + "Échec : " + (e.message || e); }
      };
      const [ra, rb] = await Promise.all([un(S.cmp.a), un(S.cmp.b)]);
      S.cmp.ra = ra; S.cmp.rb = rb; S.occupe = false; dessiner();
    }

    async function geste(b) {
      const a = b.dataset.a;
      if (a === "cat-onglet") { S.cat = { onglet: b.dataset.o, q: S.cat.q, filtre: "tous" }; dessiner(); return; }
      if (a === "cat-filtre") { S.cat.filtre = b.dataset.f; dessiner(); return; }
      if (a === "fiche") { S.fiche = { k: b.dataset.k, n: b.dataset.n }; dessiner(); const z = racine.querySelector(".fiche"); if (z) z.focus(); return; }
      if (a === "fiche-fermer") { S.fiche = null; dessiner(); return; }
      if (a === "ajouter-ce") { S.fiche = null; S.prov = b.dataset.p; S.form = { nom: b.dataset.n, base: "" }; dessiner(); const z = racine.querySelector("#md-ajout"); if (z) z.scrollIntoView({ behavior: "smooth", block: "start" }); const c = racine.querySelector("#md-cle"); if (c) c.focus(); return; }
      if (a === "console") { racine.remove(); if (CASS.console) CASS.console("modeles", corps); return; }
      if (a === "vers-ajout") { const z = racine.querySelector("#md-ajout"); if (z) z.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
      if (a === "retirer") { S.retirer = b.dataset.id; dessiner(); return; }
      if (a === "retirer-non") { S.retirer = ""; dessiner(); return; }
      if (a === "retirer-oui") return faire(() => retirerModele(b.dataset.id), "Modèle retiré.");
      if (a === "suppr") { S.suppr = b.dataset.n; dessiner(); return; }
      if (a === "suppr-non") { S.suppr = ""; dessiner(); return; }
      if (a === "suppr-oui") return faire(() => agir("modeles.ollama_supprimer", { nom: b.dataset.n }), "Modèle local supprimé.");
      if (a === "essayer") return faire(async () => { const r = await essayer(b.dataset.id); S.essais[b.dataset.id] = r.ok ? { ok: true, secondes: r.secondes } : { ok: false, erreur: r.erreur }; return r; }, (r) => (r.ok === false ? "Le modèle n’a pas répondu." : "Le modèle a répondu."));
      if (a === "declarer") return faire(() => ajouterModele({ fournisseur: "ollama", nom: b.dataset.n }), "Modèle local déclaré : " + b.dataset.n);
      if (a === "brancher-local") return faire(async () => { const r = await ajouterModele({ fournisseur: "ollama", nom: b.dataset.n }); await lierDefauts(r.id, true); try { await essayer(r.id); } catch (e) { /* l’essai se refait à la main */ } }, "Cassandra, Amizo et Itare utilisent maintenant " + b.dataset.n + ".");
      if (a === "lier-defauts") { const id = String((racine.querySelector("#md-tout") || {}).value || ""); if (!id) return; const m = declares().find((x) => x.id === id); return faire(() => lierDefauts(id, !!m && !m.en_ligne), "Cassandra, Amizo et Itare sont reliés."); }
      if (a === "installer") return faire(() => agir("modeles.ollama_telecharger", { nom: b.dataset.n }), "Téléchargement demandé : " + b.dataset.n);
      if (a === "installer-libre") {
        const n = String((racine.querySelector("#md-pull") || {}).value || "").trim();
        if (!n) { dire("Un nom de modèle, comme llama3.1:8b", "err"); return; }
        S.mini = ""; return faire(() => agir("modeles.ollama_telecharger", { nom: n }), "Téléchargement demandé : " + n);
      }
      if (a === "comparer") return comparer();
      if (a === "decouvrir") {
        const cle = String((racine.querySelector("#md-cle") || {}).value || "").trim();
        const base = String((racine.querySelector("#md-base") || {}).value || "").trim();
        if (prov().cle === "requise" && !cle) { dire("Tape d’abord la clé d’API : le fournisseur ne liste ses modèles qu’à qui en a une.", "err"); return; }
        return faire(async () => {
          const r = await decouvrir({ fournisseur: S.prov, cle, base_url: base });
          if (!r.ok) throw new Error(r.erreur || "liste indisponible");
          S.dispo[S.prov] = r.modeles;
          return r;
        }, (r) => r.total + " modèles listés par ce fournisseur : choisis dans le champ « Nom du modèle ».");
      }
      if (a === "ajouter") {
        const nom = String((racine.querySelector("#md-nom") || {}).value || "").trim() || prov().defaut || "";
        const cle = String((racine.querySelector("#md-cle") || {}).value || "").trim();
        const base = String((racine.querySelector("#md-base") || {}).value || "").trim();
        if (!nom) { dire("Le nom du modèle est obligatoire.", "err"); return; }
        if (prov().cle === "requise" && !cle) { dire("Ce fournisseur demande une clé d’API.", "err"); return; }
        return faire(async () => {
          const r = await ajouterModele({ fournisseur: S.prov, nom, cle, base_url: base });
          S.form = { nom: "", base: "" };
          const id = (r && (r.id || (r.modele && r.modele.id))) || "";
          if (id) { try { const e = await essayer(id); S.essais[id] = e.ok ? { ok: true, secondes: e.secondes } : { ok: false, erreur: e.erreur }; } catch (e) { S.essais[id] = { ok: false, erreur: e.message }; } }
          return r;
        }, "Modèle ajouté : " + nom);
      }
    }

    racine.innerHTML = '<div class="attente">Lecture des modèles…</div>';
    await charger(true);
  }
  CASS.monterModeles = monter;
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.modeles = monter;
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l’écran et ses gestes.
// EC : néant.
// LIEN : modules/modeles et modules/agents (cerveau), interface/CN_shell.js (le crochet CASS.sceneSurMesure), interface/CN_agents-ecran.js (qui le monte dans Agents IA).
