// ═════════════════════════════════════════════════════════════════
// TITRE      : Tailscale : l’écran de connexion
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #065892
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l’écran « Tailscale » du module tailscale : où en est la machine, la connexion (par un lien à ouvrir ou par une clé), la déconnexion, SSH par Tailscale et les machines du réseau.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.tailscale) ; tout vient de tailscale.etat ; pendant une identification en attente, l’écran relit l’état toutes les 2,5 s et s’arrête seul quand il quitte la page.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=065892 ▼▼▼
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

  const age = (s) => { if (!s) return "jamais vue"; const d = new Date(String(s).replace(" ", "T") + ":00Z"); if (isNaN(d)) return s; const m = Math.max(0, Math.round((Date.now() - d) / 60000)); return m < 2 ? "à l’instant" : m < 90 ? "il y a " + m + " min" : m < 2160 ? "il y a " + Math.round(m / 60) + " h" : "il y a " + Math.round(m / 1440) + " j"; };
  const ETAT = { connecte: ["ok", "Connectée"], deconnecte: ["mu", "Déconnectée"], a_identifier: ["al", "En attente d’identification"], a_approuver: ["al", "À approuver par l’administrateur du réseau"],
    demarrage: ["al", "Démarrage…"], absent: ["dg", "Non installé"], arrete: ["dg", "tailscaled ne répond pas"] };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.tailscale = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("tailscale", corps); return; }
    const anc = document.getElementById("ts-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "ts-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "ts"; corps.appendChild(racine);

    const S = { e: null, occupe: false, erreur: "", quitter: false, nom: "", ssh: false };
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
      finally { S.occupe = false; S.quitter = false; await charger(); }
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

    function carteConnexion(e) {
      return '<div class="carte"><h2 style="font:650 16px Inter,system-ui,sans-serif">Connecter cette machine à ton réseau Tailscale</h2>' +
        '<p class="note">Tailscale relie tes machines entre elles par un réseau privé chiffré : plus besoin d’ouvrir de ports pour y accéder.</p>' +
        '<div class="champs"><label class="ch"><b>Nom de la machine</b><span class="note">Facultatif ; celui du système par défaut.</span><input type="text" id="ts-nom" value="' + esc(S.nom) + '" placeholder="argos" autocomplete="off" spellcheck="false"></label>' +
        '<label class="coche"><input type="checkbox" id="ts-ssh"' + (S.ssh ? " checked" : "") + '><span><b>SSH par Tailscale</b><br><span class="note">Entrer sur cette machine depuis ton réseau privé, sans clé SSH.</span></span></label></div>' +
        '<div class="acts"><button class="btn pri" data-a="connecter"' + (S.occupe ? " disabled" : "") + ">" + (S.occupe ? "Un instant…" : "Se connecter") + "</button></div>" +
        '<details><summary>J’ai une clé d’authentification</summary><p class="note" style="margin-bottom:8px">Créée sur login.tailscale.com › Settings › Keys. Elle sert une fois, n’est gardée nulle part et l’écran l’efface aussitôt.</p>' +
        '<div class="acts"><input type="password" id="ts-cle" placeholder="tskey-auth-…" autocomplete="off" spellcheck="false" style="flex:1 1 260px"><button class="btn" data-a="cle"' + (S.occupe ? " disabled" : "") + ">Se connecter avec la clé</button></div></details></div>";
    }

    function carteReseau(e) {
      const pairs = e.pairs || [];
      let h = '<div class="carte"><div class="acts" style="justify-content:space-between"><h2 style="font:650 16px Inter,system-ui,sans-serif">Les machines du réseau <span class="note">(' + e.en_ligne + " en ligne sur " + pairs.length + ")</span></h2></div>";
      h += pairs.length ? '<div class="pairs">' + pairs.map((p) => '<div class="pair"><span class="pt' + (p.en_ligne ? " on" : "") + '"></span><span class="nom">' + esc(p.nom) + (p.sortie ? ' <span class="pastille al">sortie</span>' : "") + '</span><span class="mono ip note">' + esc(p.ip) + "</span><span class=\"note\">" + (p.en_ligne ? "en ligne" : age(p.vu)) + "</span></div>").join("") + "</div>"
        : '<p class="note">Aucune autre machine sur ce réseau pour l’instant. Installe Tailscale ailleurs et connecte-la au même compte.</p>';
      return h + "</div>";
    }

    function carteGestes(e) {
      const ssh = e.ssh === true;
      return '<div class="carte"><h2 style="font:650 16px Inter,system-ui,sans-serif">Réglages</h2>' +
        '<div class="coche"><span style="flex:1"><b>SSH par Tailscale</b> ' + (e.ssh == null ? '<span class="pastille mu">inconnu</span>' : ssh ? '<span class="pastille ok">activé</span>' : '<span class="pastille mu">coupé</span>') +
        '<br><span class="note">Entrer sur la machine depuis ton réseau privé sans clé SSH ; les droits se règlent dans la politique de ton réseau Tailscale.</span></span>' +
        '<button class="btn" data-a="ssh" data-v="' + (ssh ? "0" : "1") + '"' + (S.occupe || e.ssh == null ? " disabled" : "") + ">" + (ssh ? "Couper" : "Activer") + "</button></div>" +
        '<div class="acts"><button class="btn" data-a="deconnecter"' + (S.occupe ? " disabled" : "") + ">Déconnecter</button>" +
        (S.quitter ? '<span class="confirme">Retirer cette machine du réseau ? Il faudra s’identifier à nouveau. <button class="btn dng" data-a="quitter-oui">Oui, la retirer</button><button class="btn" data-a="quitter-non">Non</button></span>'
          : '<button class="btn dng" data-a="quitter"' + (S.occupe ? " disabled" : "") + ">Retirer du réseau…</button>") + "</div></div>";
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
      h += '<div class="carte"><div class="hero"><div><span class="lib">État</span>' + pastille(e) + (e.sante && e.sante.length ? '<span class="sante">' + esc(e.sante[0]) + "</span>" : "") + "</div>" +
        (e.etat === "connecte" ? '<div><span class="lib">Cette machine</span><span class="gros">' + esc(e.nom || "—") + '</span><span class="note mono">' + esc(e.dns) + "</span></div>" +
          '<div><span class="lib">Adresse</span><span class="gros">' + esc(e.ip4 || "—") + '</span><span class="note mono">' + esc(e.ip6) + "</span></div>" +
          '<div><span class="lib">Réseau</span><span class="gros" style="font-size:16px">' + esc(e.reseau || "—") + '</span><span class="note">client ' + esc(e.version) + "</span></div>" : "") + "</div></div>";
      if (e.en_attente) h += e.lien ? carteLien(e) : '<div class="carte attente">Tailscale prépare le lien de connexion…</div>';
      else if (e.etat === "a_approuver") h += '<div class="carte"><p>La machine est identifiée mais l’administrateur de ton réseau Tailscale doit l’approuver (login.tailscale.com › Machines).</p></div>';
      else if (e.etat === "connecte") h += carteReseau(e) + carteGestes(e);
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
      if (a === "deconnecter") return faire(() => agir("tailscale.deconnecter"), "Tailscale est coupé sur cette machine.");
      if (a === "annuler") return faire(() => agir("tailscale.annuler"), "Connexion abandonnée.");
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
