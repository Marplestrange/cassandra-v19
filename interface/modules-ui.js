/* Les modules dans les Réglages : la gestion des modules et leurs réglages, sans qu'aucun écran ne soit écrit à la main.

   Réglages a maintenant trois visions :
     - « Mon compte » reçoit une famille « Mes modules » : les réglages de portée COMPTE que les modules déclarent (boîte mail, CalDAV, voix…) ;
     - « La machine » reste celle de la V18 ;
     - « Modules » (administrateur) : le catalogue (actif, inactif, à installer, refusé), le geste d'activer ou de désactiver, ce qui dépend de quoi,
       et, dans la fiche de chaque module, ses réglages GLOBAUX. Une famille de modules = une entrée du rail.

   Tout vient de ce que les modules déclarent : le catalogue (modules.lister) et leurs réglages (reglages.lire). Un nouveau module apparaît ici sans
   toucher à l'interface. Chargé APRÈS shell.js : il enveloppe setVision, setVisionDe et setFam de la V18. */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const LIB = { socle: "Socle", moteurs: "Moteurs", reseau: "Réseau", securite: "Sécurité", sites: "Sites", communication: "Communication", travail: "Travail", gestion: "Gestion",
                supervision: "Supervision", echanges: "Échanges", agents: "Agents", hebergement: "Hébergement", canaux: "Canaux", systeme: "Système", autres: "Autres", "refusés": "Refusés" };
  const ORDRE = ["socle", "securite", "reseau", "hebergement", "sites", "communication", "echanges", "canaux", "gestion", "travail", "supervision", "agents", "moteurs", "systeme", "autres", "refusés"];
  const ETATS = { actif: ["Actif", "ok"], inactif: ["Inactif", ""], a_installer: ["À installer", "warn"], refuse: ["Refusé", "bad"] };
  const famLib = (f) => LIB[f] || (f ? f[0].toUpperCase() + f.slice(1) : "Autres");

  let catalogue = [], reglages = [], gere = true;

  function pret() { return typeof SET_VISIONS !== "undefined" && document.getElementById("set-corps"); }
  const admin = () => { try { return setEstAdmin(); } catch (e) { return false; } };
  const nomDe = (mid) => { const m = catalogue.find((x) => x.id === mid); return m ? m.nom : mid; };

  // ── ce qu'on lit ────────────────────────────────────────────────────
  async function lire() {
    reglages = ((await CASS.agir("reglages.lire", {})) || {}).reglages || [];
    catalogue = [];
    if (admin()) { try { const l = (await CASS.agir("modules.lister", {})) || {}; catalogue = l.modules || []; gere = l.gere !== false; } catch (e) { catalogue = []; } }
    if (!gere) catalogue.forEach((m) => { if (m.etat !== "refuse") m.etat = "actif"; });      // instance de développement : tout ce qui est chargé tourne
    if (!catalogue.length) {            // sans le droit : au moins les noms, depuis la porte publique du noyau
      try { const d = await (await fetch("/api/modules")).json(); catalogue = (d.modules || []).map((m) => Object.assign({ requiert: [], requis_par: [], peut_activer: {}, peut_desactiver: {} }, m)); } catch (e) {}
    }
  }
  const familles = () => {
    const f = [...new Set(catalogue.map((m) => m.famille || "autres"))];
    return f.sort((a, b) => (ORDRE.indexOf(a) < 0 ? 99 : ORDRE.indexOf(a)) - (ORDRE.indexOf(b) < 0 ? 99 : ORDRE.indexOf(b)) || a.localeCompare(b));
  };

  // ── le rail et les sections, posés une fois ─────────────────────────
  function bouton(fam, titre, sous, icone) {
    const b = document.createElement("button");
    b.className = "set-nav-item"; b.setAttribute("data-fam", fam); b.setAttribute("role", "tab");
    b.onclick = () => window.setFam(fam);
    b.innerHTML = '<span class="set-nav-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + icone + "</svg></span>" +
                  "<span><b>" + esc(titre) + "</b><i>" + esc(sous) + "</i></span>";
    return b;
  }
  function section(fam, id) {
    const s = document.createElement("div");
    s.className = "settings-section"; s.setAttribute("data-fam", fam); s.id = id; s.style.display = "none";
    return s;
  }
  const ICO_MOD = '<path d="M12 3 4 7v10l8 4 8-4V7z"/><path d="M4 7l8 4 8-4M12 11v10"/>';
  const ICO_FAM = '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>';

  function monter() {
    const rail = document.querySelector("#tab-settings .set-nav"), lay = document.querySelector("#tab-settings .settings-layout");
    if (!rail || !lay) return false;
    // la vision « Modules », après « La machine »
    const vis = document.getElementById("set-visions");
    if (vis && !vis.querySelector('[data-vis="modules"]')) {
      const b = document.createElement("button");
      b.className = "mx-scene set-vis"; b.setAttribute("data-vis", "modules"); b.setAttribute("aria-pressed", "false"); b.textContent = "Modules";
      b.onclick = () => window.setVision("modules");
      vis.appendChild(b);
    }
    // « Mes modules » dans Mon compte
    if (!rail.querySelector('[data-fam="moi-modules"]')) {
      const b = bouton("moi-modules", "Mes modules", "Ce que les modules vous laissent régler", ICO_MOD);
      const ancre = rail.querySelector('[data-fam="moi-securite"]');
      ancre ? ancre.after(b) : rail.appendChild(b);
      lay.appendChild(section("moi-modules", "set-mod-moi"));
      SET_VISIONS.moi.push("moi-modules"); SET_FAMILLES.push("moi-modules");
    }
    // la vision Modules : une entrée « Tous » puis une par famille (refaites à chaque lecture du catalogue)
    for (const x of rail.querySelectorAll("[data-mods]")) x.remove();
    SET_VISIONS.modules = [];
    const liste = [["mods-tous", "Tous les modules", catalogue.filter((m) => m.etat === "actif").length + " actifs sur " + catalogue.length, ICO_MOD]]
      .concat(familles().map((f) => ["mods-" + f, famLib(f), catalogue.filter((m) => (m.famille || "autres") === f).length + " module(s)", ICO_FAM]));
    for (const [fam, titre, sous, ico] of liste) {
      const b = bouton(fam, titre, sous, ico); b.setAttribute("data-mods", "1");
      b.style.display = (ETAT.reglages && ETAT.reglages._setVision === "modules") ? "" : "none";
      const n = document.createElement("span"); n.className = "n"; n.textContent = fam === "mods-tous" ? catalogue.length : catalogue.filter((m) => "mods-" + (m.famille || "autres") === fam).length; b.appendChild(n);
      rail.appendChild(b);
      SET_VISIONS.modules.push(fam);
      if (SET_FAMILLES.indexOf(fam) < 0) SET_FAMILLES.push(fam);
      if (!document.getElementById("set-" + fam)) lay.appendChild(section(fam, "set-" + fam));
    }
    return true;
  }

  // ── une ligne de réglage ────────────────────────────────────────────
  function champ(r) {
    const id = "rgm-" + r.cle.replace(/[^a-z0-9]/gi, "_");
    let ctl;
    if (r.type === "booleen") ctl = '<input type="checkbox" id="' + id + '" ' + (r.valeur ? "checked" : "") + ">";
    else if (r.type === "choix") ctl = '<select id="' + id + '" class="inp">' + (r.choix || []).map((c) => '<option value="' + esc(c) + '"' + (String(c) === String(r.valeur) ? " selected" : "") + ">" + esc(c) + "</option>").join("") + "</select>";
    else if (r.type === "secret") ctl = '<input type="password" id="' + id + '" class="inp" autocomplete="new-password" placeholder="' + (r.pose ? "•••••• défini — saisir pour remplacer" : "non défini") + '">';
    else if (r.type === "entier") ctl = '<input type="number" id="' + id + '" class="inp" value="' + esc(r.valeur) + '">';
    else ctl = '<input type="text" id="' + id + '" class="inp" value="' + esc(r.valeur) + '">';
    ctl = ctl.replace("<input ", '<input style="font-size:12px;padding:4px 8px;min-width:0;flex:1" ').replace("<select ", '<select style="font-size:12px;padding:4px 8px;flex:1" ');
    return '<div class="rgm" data-cle="' + esc(r.cle) + '" data-type="' + r.type + '" style="display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--bd,rgba(0,0,0,.08));flex-wrap:wrap;font-size:12px">' +
           '<label for="' + id + '" style="flex:1 1 220px;min-width:0;font-size:12px;text-transform:none;letter-spacing:0;margin:0"><b style="font-weight:600;font-size:12px">' + esc(r.libelle) + "</b>" + (r.aide ? '<div class="s-hint">' + esc(r.aide) + "</div>" : "") + "</label>" +
           '<div style="flex:1 1 220px;min-width:0;display:flex;gap:6px;align-items:center">' + ctl +
           '<button class="btn-x mini" data-defaut style="' + (r.pose ? "" : "visibility:hidden") + '" title="Rendre le défaut">Défaut</button>' +
           '<span class="rgm-etat s-hint" style="min-width:64px"></span></div></div>';
  }
  function lierChamps(racine, recharger) {
    racine.querySelectorAll(".rgm").forEach((ligne) => {
      const cle = ligne.dataset.cle, type = ligne.dataset.type, ctl = ligne.querySelector("input,select"), etat = ligne.querySelector(".rgm-etat");
      const dire = (t, bad) => { etat.textContent = t; etat.style.color = bad ? "var(--danger,#b3261e)" : ""; };
      ctl.addEventListener("change", async () => {
        let v = type === "booleen" ? ctl.checked : type === "entier" ? Number(ctl.value) : ctl.value;
        if (type === "secret" && !ctl.value) return;
        dire("…");
        try {
          await CASS.agir(type === "secret" ? "reglages.regler_secret" : "reglages.regler", { cle, valeur: v });
          if (type === "secret") ctl.value = "";
          dire("✓ enregistré"); setTimeout(recharger, 700);
        } catch (e) { dire(e.message, true); }
      });
      ligne.querySelector("[data-defaut]").addEventListener("click", async () => {
        dire("…");
        try { await CASS.agir("reglages.reinitialiser", { cle }); recharger(); } catch (e) { dire(e.message, true); }
      });
    });
  }

  // Les réglages d'UN module (pour sa console) : globaux pour l'administrateur, personnels pour les autres.
  CASS.reglagesDe = async function (mid, el) {
    if (!reglages.length) { try { await lire(); } catch (e) { el.innerHTML = '<div class="s-hint">' + esc(e.message) + "</div>"; return; } }
    const mes = reglages.filter((r) => r.module === mid);
    el.innerHTML = mes.length ? "<div class=\"s-hint\">Chaque champ s’enregistre dès que vous le quittez ; « Défaut » rend la valeur d’origine.</div>" + mes.map((r) => champ(r)).join("") : '<div class="s-hint">Ce module ne déclare aucun réglage.</div>';
    lierChamps(el, async () => { await lire(); CASS.reglagesDe(mid, el); });
  };

  // ── la fiche d'un module ────────────────────────────────────────────
  function fiche(m, portee, compact) {
    const [lib, cls] = ETATS[m.etat] || [m.etat, ""];
    const mes = reglages.filter((r) => r.module === m.id && r.portee === portee);
    const pastille = '<span class="pill ' + cls + '" style="font-size:10px;padding:1px 8px;border-radius:9px;border:1px solid currentColor;' + (cls === "ok" ? "color:var(--ok,#1b7f5c)" : cls === "warn" ? "color:var(--warn,#a86400)" : cls === "bad" ? "color:var(--danger,#b3261e)" : "color:var(--txt-faint,#777)") + '">' + esc(lib) + "</span>";
    let geste = "";
    if (portee === "global" && admin() && !gere) geste = '<span class="s-hint">Instance de développement : tous les modules sont chargés</span>';
    else if (portee === "global" && admin()) {
      if (m.etat === "actif") geste = m.peut_desactiver && m.peut_desactiver.ok
        ? '<button class="btn-x mini" data-geste="desactiver" data-mod="' + esc(m.id) + '">Désactiver</button>'
        : '<button class="btn-x mini" disabled title="' + esc((m.peut_desactiver || {}).raison || "") + '">Désactiver</button>';
      else if (m.etat === "inactif") geste = m.peut_activer && m.peut_activer.ok
        ? '<button class="btn-x mini pri" data-geste="activer" data-mod="' + esc(m.id) + '">Activer</button>'
        : '<button class="btn-x mini" disabled title="' + esc((m.peut_activer || {}).raison || "") + '">Activer</button>';
      else if (m.etat === "a_installer") geste = '<span class="s-hint">À installer sur la machine (script d\'installation du module), puis à activer</span>';
    }
    const deps = [];
    if ((m.requiert || []).length) deps.push("requiert " + m.requiert.map(nomDe).join(", "));
    if ((m.requis_par || []).length) deps.push("requis par " + m.requis_par.map(nomDe).join(", "));
    const meta = [m.version ? "v" + m.version : "", m.capacites != null ? m.capacites + " capacités" : "", m.essentiel ? "essentiel" : ""].filter(Boolean).join(" · ");
    const ouvrir = (portee === "global" && m.etat === "actif") ? '<button class="btn-x mini" data-ouvrir="' + esc(m.id) + '" data-nom="' + esc(m.nom) + '" title="Lire, agir et régler ce module">Ouvrir</button>' : "";
    return '<div class="rgm-fiche" data-id="' + esc(m.id) + '" style="padding:10px 0;border-top:1px solid var(--bd,rgba(0,0,0,.08))">' +
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b style="font-size:13px">' + esc(m.nom) + "</b>" + pastille +
      '<span class="s-hint" style="flex:1">' + esc(meta) + "</span>" + ouvrir + geste + "</div>" +
      (m.description && !compact ? '<div class="s-hint" style="margin-top:4px">' + esc((m.description.length > 260 ? m.description.slice(0, 257) + "…" : m.description)) + "</div>" : "") +
      (deps.length ? '<div class="s-hint">' + esc(deps.join(" — ")) + "</div>" : "") +
      (mes.length && !compact ? '<details style="margin-top:6px"' + (portee === "compte" ? " open" : "") + '><summary class="s-hint" style="cursor:pointer">' + mes.length + " réglage" + (mes.length > 1 ? "s" : "") + "</summary>" + mes.map(champ).join("") + "</details>" : "") + "</div>";
  }

  function gestes(racine) {
    racine.querySelectorAll("[data-ouvrir]").forEach((b) => b.addEventListener("click", () => CASS.ouvrirConsole(b.dataset.ouvrir, b.dataset.nom)));
    racine.querySelectorAll("[data-geste]").forEach((b) => b.addEventListener("click", async () => {
      const mid = b.dataset.mod, g = b.dataset.geste;
      let cascade = false;
      b.disabled = true; b.textContent = "…";
      try {
        const r = await CASS.agir("modules." + g, { module: mid });
        const n = (r.actives || r.desactives || []).length;
        if (typeof toast === "function") toast((g === "activer" ? "Activé" : "Désactivé") + " : " + nomDe(mid) + (n > 1 ? " (+ " + (n - 1) + " lié(s))" : ""), "ok");
      } catch (e) {
        if (typeof toast === "function") toast(e.message, "err");
      }
      await rendre(true);
    }));
  }

  // ── le rendu d'une famille ──────────────────────────────────────────
  async function rendre(relire) {
    if (relire !== false || !catalogue.length) { try { await lire(); } catch (e) { console.warn("modules-ui", e); } monter(); }
    const fam = (typeof ETAT !== "undefined" && ETAT.reglages && ETAT.reglages._setFam) || "";
    if (fam === "moi-modules") {
      const el = document.getElementById("set-mod-moi"); if (!el) return;
      const mods = catalogue.filter((m) => reglages.some((r) => r.module === m.id && r.portee === "compte"));
      el.innerHTML = '<div class="settings-section-title">Mes modules</div><div class="s-hint">Ce que chaque module vous laisse régler pour vous seul. Chaque champ s\'enregistre dès que vous le quittez ; « Défaut » rend la valeur d\'origine. Les mots de passe ne s\'affichent jamais.</div>' +
        (mods.map((m) => fiche(m, "compte")).join("") || '<div class="s-hint">Aucun module actif ne propose de réglage personnel.</div>');
      lierChamps(el, () => rendre(true));
    } else if (fam.indexOf("mods-") === 0) {
      const el = document.getElementById("set-" + fam); if (!el) return;
      const f = fam.slice(5);
      const mods = f === "tous" ? catalogue : catalogue.filter((m) => (m.famille || "autres") === f);
      const tete = f === "tous" ? "Tous les modules" : famLib(f);
      el.innerHTML = '<div class="settings-section-title">' + esc(tete) + '</div><div class="s-hint">Activer un module branche à chaud ses menus, ses capacités et ses moteurs ; le désactiver les retire, <b>ses données restent</b>. Un module essentiel, ou dont un autre dépend, ne se désactive pas sans cascade.</div>' +
        mods.map((m) => fiche(m, "global", f === "tous")).join("");
      gestes(el); lierChamps(el, () => rendre(true));
    }
  }

  function compter() {       // la V18 compte des sections par famille ; ici une famille compte des modules
    document.querySelectorAll("[data-mods]").forEach((b) => {
      const fam = b.getAttribute("data-fam"), n = b.querySelector(".n");
      if (n) n.textContent = fam === "mods-tous" ? catalogue.length : catalogue.filter((m) => "mods-" + (m.famille || "autres") === fam).length;
    });
  }
  // ── l'enveloppe des fonctions V18 ───────────────────────────────────
  let branche = false;
  function brancher() {
    if (branche) return;
    if (!pret() || typeof window.setVision !== "function") return setTimeout(brancher, 300);
    branche = true;
    SET_VISIONS.modules = SET_VISIONS.modules || [];        // la vision existe avant que le catalogue soit lu : le rail se remplit ensuite
    const visionDe = window.setVisionDe;
    window.setVisionDe = function (fam) {
      if (String(fam).indexOf("mods-") === 0) return "modules";
      return visionDe(fam);
    };
    const vision = window.setVision;
    window.setVision = function (v) {
      if (v === "modules" && !admin()) v = "moi";
      vision(v);
      compter();
      if (v === "modules") {
        const t = document.getElementById("set-rail-titre"), s = document.getElementById("set-rail-sous"), n = document.getElementById("set-note");
        if (t) t.textContent = "Modules";
        if (s) s.textContent = "ce qui est installé et actif";
        if (n) n.innerHTML = "La gestion des modules : <b>ce qui est actif, ce qui dépend de quoi</b>, et les réglages propres à chaque module. Un module neuf n'est jamais activé de lui-même.";
      }
    };
    const fam = window.setFam;
    window.setFam = function (f) {
      fam(f);
      if (f === "moi-modules" || String(f).indexOf("mods-") === 0) rendre(true);
    };
    rendre(true);
  }

  const demarrage = CASS.surConnexion;
  CASS.surConnexion = function () { if (demarrage) demarrage(); setTimeout(brancher, 500); };
  window.addEventListener("load", () => setTimeout(brancher, 900));
})();
