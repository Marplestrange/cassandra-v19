// ═════════════════════════════════════════════════════════════════
// TITRE      : Tailscale : l’écran de connexion
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #2da43b
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l’écran « Tailscale » du module tailscale : où en est la machine, la connexion (par un lien à ouvrir ou par une clé), la déconnexion, SSH par Tailscale et les machines du réseau.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.tailscale) ; tout vient de tailscale.etat ; pendant une identification en attente, l’écran relit l’état toutes les 2,5 s et s’arrête seul quand il quitte la page.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=2da43b ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  const LIEN_SUR = /^https:\/\/([a-z0-9-]+\.)*tailscale\.com\//i;

  const CSS = ".ts{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.ts *{box-sizing:border-box}" +
    ".ts h1,.ts h2,.ts p{margin:0}.ts .mono{font-family:" + MONO + "}" +
    ".ts .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;padding:18px 20px;display:flex;flex-direction:column;gap:12px}" +
    ".ts .tete h1{font:650 22px/1.2 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}.ts .sous{color:var(--txt-soft);font-size:13px;margin-top:3px;max-width:64ch}" +
    ".ts .acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}" +
    ".ts .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 14px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block}" +
    ".ts .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.ts .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.ts .btn.pri:hover:not([disabled]){filter:brightness(1.08);color:var(--on-accent,#fff)}" +
    ".ts .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.ts .btn[disabled]{opacity:.45;cursor:not-allowed}" +
    ".ts .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:3px 11px;font:600 12px 'Inter',system-ui,sans-serif;white-space:nowrap;border:1px solid var(--line)}" +
    ".ts .pastille::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor}" +
    ".ts .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)}.ts .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}" +
    ".ts .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent)}.ts .pastille.mu{color:var(--txt-soft)}" +
    ".ts .hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px 22px}.ts .hero>div{display:flex;flex-direction:column;gap:4px;min-width:0}" +
    ".ts .lib{font:600 10.5px 'Inter',system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}.ts .gros{font:600 20px/1.2 " + MONO + ";color:var(--txt-strong,var(--txt));overflow-wrap:anywhere}" +
    ".ts .note{font-size:12px;color:var(--txt-soft)}.ts .lien{padding:20px;border:1px dashed var(--accent);border-radius:14px;display:flex;flex-direction:column;gap:12px;background:color-mix(in srgb,var(--accent) 6%,transparent)}" +
    ".ts .lien .u{font:12px " + MONO + ";overflow-wrap:anywhere;color:var(--txt-soft)}" +
    ".ts .champs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 18px}.ts label.ch{display:flex;flex-direction:column;gap:5px}.ts label.ch b{font-weight:650}" +
    ".ts input[type=text],.ts input[type=password]{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:8px 12px;font:13px " + MONO + ";min-width:0}" +
    ".ts input:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}.ts .coche{display:flex;gap:8px;align-items:flex-start}.ts .coche input{margin-top:3px}" +
    ".ts details summary{cursor:pointer;font-weight:650;color:var(--accent)}.ts details[open] summary{margin-bottom:10px}" +
    ".ts .pairs{display:flex;flex-direction:column}.ts .pair{display:grid;grid-template-columns:auto minmax(120px,1fr) minmax(110px,auto) auto;gap:6px 14px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}" +
    ".ts .pair .nom{font:600 13px " + MONO + ";overflow-wrap:anywhere}.ts .pt{width:9px;height:9px;border-radius:50%;background:var(--txt-faint)}.ts .pt.on{background:var(--ok)}" +
    ".ts .sante{color:var(--warn);font-size:12.5px}.ts .attente{padding:30px;text-align:center;color:var(--txt-soft)}.ts .confirme{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px}" +
    ".sh-scene:has(>.sh-corps>.ts)>.sh-titre{display:none}" +
    "@media (max-width:820px){.ts .pair{grid-template-columns:auto minmax(0,1fr) auto}.ts .pair .ip{grid-column:2 / -1}}";

  // Ce que le client Tailscale dit de sa santé arrive en anglais : les messages connus sont traduits, les autres restent tels quels (le texte d'origine reste en infobulle).
  const SANTE = [
    [/advertising routes but --accept-routes is false/i, "D’autres machines proposent des routes que celle-ci n’accepte pas (--accept-routes coupé) : normal pour un serveur ; à activer seulement pour joindre ces réseaux."],
    [/not connected to the (control|coordination) server|unable to connect to the (control|coordination) server/i, "Tailscale ne joint pas son serveur de coordination : vérifie la connexion Internet de la machine."],
    [/(no|not) (reachable|connected).*(DERP|relay)|DERP.*(unreachable|not connected)/i, "Aucun relais Tailscale (DERP) joignable : les connexions directes marchent, pas celles qui passent par un relais."],
    [/Tailscale is stopped/i, "Tailscale est arrêté sur cette machine : « Se connecter » le relance."],
    [/(update|upgrade) (is )?available|new version/i, "Une mise à jour de Tailscale est disponible."],
    [/key (will )?expire|expired/i, "La clé de cette machine expire ou a expiré : reconnecte-la ou désactive l’expiration dans la console Tailscale."],
  ];
  const sante = (t) => { const s = String(t || ""); const m = SANTE.find((x) => x[0].test(s)); return '<span class="sante" title="' + esc(s) + '">' + esc(m ? m[1] : s) + "</span>"; };
  const age = (s) => { if (!s) return "jamais vue"; const d = new Date(String(s).replace(" ", "T") + ":00Z"); if (isNaN(d)) return s; const m = Math.max(0, Math.round((Date.now() - d) / 60000)); return m < 2 ? "à l’instant" : m < 90 ? "il y a " + m + " min" : m < 2160 ? "il y a " + Math.round(m / 60) + " h" : "il y a " + Math.round(m / 1440) + " j"; };
  const ETAT = { connecte: ["ok", "Connectée"], deconnecte: ["mu", "Déconnectée"], a_identifier: ["al", "En attente d’identification"], a_approuver: ["al", "À approuver par l’administrateur du réseau"],
    demarrage: ["al", "Démarrage…"], absent: ["dg", "Non installé"], arrete: ["dg", "tailscaled ne répond pas"] };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.tailscale = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("tailscale", corps); return; }
    const anc = document.getElementById("ts-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "ts-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "ts"; corps.appendChild(racine);

    const S = { e: null, occupe: false, erreur: "", quitter: false, couper: false, nom: "", ssh: false, ping: {} };
    let minuterie = null;

    async function charger(silencieux) {
      try { S.e = await agir("tailscale.etat"); S.erreur = ""; } catch (e) { S.erreur = e.message || String(e); }
      if (!silencieux || document.body.contains(racine)) dessiner();
      armer();
    }
    // Une identification en attente se relit seule ; l’écran qui n’est plus dans la page arrête sa minuterie.
    function armer() {
      if (minuterie) { clearTimeout(minuterie); minuterie = null; }
      const e = S.e;
      if (e && (e.en_attente || e.etat === "demarrage") && document.body.contains(racine)) minuterie = setTimeout(() => { if (document.body.contains(racine) && !S.occupe) charger(true); }, 2500);
    }
    const faire = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; dessiner();
      try { await f(); if (ok) dire(ok); } catch (e) { dire(e.message || String(e), "err"); S.erreur = e.message || String(e); }
      finally { S.occupe = false; S.quitter = false; S.couper = false; await charger(); }
    };

    function pastille(e) { const p = (e.etat === "a_identifier" && !e.en_attente) ? ["mu", "Non connectée"] : (ETAT[e.etat] || ["mu", e.etat]); return '<span class="pastille ' + p[0] + '">' + esc(p[1]) + "</span>"; }

    function carteLien(e) {
      const sur = LIEN_SUR.test(e.lien || "");
      return '<div class="lien"><h2 style="font:650 16px Inter,system-ui,sans-serif">Ouvre ce lien pour connecter la machine</h2>' +
        '<p class="note">Identifie-toi chez Tailscale (Google, Microsoft, GitHub… selon ton réseau) : la machine rejoint ton réseau dès que c’est fait. Cet écran se met à jour tout seul.</p>' +
        (sur ? '<div class="acts"><a class="btn pri" href="' + esc(e.lien) + '" target="_blank" rel="noopener noreferrer">Ouvrir la page de connexion</a><button class="btn" data-a="annuler"' + (S.occupe ? " disabled" : "") + ">Annuler</button></div>" +
          '<span class="u">' + esc(e.lien) + "</span>"
          : '<p class="note" style="color:var(--danger)">Le lien reçu ne vient pas de Tailscale : il n’est pas proposé. Annule et recommence.</p><div class="acts"><button class="btn" data-a="annuler">Annuler</button></div>') + "</div>";
    }

    // Le retrait du réseau (`tailscale logout`) efface aussi le droit d'opérateur : Cassandra ne peut plus reconnecter la machine, le client exige alors root. On le dit au lieu de proposer
    // un bouton qui échoue (constaté sur argos).
    function avisOperateur(e) {
      return e.pilotable === false ? '<div class="carte" style="color:var(--warn)">Cassandra n’a plus le droit de piloter Tailscale sur cette machine (le retrait du réseau l’efface). Pour reconnecter d’ici, ' +
        'lance d’abord sur la machine : <span class="mono">sudo tailscale set --operator=cassandra</span> ; ou connecte-la directement : <span class="mono">sudo tailscale up --operator=cassandra</span>.</div>' : "";
    }

    function carteConnexion(e) {
      return avisOperateur(e) + '<div class="carte"><h2 style="font:650 16px Inter,system-ui,sans-serif">Connecter cette machine à ton réseau Tailscale</h2>' +
        '<p class="note">Tailscale relie tes machines entre elles par un réseau privé chiffré : plus besoin d’ouvrir de ports pour y accéder.</p>' +
        '<div class="champs"><label class="ch"><b>Nom de la machine</b><span class="note">Facultatif ; celui du système par défaut.</span><input type="text" id="ts-nom" value="' + esc(S.nom) + '" placeholder="argos" autocomplete="off" spellcheck="false"></label>' +
        '<label class="coche"><input type="checkbox" id="ts-ssh"' + (S.ssh ? " checked" : "") + '><span><b>SSH par Tailscale</b><br><span class="note">Entrer sur cette machine depuis ton réseau privé, sans clé SSH.</span></span></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="connecter"' + (S.occupe || e.pilotable === false ? " disabled" : "") + ">" + (S.occupe ? "Un instant…" : "Se connecter") + "</button></div>" +
        '<details><summary>J’ai une clé d’authentification</summary><p class="note" style="margin-bottom:8px">Créée sur login.tailscale.com › Settings › Keys. Elle sert une fois, n’est gardée nulle part et l’écran l’efface aussitôt.</p>' +
        '<div class="acts"><input type="password" id="ts-cle" placeholder="tskey-auth-…" autocomplete="off" spellcheck="false" style="flex:1 1 260px"><button class="btn" data-a="cle"' + (S.occupe || e.pilotable === false ? " disabled" : "") + ">Se connecter avec la clé</button></div></details></div>";
    }

    function carteReseau(e) {
      const pairs = e.pairs || [];
      let h = '<div class="carte"><div class="acts" style="justify-content:space-between"><h2 style="font:650 16px Inter,system-ui,sans-serif">Les machines du réseau <span class="note">(' + e.en_ligne + " en ligne sur " + pairs.length + ")</span></h2></div>";
      h += pairs.length ? '<div class="pairs">' + pairs.map((p) => '<div class="pair"><span class="pt' + (p.en_ligne ? " on" : "") + '"></span><span class="nom">' + esc(p.nom) + (p.sortie ? ' <span class="pastille al">sortie</span>' : "") + '</span><span class="mono ip note">' + esc(p.ip) + "</span><span class=\"note\">" + (p.en_ligne ? "en ligne" : age(p.vu)) + (p.en_ligne ? ' <button class="btn" data-a="ping" data-m="' + esc(p.nom) + '" style="padding:2px 8px;font-size:11px;margin-left:6px"' + (S.ping[p.nom] === "…" ? " disabled" : "") + ">Ping</button>" : "") +
        (S.ping[p.nom] && S.ping[p.nom] !== "…" ? '<br><span class="mono">' + esc(S.ping[p.nom]) + "</span>" : "") + "</span></div>").join("") + "</div>"
        : '<p class="note">Aucune autre machine sur ce réseau pour l’instant. Installe Tailscale ailleurs et connecte-la au même compte.</p>';
      return h + "</div>";
    }

    // Une clé qui expire fait tomber la machine du réseau sans prévenir : on le dit 14 jours avant.
    function avisExpiration(e) {
      let h = "";
      const x = e.expiration;
      if (x && x.jours <= 14) {
        h += '<div class="carte" style="color:var(--warn)">La clé de cette machine ' + (x.jours < 0 ? "a expiré le " : "expire le ") + esc(x.date) + (x.jours >= 0 ? " (dans " + x.jours + " j)" : "") +
          " : reconnecte-la, ou désactive l’expiration dans la console Tailscale (Machines › ⋯ › Disable key expiry).</div>";
      }
      if (e.expirent && e.expirent.length) {
        h += '<div class="carte"><span class="sante">Clés de machines qui expirent : ' + e.expirent.map((y) => esc(y.nom) + (y.jours < 0 ? " (expirée)" : " (" + y.jours + " j)")).join(", ") + "</span></div>";
      }
      return h;
    }

    function carteReglages(e) {
      const g = e.reglages;
      if (!g) return "";
      const bloque = S.occupe || e.pilotable === false;
      const bool = (cle, titre, aide) => '<div class="coche"><span style="flex:1"><b>' + titre + '</b> <span class="pastille ' + (g[cle] ? "ok" : "mu") + '">' + (g[cle] ? "activé" : "coupé") + "</span>" +
        '<br><span class="note">' + aide + '</span></span><button class="btn" data-a="regler" data-c="' + cle + '" data-v="' + (g[cle] ? "0" : "1") + '"' + (bloque ? " disabled" : "") + ">" + (g[cle] ? "Couper" : "Activer") + "</button></div>";
      const dis = bloque ? " disabled" : "";
      const sorties = (e.pairs || []).filter((p) => p.offre_sortie);
      const titre = 'font:650 16px Inter,system-ui,sans-serif';
      return '<div class="carte"><h2 style="' + titre + '">Réglages avancés</h2>' +
        bool("accept_routes", "Accepter les routes des autres machines", "Joindre les réseaux (192.168…) que d’autres machines annoncent. Inutile pour un simple serveur.") +
        bool("accept_dns", "Utiliser le DNS du réseau (MagicDNS)", "Résoudre les noms des machines du réseau.") +
        bool("shields_up", "Bouclier : refuser les connexions entrantes", "Cette machine joint les autres, mais personne ne la joint par Tailscale (SSH par Tailscale compris).") +
        bool("advertise_exit_node", "Offrir la sortie Internet de cette machine", "Les autres machines peuvent passer par elle pour sortir sur Internet ; l’administrateur doit l’approuver.") +
        '<div class="champs"><label class="ch"><b>Nom de la machine</b><span class="note">Lettres, chiffres et tirets ; vide : le nom du système. Change son adresse DNS dans le réseau.</span><input type="text" id="ts-r-nom" value="' + esc(g.hostname) + '"></label>' +
        '<label class="ch"><b>Routes annoncées</b><span class="note">Réseaux joignables par cette machine, séparés par des virgules (192.168.1.0/24).</span><input type="text" id="ts-r-routes" value="' + esc((g.advertise_routes || []).join(", ")) + '"></label>' +
        '<label class="ch"><b>Sortie Internet utilisée</b><span class="note">' + (sorties.length ? "Tout le trafic de cette machine passera par la machine choisie." : "Aucune machine du réseau n’offre de sortie.") + '</span><select id="ts-r-sortie"><option value="">aucune</option>' +
        sorties.map((p) => '<option value="' + esc(p.ip) + '"' + (p.ip === g.exit_node ? " selected" : "") + ">" + esc(p.nom) + "</option>").join("") + "</select></label></div>" +
        '<div class="acts"><button class="btn" data-a="regler-nom"' + dis + '>Renommer</button><button class="btn" data-a="regler-routes"' + dis + '>Annoncer ces routes</button><button class="btn" data-a="regler-sortie"' + dis + ">Appliquer la sortie</button></div></div>";
    }

    function carteGestes(e) {
      const ssh = e.ssh === true;
      const refus = e.pilotable === false;      // Cassandra n'est pas l'opérateur du client : tout geste serait refusé, on le dit au lieu de proposer des boutons qui échouent
      const bloque = S.occupe || refus;
      return (refus ? '<div class="carte" style="color:var(--warn)">Cassandra n’a pas le droit de piloter Tailscale sur cette machine' + (e.operateur ? " (l’opérateur est « " + esc(e.operateur) + " »)" : "") +
        ' : sur la machine, <span class="mono">sudo tailscale set --operator=cassandra</span> (ou relancer l’installateur du module).</div>' : "") + '<div class="carte"><h2 style="font:650 16px Inter,system-ui,sans-serif">Réglages</h2>' +
        '<div class="coche"><span style="flex:1"><b>SSH par Tailscale</b> ' + (e.ssh == null ? '<span class="pastille mu">inconnu</span>' : ssh ? '<span class="pastille ok">activé</span>' : '<span class="pastille mu">coupé</span>') +
        '<br><span class="note">Entrer sur la machine depuis ton réseau privé sans clé SSH ; les droits se règlent dans la politique de ton réseau Tailscale.</span></span>' +
        '<button class="btn" data-a="ssh" data-v="' + (ssh ? "0" : "1") + '"' + (bloque || e.ssh == null ? " disabled" : "") + ">" + (ssh ? "Couper" : "Activer") + "</button></div>" +
        '<div class="acts">' + (S.couper ? '<span class="confirme">Couper Tailscale sur cette machine ? Si tu t’y connectes par Tailscale, tu perdras l’accès. <button class="btn dng" data-a="deconnecter-oui">Oui, couper</button><button class="btn" data-a="deconnecter-non">Non</button></span>'
          : '<button class="btn" data-a="deconnecter"' + (bloque ? " disabled" : "") + ">Déconnecter</button>") +
        (S.quitter ? '<span class="confirme">Retirer cette machine du réseau ? Il faudra s’identifier à nouveau, et Cassandra perdra aussi son droit de piloter Tailscale (à rendre sur la machine : sudo tailscale set --operator=cassandra). <button class="btn dng" data-a="quitter-oui">Oui, la retirer</button><button class="btn" data-a="quitter-non">Non</button></span>'
          : '<button class="btn dng" data-a="quitter"' + (bloque ? " disabled" : "") + ">Retirer du réseau…</button>") + "</div></div>";
    }

    function dessiner() {
      const e = S.e;
      let h = '<div class="tete"><h1>Tailscale</h1><p class="sous">Le réseau privé de cette machine : la joindre de n’importe où sans ouvrir un seul port, et joindre tes autres machines.</p></div>';
      if (S.erreur) h += '<div class="carte" style="color:var(--danger)">' + esc(S.erreur) + "</div>";
      if (!e) { racine.innerHTML = h + '<div class="attente">Lecture de l’état de Tailscale…</div>'; return; }
      if (e.etat === "absent" || e.etat === "arrete") {
        h += '<div class="carte"><div>' + pastille(e) + '</div><p>' + esc(e.texte || "") + "</p>" +
          (e.etat === "absent" ? '<p class="note">Sur la machine : <span class="mono">CN_install.sh --module tailscale</span> installe le client et donne à Cassandra le droit de le piloter.</p>'
            : '<p class="note">Sur la machine : <span class="mono">sudo systemctl enable --now tailscaled</span>, puis recharge cet écran.</p>') + '<div class="acts"><button class="btn" data-a="relire">Relire</button></div></div>';
        racine.innerHTML = h; lier(); return;
      }
      h += '<div class="carte"><div class="hero"><div><span class="lib">État</span>' + pastille(e) + (e.sante && e.sante.length ? e.sante.slice(0, 3).map(sante).join("") : "") + "</div>" +
        (e.etat === "connecte" ? '<div><span class="lib">Cette machine</span><span class="gros">' + esc(e.nom || "—") + '</span><span class="note mono">' + esc(e.dns) + "</span></div>" +
          '<div><span class="lib">Adresse</span><span class="gros">' + esc(e.ip4 || "—") + '</span><span class="note mono">' + esc(e.ip6) + "</span></div>" +
          '<div><span class="lib">Réseau</span><span class="gros" style="font-size:16px">' + esc(e.reseau || "—") + '</span><span class="note">client ' + esc(e.version) + "</span></div>" : "") + "</div></div>";
      if (e.en_attente) h += e.lien ? carteLien(e) : '<div class="carte attente">Tailscale prépare le lien de connexion…</div>';
      else if (e.etat === "a_approuver") h += '<div class="carte"><p>La machine est identifiée mais l’administrateur de ton réseau Tailscale doit l’approuver (login.tailscale.com › Machines).</p></div>';
      else if (e.etat === "connecte") h += avisExpiration(e) + carteReseau(e) + carteGestes(e) + carteReglages(e);
      else h += carteConnexion(e);
      racine.innerHTML = h; lier();
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
      const n = racine.querySelector("#ts-nom"), s = racine.querySelector("#ts-ssh");
      if (n) n.addEventListener("input", () => { S.nom = n.value; });
      if (s) s.addEventListener("change", () => { S.ssh = s.checked; });
    }

    async function geste(b) {
      const a = b.dataset.a;
      if (a === "relire") return charger();
      if (a === "quitter") { S.quitter = true; dessiner(); return; }
      if (a === "quitter-non") { S.quitter = false; dessiner(); return; }
      if (a === "quitter-oui") return faire(() => agir("tailscale.quitter"), "Machine retirée du réseau Tailscale.");
      if (a === "deconnecter") { S.couper = true; dessiner(); return; }
      if (a === "deconnecter-non") { S.couper = false; dessiner(); return; }
      if (a === "deconnecter-oui") return faire(() => agir("tailscale.deconnecter"), "Tailscale est coupé sur cette machine.");
      if (a === "annuler") return faire(() => agir("tailscale.annuler"), "Connexion abandonnée.");
      if (a === "ping") {
        const m = b.dataset.m;
        S.ping[m] = "…"; dessiner();
        try { const r = await agir("tailscale.ping", { machine: m }); S.ping[m] = r.ok ? (r.chemin === "direct" ? "direct" : "par un relais") + " · " + r.ms + " ms" : "pas de réponse"; }
        catch (err) { S.ping[m] = err.message || String(err); }
        dessiner(); return;
      }
      if (a === "regler") {
        const cle = b.dataset.c, val = b.dataset.v === "1";
        if (val && cle === "shields_up" && !confirm("Le bouclier refuse toutes les connexions entrantes par Tailscale, SSH compris. Continuer ?")) return;
        if (val && cle === "advertise_exit_node" && !confirm("Offrir la sortie Internet de cette machine au réseau : l’administrateur devra l’approuver. Continuer ?")) return;
        return faire(() => agir("tailscale.regler", { cle: cle, valeur: val }), "Réglage appliqué.");
      }
      if (a === "regler-nom") return faire(() => agir("tailscale.regler", { cle: "hostname", valeur: String((racine.querySelector("#ts-r-nom") || {}).value || "").trim() }), "Nom changé.");
      if (a === "regler-routes") return faire(() => agir("tailscale.regler", { cle: "advertise_routes", valeur: String((racine.querySelector("#ts-r-routes") || {}).value || "") }), "Routes annoncées.");
      if (a === "regler-sortie") {
        const v = String((racine.querySelector("#ts-r-sortie") || {}).value || "");
        if (v && !confirm("Tout le trafic de cette machine passera par la machine choisie : si tu t’y connectes par Tailscale, tu peux perdre l’accès. Continuer ?")) return;
        return faire(() => agir("tailscale.regler", { cle: "exit_node", valeur: v }), v ? "Sortie Internet changée." : "Sortie Internet remise à la normale.");
      }
      if (a === "ssh") return faire(() => agir("tailscale.ssh_regler", { actif: b.dataset.v === "1" }), b.dataset.v === "1" ? "SSH par Tailscale activé." : "SSH par Tailscale coupé.");
      if (a === "connecter") {
        const nom = String((racine.querySelector("#ts-nom") || {}).value || "").trim();
        return faire(() => agir("tailscale.connecter", { nom: nom, ssh: S.ssh }), "");
      }
      if (a === "cle") {
        const cle = String((racine.querySelector("#ts-cle") || {}).value || "").trim();
        if (!/^tskey-[A-Za-z0-9_-]{8,}$/.test(cle)) { dire("Une clé du type tskey-auth-…", "err"); return; }
        const nom = String((racine.querySelector("#ts-nom") || {}).value || "").trim();
        return faire(async () => {
          await agir("reglages.regler_secret", { cle: "tailscale.cle_auth", valeur: cle });
          try { await agir("tailscale.connecter", { nom: nom, ssh: S.ssh, avec_cle: true }); }
          finally { try { await agir("reglages.reinitialiser", { cle: "tailscale.cle_auth" }); } catch (_) { /* la clé n’était pas gardée */ } }
        }, "Machine connectée à Tailscale.");
      }
    }

    racine.innerHTML = '<div class="attente">Lecture de l’état de Tailscale…</div>';
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l’écran et ses gestes.
// EC : néant.
// LIEN : modules/tailscale (le module et ses capacités), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
