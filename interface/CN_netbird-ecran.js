// ═════════════════════════════════════════════════════════════════
// TITRE      : NetBird : l’écran
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #673786
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les pages « NetBird » du module netbird : où en est la machine, sa connexion (par un lien à ouvrir ou par une clé), les machines du réseau, l’installation du client dans Docker, l’historique des gestes.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.netbird) ; la page vient de l’écran ouvert (ctx.ecran = « netbird:n_machines ») ; tout vient de netbird.etat ; l’état se relit seul (20 s, 2,5 s pendant une identification), jamais sous les doigts de quelqu’un qui tape.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=673786 ▼▼▼
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
    "@media (max-width:820px){.nb .pair{grid-template-columns:auto minmax(0,1fr) auto}.nb .pair .ip{grid-column:2 / -1}}" +
    "@media (max-width:620px){.nb .pair[style*=\"grid-template-columns\"]{grid-template-columns:minmax(0,1fr) !important}.nb .acts{flex-wrap:wrap}}";

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

    const S = { e: null, occupe: false, erreur: "", couper: false, q: "", filtre: "tous", j: null, lu: 0, nom: "", s: null, g: null, onglet: "machines", edit: "", cle: null, txt: null, dl: null, f: { version: "", domaine: "", email: "", proxy: "nginx", hors: false }, pt: null,
      cMode: "docker", px: null, pj: false, v: null, sBack: true, pf: null, sv: null, ipm: null, ipSaisie: "", dnsv: null, dmv: null };
    let minuterie = null;

    async function charger(silencieux) {
      try {
        if (page === "serveur") { S.s = await agir("netbird.serveur_etat"); S.dm = S.s.installe ? null : await agir("netbird.serveur_domaines").catch(() => null); S.pt = await agir("netbird.serveur_ports", S.s.installe ? {} : { proxy: S.f.proxy }).catch(() => null);
          S.pf = await agir("netbird.pare_feu_etat", { proxy: S.s.installe ? (S.s.meta || {}).proxy || "" : S.f.proxy }).catch(() => null);
          S.sv = S.s.installe ? await agir("netbird.serveur_sauvegardes").catch(() => null) : null;
          await chargerDns();
          const dom = S.s.installe ? (S.s.meta || {}).domaine : "";
          S.px = dom ? await agir("netbird.serveur_proxy_etat", { domaine: dom }).catch(() => null) : null;
          S.pj = !!(S.px && S.px.routes_ok && !S.s.setup_requis) && await agir("netbird.api_verifier").then(() => true).catch(() => false); }
        else if (page === "gestion") S.g = await chargerReseau();
        else S.e = await agir("netbird.etat");
        if (page === "vue" || page === "installation" || page === "serveur") S.v = await agir("netbird.versions").catch(() => null);
        if (page === "serveur" && !S.f.version && S.v && S.v.derniere) S.f.version = S.v.derniere;            // personne ne devine la dernière version : on la propose
        S.erreur = ""; S.lu = Date.now();
      } catch (e) { S.erreur = e.message || String(e); if (page === "gestion") S.g = null; }
      if (page === "historique") { try { S.j = (await agir("netbird.journal", { limite: 30 })).gestes; } catch (_) { S.j = null; } }
      if (!silencieux || document.body.contains(racine)) dessiner();
      armer();
    }
    // Le DNS du domaine du serveur : l’adresse de la machine, ce que le domaine devient dans les zones de Cassandra, et s’il se résout déjà vers elle
    async function chargerDns() {
      const s = S.s || {};
      if (!s.installe && !S.f.domaine && !S.f.hors && S.dm && S.dm.propositions && S.dm.propositions.length) S.f.domaine = S.dm.propositions[0];      // la liste montre déjà ce domaine : c'est lui qu'on installe si on ne touche à rien
      const dom = s.installe ? (s.meta || {}).domaine : S.f.domaine;
      if (!S.ipm) S.ipm = await agir("netbird.serveur_ip").catch(() => null);
      S.dmv = dom ? await agir("netbird.serveur_domaines", { domaine: dom }).catch(() => null) : null;
      const ip = S.ipSaisie || (S.ipm ? S.ipm.ip : "");
      S.dnsv = dom && ip ? await agir("netbird.serveur_dns_verifier", { domaine: dom, ip: ip }).catch(() => null) : null;
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
    // « Es-tu sûr ? » : la fenêtre de Cassandra (une promesse), jamais confirm() natif, que le navigateur d’une application peut taire : le clic ne ferait alors plus rien.
    const demander = (texte, oui) => {
      const danger = /Retirer|Supprimer|Désinstaller|Oublier|Restaurer|SANS sauvegarde/.test(texte);
      if (!(CASS.kit && CASS.kit.confirmer)) return Promise.resolve(window.confirm(texte));
      return CASS.kit.confirmer("Confirmer", "<p>" + esc(texte).split(String.fromCharCode(10)).join("<br>") + "</p>", oui || "Oui, continuer", danger);
    };
    const faire = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; S.echec = ""; dessiner();
      try { await f(); if (ok) dire(ok); } catch (e) { dire(e.message || String(e), "err"); S.erreur = e.message || String(e); S.echec = S.erreur; }      // l’échec reste affiché : la relecture qui suit effacerait l’erreur, et le clic semblerait ne rien faire
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
          '<span class="note">relais ' + e.relais_dispo + "/" + e.relais_total + " · client " + esc(e.version) + (S.v && S.v.client_a_jour === false ? " (mise à jour : " + esc(S.v.derniere) + ")" : "") + (e.mode === "docker" ? " · dans Docker" : e.natif ? " · natif" : "") + "</span></div>" : "") + "</div></div>";
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
      let h = '<div class="carte"><div class="acts" style="justify-content:space-between"><h2 ' + H2 + '>Les machines du réseau <span class="note">(' + e.en_ligne + " autre(s) en ligne sur " + pairs.length + ")</span></h2></div>";
      if (pairs.length > 3) h += '<div class="acts"><input type="text" id="nb-q" placeholder="Chercher une machine, une adresse…" value="' + esc(S.q) + '" style="flex:1 1 220px"><select id="nb-f">' +
        [["tous", "Toutes"], ["en_ligne", "En ligne"], ["hors_ligne", "Hors ligne"]].map((o) => '<option value="' + o[0] + '"' + (S.filtre === o[0] ? " selected" : "") + ">" + o[1] + "</option>").join("") + "</select></div>";
      if (e.nom || e.ip) h += '<div class="pairs"><div class="pair" style="grid-template-columns:auto minmax(0,1fr) auto"><span class="pt on"></span><span class="nom">' + esc(e.nom || "cette machine") + ' <span class="pastille ok">cette machine</span></span><span class="mono ip note">' + esc(e.ip || "") + (e.ip ? copie(e.ip) : "") + "</span></div></div>" +
        '<p class="note">Cette page montre cette machine puis les autres que le client voit. La liste complète du réseau, avec toutes les machines, est dans Administration.</p>';
      h += vus.length ? '<div class="pairs">' + vus.map(ligneMachine).join("") + "</div>" : '<p class="note">' + (pairs.length ? "Aucune machine ne correspond." : "Aucune autre machine sur ce réseau pour l’instant : elles apparaîtront ici dès qu’elles rejoindront le réseau.") + "</p>";
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
    // Versions : ce qui est installé et la dernière publiée par NetBird (GitHub) ; « inconnu » quand on ne peut pas comparer
    function ligneVersion(installee, aJour, derniere) {
      return '<p class="note">Installée : <b>' + esc(installee || "inconnue") + "</b> · dernière publiée : <b>" + esc(derniere || "inconnue") + "</b>" + (aJour === true ? " : à jour." : aJour === false ? " : une mise à jour est disponible." : " : on ne peut pas comparer.") + (S.v && S.v.erreur ? " (" + esc(S.v.erreur) + ")" : "") + "</p>";
    }
    function pageInstallation(e) {
      const nonRoot = e.courtier === false, conteneurLa = e.conteneur === "en_marche" || e.conteneur === "arrete", v = S.v || {};
      const oui = (b) => '<span class="pastille ' + (b ? "ok" : "mu") + '">' + (b ? "oui" : "non") + "</span>";
      let h = aiguillage(true) + '<div class="carte"><h2 ' + H2 + ">Ce qui existe sur cette machine</h2><div class=\"hero\">" +
        '<div><span class="lib">Client NetBird installé</span>' + oui(e.natif) + "</div><div><span class=\"lib\">Docker</span>" + oui(e.docker) + "</div>" +
        '<div><span class="lib">Conteneur « ' + esc(e.nom_conteneur) + '»</span><span class="pastille ' + (e.conteneur === "en_marche" ? "ok" : e.conteneur === "absent" ? "mu" : "al") + '">' +
        esc({ en_marche: "en marche", arrete: "arrêté", absent: "absent", autre: "autre service (intouché)" }[e.conteneur] || e.conteneur) + "</span></div>" +
        ((e.natif || conteneurLa) ? '<div><span class="lib">Version du client</span><span class="gros" style="font-size:16px">' + esc(v.client || e.version || "—") + '</span><span class="note">' + (v.client_a_jour === true ? "à jour" : v.client_a_jour === false ? "disponible : " + esc(v.derniere) : "") + "</span></div>" : "") +
        '<div><span class="lib">Utilisé par Cassandra</span><span class="gros" style="font-size:16px">' + esc({ natif_direct: "client natif", natif_racine: "client natif (par le courtier)", docker: "conteneur Docker", absent: "—" }[e.mode] || e.mode) + "</span></div></div></div>";
      h = aiguillage(true) + avisConflit(e) + h.slice(aiguillage(true).length);
      if (nonRoot) h += '<div class="carte" style="color:var(--warn)">Le courtier ne répond pas ou la commande root du module n’est pas posée : <span class="mono">CN_install.sh --module netbird</span> la pose. Sans elle, ni Docker ni le paquet ne se pilotent d’ici.</div>';
      const natif = S.cMode === "natif", autre = e.conteneur === "autre";
      const bloque = S.occupe || nonRoot || e.natif || conteneurLa || autre || (!natif && !e.docker);
      h += '<div class="carte"><h2 ' + H2 + ">Installer le client NetBird</h2>" +
        (natif ? '<p class="note">Installe le paquet officiel de NetBird (apt ou dnf, par le courtier) : le client tourne comme un service de la machine. Un seul client par machine. Ensuite, connecte la machine depuis la <b>Vue d’ensemble</b>.</p>'
          : '<p class="note">Crée le conteneur officiel <span class="mono">netbirdio/netbird</span> : il redémarre avec la machine, utilise le réseau de la machine et garde son identité dans un volume. Aucun autre conteneur n’est touché.</p>') +
        (e.natif ? '<p class="note" style="color:var(--warn)">Un client NetBird est déjà installé sur cette machine : un seul client par machine. Utilise celui-là, ou désinstalle-le avant d’en installer un autre.</p>' : conteneurLa ? '<p class="note" style="color:var(--warn)">Un conteneur NetBird existe déjà : un seul client par machine. Retire-le avant d’installer le paquet.</p>' : !natif && !e.docker ? '<p class="note" style="color:var(--warn)">Docker n’est pas installé sur cette machine : choisis « Natif ».</p>' : autre ? '<p class="note" style="color:var(--warn)">Un conteneur « ' + esc(e.nom_conteneur) + ' » existe déjà mais n’est pas NetBird : change le réglage « conteneur ».</p>' : "") +
        '<div class="champs"><label class="ch"><b>Où l’installer</b><span class="note">Docker (conseillé : isolé, facile à mettre à jour) ou natif (paquet officiel, service de la machine).</span><select id="nb-i-mode"><option value="docker"' + (natif ? "" : " selected") + '>Dans Docker</option><option value="natif"' + (natif ? " selected" : "") + ">Natif (paquet officiel)</option></select></label>" +
        (natif ? "" : '<label class="ch"><b>Version</b><span class="note">latest, ou une version précise (0.40.0).</span><input type="text" id="nb-tag" value="latest" autocomplete="off" spellcheck="false"></label>' +
          '<label class="ch"><b>Nom de la machine</b><span class="note">Facultatif.</span><input type="text" id="nb-i-nom" placeholder="argos" autocomplete="off" spellcheck="false"></label>' +
          '<label class="ch"><b>Serveur de gestion</b><span class="note">Vide : NetBird Cloud (ou le réglage « url_gestion »).</span><input type="text" id="nb-i-url" placeholder="https://netbird.exemple.fr:443" autocomplete="off" spellcheck="false"></label>' +
          '<label class="ch"><b>Clé d’installation</b><span class="note">Facultatif : avec elle le conteneur se connecte seul ; sans elle, un lien à ouvrir.</span><input type="password" id="nb-i-cle" placeholder="XXXXXXXX-XXXX-…" autocomplete="off" spellcheck="false"></label>') + "</div>" +
        '<div class="acts"><button class="btn pri" data-a="' + (natif ? "installer-natif" : "installer") + '"' + (bloque ? " disabled" : "") + ">" + (natif ? "Installer le client natif" : "Installer dans Docker") + "</button></div></div>";
      if (conteneurLa || e.natif) {
        const aJour = v.client_a_jour === true;
        h += '<div class="carte"><h2 ' + H2 + ">Mettre à jour le client</h2>" + ligneVersion(v.client || e.version, v.client_a_jour, v.derniere) +
          '<p class="note">' + (e.natif ? "Le paquet est mis à jour par le gestionnaire de paquets de la machine (apt ou dnf), par le courtier." : "L’image est téléchargée et, si elle a changé, le conteneur est recréé avec son volume : la machine est coupée quelques secondes, son identité est gardée.") + " Le geste peut être défait depuis l’Historique.</p>" +
          '<div class="acts"><button class="btn pri" data-a="client-maj"' + (S.occupe || nonRoot || aJour ? " disabled" : "") + ">" + (aJour ? "Déjà à jour" : v.client_a_jour === false ? "Mettre à jour vers " + esc(v.derniere) : "Mettre à jour le client") + "</button></div></div>";
      }
      if (conteneurLa) {
        h += '<div class="carte"><h2 ' + H2 + ">Retirer le conteneur</h2><p class=\"note\">Le volume est gardé : une réinstallation retrouve l’identité de la machine dans NetBird.</p><div class=\"acts\">" +
          (S.couper ? '<span class="confirme"><label class="coche"><input type="checkbox" id="nb-purge"><span>Supprimer aussi le volume : la machine perd son identité et il faudra une nouvelle identification.</span></label> <button class="btn dng" data-a="retirer-oui">Oui, retirer</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
            : '<button class="btn dng" data-a="retirer"' + (S.occupe || nonRoot ? " disabled" : "") + ">Retirer le conteneur…</button>") + "</div></div>";
      }
      if (e.natif) h += '<div class="carte"><h2 ' + H2 + ">Désinstaller le client natif</h2><p class=\"note\">Retire le paquet NetBird de la machine. La machine reste enregistrée dans le réseau : elle pourra se reconnecter.</p><div class=\"acts\"><button class=\"btn dng\" data-a=\"natif-retirer\"" + (S.occupe || nonRoot ? " disabled" : "") + ">Désinstaller le client…</button></div></div>";
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
    // Le pas à pas : tout ce qu’il faut pour avoir un serveur NetBird qui marche, dans l’ordre, avec l’état de chaque étape et le bouton qui la fait quand Cassandra le peut.
    function etapesServeur(s) {
      const dom = s.installe ? (s.meta || {}).domaine : S.f.domaine, pf = S.pf, px = S.px, inst = !!s.installe && !s.partiel;
      const portsOk = !pf || !pf.outil || !pf.actif || (pf.publics || []).every((p) => (pf.ouverts || []).includes(p));
      const dnsOk = !!(S.dnsv && S.dnsv.correspond), routesOk = !!(px && px.routes_ok), compteFait = inst && routesOk && !s.setup_requis;
      const manque = pf ? (pf.publics || []).filter((p) => !(pf.ouverts || []).includes(p)) : [];
      const urlSetup = dom ? "https://" + dom + "/setup" : "";
      return [
        { t: "Docker", ok: !!s.docker, aide: s.docker ? "" : "Cassandra ne l’installe pas : installe-le d’abord, puis relis la page." },
        { t: "Docker Compose", ok: !!s.compose, aide: s.compose ? "" : "Le script officiel d’installation du serveur en a besoin.", act: !s.compose && s.docker ? ["srv-compose", "Installer Docker Compose"] : null },
        { t: "jq", ok: !!s.jq, aide: s.jq ? "" : "Le script officiel d’installation du serveur en a besoin.", act: !s.jq ? ["srv-jq", "Installer jq"] : null },
        { t: "Un domaine pour le serveur, qui pointe vers cette machine", ok: !!dom && dnsOk,
          aide: !dom ? "Choisis le domaine du serveur dans le formulaire plus bas (un nom réservé à NetBird, pas celui de Cassandra)." : dnsOk ? "" : "Le domaine ne pointe pas encore vers cette machine : crée l’enregistrement DNS (carte « Enregistrement DNS » plus bas). Avec nginx derrière FASTPANEL, crée aussi dans FASTPANEL un site « reverse proxy » vers 127.0.0.1:8080, avec un certificat." },
        { t: "Ports ouverts dans le pare-feu", ok: portsOk, aide: portsOk ? "" : "443/tcp et 3478/udp (et 80/tcp avec traefik) doivent être ouverts sur internet.", act: !portsOk && manque.length ? ["pf-ouvrir", "Ouvrir " + manque.join(", ")] : null },
        { t: "Installer le serveur", ok: inst, aide: inst ? "" : s.partiel ? "L’installation précédente n’a pas abouti : retire-la (en bas de page), puis recommence." : "Remplis le formulaire plus bas (la dernière version est proposée), télécharge le script, vérifie son empreinte, puis installe." },
        { t: "Publier les routes du serveur dans le proxy", ok: routesOk, voir: inst,
          aide: routesOk ? "" : px && px.fastpanel ? "Le domaine envoie tout au tableau de bord : il manque les routes /api, /oauth2, /relay et gRPC vers le serveur. Cassandra peut les poser dans le site FASTPANEL (elle teste nginx avant de le recharger)." : "Le domaine doit envoyer /api, /oauth2, /relay et le gRPC au serveur (127.0.0.1:8081). Ce n’est pas un site FASTPANEL : copie la configuration nginx (« Voir la conf nginx ») dans ton proxy.",
          act: !routesOk && px && px.fastpanel ? ["srv-proxy", "Publier les routes dans FASTPANEL"] : null },
        { t: "Créer ton compte administrateur", ok: compteFait, voir: inst && routesOk,
          aide: compteFait ? "" : "Ouvre la page d’installation de NetBird et crée toi-même ton compte : Cassandra ne choisit ni ne garde aucun mot de passe.", lien: !compteFait && urlSetup ? urlSetup : "" },
        { t: "Donner un jeton d’accès à Cassandra", ok: !!S.pj, voir: compteFait,
          aide: S.pj ? "" : "Dans le tableau de bord NetBird (Settings › Personal Access Tokens), crée un jeton ; donne-le à Cassandra depuis la page Administration.", act: !S.pj ? ["vers-gestion", "Aller à l’Administration"] : null },
      ];
    }
    function cartePrerequis(s) {
      const e = etapesServeur(s), prochaine = e.findIndex((x) => !x.ok && x.voir !== false);
      if (prochaine < 0) return "";
      return '<div class="carte"><h2 ' + H2 + ">Pas à pas</h2><p class=\"note\">Dans l’ordre : chaque étape dit où elle en est, et propose le bouton quand Cassandra peut la faire.</p><div class=\"pairs\">" +
        e.map((x, i) => x.voir === false ? "" : '<div class="pair" style="grid-template-columns:auto minmax(0,1fr)"><span class="pastille ' + (x.ok ? "ok" : i === prochaine ? "al" : "mu") + '">' + (x.ok ? "✓" : i + 1) + '</span><span class="nom" style="font-family:inherit">' + esc(x.t) + (i === prochaine ? ' <span class="pastille al">prochaine étape</span>' : "") +
          (x.ok || !x.aide ? "" : '<br><span class="note">' + esc(x.aide) + "</span>") +
          (x.act ? '<br><button class="btn pri" data-a="' + x.act[0] + '"' + (S.occupe ? " disabled" : "") + ">" + esc(x.act[1]) + "</button>" : "") +
          (x.lien ? '<br><a class="btn pri" href="' + esc(x.lien) + '" target="_blank" rel="noopener noreferrer">Ouvrir la page de création du compte</a>' : "") + "</span></div>").join("") + "</div></div>";
    }
    const ETP = { libre: ["ok", "libre"], occupe: ["dg", "déjà pris : bloque l’installation"], pris_par_proxy: ["mu", "pris par ton proxy (normal)"], inconnu: ["mu", ""] };
    // Le pare-feu : lesquels des ports publics de NetBird sont ouverts, et un bouton pour ouvrir ceux qui manquent
    function bandePareFeu() {
      const pf = S.pf;
      if (!pf) return "";
      if (!pf.outil) return '<p class="note">Aucun pare-feu géré d’ici (ufw ou firewalld) : si la machine en a un autre, ouvre-y <span class="mono">' + esc((pf.publics || []).join(", ")) + "</span> toi-même.</p>";
      if (!pf.actif) return '<p class="note">Le pare-feu <b>' + esc(pf.outil) + "</b> est inactif : les ports ne sont pas filtrés.</p>";
      const manque = (pf.publics || []).filter((p) => !(pf.ouverts || []).includes(p));
      return '<div class="acts" style="margin-top:8px"><span class="note">Pare-feu : <b>' + esc(pf.outil) + "</b> (actif)</span>" + (manque.length ? '<button class="btn" data-a="pf-ouvrir"' + (S.occupe ? " disabled" : "") + ">Ouvrir " + esc(manque.join(", ")) + " dans " + esc(pf.outil) + "</button>" : '<span class="pastille ok">ports ouverts</span>') + "</div>";
    }
    function cartePorts() {
      const p = S.pt;
      if (!p || !p.ports.length) return "";
      const pf = S.pf && S.pf.outil && S.pf.actif ? S.pf : null;
      return '<div class="carte"><h2 ' + H2 + ">Ports" + (p.proxy ? " (proxy " + esc(p.proxy) + ")" : "") + '</h2><div class="pairs">' +
        p.ports.map((x) => '<div class="pair" style="grid-template-columns:minmax(110px,auto) minmax(140px,1fr) auto"><span class="nom">' + esc(x.proto.toUpperCase() + " " + x.port) + '<br><span class="note">' + (x.public ? "à ouvrir sur internet" : "sur cette machine seulement") + "</span></span><span class=\"note\">" + esc(x.usage) + "</span>" +
          "<span>" + (p.installe || !ETP[x.etat][1] ? "" : '<span class="pastille ' + ETP[x.etat][0] + '">' + ETP[x.etat][1] + "</span>") +
          (pf && x.public ? ' <span class="pastille ' + (pf.ouverts.includes(x.port + "/" + x.proto) ? "ok" : "al") + '">' + (pf.ouverts.includes(x.port + "/" + x.proto) ? "ouvert" : "fermé") + " dans " + esc(pf.outil) + "</span>" : "") + "</span></div>").join("") + "</div>" + bandePareFeu() +
        (p.reels.length ? '<p class="note">Publiés par les conteneurs : <span class="mono">' + p.reels.map((r) => esc(r.service + " " + r.ports.join(", "))).join(" · ") + "</span></p>" : "") +
        '<p class="note">Le port 3478/udp ne passe jamais par un proxy. Source : documentation de NetBird (selfhosted-quickstart, external-reverse-proxy).</p></div>';
    }
    // L’enregistrement DNS du domaine du serveur : créé dans FASTPANEL quand la zone y est, à faire chez l’hébergeur DNS sinon
    function carteDns(s) {
      const dom = s.installe ? (s.meta || {}).domaine : S.f.domaine, titre = '<h2 ' + H2 + ">Enregistrement DNS</h2>";
      if (!dom) return '<div class="carte">' + titre + '<p class="note">Choisis d’abord le domaine du serveur.</p></div>';
      const ip = S.ipSaisie || (S.ipm ? S.ipm.ip : ""), v = S.dnsv, par = (S.dmv && S.dmv.par) || "", zone = /zone DNS/.test(par), present = !!(v && v.correspond && v.attendue === ip);
      const etat = !v ? '<span class="pastille mu">inconnu</span>' : v.correspond ? '<span class="pastille ok">présent</span>' : v.resolu ? '<span class="pastille al">pointe ailleurs : ' + esc(v.adresses.join(", ")) + "</span>" : '<span class="pastille al">absent</span>';
      let h = '<div class="carte">' + titre + '<div class="pairs"><div class="pair" style="grid-template-columns:minmax(120px,auto) minmax(120px,1fr) auto"><span class="nom">' + esc(dom) + '<br><span class="note">type A</span></span><span class="mono note">' + esc(ip || "adresse inconnue") + "</span><span>" + etat + "</span></div></div>" +
        '<label class="ch" style="margin-top:8px"><b>Adresse de cette machine</b><span class="note">' + (S.ipm && S.ipm.privee ? "L’adresse vue ici est privée (machine derrière un routeur) : saisis l’adresse publique." : "Adresse vue par le système ; corrige-la si la machine est derrière un routeur.") + '</span><input type="text" id="nb-d-ip" value="' + esc(ip) + '" autocomplete="off" spellcheck="false"></label>';
      if (present) h += '<p class="note">L’enregistrement est en place' + (zone ? " (zone hébergée par le panneau FASTPANEL)" : "") + ".</p>";
      else if (zone) h += '<p class="note">La zone de ce domaine est hébergée par FASTPANEL : Cassandra peut créer l’enregistrement.</p><div class="acts"><button class="btn pri" data-a="dns-creer"' + (S.occupe || !ip ? " disabled" : "") + ">Créer l’enregistrement dans FASTPANEL</button><button class=\"btn\" data-a=\"dns-verifier\">Vérifier</button></div>";
      else if (par) h += '<p class="note">Ce site est géré par le panneau d’hébergement : son DNS pointe normalement déjà vers cette machine.</p><div class="acts"><button class="btn" data-a="dns-verifier">Vérifier</button></div>';
      else h += '<p class="note" style="color:var(--warn)">Domaine que Cassandra n’administre pas : crée cet enregistrement chez ton hébergeur DNS, puis vérifie.</p><div class="acts"><button class="btn" data-a="copier" data-t="' + esc(dom + " A " + ip) + '">Copier l’enregistrement</button><button class="btn" data-a="dns-verifier">Vérifier la résolution</button></div>';
      return h + "</div>";
    }
    // Les sauvegardes du serveur : hors du dossier du serveur, donc la purge ne les emporte pas
    function carteSauvegardes() {
      const sv = S.sv, liste = (sv && sv.sauvegardes) || [], taille = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " Mo" : Math.max(1, Math.round(n / 1024)) + " Ko";
      const RAISON = { manuelle: "à la demande", avant_maj: "avant une mise à jour", avant_retrait: "avant un retrait avec données", avant_restauration: "avant une restauration" };
      return '<div class="carte"><h2 ' + H2 + ">Sauvegardes</h2><p class=\"note\">Copie des comptes, machines et clés du serveur, dans <span class=\"mono\">" + esc((sv && sv.dossier) || "/var/backups/cassandra/netbird") + "</span> (lisible par root seul). Le serveur est arrêté quelques secondes le temps de la copie. Une sauvegarde est faite avant chaque mise à jour et avant tout retrait avec données ; les " + ((sv && sv.garde) || 10) + " plus récentes sont gardées.</p>" +
        (liste.length ? '<div class="pairs">' + liste.map((b) => '<div class="pair" style="grid-template-columns:minmax(130px,1fr) minmax(90px,auto) auto"><span class="nom">' + esc(b.quand) + '<br><span class="note">' + esc(RAISON[b.raison] || b.raison) + (b.version ? " · " + esc(b.version) : "") + '</span></span><span class="note">' + esc(taille(b.taille)) + '</span><button class="btn" data-a="srv-resto" data-id="' + esc(b.id) + '"' + (S.occupe ? " disabled" : "") + ">Restaurer…</button></div>").join("") + "</div>" : '<p class="note">' + (sv ? "Aucune sauvegarde pour l’instant." : "La liste n’est pas lisible pour l’instant.") + "</p>") +
        '<div class="acts"><button class="btn" data-a="srv-sauv"' + (S.occupe ? " disabled" : "") + ">Sauvegarder maintenant</button></div></div>";
    }
    function carteMajServeur(s) {
      const m = s.meta || {}, v = S.v || {}, aJour = v.serveur_a_jour === true;
      return '<div class="carte"><h2 ' + H2 + ">Mettre à jour le serveur</h2>" + ligneVersion(m.version, v.serveur_a_jour, v.derniere) +
        '<p class="note">Télécharge les nouvelles images, puis redémarre le serveur : les machines se reconnectent seules. NetBird publie sous la même étiquette : la version affichée est celle de la dernière publication installée. Le geste peut être défait depuis l’Historique (données, configuration et images d’avant), s’il y a eu une sauvegarde.</p>' +
        '<label class="coche"><input type="checkbox" id="nb-s-sauv"' + (S.sBack ? " checked" : "") + '><span>Sauvegarder les données avant (conseillé)</span></label>' +
        '<div class="acts" style="margin-top:8px"><button class="btn pri" data-a="srv-maj"' + (S.occupe || aJour ? " disabled" : "") + ">" + (aJour ? "Déjà à jour" : v.serveur_a_jour === false ? "Mettre à jour vers " + esc(v.derniere) : "Mettre à jour le serveur") + "</button></div></div>";
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
      const f = S.f, d = S.dl, bloque = S.occupe || !s.docker || !s.jq || !s.compose;
      const choix = [["nginx", "nginx (ton nginx publie le serveur)"], ["caddy", "caddy (ton caddy publie le serveur)"], ["traefik", "traefik (tout intégré : ports 80 et 443 libres)"]];
      let h = '<div class="carte"><h2 ' + H2 + ">Installer un serveur NetBird sur cette machine</h2>" +
        '<p class="note">Deux temps : Cassandra télécharge d’abord le script officiel de NetBird, et te montre son empreinte. Elle ne l’exécute qu’après ta confirmation, et seulement s’il n’a pas changé entre-temps.</p>' +
        '<div class="champs"><label class="ch"><b>Version</b><span class="note">' + (S.v && S.v.derniere ? "Dernière publiée par NetBird : <b>" + esc(S.v.derniere) + "</b>, proposée ici. Précise : jamais « latest »." : "On n’a pas pu lire la dernière version publiée : saisis-la (github.com/netbirdio/netbird/releases), précise : jamais « latest ».") + '</span><input type="text" id="nb-s-ver" value="' + esc(f.version) + '" placeholder="' + esc((S.v && S.v.derniere) || "v0.82.0") + '" autocomplete="off" spellcheck="false"></label>' +
        champDomaine() +
        '<label class="ch"><b>Adresse e-mail</b><span class="note">Pour les certificats Let’s Encrypt.</span><input type="text" id="nb-s-mel" value="' + esc(f.email) + '" placeholder="admin@exemple.fr" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Proxy</b><span class="note">Qui publie le serveur sur internet.</span><select id="nb-s-prx">' + choix.map((o) => '<option value="' + o[0] + '"' + (f.proxy === o[0] ? " selected" : "") + ">" + o[1] + "</option>").join("") + "</select></label></div>" +
        '';
      if (d) h += '<div class="lien"><h2 ' + H2 + ">Script téléchargé : " + esc(d.version) + '</h2><p class="note">Empreinte SHA-256 (' + esc(d.taille) + ' octets) : compare-la, si tu veux, à celle du script de cette version sur github.com/netbirdio/netbird.</p><span class="u">' + esc(d.sha256) + "</span>" +
        '<div class="acts"><button class="btn pri" data-a="srv-installer"' + (bloque ? " disabled" : "") + ">Installer cette version</button></div></div>";
      else h += '<div class="acts"><button class="btn pri" data-a="srv-telecharger"' + (bloque ? " disabled" : "") + ">Télécharger le script et voir son empreinte</button></div>";
      return h + "</div>";
    }
    function carteRetrait() {
      return '<div class="carte"><h2 ' + H2 + ">Retirer le serveur</h2><p class=\"note\">Arrête les conteneurs. Les données (comptes, machines, clés) sont gardées : réinstaller retrouve le réseau tel quel.</p><div class=\"acts\">" +
        (S.couper ? '<span class="confirme"><label class="coche"><input type="checkbox" id="nb-s-purge"><span>Supprimer aussi les données : tous les comptes, machines et clés sont retirés du serveur. Une sauvegarde est faite avant, hors du dossier du serveur ; sans elle, rien n’est supprimé.</span></label> <button class="btn dng" data-a="srv-retirer-oui">Oui, retirer</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
          : '<button class="btn dng" data-a="srv-retirer"' + (S.occupe ? " disabled" : "") + ">Retirer le serveur…</button>") + "</div></div>";
    }
    function carteServeur(s) {
      const m = s.meta || {}, url = m.domaine ? "https://" + m.domaine : "";
      const avisPartiel = s.partiel ? '<div class="carte" role="alert" style="color:var(--warn)"><b>Installation inachevée.</b> Le script d’installation a échoué ou n’a pas eu le temps de finir : la pile est à moitié posée. Retire-la avec ses données (en bas de page), puis recommence l’installation.</div>' : "";
      if (s.partiel) return avisPartiel + carteRetrait();
      let h = avisPartiel + '<div class="carte"><div class="hero"><div><span class="lib">Serveur</span><span class="pastille ' + (s.conteneurs.some((c) => c.etat === "running") ? "ok" : "al") + '">' + (s.conteneurs.some((c) => c.etat === "running") ? "En marche" : "Arrêté") + "</span></div>" +
        fiche("Domaine", esc(m.domaine || "—")) + fiche("Version", esc(m.version || "—")) + fiche("Proxy", esc(m.proxy || "—")) + fiche("API", s.api_joignable ? "joignable ✓" : "ne répond pas ✗") + "</div>" +
        (s.conteneurs.length ? '<div class="pairs">' + s.conteneurs.map((c) => '<div class="pair" style="grid-template-columns:auto minmax(0,1fr) minmax(0,auto)"><span class="pt' + (c.etat === "running" ? " on" : "") + '"></span><span class="nom">' + esc(c.service) + '</span><span class="note" style="overflow-wrap:anywhere">' + esc(c.etat) + " · " + esc(c.image) + "</span></div>").join("") + "</div>" : "") + "</div>";
      h += carteMajServeur(s) + carteDns(s) + carteSauvegardes();
      h += cartePorts() + '<div class="carte"><h2 ' + H2 + ">Entretien</h2><div class=\"acts\"><button class=\"btn\" data-a=\"srv-journaux\"" + (S.occupe ? " disabled" : "") + ">Voir les journaux</button><button class=\"btn\" data-a=\"srv-redemarrer\"" + (S.occupe ? " disabled" : "") + ">Redémarrer</button>" +
        (m.proxy === "nginx" ? '<button class="btn" data-a="srv-nginx"' + (S.occupe ? " disabled" : "") + ">Voir la conf nginx</button>" : "") + "</div>" + carteTexte() + "</div>";
      h += carteRetrait();
      return h;
    }
    function carteTexte() {
      return S.txt ? '<div class="acts" style="justify-content:space-between"><b>' + esc(S.txt.titre) + '</b><span><button class="btn" data-a="copier" data-t="' + esc(S.txt.texte) + '">Copier</button> <button class="btn" data-a="txt-fermer">Fermer</button></span></div>' +
        '<pre class="mono" style="margin:0;padding:12px;max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:10px;font-size:11.5px;white-space:pre-wrap">' + esc(S.txt.texte) + "</pre>" : "";
    }
    function pageServeur(s) {
      if (!s.disponible) return '<div class="carte" style="color:var(--warn)">La commande root « serveur » du module ne répond pas : <span class="mono">CN_install.sh --module netbird</span> la pose, et le courtier doit être armé. Détail : ' + esc(s.erreur || "") + "</div>";
      return aiguillage(false) + cartePrerequis(s) + (s.installe ? carteServeur(s) : cartePorts() + carteDns(s) + carteInstallation(s));
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
      if (racine.querySelector("#nb-s-ver")) S.f = lireForm();            // ce qui est tapé dans le formulaire survit à un redessin (relecture, minuterie)
      const e = S.e, t = TITRES[page];
      let h = '<div class="tete"><h1>NetBird' + (t[0] ? ' <span class="note" style="font-weight:500">› ' + esc(t[0]) + "</span>" : "") + '</h1><p class="sous">' + esc(t[1]) + '</p><div class="acts" style="margin-top:8px"><button class="btn" data-a="relire">Relire</button><span class="note">' +
        (S.lu ? "Relu à " + new Date(S.lu).toLocaleTimeString() : "") + "</span></div></div>";
      if (S.echec && !S.erreur) h += '<div class="carte" role="alert" style="color:var(--danger)"><b>Le geste n’a pas abouti.</b> ' + esc(S.echec) + '<div class="acts"><button class="btn" data-a="echec-fermer">Fermer</button></div></div>';
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
      if (px) px.addEventListener("change", async () => { S.f = lireForm(); try { S.pt = await agir("netbird.serveur_ports", { proxy: S.f.proxy }); S.pf = await agir("netbird.pare_feu_etat", { proxy: S.f.proxy }).catch(() => S.pf); } catch (_) { /* la carte garde l’ancienne vue */ } dessiner(); });
      const im = racine.querySelector("#nb-i-mode"), sb = racine.querySelector("#nb-s-sauv"), di = racine.querySelector("#nb-d-ip"), dd = racine.querySelector("#nb-s-dom");
      if (im) im.addEventListener("change", () => { S.cMode = im.value; dessiner(); });
      if (sb) sb.addEventListener("change", () => { S.sBack = sb.checked; });
      if (di) di.addEventListener("change", async () => { S.ipSaisie = di.value.trim(); await chargerDns(); dessiner(); });
      if (dd) dd.addEventListener("change", async () => { S.f = lireForm(); await chargerDns(); dessiner(); });
      const ds = racine.querySelector("#nb-s-domsel");
      if (ds) ds.addEventListener("change", async () => { S.f = lireForm(); if (S.f.hors) S.f.domaine = ""; await chargerDns(); dessiner(); });
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
        if (!(await demander("Installer le client NetBird dans un conteneur Docker (netbirdio/netbird:" + tag + ") ? L’image est téléchargée depuis Docker Hub."))) return;
        const args = { tag: tag, nom: val("#nb-i-nom"), url: val("#nb-i-url") };
        return faire(() => (cle ? avecCle(cle, () => agir("netbird.installer_docker", Object.assign({ avec_cle: true }, args))) : agir("netbird.installer_docker", args)), "NetBird est installé dans Docker.");
      }
      if (a === "client-maj") {
        if (!(await demander("Mettre à jour le client NetBird ? " + (S.e && S.e.natif && S.e.conteneur === "absent" ? "Le paquet est mis à jour par apt ou dnf." : "L’image est téléchargée ; si elle a changé, le conteneur est recréé (identité gardée).") + " La machine est coupée quelques secondes. Le geste peut être défait depuis l’Historique."))) return;
        return faire(async () => { const r = await agir("netbird.mettre_a_jour_client"); dire(r && r.maj_change ? "Client NetBird mis à jour" + (r.version_apres && r.version_avant !== r.version_apres ? " : " + r.version_avant + " → " + r.version_apres : "") + "." : "Le client NetBird est déjà à jour."); }, "");
      }
      if (a === "installer-natif") {
        if (!(await demander("Installer le client NetBird natif (paquet officiel) ? Le dépôt de NetBird est ajouté à la machine (apt ou dnf, clés vérifiées), puis le paquet est installé et son service démarré."))) return;
        return faire(() => agir("netbird.installer_natif"), "Le client NetBird natif est installé : connecte-le depuis la Vue d’ensemble.");
      }
      if (a === "natif-retirer") { if (!(await demander("Désinstaller le client NetBird natif ? La machine quitte le réseau tant qu’elle n’est pas reconnectée."))) return; return faire(() => agir("netbird.retirer_natif"), "Client natif désinstallé."); }
      if (a === "vers-gestion") { if (CASS.ouvrirEcran) CASS.ouvrirEcran("netbird:n_gestion", "Administration"); return; }
      if (a === "srv-proxy") {
        const dom = (S.s && S.s.meta || {}).domaine || S.f.domaine;
        if (!(await demander("Poser les routes NetBird (/api, /oauth2, /relay, gRPC) dans le site FASTPANEL " + dom + " ? Cassandra écrit entre deux marques dans le fichier d’inclusion du site, teste nginx, puis le recharge ; au moindre refus de nginx, l’ancien contenu est remis. Ce que tu y as mis reste. Le geste peut être défait depuis l’Historique.", "Oui, publier"))) return;
        return faire(() => agir("netbird.serveur_proxy_publier", { domaine: dom }), "Routes posées : le domaine sert maintenant l’API de NetBird.");
      }
      if (a === "srv-compose") {
        if (!(await demander("Installer Docker Compose sur cette machine ? C’est un paquet de la distribution (apt, dnf ou yum), installé par le courtier : le script officiel du serveur NetBird en a besoin. Docker lui-même n’est pas touché.", "Oui, installer"))) return;
        return faire(() => agir("netbird.serveur_installer_compose"), "Docker Compose est installé : tu peux maintenant télécharger le script du serveur.");
      }
      if (a === "srv-jq") {
        if (!(await demander("Installer jq sur cette machine ? C’est un petit paquet de la distribution (apt, dnf ou yum), installé par le courtier : le script officiel du serveur NetBird en a besoin."))) return;
        return faire(() => agir("netbird.serveur_installer_jq"), "jq est installé : tu peux maintenant télécharger le script du serveur.");
      }
      if (a === "srv-sauv") return faire(async () => { const r = await agir("netbird.serveur_sauvegarder"); dire("Sauvegarde " + r.id + " faite."); }, "");
      if (a === "srv-resto") {
        const id = b.dataset.id;
        if (!(await demander("Restaurer la sauvegarde " + id + " ? Les données et la configuration actuelles du serveur sont remplacées (une sauvegarde de sécurité est faite avant). Le serveur est arrêté puis relancé."))) return;
        return faire(() => agir("netbird.serveur_restaurer", { id: id }), "Sauvegarde restaurée.");
      }
      if (a === "pf-ouvrir") {
        const px = S.s && S.s.installe ? (S.s.meta || {}).proxy || "" : S.f.proxy, manque = ((S.pf && S.pf.publics) || []).filter((p) => !(S.pf.ouverts || []).includes(p));
        if (!(await demander("Ouvrir " + manque.join(", ") + " dans le pare-feu " + ((S.pf && S.pf.outil) || "") + " de cette machine ? Seuls ces ports sont ajoutés ; rien n’est retiré. Le geste peut être défait depuis l’Historique."))) return;
        return faire(() => agir("netbird.pare_feu_ouvrir", { proxy: px }), "Ports ouverts dans le pare-feu.");
      }
      if (a === "dns-creer") {
        const ip = val("#nb-d-ip"), dom = S.s && S.s.installe ? (S.s.meta || {}).domaine : S.f.domaine;
        if (!ip || !dom) { dire("Il faut un domaine et l’adresse de la machine.", "err"); return; }
        if (!(await demander("Créer dans la zone FASTPANEL l’enregistrement " + dom + " A " + ip + " ? Un nom qui a déjà un enregistrement n’est jamais remplacé. Le geste peut être défait."))) return;
        S.ipSaisie = ip;
        return faire(() => agir("fastpanel.dns_enregistrer", { domaine: dom, adresse: ip }), "Enregistrement DNS créé : la propagation peut prendre quelques minutes.");
      }
      if (a === "dns-verifier") { S.ipSaisie = val("#nb-d-ip"); return charger(); }
      if (a === "echec-fermer") { S.echec = ""; dessiner(); return; }
      if (a === "txt-fermer") { S.txt = null; dessiner(); return; }
      if (a === "onglet") { S.onglet = b.dataset.id; S.edit = ""; dessiner(); return; }
      if (a === "cle-ok") { S.cle = null; dessiner(); return; }
      if (a === "jeton-enregistrer") {
        // Une copie depuis le tableau de bord traîne parfois des caractères invisibles (espace de largeur nulle, marque de sens, guillemets) : on les retire avant de juger.
        const jeton = val("#nb-j-jeton").replace(/[​-‏‪-‮⁠﻿ \s"'“”‘’`]/g, ""), url = val("#nb-j-url");
        if (jeton) {
          // Dire POURQUOI le texte collé n’est pas un jeton, sans jamais le répéter : seule sa longueur et sa forme sont données.
          const raison = /\s/.test(jeton) ? "il contient un espace ou un saut de ligne : recopie seulement le jeton" : !/^[A-Za-z0-9_.-]+$/.test(jeton) ? "il contient un caractère inattendu en position " + (jeton.search(/[^A-Za-z0-9_.-]/) + 1) + " (code U+" + jeton.charCodeAt(jeton.search(/[^A-Za-z0-9_.-]/)).toString(16).toUpperCase().padStart(4, "0") + ") : un jeton NetBird n’a que des lettres, des chiffres et _" : jeton.length < 16 ? "il est trop court (" + jeton.length + " caractères)" : jeton.length > 300 ? "il est trop long (" + jeton.length + " caractères)" : !/^nbp_/.test(jeton) ? "il ne commence pas par nbp_ : ce n’est pas un jeton d’accès personnel (c’est peut-être l’identifiant du jeton, ou autre chose)" : "";
          if (raison) { S.echec = "Ce texte n’est pas un jeton d’accès NetBird : " + raison + ". Un jeton ressemble à nbp_ suivi de lettres et de chiffres, environ 40 caractères."; dire("Jeton refusé : " + raison, "err"); refus(); return; }
        }
        // La page est redessinée après un refus : on remet ce qui avait été saisi (en mémoire le temps du redessin seulement, rien n’est gardé).
        function refus() { dessiner(); const j = racine.querySelector("#nb-j-jeton"), u = racine.querySelector("#nb-j-url"); if (j) j.value = jeton; if (u) u.value = url; }
        const urlNette = url.replace(/\/+$/, "");
        if (url && !/^(https:\/\/[A-Za-z0-9.-]{1,253}(:\d{1,5})?|http:\/\/(127\.0\.0\.1|localhost)(:\d{1,5})?)$/i.test(urlNette)) {
          S.echec = "L’adresse de l’API n’est pas valide : il faut https://nom-du-serveur (par exemple https://netbird.exemple.fr), sans chemin. Laisse le champ vide pour utiliser le serveur installé par Cassandra.";
          dire("Adresse de l’API invalide", "err"); refus(); return;
        }
        if (!jeton && !url) { dire("Rien à enregistrer", "err"); return; }
        return faire(async () => { if (jeton) await agir("reglages.regler_secret", { cle: "netbird.jeton_api", valeur: jeton }); if (url) await agir("reglages.regler", { cle: "netbird.url_api", valeur: urlNette });
          // Une adresse bien formée mais fausse (une lettre de travers) n’est pas reconnue par sa forme : on essaie vraiment l’API, et on le dit si elle ne répond pas.
          try { await agir("netbird.api_verifier"); } catch (e) { throw new Error("Enregistré, mais l’API ne répond pas avec cette adresse et ce jeton : " + (e.message || e)); } }, "Accès à l’API enregistré et vérifié.");
      }
      if (a === "jeton-oublier") { if (!(await demander("Oublier le jeton d’accès ? Cassandra ne pourra plus administrer le réseau."))) return; return faire(() => agir("reglages.reinitialiser", { cle: "netbird.jeton_api" }), "Jeton oublié."); }
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
        if (!(await demander("Installer le serveur NetBird " + S.f.version + " pour " + S.f.domaine + " (proxy " + S.f.proxy + ") ?" + (S.f.hors ? "\nDomaine non administré par Cassandra : son DNS et son certificat sont à ta charge." : "") + "\nScript d’empreinte " + S.dl.sha256.slice(0, 16) + "…\nIl télécharge les images NetBird et, avec traefik, demande un certificat Let’s Encrypt."))) return;
        return faire(async () => { await agir("netbird.serveur_installer", { version: S.f.version, sha256: S.dl.sha256, domaine: S.f.domaine, email: S.f.email, proxy: S.f.proxy, hors_cassandra: S.f.hors }); S.dl = null; }, "Serveur NetBird installé.");
      }
      if (a === "srv-redemarrer") { if (!(await demander("Redémarrer le serveur NetBird ? Les machines se reconnectent seules."))) return; return faire(() => agir("netbird.serveur_redemarrer"), "Serveur redémarré."); }
      if (a === "srv-maj") {
        const sauv = !!(racine.querySelector("#nb-s-sauv") || {}).checked;
        S.sBack = sauv;
        if (!(await demander("Mettre à jour le serveur NetBird" + (S.v && S.v.derniere ? " vers " + S.v.derniere : "") + (sauv ? " après une sauvegarde" : " SANS sauvegarde (la mise à jour ne pourra pas être défaite)") + " ? Les images sont téléchargées puis le serveur redémarre."))) return;
        return faire(async () => { const r = await agir("netbird.serveur_mettre_a_jour", { sauvegarde: sauv }); dire("Serveur mis à jour" + (r.version_avant !== r.version_apres ? " : " + r.version_avant + " → " + r.version_apres : "") + (r.sauvegarde ? " ; sauvegarde " + r.sauvegarde + " faite avant." : ".")); }, "");
      }
      if (a === "srv-journaux") return faire(async () => { S.txt = { titre: "Journaux du serveur (80 dernières lignes)", texte: (await agir("netbird.serveur_journaux")).journaux || "(vide)" }; }, "");
      if (a === "srv-nginx") return faire(async () => { S.txt = { titre: "Configuration nginx à publier", texte: (await agir("netbird.serveur_nginx")).conf || "" }; }, "");
      if (a === "srv-retirer") { S.couper = true; dessiner(); return; }
      if (a === "srv-retirer-oui") { const purger = !!(racine.querySelector("#nb-s-purge") || {}).checked; return faire(async () => { const r = await agir("netbird.serveur_retirer", { purger: purger }); if (r && r.avertissement) dire(r.avertissement, "err"); else dire(r && r.purge ? "Serveur et données retirés" + (r.sauvegarde ? " ; sauvegarde " + r.sauvegarde + " gardée." : ".") : "Serveur retiré (données gardées)."); }, ""); }
      // ---- le réseau
      if (a === "m-renommer") { S.edit = b.dataset.id; dessiner(); return; }
      if (a === "m-non") { S.edit = ""; dessiner(); return; }
      if (a === "m-ok") { const nom = val("#nb-m-nom"), id = b.dataset.id; return faire(async () => { await agir("netbird.machine_modifier", { id: id, nom: nom }); S.edit = ""; }, "Machine renommée."); }     // lu AVANT faire : faire redessine, et le champ reprendrait l’ancien nom
      if (a === "m-ssh") { const m = S.g.machines.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.machine_modifier", { id: b.dataset.id, ssh: !(m && m.ssh) }), "SSH modifié."); }
      if (a === "m-suppr") {
        const m = (S.g.machines || []).find((x) => x.id === b.dataset.id), loc = await agir("netbird.etat").catch(() => null);
        const locale = !!(m && loc && ((loc.ip && m.ip === loc.ip) || (loc.nom && String(m.nom).toLowerCase() === String(loc.nom).toLowerCase())));
        const texte = locale
          ? "« " + m.nom + " » est CETTE machine, celle où tourne Cassandra. La retirer du réseau coupe son client NetBird : elle perd son identité et ne se reconnecte qu’avec une nouvelle clé d’installation. Retirer quand même ?"
          : "Retirer cette machine du réseau NetBird ? Elle devra se reconnecter avec une clé.";
        if (!(await demander(texte, locale ? "Oui, retirer cette machine" : undefined))) return; return faire(() => agir("netbird.machine_supprimer", { id: b.dataset.id }), "Machine retirée du réseau."); }
      if (a === "cle-creer") {
        const nom = val("#nb-k-nom"), args = { nom: nom, type: val("#nb-k-type"), jours: parseInt(val("#nb-k-jours"), 10) || 30, groupes: cochees("nb-k-g") };
        if (!nom) { dire("Donne un nom à la clé", "err"); return; }
        return faire(async () => { const r = await agir("netbird.cle_creer", args); S.cle = { nom: r.nom, cle: r.cle_secrete }; }, "Clé créée : copie-la maintenant.");
      }
      if (a === "k-revoquer") { const k = S.g.cles.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.cle_revoquer", { id: b.dataset.id, revoquer: !(k && k.revoquee) }), "Clé modifiée."); }
      if (a === "k-suppr") { if (!(await demander("Supprimer cette clé d’installation ?"))) return; return faire(() => agir("netbird.cle_supprimer", { id: b.dataset.id }), "Clé supprimée."); }
      if (a === "g-creer") { const nom = val("#nb-g-nom"); if (!nom) { dire("Donne un nom au groupe", "err"); return; } return faire(() => agir("netbird.groupe_creer", { nom: nom }), "Groupe créé."); }
      if (a === "g-suppr") { if (!(await demander("Supprimer ce groupe ? NetBird refuse tant qu’une règle ou une clé l’utilise."))) return; return faire(() => agir("netbird.groupe_supprimer", { id: b.dataset.id }), "Groupe supprimé."); }
      if (a === "p-creer") {
        const nom = val("#nb-p-nom"), src = cochees("nb-p-src"), dst = cochees("nb-p-dst");
        if (!nom || !src.length || !dst.length) { dire("Un nom, au moins un groupe source et un groupe destination", "err"); return; }
        const args = { nom: nom, sources: src, destinations: dst, protocole: val("#nb-p-proto") || "all", bidirectionnel: !!(racine.querySelector("#nb-p-bi") || {}).checked };     // lus AVANT faire (qui redessine)
        return faire(() => agir("netbird.politique_creer", args), "Politique créée.");
      }
      if (a === "p-actif") { const p = S.g.politiques.find((x) => x.id === b.dataset.id); return faire(() => agir("netbird.politique_activer", { id: b.dataset.id, actif: !(p && p.actif) }), "Politique modifiée."); }
      if (a === "p-suppr") { if (!(await demander("Supprimer cette politique d’accès ? Les machines qu’elle reliait ne se joindront plus."))) return; return faire(() => agir("netbird.politique_supprimer", { id: b.dataset.id }), "Politique supprimée."); }
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
