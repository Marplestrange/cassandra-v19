// ═════════════════════════════════════════════════════════════════
// TITRE      : NetBird : l’écran
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #9f3ad6
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les pages « NetBird » du module netbird : où en est la machine, sa connexion (par un lien à ouvrir ou par une clé), les machines du réseau, l’installation du client dans Docker, l’historique des gestes.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.netbird) ; la page vient de l’écran ouvert (ctx.ecran = « netbird:n_machines ») ; tout vient de netbird.etat ; l’état se relit seul (20 s, 2,5 s pendant une identification), jamais sous les doigts de quelqu’un qui tape.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=9f3ad6 ▼▼▼
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
  const PAGES = { n_vue: "vue", n_machines: "machines", n_installation: "installation", n_historique: "historique" };
  const TITRES = {
    vue: ["", "Le réseau privé NetBird de cette machine : la joindre de n’importe où, et joindre tes autres machines."],
    machines: ["Machines", "Les machines de ton réseau : qui est en ligne, par quel chemin on les joint et en combien de temps."],
    installation: ["Installation", "Où est le client NetBird sur cette machine, et son installation dans Docker."],
    historique: ["Historique", "Les derniers gestes faits sur NetBird depuis Cassandra, avec leur retour."],
  };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.netbird = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("netbird", corps); return; }
    const page = PAGES[String((ctx && ctx.ecran) || "").split(":")[1]] || "vue";
    const anc = document.getElementById("nb-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "nb-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "nb"; corps.appendChild(racine);

    const S = { e: null, occupe: false, erreur: "", couper: false, q: "", filtre: "tous", j: null, lu: 0, nom: "" };
    let minuterie = null;

    async function charger(silencieux) {
      try { S.e = await agir("netbird.etat"); S.erreur = ""; S.lu = Date.now(); } catch (e) { S.erreur = e.message || String(e); }
      if (page === "historique") { try { S.j = (await agir("netbird.journal", { limite: 30 })).gestes; } catch (_) { S.j = null; } }
      if (!silencieux || document.body.contains(racine)) dessiner();
      armer();
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
      return '<div class="carte"><h2 ' + H2 + ">NetBird n’est pas encore là</h2><p>" + esc(e.texte || "") + '</p><div class="acts"><button class="btn pri" data-a="vers-installation">Aller à l’installation</button></div></div>';
    }
    function pageVue(e) {
      let h = carteEtat(e);
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

    // ---- l’installation : où est le client, et le conteneur Docker
    function pageInstallation(e) {
      const nonRoot = e.courtier === false;
      const oui = (b) => '<span class="pastille ' + (b ? "ok" : "mu") + '">' + (b ? "oui" : "non") + "</span>";
      let h = '<div class="carte"><h2 ' + H2 + ">Ce qui existe sur cette machine</h2><div class=\"hero\">" +
        '<div><span class="lib">Client NetBird installé</span>' + oui(e.natif) + "</div><div><span class=\"lib\">Docker</span>" + oui(e.docker) + "</div>" +
        '<div><span class="lib">Conteneur « ' + esc(e.nom_conteneur) + '»</span><span class="pastille ' + (e.conteneur === "en_marche" ? "ok" : e.conteneur === "absent" ? "mu" : "al") + '">' +
        esc({ en_marche: "en marche", arrete: "arrêté", absent: "absent", autre: "autre service (intouché)" }[e.conteneur] || e.conteneur) + "</span></div>" +
        '<div><span class="lib">Utilisé par Cassandra</span><span class="gros" style="font-size:16px">' + esc({ natif_direct: "client natif", natif_racine: "client natif (par le courtier)", docker: "conteneur Docker", absent: "—" }[e.mode] || e.mode) + "</span></div></div></div>";
      if (nonRoot) h += '<div class="carte" style="color:var(--warn)">Le courtier ne répond pas ou la commande root du module n’est pas posée : <span class="mono">CN_install.sh --module netbird</span> la pose. Sans elle, Docker ne se pilote pas d’ici.</div>';
      const bloque = S.occupe || !e.docker || nonRoot || e.conteneur === "en_marche" || e.conteneur === "arrete" || e.conteneur === "autre";
      h += '<div class="carte"><h2 ' + H2 + ">Installer NetBird dans Docker</h2><p class=\"note\">Crée le conteneur officiel <span class=\"mono\">netbirdio/netbird</span> : il redémarre avec la machine, utilise le réseau de la machine et garde son identité dans un volume. Aucun autre conteneur n’est touché.</p>" +
        (!e.docker ? '<p class="note" style="color:var(--warn)">Docker n’est pas installé sur cette machine.</p>' : e.conteneur === "autre" ? '<p class="note" style="color:var(--warn)">Un conteneur « ' + esc(e.nom_conteneur) + ' » existe déjà mais n’est pas NetBird : change le réglage « conteneur ».</p>' : "") +
        '<div class="champs"><label class="ch"><b>Version</b><span class="note">latest, ou une version précise (0.40.0).</span><input type="text" id="nb-tag" value="latest" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Nom de la machine</b><span class="note">Facultatif.</span><input type="text" id="nb-i-nom" placeholder="argos" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Serveur de gestion</b><span class="note">Vide : NetBird Cloud (ou le réglage « url_gestion »).</span><input type="text" id="nb-i-url" placeholder="https://netbird.exemple.fr:443" autocomplete="off" spellcheck="false"></label>' +
        '<label class="ch"><b>Clé d’installation</b><span class="note">Facultatif : avec elle le conteneur se connecte seul ; sans elle, un lien à ouvrir.</span><input type="password" id="nb-i-cle" placeholder="XXXXXXXX-XXXX-…" autocomplete="off" spellcheck="false"></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="installer"' + (bloque ? " disabled" : "") + ">Installer dans Docker</button></div></div>";
      if (e.conteneur === "en_marche" || e.conteneur === "arrete") {
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

    function dessiner() {
      const e = S.e, t = TITRES[page];
      let h = '<div class="tete"><h1>NetBird' + (t[0] ? ' <span class="note" style="font-weight:500">› ' + esc(t[0]) + "</span>" : "") + '</h1><p class="sous">' + esc(t[1]) + '</p><div class="acts" style="margin-top:8px"><button class="btn" data-a="relire">Relire</button><span class="note">' +
        (S.lu ? "Relu à " + new Date(S.lu).toLocaleTimeString() : "") + "</span></div></div>";
      if (S.erreur) h += '<div class="carte" role="alert" style="color:var(--danger)">' + esc(S.erreur) + '<div class="acts"><button class="btn" data-a="relire">Réessayer</button></div></div>';
      if (!e) { racine.innerHTML = h + '<div class="attente" role="status" aria-live="polite">Lecture de l’état de NetBird…</div>'; return; }
      h += page === "vue" ? pageVue(e) : page === "machines" ? pageMachines(e) : page === "installation" ? pageInstallation(e) : pageHistorique(e);
      racine.innerHTML = h; lier();
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
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
      if (a === "vers-installation") { if (CASS.ouvrirEcran) CASS.ouvrirEcran("netbird:n_installation", "Installation"); return; }
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
