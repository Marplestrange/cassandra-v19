// ═════════════════════════════════════════════════════════════════
// TITRE      : NetBird : l’écran
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #647502
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les pages « NetBird » du module netbird : où en est la machine, sa connexion (par un lien à ouvrir ou par une clé), les machines du réseau, l’installation du client dans Docker, l’historique des gestes.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.netbird) ; la page vient de l’écran ouvert (ctx.ecran = « netbird:n_machines ») ; tout vient de netbird.etat ; l’état se relit seul (20 s, 2,5 s pendant une identification), jamais sous les doigts de quelqu’un qui tape.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=647502 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  const LIEN_SUR = /^https:\/\/[A-Za-z0-9.-]+(:\d+)?\//i;

  const CSS = ".nb{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.nb *{box-sizing:border-box}" +
    ".nb h1,.nb h2,.nb p{margin:0}.nb .mono{font-family:" + MONO + "}" +
    ".nb .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:12px}" +
    ".nb .tete h1{font:650 22px/1.2 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}.nb .sous{color:var(--txt-soft);font-size:13px;margin-top:3px;max-width:64ch}" +
    ".nb .acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}" +
    ".nb .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 14px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer}" +
    ".nb .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.nb .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}" +
    ".nb .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.nb .btn[disabled]{opacity:.45;cursor:not-allowed}" +
    ".nb .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:3px 11px;font:600 12px 'Inter',system-ui,sans-serif;white-space:nowrap;border:1px solid var(--line)}" +
    ".nb .pastille::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor}" +
    ".nb .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)}.nb .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}" +
    ".nb .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent)}.nb .pastille.mu{color:var(--txt-soft)}" +
    ".nb .hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px 22px}.nb .hero>div{display:flex;flex-direction:column;gap:4px;min-width:0}" +
    ".nb .lib{font:600 10.5px 'Inter',system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}.nb .gros{font:600 20px/1.2 " + MONO + ";color:var(--txt-strong,var(--txt));overflow-wrap:anywhere}" +
    ".nb .note{font-size:12px;color:var(--txt-soft)}.nb .lien{padding:20px;border:1px dashed var(--accent);border-radius:14px;display:flex;flex-direction:column;gap:12px;background:color-mix(in srgb,var(--accent) 6%,transparent)}" +
    ".nb .lien .u{font:12px " + MONO + ";overflow-wrap:anywhere;color:var(--txt-soft)}" +
    ".nb .champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 18px}.nb label.ch{display:flex;flex-direction:column;gap:5px}.nb label.ch b{font-weight:650}" +
    ".nb input[type=text],.nb input[type=password]{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:8px 12px;font:13px " + MONO + ";min-width:0;width:100%}" +
    ".nb .coche{display:flex;gap:8px;align-items:flex-start}.nb .coche input{margin-top:3px}" +
    ".nb .pairs{display:flex;flex-direction:column}.nb .pair{display:grid;grid-template-columns:auto minmax(120px,1fr) minmax(110px,auto) auto;gap:6px 14px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}" +
    ".nb .pair .nom{font:600 13px " + MONO + ";overflow-wrap:anywhere}.nb .pt{width:9px;height:9px;border-radius:50%;background:var(--txt-faint)}.nb .pt.on{background:var(--ok)}" +
    ".nb .attente{padding:30px;text-align:center;color:var(--txt-soft)}.nb .confirme{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px}" +
    ".sh-scene:has(>.sh-corps>.nb)>.sh-titre{display:none}" +
    "@media (max-width:820px){.nb .pair{grid-template-columns:auto minmax(0,1fr) auto}.nb .pair .ip{grid-column:2 / -1}}";

  const age = (s) => { if (!s) return "jamais vue"; const d = new Date(String(s).replace(" ", "T") + ":00Z"); if (isNaN(d)) return s; const m = Math.max(0, Math.round((Date.now() - d) / 60000)); return m < 2 ? "à l’instant" : m < 90 ? "il y a " + m + " min" : m < 2880 ? "il y a " + Math.round(m / 60) + " h" : "il y a " + Math.round(m / 1440) + " j"; };
  const octets = (n) => (n >= 1e9 ? (n / 1e9).toFixed(1) + " Go" : n >= 1e6 ? (n / 1e6).toFixed(1) + " Mo" : n >= 1e3 ? Math.round(n / 1e3) + " Ko" : n ? n + " o" : "");
  const ETAT = { connecte: ["ok", "Connecté"], deconnecte: ["mu", "Déconnecté"], a_identifier: ["al", "En attente d’identification"], session_expiree: ["al", "Session expirée : à reconnecter"], echec_connexion: ["dg", "Connexion refusée"],
    demarrage: ["al", "Connexion en cours…"], inconnu: ["al", "État inconnu"], a_installer: ["al", "Client à installer"], absent: ["dg", "Non installé"], arrete: ["dg", "Le démon ne répond pas"] };
  const PAGES = { n_vue: "vue", n_machines: "machines", n_installation: "installation", n_serveur: "serveur", n_gestion: "gestion", n_historique: "historique" };
  const TITRES = {
    vue: ["", "Le réseau privé NetBird de cette machine : la joindre de n’importe où, et joindre tes autres machines."],
    machines: ["Machines", "Les machines de ton réseau : qui est en ligne, par quel chemin on les joint et en combien de temps."],
    installation: ["Client", "Cette machine rejoint un réseau NetBird (le tien ou NetBird Cloud) : où est le client, et son installation dans Docker."],
    serveur: ["Serveur", "Héberger ton propre réseau NetBird sur cette machine : installer le serveur, le tenir à jour, le retirer. Aucun n’est installé tant que tu ne le demandes pas."],
    gestion: ["Administration", "Les machines, les clés d’installation, les groupes et les politiques d’accès d’un serveur NetBird auto-hébergé, administrés depuis Cassandra."],
    historique: ["Historique", "Les derniers gestes faits sur NetBird depuis Cassandra, avec leur retour."],
  };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.netbird = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("netbird", corps); return; }
    const page = PAGES[String((ctx && ctx.ecran) || "").split(":")[1]] || "vue";
    const anc = document.getElementById("nb-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "nb-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "nb"; corps.appendChild(racine);

    const S = { e: null, occupe: false, erreur: "", couper: false, q: "", filtre: "tous", j: null, lu: 0, nom: "", s: null, g: null, onglet: "machines", edit: "", cle: null, txt: null, dl: null, f: { version: "", domaine: "", email: "", proxy: "nginx", hors: false }, pt: null };
    let minuterie = null;

    async function charger(silencieux) {
      try {
        if (page === "serveur") { S.s = await agir("netbird.serveur_etat"); S.dm = S.s.installe ? null : await agir("netbird.serveur_domaines").catch(() => null); S.pt = await agir("netbird.serveur_ports", S.s.installe ? {} : { proxy: S.f.proxy }).catch(() => null); }
        else if (page === "gestion") S.g = await chargerReseau();
        else S.e = await agir("netbird.etat");
        S.erreur = ""; S.lu = Date.now();
      } catch (e) { S.erreur = e.message || String(e); if (page === "gestion") S.g = null; }
      if (page === "historique") { try { S.j = (await agir("netbird.journal", { limite: 30 })).gestes; } catch (_) { S.j = null; } }
      if (!silencieux || document.body.contains(racine)) dessiner();
      armer();
    }
    async function chargerReseau() {
      const noms = ["machines", "cles", "groupes", "politiques"], r = await Promise.all(noms.map((n) => agir("netbird.api_" + n))), g = {};
      noms.forEach((n, i) => { g[n] = r[i][n]; });
      return g;
    }
    function armer() {
      if (minuterie) { clearTimeout(minuterie); minuterie = null; }
      if (!document.body.contains(racine)) return;
      const e = S.e, vite = e && (e.en_attente || e.etat === "demarrage");
      minuterie = setTimeout(() => {
        if (!document.body.contains(racine)) return;
        const ae = document.activeElement, saisie = ae && racine.contains(ae) && /^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName);
        if (!S.occupe && !saisie) charger(true); else armer();
      }, vite ? 2500 : 20000);
    }
    const faire = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; dessiner();
      try { await f(); if (ok) dire(ok); } catch (e) { dire(e.message || String(e), "err"); S.erreur = e.message || String(e); }
      finally { S.occupe = false; S.couper = false; await charger(); }
    };
    async function copier(t) {
      try { await navigator.clipboard.writeText(t); dire("Copié : " + t); }
      catch (_) { const x = document.createElement("textarea"); x.value = t; document.body.appendChild(x); x.select(); try { document.execCommand("copy"); dire("Copié : " + t); } catch (e2) { dire("Copie impossible", "err"); } x.remove(); }
    }
    // La clé d’installation est enregistrée le temps du geste, puis effacée aussitôt : elle ne reste ni dans l’écran ni dans les réglages.
    async function avecCle(cle, f) {
      await agir("reglages.regler_secret", { cle: "netbird.cle_install", valeur: cle });
      try { return await f(); } finally { try { await agir("reglages.reinitialiser", { cle: "netbird.cle_install" }); } catch (_) { /* la clé n’était pas gardée */ } }
    }
    const pastille = (e) => { const p = (e.etat === "a_identifier" && !e.en_attente) ? ["mu", "Non connecté"] : (ETAT[e.etat] || ["mu", e.etat]); return '<span class="pastille ' + p[0] + '">' + esc(p[1]) + "</span>"; };
    const copie = (t, lib) => ' <button class="btn" data-a="copier" data-t="' + esc(t) + '" style="padding:1px 6px;font-size:10.5px">' + (lib || "Copier") + "</button>";
    const H2 = 'style="font:650 16px Inter,system-ui,sans-serif"';

    function carteEtat(e) {
      const c = e.etat === "connecte";
      return '<div class="carte"><div class="hero"><div><span class="lib">État</span>' + pastille(e) + (e.etat === "echec_connexion" || (e.gestion && e.gestion.erreur) ? '<span class="note" style="color:var(--danger)">' + esc((e.gestion || {}).erreur || "") + "</span>" : "") + "</div>" +
        (c ? '<div><span class="lib">Cette machine</span><span class="gros">' + esc(e.nom || "—") + '</span><span class="note mono">' + esc(e.fqdn) + copie(e.fqdn) + "</span></div>" +
          '<div><span class="lib">Adresse</span><span class="gros">' + esc(e.ip || "—") + '</span><span class="note mono">' + esc(e.ip6 || "") + copie(e.ip, "Copier l’adresse") + "</span></div>" +
          '<div><span class="lib">Serveurs</span><span class="gros" style="font-size:16px">' + (e.gestion.connecte ? "gestion ✓" : "gestion ✗") + " · " + (e.signal.connecte ? "signal ✓" : "signal ✗") + "</span>" +
          '<span class="note">relais ' + e.relais_dispo + "/" + e.relais_total + " · client " + esc(e.version) + (e.mode === "docker" ? " · dans Docker" : "") + "</span></div>" : "") + "</div></div>";
    }
    function avisSession(e) {
      return e.session_jours != null && e.session_jours <= 14 ? '<div class="carte" style="color:var(--warn)">La session de cette machine ' + (e.session_jours < 0 ? "a expiré" : "expire dans " + e.session_jours + " j") + " : reconnecte-la (sinon elle quitte le réseau).</div>" : "";
    }
    function carteLien(e) {
      const sur = LIEN_SUR.test(e.lien || "");
      return '<div class="lien"><h2 ' + H2 + '>Ouvre ce lien pour connecter la machine</h2><p class="note">Identifie-toi chez NetBird : la machine rejoint ton réseau dès que c’est fait. Cet écran se met à jour tout seul.</p>' +
        (sur ? '<div class="acts"><a class="btn pri" href="' + esc(e.lien) + '" target="_blank" rel="noopener noreferrer">Ouvrir la page de connexion</a><button class="btn" data-a="annuler"' + (S.occupe ? " disabled" : "") + ">Annuler</button></div>" +
          '<span class="u">' + esc(e.lien) + "</span>" : '<p class="note" style="color:var(--danger)">Le lien reçu n’est pas une adresse https : il n’est pas proposé. Annule et recommence.</p><div class="acts"><button class="btn" data-a="annuler">Annuler</button></div>') + "</div>";
    }
    function carteConnexion(e) {
      return '<div class="carte"><h2 ' + H2 + ">Connecter cette machine à ton réseau NetBird</h2>" +
        '<p class="note">NetBird relie tes machines entre elles par un réseau privé chiffré. Sans clé : un lien à ouvrir. Avec une clé d’installation (tableau de bord NetBird › Setup Keys) : la machine se connecte seule.</p>' +
        '<div class="champs"><label class="ch"><b>Nom de la machine</b><span class="note">Facultatif ; celui du système par défaut.</span><input type="text" id="nb-nom" value="' + esc(S.nom) + '" placeholder="argos" autocomplete="off" spellcheck="false"></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="connecter"' + (S.occupe ? " disabled" : "") + ">" + (S.occupe ? "Un instant…" : "Se connecter par un lien") + "</button></div>" +
        '<details><summary style="cursor:pointer;font-weight:650;color:var(--accent)">J’ai une clé d’installation</summary><p class="note" style="margin:8px 0">Elle sert le temps de la connexion et n’est gardée nulle part.</p>' +
        '<div class="acts"><input type="password" id="nb-cle" placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" autocomplete="off" spellcheck="false" style="flex:1 1 260px"><button class="btn" data-a="cle"' + (S.occupe ? " disabled" : "") + ">Se connecter avec la clé</button></div></details></div>";
    }
    function carteGestes(e) {
      return '<div class="carte"><h2 ' + H2 + ">Connexion</h2>" + '<div class="acts">' + (S.couper ? '<span class="confirme">Couper NetBird sur cette machine ? Si tu t’y connectes par NetBird, tu perdras l’accès. <button class="btn dng" data-a="deconnecter-oui">Oui, couper</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
        : '<button class="btn" data-a="deconnecter"' + (S.occupe ? " disabled" : "") + ">Déconnecter</button>") + "</div></div>";
    }
    function carteAInstaller(e) {
      return '<div class="carte"><h2 ' + H2 + ">Qu’est-ce que NetBird ?</h2>" +
        '<p>NetBird relie tes machines entre elles par un <b>réseau privé chiffré</b> (WireGuard) : serveurs, portables, téléphones se joignent comme s’ils étaient sur le même réseau local, où qu’ils soient et sans ouvrir de port sur internet.</p>' +
        '<p class="note">Il a deux morceaux. Le <b>client</b> tourne sur chaque machine qui rejoint le réseau. Le <b>serveur</b> tient le registre : qui est dans le réseau, avec quelle clé, et qui a le droit de joindre quoi. Ce serveur peut être celui de NetBird (NetBird Cloud) ou le tien.</p></div>' +
        '<div class="carte"><h2 ' + H2 + ">Par où commencer ?</h2>" +
        '<p class="note">' + esc(e.texte || "") + "</p>" +
        '<div class="champs"><div><b>Rejoindre un réseau NetBird</b><p class="note">Cette machine devient un membre : le réseau est sur NetBird Cloud ou sur un serveur existant. Il suffit d’installer le <b>client</b>.</p><div class="acts"><button class="btn pri" data-a="vers-installation">Installer le client</button></div></div>' +
        '<div><b>Héberger mon propre réseau</b><p class="note">Cassandra installe et administre un <b>serveur</b> NetBird sur cette machine (avec ton domaine), puis tu gères machines, clés et accès depuis ici. Ensuite, installe aussi le client si cette machine doit en faire partie.</p><div class="acts"><button class="btn" data-a="vers-serveur">Installer le serveur</button></div></div></div></div>';
    }
    // Un seul client NetBird par machine : le natif ET le conteneur en même temps se disputent l’interface wt0 et le port 51820.
    function avisConflit(e) {
      return e.conflit ? '<div class="carte" style="color:var(--warn)">Deux clients NetBird sont installés sur cette machine (le client natif et le conteneur « ' + esc(e.nom_conteneur) + ' ») : ils se disputent l’interface <span class="mono">wt0</span> et le port 51820. Garde-en un seul : retire le conteneur depuis la page <b>Client</b>, ou désinstalle le client natif.</div>' : "";
    }
    function pageVue(e) {
      let h = avisConflit(e) + carteEtat(e);
      if (e.etat === "absent" || e.etat === "a_installer") return h + carteAInstaller(e);
      if (e.etat === "arrete") return h + '<div class="carte"><p>' + esc(e.texte || "") + '</p><div class="acts"><button class="btn" data-a="relire">Relire</button></div></div>';
      if (e.en_attente && e.lien) return h + carteLien(e);
      if (e.etat === "connecte") return h + avisSession(e) + carteGestes(e);
      if (e.etat === "demarrage") return h + '<div class="carte attente">NetBird se connecte…</div>';
      return h + carteConnexion(e);
    }

    // ---- les machines
    function ligneMachine(p) {
      const det = [p.en_ligne && p.chemin ? "chemin " + p.chemin + (p.chemin === "relais" && p.relais ? " (" + p.relais.replace(/^rels?:\/\//, "") + ")" : "") : "", p.ms != null ? p.ms + " ms" : "", octets(p.octets) ? "échanges " + octets(p.octets) : "",
        p.reseaux && p.reseaux.length ? "réseaux " + p.reseaux.join(", ") : ""].filter(Boolean).join(" · ");
      return '<div class="pair"><span class="pt' + (p.en_ligne ? " on" : "") + '"></span><span class="nom">' + esc(p.nom) + (p.pq ? ' <span class="pastille mu">post-quantique</span>' : "") + '<br><span class="note">' + esc(det) + "</span></span>" +
        '<span class="mono ip note">' + esc(p.ip) + copie(p.ip) + '</span><span class="note">' + (p.en_ligne ? "en ligne" : age(p.vu)) + "</span></div>";
    }
    function pageMachines(e) {
      if (e.etat !== "connecte") return '<div class="carte"><p>NetBird n’est pas connecté sur cette machine : connecte-la depuis la <b>Vue d’ensemble</b>.</p></div>';
      const pairs = e.pairs || [], q = String(S.q || "").trim().toLowerCase();
      const vus = pairs.filter((p) => (S.filtre === "tous" || (S.filtre === "en_ligne" ? p.en_ligne : !p.en_ligne)) && (!q || (p.nom + " " + p.ip + " " + (p.reseaux || []).join(" ")).toLowerCase().includes(q)));
      let h = '<div class="carte"><div class="acts" style="justify-content:space-between"><h2 ' + H2 + '>Les machines du réseau <span class="note">(' + e.en_ligne + " en ligne sur " + pairs.length + ")</span></h2></div>";
      if (pairs.length > 3) h += '<div class="acts"><input type="text" id="nb-q" placeholder="Chercher une machine, une adresse…" value="' + esc(S.q) + '" style="flex:1 1 220px"><select id="nb-f">' +
        [["tous", "Toutes"], ["en_ligne", "En ligne"], ["hors_ligne", "Hors ligne"]].map((o) => '<option value="' + o[0] + '"' + (S.filtre === o[0] ? " selected" : "") + ">" + o[1] + "</option>").join("") + "</select></div>";
      h += vus.length ? '<div class="pairs">' + vus.map(ligneMachine).join("") + "</div>" : '<p class="note">' + (pairs.length ? "Aucune machine ne correspond." : "Aucune autre machine sur ce réseau pour l’instant.") + "</p>";
      h += "</div>";
      if (e.reseaux && e.reseaux.length) h += '<div class="carte"><h2 ' + H2 + '>Réseaux joignables par cette machine</h2><p class="mono note">' + e.reseaux.map(esc).join(" · ") + "</p></div>";
      return h;
    }

    // Deux choses se ressemblent et n’ont rien à voir : rejoindre un réseau NetBird (le client) et héberger le sien (le serveur). Chaque page dit laquelle elle est, et renvoie vers l’autre.
    function aiguillage(client) {
      return '<div class="carte"><p class="note" style="margin:0">' + (client
        ? "<b>Client</b> : cette machine <b>rejoint</b> un réseau NetBird, le tien ou NetBird Cloud. Pour <b>héberger ton propre réseau</b>, c’est la page <b>Serveur</b>."
        : "<b>Serveur</b> : tu <b>héberges</b> ton propre réseau NetBird. Pour que cette machine <b>rejoigne</b> un réseau, c’est la page <b>Client</b>.") +
        '</p><div class="acts" style="margin-top:8px"><button class="btn" data-a="' + (client ? "vers-serveur" : "vers-installation") + '">' + (client ? "Aller au Serveur" : "Aller au Client") + "</button></div></div>";
    }
    // ---- le client : où il est, et le conteneur Docker
    function pageInstallation(e) {
      const nonRoot = e.courtier === false;
      const oui = (b) => '<span class="pastille ' + (b ? "ok" : "mu") + '">' + (b ? "oui" : "non") + "</span>";
      let h = aiguillage(true) + '<div class="carte"><h2 ' + H2 + ">Ce qui existe sur cette machine</h2><div class=\"hero\">" +
        '<div><span class="lib">Client NetBird installé</span>' + oui(e.natif) + "</div><div><span class=\"lib\">Docker</span>" + oui(e.docker) + "</div>" +
        '<div><span class="lib">Conteneur « ' + esc(e.nom_conteneur) + '»</span><span class="pastille ' + (e.conteneur === "en_marche" ? "ok" : e.conteneur === "absent" ? "mu" : "al") + '">' +
        esc({ en_marche: "en marche", arrete: "arrêté", absent: "absent", autre: "autre service (intouché)" }[e.conteneur] || e.conteneur) + "</span></div>" +
        '<div><span class="lib">Utilisé par Cassandra</span><span class="gros" style="font-size:16px">' + esc({ natif_direct: "client natif", natif_racine: "client natif (par le courtier)", docker: "conteneur Docker", absent: "—" }[e.mode] || e.mode) + "</span></div></div></div>";
      h = aiguillage(true) + avisConflit(e) + h.slice(aiguillage(true).length);
      if (nonRoot) h += '<div class="carte" style="color:var(--warn)">Le courtier ne répond pas ou la commande root du module n’est pas posée : <span class="mono">CN_install.sh --module netbird</span> la pose. Sans elle, Docker ne se pilote pas d’ici.</div>';
      const bloque = S.occupe || !e.docker || nonRoot || e.natif || e.conteneur === "en_marche" || e.conteneur === "arrete" || e.conteneur === "autre";
      h += '<div class="carte"><h2 ' + H2 + ">Installer NetBird dans Docker</h2><p class=\"note\">Crée le conteneur officiel <span class=\"mono\">netbirdio/netbird</span> : il redémarre avec la machine, utilise le réseau de la machine et garde son identité dans un volume. Aucun autre conteneur n’est touché.</p>" +
        (e.natif ? '<p class="note" style="color:var(--warn)">Un client NetBird est déjà installé sur cette machine : un seul client par machine. Utilise celui-là, ou désinstalle-le avant d’installer le conteneur.</p>' : !e.docker ? '<p class="note" style="color:var(--warn)">Docker n’est pas installé sur cette machine.</p>' : e.conteneur === "autre" ? '<p class="note" style="color:var(--warn)">Un conteneur « ' + esc(e.nom_conteneur) + ' » existe déjà mais n’est pas NetBird : change le réglage « conteneur ».</p>' : "") +
        '<div class="champs"><label class="ch"><b>Version</b><span class="note">latest, ou une version précise (0.40.0).</span><input type="text" id="nb-tag" value="latest" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Nom de la machine</b><span class="note">Facultatif.</span><input type="text" id="nb-i-nom" placeholder="argos" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Serveur de gestion</b><span class="note">Vide : NetBird Cloud (ou le réglage « url_gestion »).</span><input type="text" id="nb-i-url" placeholder="https://netbird.exemple.fr:443" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Clé d’installation</b><span class="note">Facultatif : avec elle le conteneur se connecte seul ; sans elle, un lien à ouvrir.</span><input type="password" id="nb-i-cle" placeholder="XXXXXXXX-XXXX-…" autocomplete="off" spellcheck="false"></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="installer"' + (bloque ? " disabled" : "") + ">Installer dans Docker</button></div></div>";
      if (e.conteneur === "en_marche" || e.conteneur === "arrete") {
        h += '<div class="carte"><h2 ' + H2 + ">Mettre à jour le client</h2><p class=\"note\">Télécharge la dernière image de la même étiquette et, si elle a changé, recrée le conteneur avec son volume : la machine est coupée quelques secondes, son identité est gardée.</p><div class=\"acts\"><button class=\"btn pri\" data-a=\"client-maj\"" + (S.occupe || nonRoot ? " disabled" : "") + ">Mettre à jour le client</button></div></div>";
        h += '<div class="carte"><h2 ' + H2 + ">Retirer le conteneur</h2><p class=\"note\">Le volume est gardé : une réinstallation retrouve l’identité de la machine dans NetBird.</p><div class=\"acts\">" +
          (S.couper ? '<span class="confirme"><label class="coche"><input type="checkbox" id="nb-purge"><span>Supprimer aussi le volume : la machine perd son identité et il faudra une nouvelle identification.</span></label> <button class="btn dng" data-a="retirer-oui">Oui, retirer</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
            : '<button class="btn dng" data-a="retirer"' + (S.occupe || nonRoot ? " disabled" : "") + ">Retirer le conteneur…</button>") + "</div></div>";
      }
      return h;
    }

    function pageHistorique(e) {
      const g = S.j || [];
      if (!g.length) return '<div class="carte"><p class="note">' + (S.j === null ? "Le journal n’est pas lisible pour l’instant." : "Aucun geste noté pour l’instant : ils apparaissent ici dès qu’on connecte, coupe ou installe NetBird depuis Cassandra.") + "</p></div>";
      const quand = (ts) => { const d = new Date(String(ts).replace(" ", "T") + "Z"); return isNaN(d) ? ts : d.toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); };
      return '<div class="carte"><h2 ' + H2 + '>Derniers gestes</h2><div class="pairs">' + g.map((x) => '<div class="pair" style="grid-template-columns:minmax(90px,auto) minmax(120px,1fr) auto"><span class="note">' + esc(quand(x.ts)) + "</span><span>" + esc(x.libelle) +
        '<br><span class="note">' + esc(x.compte || "") + (x.defait ? " · défait" : "") + "</span></span>" + (x.defaisable ? '<button class="btn" data-a="defaire-geste" data-id="' + x.id + '"' + (S.occupe ? " disabled" : "") + ">Défaire</button>" : "<span></span>") + "</div>").join("") + "</div></div>";
    }

    // ---- le serveur NetBird auto-hébergé : l’installer, le tenir à jour, le retirer
    const oui = (b) => '<span class="pastille ' + (b ? "ok" : "mu") + '">' + (b ? "oui" : "non") + "</span>";
    const fiche = (l, v) => '<div><span class="lib">' + l + '</span><span class="gros" style="font-size:16px">' + v + "</span></div>";
    function cartePrerequis(s) {
      return '<div class="carte"><h2 ' + H2 + ">Avant d’installer</h2><div class=\"hero\">" + fiche("Docker", oui(s.docker)) + fiche("jq (exigé par le script officiel)", oui(s.jq)) + "</div>" +
        '<p class="note">Il faut aussi un nom de domaine propre au serveur NetBird (pas celui de Cassandra) qui pointe déjà vers cette machine, et les ports 80, 443 et 3478/udp ouverts (avec le proxy « nginx » ou « caddy », ton proxy existant publie le serveur : seul le port 3478/udp doit être libre).</p></div>';
    }
    const ETP = { libre: ["ok", "libre"], occupe: ["dg", "déjà pris : bloque l’installation"], pris_par_proxy: ["mu", "pris par ton proxy (normal)"], inconnu: ["mu", ""] };
    function cartePorts() {
      const p = S.pt;
      if (!p || !p.ports.length) return "";
      return '<div class="carte"><h2 ' + H2 + ">Ports" + (p.proxy ? " (proxy " + esc(p.proxy) + ")" : "") + '</h2><div class="pairs">' +
        p.ports.map((x) => '<div class="pair" style="grid-template-columns:minmax(110px,auto) minmax(140px,1fr) auto"><span class="nom">' + esc(x.proto.toUpperCase() + " " + x.port) + '<br><span class="note">' + (x.public ? "à ouvrir sur internet" : "sur cette machine seulement") + "</span></span><span class=\"note\">" + esc(x.usage) + "</span>" +
          (p.installe || !ETP[x.etat][1] ? "<span></span>" : '<span class="pastille ' + ETP[x.etat][0] + '">' + ETP[x.etat][1] + "</span>") + "</div>").join("") + "</div>" +
        (p.reels.length ? '<p class="note">Publiés par les conteneurs : <span class="mono">' + p.reels.map((r) => esc(r.service + " " + r.ports.join(", "))).join(" · ") + "</span></p>" : "") +
        '<p class="note">Le port 3478/udp ne passe jamais par un proxy. Source : documentation de NetBird (selfhosted-quickstart, external-reverse-proxy).</p></div>';
    }
    const AUTRE = "__autre";
    // Le domaine se choisit dans UNE liste : ceux que Cassandra administre, puis, en dernier, « un autre domaine » (champ libre, DNS et certificat à la charge de l’utilisateur).
    const lireForm = () => { const hors = val("#nb-s-domsel") === AUTRE; return { version: val("#nb-s-ver"), domaine: hors ? val("#nb-s-dom") : val("#nb-s-domsel"), email: val("#nb-s-mel"), proxy: val("#nb-s-prx") || "nginx", hors: hors }; };
    function noteDomaines() {
      const d = S.dm;
      if (!d) return "";
      if (!d.disponible) return "Le panneau d’hébergement ne répond pas : Cassandra ne peut pas vérifier le domaine" + (d.libre ? " (réglage « domaine_libre » actif : accepté)." : ".");
      return d.propositions.length ? d.sites.length + " site(s) et " + d.zones.length + " zone(s) DNS administrés par Cassandra." : "Aucun site ni zone DNS dans le panneau d’hébergement : déclare « un autre domaine », ou ajoutes-en un au panneau.";
    }
    function champDomaine() {
      const props = (S.dm && S.dm.propositions) || [], hors = S.f.hors || !props.length;
      const options = props.map((x) => '<option value="' + esc(x) + '"' + (!hors && S.f.domaine === x ? " selected" : "") + ">" + esc(x) + " (administré par Cassandra)</option>").join("") +
        '<option value="' + AUTRE + '"' + (hors ? " selected" : "") + ">Un autre domaine, que Cassandra n’administre pas…</option>";
      return '<label class="ch"><b>Domaine du serveur NetBird</b><span class="note">Un nom réservé à NetBird, différent de celui de Cassandra. La liste reprend les domaines qu’elle administre (sites du panneau d’hébergement, zones DNS).</span><select id="nb-s-domsel">' + options + "</select>" +
        (hors ? '<input type="text" id="nb-s-dom" value="' + esc(S.f.domaine) + '" placeholder="netbird.exemple.fr" autocomplete="off" spellcheck="false" aria-label="Domaine du serveur NetBird"><span class="note" style="color:var(--warn)">Cassandra n’administre pas ce domaine : à ta charge, l’enregistrement DNS (A ou AAAA) vers l’adresse publique de cette machine, et le certificat (avec traefik il est demandé tout seul à Let’s Encrypt ; avec nginx ou caddy, c’est ton proxy). Cassandra ne vérifiera ni l’un ni l’autre.</span>' : "") +
        '<span class="note" id="nb-s-verd">' + noteDomaines() + "</span></label>";
    }
    function carteInstallation(s) {
      const f = S.f, d = S.dl, bloque = S.occupe || !s.docker || !s.jq;
      const choix = [["nginx", "nginx (ton nginx publie le serveur)"], ["caddy", "caddy (ton caddy publie le serveur)"], ["traefik", "traefik (tout intégré : ports 80 et 443 libres)"]];
      let h = '<div class="carte"><h2 ' + H2 + ">Installer un serveur NetBird sur cette machine</h2>" +
        '<p class="note">Deux temps : Cassandra télécharge d’abord le script officiel de NetBird, et te montre son empreinte. Elle ne l’exécute qu’après ta confirmation, et seulement s’il n’a pas changé entre-temps.</p>' +
        '<div class="champs"><label class="ch"><b>Version</b><span class="note">Précise (v0.40.0) : jamais « latest ».</span><input type="text" id="nb-s-ver" value="' + esc(f.version) + '" placeholder="v0.40.0" autocomplete="off" spellcheck="false"></label>' +
        champDomaine() +
        '<label class="ch"><b>Adresse e-mail</b><span class="note">Pour les certificats Let’s Encrypt.</span><input type="text" id="nb-s-mel" value="' + esc(f.email) + '" placeholder="admin@exemple.fr" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Proxy</b><span class="note">Qui publie le serveur sur internet.</span><select id="nb-s-prx">' + choix.map((o) => '<option value="' + o[0] + '"' + (f.proxy === o[0] ? " selected" : "") + ">" + o[1] + "</option>").join("") + "</select></label></div>" +
        '';
      if (d) h += '<div class="lien"><h2 ' + H2 + ">Script téléchargé : " + esc(d.version) + '</h2><p class="note">Empreinte SHA-256 (' + esc(d.taille) + ' octets) : compare-la, si tu veux, à celle du script de cette version sur github.com/netbirdio/netbird.</p><span class="u">' + esc(d.sha256) + "</span>" +
        '<div class="acts"><button class="btn pri" data-a="srv-installer"' + (bloque ? " disabled" : "") + ">Installer cette version</button></div></div>";
      else h += '<div class="acts"><button class="btn pri" data-a="srv-telecharger"' + (bloque ? " disabled" : "") + ">Télécharger le script et voir son empreinte</button></div>";
      return h + "</div>";
    }
    function carteServeur(s) {
      const m = s.meta || {}, url = m.domaine ? "https://" + m.domaine : "";
      let h = '<div class="carte"><div class="hero"><div><span class="lib">Serveur</span><span class="pastille ' + (s.conteneurs.some((c) => c.etat === "running") ? "ok" : "al") + '">' + (s.conteneurs.some((c) => c.etat === "running") ? "En marche" : "Arrêté") + "</span></div>" +
        fiche("Domaine", esc(m.domaine || "—")) + fiche("Version", esc(m.version || "—")) + fiche("Proxy", esc(m.proxy || "—")) + fiche("API", s.api_joignable ? "joignable ✓" : "ne répond pas ✗") + "</div>" +
        (s.conteneurs.length ? '<div class="pairs">' + s.conteneurs.map((c) => '<div class="pair" style="grid-template-columns:auto minmax(100px,1fr) minmax(120px,auto)"><span class="pt' + (c.etat === "running" ? " on" : "") + '"></span><span class="nom">' + esc(c.service) + '</span><span class="note">' + esc(c.etat) + " · " + esc(c.image) + "</span></div>").join("") + "</div>" : "") + "</div>";
      if (s.setup_requis && url) h += '<div class="lien"><h2 ' + H2 + ">Dernier pas : crée le premier compte administrateur</h2><p class=\"note\">Ouvre la page d’installation de NetBird et crée toi-même ton compte : Cassandra ne choisit ni ne garde aucun mot de passe. Puis, dans le tableau de bord, crée un jeton d’accès personnel (Settings › Personal Access Tokens) et donne-le à Cassandra depuis la page <b>Administration</b>.</p><div class=\"acts\"><a class=\"btn pri\" href=\"" + esc(url) + '/setup" target="_blank" rel="noopener noreferrer">Ouvrir la page de création du compte</a></div></div>';
      h += '<div class="carte"><h2 ' + H2 + ">Mettre à jour le serveur</h2><p class=\"note\">Télécharge les dernières images NetBird de la version installée, puis redémarre le serveur : les machines se reconnectent seules, les données et la configuration sont gardées.</p><div class=\"acts\"><button class=\"btn pri\" data-a=\"srv-maj\"" + (S.occupe ? " disabled" : "") + ">Mettre à jour le serveur</button></div></div>";
      h += cartePorts() + '<div class="carte"><h2 ' + H2 + ">Entretien</h2><div class=\"acts\"><button class=\"btn\" data-a=\"srv-journaux\"" + (S.occupe ? " disabled" : "") + ">Voir les journaux</button><button class=\"btn\" data-a=\"srv-redemarrer\"" + (S.occupe ? " disabled" : "") + ">Redémarrer</button>" +
        (m.proxy === "nginx" ? '<button class="btn" data-a="srv-nginx"' + (S.occupe ? " disabled" : "") + ">Voir la conf nginx</button>" : "") + "</div>" + carteTexte() + "</div>";
      h += '<div class="carte"><h2 ' + H2 + ">Retirer le serveur</h2><p class=\"note\">Arrête les conteneurs. Les données (comptes, machines, clés) sont gardées : réinstaller retrouve le réseau tel quel.</p><div class=\"acts\">" +
        (S.couper ? '<span class="confirme"><label class="coche"><input type="checkbox" id="nb-s-purge"><span>Supprimer aussi les données : tous les comptes, machines et clés sont perdus, sans retour.</span></label> <button class="btn dng" data-a="srv-retirer-oui">Oui, retirer</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
          : '<button class="btn dng" data-a="srv-retirer"' + (S.occupe ? " disabled" : "") + ">Retirer le serveur…</button>") + "</div></div>";
      return h;
    }
    function carteTexte() {
      return S.txt ? '<div class="acts" style="justify-content:space-between"><b>' + esc(S.txt.titre) + '</b><span><button class="btn" data-a="copier" data-t="' + esc(S.txt.texte) + '">Copier</button> <button class="btn" data-a="txt-fermer">Fermer</button></span></div>' +
        '<pre class="mono" style="margin:0;padding:12px;max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:10px;font-size:11.5px;white-space:pre-wrap">' + esc(S.txt.texte) + "</pre>" : "";
    }
    function pageServeur(s) {
      if (!s.disponible) return '<div class="carte" style="color:var(--warn)">La commande root « serveur » du module ne répond pas : <span class="mono">CN_install.sh --module netbird</span> la pose, et le courtier doit être armé. Détail : ' + esc(s.erreur || "") + "</div>";
      return aiguillage(false) + (s.installe ? carteServeur(s) : cartePrerequis(s) + cartePorts() + carteInstallation(s));
    }

    // ---- l’administration du réseau, par l’API du serveur : machines, clés d’installation, groupes, politiques
    const OGL = [["machines", "Machines"], ["cles", "Clés d’installation"], ["groupes", "Groupes"], ["politiques", "Politiques d’accès"]];
    const coches = (cl, groupes) => groupes.length ? groupes.map((g) => '<label class="coche"><input type="checkbox" class="' + cl + '" value="' + esc(g.id) + '"><span>' + esc(g.nom) + "</span></label>").join("") : '<span class="note">Aucun groupe.</span>';
    const cochees = (cl) => Array.from(racine.querySelectorAll("." + cl + ":checked")).map((x) => x.value);
    const ligne = (g, gauche, droite) => '<div class="pair" style="grid-template-columns:' + g + '">' + gauche + droite + "</div>";
    const bouton = (a, id, lib, cls) => '<button class="btn ' + (cls || "") + '" data-a="' + a + '" data-id="' + esc(id) + '"' + (S.occupe ? " disabled" : "") + ">" + lib + "</button>";
    function carteJeton(ouvert) {
      return '<div class="carte"><details' + (ouvert ? " open" : "") + '><summary style="cursor:pointer;font-weight:650;color:var(--accent)">Accès à l’API du serveur</summary><p class="note" style="margin:8px 0">Le jeton d’accès personnel (tableau de bord NetBird › Settings › Personal Access Tokens) donne à Cassandra la main d’un administrateur sur le réseau. Il est gardé comme un secret, jamais relu ni écrit au journal. Sans adresse, Cassandra utilise celle du serveur qu’elle a installé.</p>' +
        '<div class="champs"><label class="ch"><b>Adresse de l’API</b><input type="text" id="nb-j-url" placeholder="https://netbird.exemple.fr" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Jeton d’accès</b><input type="password" id="nb-j-jeton" placeholder="nbp_…" autocomplete="off" spellcheck="false"></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="jeton-enregistrer"' + (S.occupe ? " disabled" : "") + '>Enregistrer</button><button class="btn dng" data-a="jeton-oublier"' + (S.occupe ? " disabled" : "") + ">Oublier le jeton</button></div></details></div>";
    }
    function ongletMachines(g) {
      if (!g.machines.length) return '<p class="note">Aucune machine dans ce réseau pour l’instant.</p>';
      return '<div class="pairs">' + g.machines.map((p) => ligne("auto minmax(130px,1fr) minmax(110px,auto) auto",
        '<span class="pt' + (p.connecte ? " on" : "") + '"></span><span class="nom">' + (S.edit === p.id ? '<input type="text" id="nb-m-nom" value="' + esc(p.nom) + '" autocomplete="off" spellcheck="false">' : esc(p.nom)) +
        '<br><span class="note">' + esc([p.os, p.version, p.groupes.join(", "), p.ssh ? "SSH" : "", p.expiree ? "session expirée" : "", p.connecte ? "en ligne" : age(p.vu)].filter(Boolean).join(" · ")) + "</span></span>",
        '<span class="mono note">' + esc(p.ip) + "</span>" + '<span class="acts" style="gap:4px">' + (S.edit === p.id ? bouton("m-ok", p.id, "Valider", "pri") + bouton("m-non", p.id, "Annuler") :
          bouton("m-renommer", p.id, "Renommer") + bouton("m-ssh", p.id, p.ssh ? "SSH ✓" : "SSH") + bouton("m-suppr", p.id, "Retirer", "dng")) + "</span>")).join("") + "</div>";
    }
    function ongletCles(g) {
      let h = S.cle ? '<div class="lien"><h2 ' + H2 + ">Clé « " + esc(S.cle.nom) + " » créée</h2><p class=\"note\">Copie-la maintenant : NetBird ne la montre qu’une fois, et Cassandra ne la garde nulle part.</p><span class=\"u\">" + esc(S.cle.cle) + '</span><div class="acts"><button class="btn pri" data-a="copier" data-t="' + esc(S.cle.cle) + '">Copier la clé</button><button class="btn" data-a="cle-ok">C’est noté, fermer</button></div></div>' : "";
      h += '<details><summary style="cursor:pointer;font-weight:650;color:var(--accent)">Créer une clé d’installation</summary><div class="champs" style="margin:10px 0"><label class="ch"><b>Nom</b><input type="text" id="nb-k-nom" placeholder="portable-de-paul" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Type</b><select id="nb-k-type"><option value="reusable">Réutilisable</option><option value="one-off">Un seul usage</option></select></label>' +
        '<label class="ch"><b>Valable (jours)</b><input type="text" id="nb-k-jours" value="30" autocomplete="off"></label><label class="ch"><b>Groupes d’arrivée</b><span class="champs" style="grid-template-columns:1fr">' + coches("nb-k-g", g.groupes) + "</span></label></div>" +
        '<div class="acts"><button class="btn pri" data-a="cle-creer"' + (S.occupe ? " disabled" : "") + ">Créer la clé</button></div></details>";
      h += g.cles.length ? '<div class="pairs">' + g.cles.map((k) => ligne("minmax(130px,1fr) minmax(120px,auto) auto", '<span class="nom">' + esc(k.nom) + '<br><span class="note">' + esc([k.type, k.utilisations + " utilisation(s)" + (k.limite ? " sur " + k.limite : ""), k.expire ? "expire le " + k.expire : "", k.groupes.join(", ")].filter(Boolean).join(" · ")) + "</span></span>",
        '<span class="pastille ' + (k.revoquee ? "dg" : k.valide ? "ok" : "al") + '">' + (k.revoquee ? "révoquée" : k.valide ? "valide" : "épuisée / expirée") + '</span><span class="acts" style="gap:4px">' + bouton("k-revoquer", k.id, k.revoquee ? "Rétablir" : "Révoquer") + bouton("k-suppr", k.id, "Supprimer", "dng") + "</span>")).join("") + "</div>" : '<p class="note">Aucune clé d’installation.</p>';
      return h;
    }
    function ongletGroupes(g) {
      return '<div class="acts"><input type="text" id="nb-g-nom" placeholder="Nom du nouveau groupe" style="flex:1 1 220px" autocomplete="off" spellcheck="false"><button class="btn pri" data-a="g-creer"' + (S.occupe ? " disabled" : "") + ">Créer le groupe</button></div>" +
        '<div class="pairs">' + g.groupes.map((x) => ligne("minmax(130px,1fr) auto auto", '<span class="nom">' + esc(x.nom) + "</span>", '<span class="note">' + x.machines + " machine(s)</span>" + (x.nom === "All" ? "<span></span>" : bouton("g-suppr", x.id, "Supprimer", "dng")))).join("") + "</div>";
    }
    function ongletPolitiques(g) {
      let h = '<details><summary style="cursor:pointer;font-weight:650;color:var(--accent)">Créer une politique d’accès</summary><div class="champs" style="margin:10px 0"><label class="ch"><b>Nom</b><input type="text" id="nb-p-nom" placeholder="Équipe vers serveurs" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Protocole</b><select id="nb-p-proto"><option value="all">Tous</option><option value="tcp">TCP</option><option value="udp">UDP</option><option value="icmp">ICMP</option></select></label>' +
        '<label class="ch"><b>Sources</b><span class="champs" style="grid-template-columns:1fr">' + coches("nb-p-src", g.groupes) + '</span></label><label class="ch"><b>Destinations</b><span class="champs" style="grid-template-columns:1fr">' + coches("nb-p-dst", g.groupes) + "</span></label></div>" +
        '<label class="coche"><input type="checkbox" id="nb-p-bi" checked><span>Dans les deux sens</span></label><div class="acts" style="margin-top:8px"><button class="btn pri" data-a="p-creer"' + (S.occupe ? " disabled" : "") + ">Créer la politique</button></div></details>";
      h += g.politiques.length ? '<div class="pairs">' + g.politiques.map((p) => ligne("minmax(130px,1fr) minmax(110px,auto) auto", '<span class="nom">' + esc(p.nom) + '<br><span class="note">' + esc(p.regles.map((r) => r.sources.join(", ") + " → " + r.destinations.join(", ") + " (" + r.protocole + (r.bidirectionnel ? ", 2 sens" : "") + (r.action === "drop" ? ", bloque" : "") + ")").join(" · ")) + "</span></span>",
        '<span class="pastille ' + (p.actif ? "ok" : "mu") + '">' + (p.actif ? "active" : "désactivée") + '</span><span class="acts" style="gap:4px">' + bouton("p-actif", p.id, p.actif ? "Désactiver" : "Activer") + bouton("p-suppr", p.id, "Supprimer", "dng") + "</span>")).join("") + "</div>" : '<p class="note">Aucune politique d’accès : sans elle, les machines ne se joignent pas.</p>';
      return h;
    }
    function pageGestion() {
      const g = S.g;
      if (!g) return carteJeton(true);
      const n = { machines: g.machines.length, cles: g.cles.length, groupes: g.groupes.length, politiques: g.politiques.length };
      return '<div class="carte"><div class="acts">' + OGL.map((o) => '<button class="btn' + (S.onglet === o[0] ? " pri" : "") + '" data-a="onglet" data-id="' + o[0] + '">' + o[1] + " (" + n[o[0]] + ")</button>").join("") + "</div>" +
        (S.onglet === "machines" ? ongletMachines(g) : S.onglet === "cles" ? ongletCles(g) : S.onglet === "groupes" ? ongletGroupes(g) : ongletPolitiques(g)) + "</div>" + carteJeton(false);
    }

    function dessiner() {
      const e = S.e, t = TITRES[page];
      let h = '<div class="tete"><h1>NetBird' + (t[0] ? ' <span class="note" style="font-weight:500">› ' + esc(t[0]) + "</span>" : "") + '</h1><p class="sous">' + esc(t[1]) + '</p><div class="acts" style="margin-top:8px"><button class="btn" data-a="relire">Relire</button><span class="note">' +
        (S.lu ? "Relu à " + new Date(S.lu).toLocaleTimeString() : "") + "</span></div></div>";
      if (S.erreur) h += '<div class="carte" role="alert" style="color:var(--danger)">' + esc(S.erreur) + '<div class="acts"><button class="btn" data-a="relire">Réessayer</button></div></div>';
      if (page === "gestion") { racine.innerHTML = h + (S.lu || S.erreur ? pageGestion() : '<div class="attente" role="status" aria-live="polite">Lecture du réseau…</div>'); lier(); return; }
      if (page === "serveur") { racine.innerHTML = h + (S.s ? pageServeur(S.s) : '<div class="attente" role="status" aria-live="polite">Lecture du serveur…</div>'); lier(); return; }
      if (!e) { racine.innerHTML = h + '<div class="attente" role="status" aria-live="polite">Lecture de l’état de NetBird…</div>'; return; }
      h += page === "vue" ? pageVue(e) : page === "machines" ? pageMachines(e) : page === "installation" ? pageInstallation(e) : pageHistorique(e);
      racine.innerHTML = h; lier();
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
      const px = racine.querySelector("#nb-s-prx");
      if (px) px.addEventListener("change", async () => { S.f = lireForm(); try { S.pt = await agir("netbird.serveur_ports", { proxy: S.f.proxy }); } catch (_) { /* la carte garde l’ancienne vue */ } dessiner(); });
      const ds = racine.querySelector("#nb-s-domsel");
      if (ds) ds.addEventListener("change", () => { S.f = lireForm(); if (S.f.hors) S.f.domaine = ""; dessiner(); });
      const qi = racine.querySelector("#nb-q"), fi = racine.querySelector("#nb-f"), n = racine.querySelector("#nb-nom");
      if (qi) qi.addEventListener("input", () => { S.q = qi.value; dessiner(); const n2 = racine.querySelector("#nb-q"); if (n2) { n2.focus(); n2.setSelectionRange(n2.value.length, n2.value.length); } });
      if (fi) fi.addEventListener("change", () => { S.filtre = fi.value; dessiner(); });
      if (n) n.addEventListener("input", () => { S.nom = n.value; });
    }
    const val = (id) => String((racine.querySelector(id) || {}).value || "").trim();

    async function geste(b) {
      const a = b.dataset.a;
      if (a === "relire") return charger();
      if (a === "copier") return copier(b.dataset.t);
      if (a === "vers-installation") { if (CASS.ouvrirEcran) CASS.ouvrirEcran("netbird:n_installation", "Client"); return; }
      if (a === "vers-serveur") { if (CASS.ouvrirEcran) CASS.ouvrirEcran("netbird:n_serveur", "Serveur"); return; }
      if (a === "annuler") return faire(() => agir("netbird.annuler"), "Connexion abandonnée.");
      if (a === "deconnecter") { S.couper = true; dessiner(); return; }
      if (a === "deconnecter-non") { S.couper = false; dessiner(); return; }
      if (a === "deconnecter-oui") return faire(() => agir("netbird.deconnecter"), "NetBird est coupé sur cette machine.");
      if (a === "defaire-geste") return faire(() => agir("netbird.defaire_geste", { id: parseInt(b.dataset.id, 10) }), "Geste défait.");
      if (a === "connecter") return faire(() => agir("netbird.connecter", { nom: val("#nb-nom") }), "");
      if (a === "cle") {
        const cle = val("#nb-cle");
        if (!/^[A-Za-z0-9_-]{16,128}$/.test(cle)) { dire("Une clé d’installation du type XXXXXXXX-XXXX-…", "err"); return; }
        return faire(() => avecCle(cle, () => agir("netbird.connecter", { nom: val("#nb-nom"), avec_cle: true })), "Machine connectée à NetBird.");
      }
      if (a === "installer") {
        const tag = val("#nb-tag") || "latest", cle = val("#nb-i-cle");
        if (cle && !/^[A-Za-z0-9_-]{16,128}$/.test(cle)) { dire("Une clé d’installation du type XXXXXXXX-XXXX-…", "err"); return; }
        if (!confirm("Installer le client NetBird dans un conteneur Docker (netbirdio/netbird:" + tag + ") ? L’image est téléchargée depuis Docker Hub.")) return;
        const args = { tag: tag, nom: val("#nb-i-nom"), url: val("#nb-i-url") };
        return faire(() => (cle ? avecCle(cle, () => agir("netbird.installer_docker", Object.assign({ avec_cle: true }, args))) : agir("netbird.installer_docker", args)), "NetBird est installé dans Docker.");
      }
      if (a === "client-maj") {
        if (!confirm("Mettre à jour le client NetBird ? L’image est téléchargée ; si elle a changé, le conteneur est recréé (identité gardée) et la machine est coupée quelques secondes.")) return;
        return faire(async () => { const r = await agir("netbird.mettre_a_jour_client"); dire(r && r.maj_change ? "Client NetBird mis à jour." : "Le client NetBird est déjà à jour."); }, "");
      }
      if (a === "txt-fermer") { S.txt = null; dessiner(); return; }
      if (a === "onglet") { S.onglet = b.dataset.id; S.edit = ""; dessiner(); return; }
      if (a === "cle-ok") { S.cle = null; dessiner(); return; }
      if (a === "jeton-enregistrer") {
        const jeton = val("#nb-j-jeton"), url = val("#nb-j-url");
        if (jeton && !/^[A-Za-z0-9_.-]{16,300}$/.test(jeton)) { dire("Un jeton d’accès personnel NetBird (nbp_…)", "err"); return; }
        if (!jeton && !url) { dire("Rien à enregistrer", "err"); return; }
        return faire(async () => { if (jeton) await agir("reglages.regler_secret", { cle: "netbird.jeton_api", valeur: jeton }); if (url) await agir("reglages.regler", { cle: "netbird.url_api", valeur: url }); }, "Accès à l’API enregistré.");
      }
      if (a === "jeton-oublier") { if (!confirm("Oublier le jeton d’accès ? Cassandra ne pourra plus administrer le réseau.")) return; return faire(() => agir("reglages.reinitialiser", { cle: "netbird.jeton_api" }), "Jeton oublié."); }
      // ---- le serveur
      if (a === "srv-telecharger") {
        S.f = lireForm();
        const dm = await agir("netbird.serveur_domaines", { domaine: S.f.domaine }).catch((e) => ({ administre: false, libre: false, raison: e.message || String(e) }));
        if (!dm.administre && !dm.libre && !S.f.hors) { dire(dm.raison || "Domaine non administré par Cassandra.", "err"); return; }
        return faire(async () => { S.dl = await agir("netbird.serveur_telecharger", { version: S.f.version }); }, "Script téléchargé : vérifie son empreinte.");
      }
      if (a === "srv-installer") {
        S.f = lireForm();
        if (S.f.version !== S.dl.version) { dire("La version a changé : retélécharge le script.", "err"); S.dl = null; dessiner(); return; }
        if (!confirm("Installer le serveur NetBird " + S.f.version + " pour " + S.f.domaine + " (proxy " + S.f.proxy + ") ?" + (S.f.hors ? "\nDomaine non administré par Cassandra : son DNS et son certificat sont à ta charge." : "") + "\nScript d’empreinte " + S.dl.sha256.slice(0, 16) + "…\nIl télécharge les images NetBird et, avec traefik, demande un certificat Let’s Encrypt.")) return;
        return faire(async () => { await agir("netbird.serveur_installer", { version: S.f.version, sha256: S.dl.sha256, domaine: S.f.domaine, email: S.f.email, proxy: S.f.proxy, hors_cassandra: S.f.hors }); S.dl = null; }, "Serveur NetBird installé.");
      }
      if (a === "srv-redemarrer") { if (!confirm("Redémarrer le serveur NetBird ? Les machines se reconnectent seules.")) return; return faire(() => agir("netbird.serveur_redemarrer"), "Serveur redémarré."); }
      if (a === "srv-maj") { if (!confirm("Mettre à jour les images du serveur NetBird ? Elles sont téléchargées puis le serveur redémarre.")) return; return faire(() => agir("netbird.serveur_mettre_a_jour"), "Serveur mis à jour."); }
      if (a === "srv-journaux") return faire(async () => { S.txt = { titre: "Journaux du serveur (80 dernières lignes)", texte: (await agir("netbird.serveur_journaux")).journaux || "(vide)" }; }, "");
      if (a === "srv-nginx") return faire(async () => { S.txt = { titre: "Configuration nginx à publier", texte: (await agir("netbird.serveur_nginx")).conf || "" }; }, "");
      if (a === "srv-retirer") { S.couper = true; dessiner(); return; }
      if (a === "srv-retirer-oui") { const purger = !!(racine.querySelector("#nb-s-purge") || {}).checked; return faire(() => agir("netbird.serveur_retirer", { purger: purger }), purger ? "Serveur et données retirés." : "Serveur retiré (données gardées)."); }
      // ---- le réseau
      if (a === "m-renommer") { S.edit = b.dataset.id; dessiner(); return; }
      if (a === "m-non") { S.edit = ""; dessiner(); return; }
      if (a === "m-ok") { const nom = val("#nb-m-nom"), id = b.dataset.id; return faire(async () => { await agir("netbird.machine_modifier", { id: id, nom: nom }); S.edit = ""; }, "Machine renommée."); }     // lu AVANT faire : faire redessine, et le champ reprendrait l’ancien nom
      if (a === "m-ssh") { const m = S.g.machines.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.machine_modifier", { id: b.dataset.id, ssh: !(m && m.ssh) }), "SSH modifié."); }
      if (a === "m-suppr") { if (!confirm("Retirer cette machine du réseau NetBird ? Elle devra se reconnecter avec une clé.")) return; return faire(() => agir("netbird.machine_supprimer", { id: b.dataset.id }), "Machine retirée du réseau."); }
      if (a === "cle-creer") {
        const nom = val("#nb-k-nom"), args = { nom: nom, type: val("#nb-k-type"), jours: parseInt(val("#nb-k-jours"), 10) || 30, groupes: cochees("nb-k-g") };
        if (!nom) { dire("Donne un nom à la clé", "err"); return; }
        return faire(async () => { const r = await agir("netbird.cle_creer", args); S.cle = { nom: r.nom, cle: r.cle_secrete }; }, "Clé créée : copie-la maintenant.");
      }
      if (a === "k-revoquer") { const k = S.g.cles.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.cle_revoquer", { id: b.dataset.id, revoquer: !(k && k.revoquee) }), "Clé modifiée."); }
      if (a === "k-suppr") { if (!confirm("Supprimer cette clé d’installation ?")) return; return faire(() => agir("netbird.cle_supprimer", { id: b.dataset.id }), "Clé supprimée."); }
      if (a === "g-creer") { const nom = val("#nb-g-nom"); if (!nom) { dire("Donne un nom au groupe", "err"); return; } return faire(() => agir("netbird.groupe_creer", { nom: nom }), "Groupe créé."); }
      if (a === "g-suppr") { if (!confirm("Supprimer ce groupe ? NetBird refuse tant qu’une règle ou une clé l’utilise.")) return; return faire(() => agir("netbird.groupe_supprimer", { id: b.dataset.id }), "Groupe supprimé."); }
      if (a === "p-creer") {
        const nom = val("#nb-p-nom"), src = cochees("nb-p-src"), dst = cochees("nb-p-dst");
        if (!nom || !src.length || !dst.length) { dire("Un nom, au moins un groupe source et un groupe destination", "err"); return; }
        const args = { nom: nom, sources: src, destinations: dst, protocole: val("#nb-p-proto") || "all", bidirectionnel: !!(racine.querySelector("#nb-p-bi") || {}).checked };     // lus AVANT faire (qui redessine)
        return faire(() => agir("netbird.politique_creer", args), "Politique créée.");
      }
      if (a === "p-actif") { const p = S.g.politiques.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.politique_activer", { id: b.dataset.id, actif: !(p && p.actif) }), "Politique modifiée."); }
      if (a === "p-suppr") { if (!confirm("Supprimer cette politique d’accès ? Les machines qu’elle reliait ne se joindront plus.")) return; return faire(() => agir("netbird.politique_supprimer", { id: b.dataset.id }), "Politique supprimée."); }
      if (a === "retirer") { S.couper = true; dessiner(); return; }
      if (a === "retirer-oui") {
        const purger = !!(racine.querySelector("#nb-purge") || {}).checked;
        return faire(() => agir("netbird.retirer_docker", { purger: purger }), purger ? "Conteneur et volume retirés." : "Conteneur retiré (son volume est gardé).");
      }
    }

    racine.innerHTML = '<div class="attente" role="status" aria-live="polite">Lecture de l’état de NetBird…</div>';
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin des pages et leurs gestes.
// EC : néant.
// LIEN : modules/netbird (le module et ses capacités), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
