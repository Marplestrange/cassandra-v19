// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : ▼▼▼ BORNE CN version=0
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #b2098c
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=b2098c ▼▼▼
// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Sensorium » du module sensorium : ce que Cassandra sait de la machine et de son monde (maintenant, par famille, ce qui a changé, les capteurs eux-mêmes, la flotte).
// Les données viennent des capacités du module : sensorium.monde (les relevés), sensorium.changements, sensorium.historique (l'histoire d'un relevé).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, ic = K.ic, pill = K.pill, agir = K.agir;
  const SCENES = [["maintenant", "Maintenant"], ["famille", "Par famille"], ["changements", "Ce qui a changé"], ["capteurs", "Les capteurs"]];
  const FAMILLES = [
    ["system", "Système", "system."], ["ressources", "Ressources", "cpu.|ram.|swap.|load.|disk.|montage."], ["service", "Services", "service.|systemd."],
    ["docker", "Conteneurs", "docker.|conteneur_ressources.|image."], ["web", "Sites", "web."], ["controle", "Contrôles de bout en bout", "controle."],
    ["ssl", "Certificats", "ssl."], ["sauvegarde", "Sauvegardes", "sauvegarde."], ["prevision", "Ce qui va arriver", "prevision."],
    ["flotte", "Flotte", "fleet.|machine."], ["config", "Config de Cassandra", "config."], ["logiciel", "Logiciels", "logiciel."],
    ["reseau", "Réseau", "interface.|port."], ["stockage", "Stockage", "stockage."], ["securite", "Sécurité", "security."],
    ["maj", "Mises à jour", "maj."], ["courriel", "Courriel", "courriel.|domaine_courriel."], ["acces", "Accès et pare-feu", "ssh.|cle_ssh.|pare_feu.|fail2ban.|prison."],
    ["cron", "Tâches planifiées", "cron."], ["fastpanel", "FastPanel", "fastpanel."], ["erreurs", "Erreurs des journaux", "erreurs.|journaux."],
    ["certbot", "Renouvellement des certificats", "certbot."], ["box", "La box", "box.|dns_local"], ["outils", "Outils de sécurité", "outil_secu."],
    ["tailnet", "Tailnet", "tailnet."], ["capteur", "Capteurs", "capteur."], ["sante", "Santé", "health."],
  ];
  const MACH = { os: "système", antivirus: "antivirus", charge: "charge", mises_a_jour: "mises à jour", services_en_echec: "services en échec", echecs_au_demarrage: "échecs au démarrage" };
  const CHANGE = { added: "apparu", removed: "disparu", modified: "changé" };

  const famDe = (wk) => { for (const f of FAMILLES) if (f[2].split("|").some((p) => wk.indexOf(p) === 0)) return f[0]; return "autre"; };
  const nomDe = (wk) => { const i = wk.indexOf("."); return i >= 0 ? wk.slice(i + 1) : wk; };
  const epoch = (ts) => { if (!ts) return 0; let t = String(ts); if (!/[zZ]$|[+-]\d\d:?\d\d$/.test(t)) t = t.replace(" ", "T"); const d = new Date(t); return isNaN(d) ? 0 : d.getTime() / 1000; };
  const age = (ts) => { const e = epoch(ts); return e ? K.depuis(e) : "date inconnue"; };
  const court = (ts) => String(ts || "").replace("T", " ").slice(0, 16);
  const mach = (cle) => (cle.indexOf("disque.") === 0 ? "disque " + cle.slice(7) : MACH[cle] || cle.replace(/_/g, " "));
  const causes = (r) => { try { const d = r.detail ? (typeof r.detail === "string" ? JSON.parse(r.detail) : r.detail) : null; return (d && d.causes_probables) || []; } catch (e) { return []; } };
  const lignesDe = (m) => (Array.isArray(m) ? m : (m && (m.rows || m.monde || m.entites || m.lignes)) || []);

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.sensorium = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("sensorium", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "maintenant", rows: null, changes: null, fam: "", histo: null, erreur: "", charge: true };

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0]) + '">' + esc(s[1]) + "</button>").join("") + "</div>";
    const alerte = (r) => r.severity === "warning";
    const valeur = (k) => ((S.rows || []).find((r) => r.wkey === k) || {}).value;

    function ligne(r) {
      const wk = String(r.wkey || ""), w = alerte(r), c = causes(r);
      return '<div class="li"><div class="sp"><b><a href="#" data-a="histo" data-k="' + esc(wk) + '" title="' + esc(wk) + ' — son histoire sur 30 jours">' + esc(r.libelle || nomDe(wk)) + "</a> " + (w ? pill("à voir", "al", "warn") : "") + "</b>" +
        '<span class="note">' + esc(r.value == null ? "" : r.value) + "</span>" +
        (c.length ? '<span class="note" style="color:var(--warn)">cause probable : ' + esc(c[0]) + (c.length > 1 ? " (+" + (c.length - 1) + ")" : "") + "</span>" : "") +
        '</div><span class="faint mono" style="font-size:11.5px" title="' + esc(r.observed_at || "") + '">' + esc(age(r.observed_at)) + "</span></div>";
    }
    const kpi = (lib, v, em) => (v ? '<div class="carte"><span class="note">' + esc(lib) + '</span><div style="font-size:22px;font-weight:600">' + esc(v) + "</div>" + (em ? '<span class="note">' + esc(em) + "</span>" : "") + "</div>" : "");

    function maintenant() {
      const rows = S.rows || [];
      const al = rows.filter((r) => alerte(r) && r.wkey.indexOf("capteur.") !== 0);
      const ko = rows.filter((r) => alerte(r) && r.wkey.indexOf("capteur.") === 0);
      const prev = rows.filter((r) => r.wkey.indexOf("prevision.") === 0);
      const sante = String(valeur("health.score") || ""), i = sante.indexOf(" · ");
      const titre = al.length ? al.length + (al.length > 1 ? " points demandent un regard" : " point demande un regard") : "Tout ce qui est mesuré va bien";
      const haut = '<div class="carte"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h3 style="flex:1;min-width:200px">' + esc(titre) + "</h3>" + pill(al.length ? "à voir" : "stable", al.length ? "al" : "", al.length ? "warn" : "") + "</div>" +
        '<p class="note">' + esc([valeur("system.hostname"), valeur("system.os"), valeur("system.uptime") ? "allumée depuis " + valeur("system.uptime") : "", rows.length + " relevés"].filter(Boolean).join(" · ")) + "</p>" +
        (ko.length ? '<p class="note"><a href="#" data-s="capteurs" style="color:var(--warn)">' + ko.length + " capteur" + (ko.length > 1 ? "s" : "") + " en défaut</a></p>" : "") + "</div>";
      const chiffres = '<div class="grille-m">' + kpi("Santé", i > 0 ? sante.slice(0, i) : sante, i > 0 ? sante.slice(i + 3) : "") + kpi("Disque /", valeur("disk./.usage")) + kpi("RAM", valeur("ram.usage")) +
        kpi("Charge", valeur("load.1m"), valeur("cpu.load") ? "CPU " + valeur("cpu.load") : "") + kpi("Température", valeur("system.temperature")) + "</div>";
      const regard = al.length ? '<div class="carte"><h3>Ce qui demande un regard</h3><div class="liste">' + al.map(ligne).join("") + "</div></div>" : "";
      const futur = prev.length ? '<div class="carte"><h3>Ce qui va arriver</h3><div class="liste">' + prev.map(ligne).join("") + "</div></div>" : "";
      const flotte = rows.filter((r) => r.wkey.indexOf("fleet.") === 0).map((r) => {
        const m = r.wkey.slice(6), det = rows.filter((x) => x.wkey.indexOf("machine." + m + ".") === 0 && !/\.sonde$/.test(x.wkey));
        const w = alerte(r) || det.some(alerte);
        const txt = det.slice(0, 4).map((x) => { const c = x.wkey.split(".").slice(2).join("."), v = String(x.value || ""); return mach(c) + " " + (c === "mises_a_jour" ? v.replace(/^dernière mise à jour\s*/, "") : v); }).join(" · ");
        return '<div class="li"><div class="sp"><b>' + esc(m) + " " + (w ? pill("à voir", "al", "warn") : "") + '</b><span class="note">' + esc(r.value || "") + (txt ? " · " + esc(txt) : "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(age(r.observed_at)) + "</span></div>";
      }).join("");
      return haut + chiffres + regard + futur + '<div class="carte"><h3>La flotte</h3>' + (flotte ? '<div class="liste">' + flotte + "</div>" : '<div class="vide">Aucune machine relevée.</div>') + "</div>";
    }
    function famille() {
      const par = {}; (S.rows || []).forEach((r) => { const f = famDe(String(r.wkey || "")); (par[f] = par[f] || { n: 0, w: 0 }); par[f].n++; if (alerte(r)) par[f].w++; });
      const puces = '<div class="chips">' + FAMILLES.filter((f) => par[f[0]]).map((f) => '<button class="p ' + (S.fam === f[0] ? "on" : par[f[0]].w ? "al" : "") + '" data-a="fam" data-k="' + f[0] + '">' + esc(f[1]) + " " + (par[f[0]].w ? par[f[0]].w + " ⚠" : par[f[0]].n) + "</button>").join("") + "</div>";
      if (!S.fam) return '<div class="carte"><h3>Les relevés, par famille</h3>' + (puces.indexOf("data-a") >= 0 ? puces : '<div class="vide">Rien de relevé.</div>') + "</div>";
      const lib = (FAMILLES.find((f) => f[0] === S.fam) || [])[1] || S.fam;
      const sel = (S.rows || []).filter((r) => famDe(String(r.wkey || "")) === S.fam).sort((a, b) => alerte(b) - alerte(a) || String(a.wkey).localeCompare(String(b.wkey)));
      return '<div class="carte">' + puces + "</div>" + '<div class="carte"><h3>' + esc(lib) + " · " + sel.length + " relevé" + (sel.length > 1 ? "s" : "") + '</h3><div class="liste">' + sel.map(ligne).join("") + "</div></div>";
    }
    function changements() {
      const ch = S.changes || [];
      return '<div class="carte"><h3>Derniers changements</h3><div class="liste">' + (ch.length ? ch.map((c) => '<div class="li"><div class="sp"><b>' + esc(c.entity_name || c.wkey || "") + " " + pill(CHANGE[c.change_type] || c.change_type || "", c.severity === "warning" ? "al" : "") + '</b><span class="note">' + esc(c.new_value != null ? c.new_value : "") + (c.old_value != null && c.old_value !== "" ? " (avant : " + esc(c.old_value) + ")" : "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(c.timestamp || c.ts || c.observed_at)) + "</span></div>").join("") : '<div class="vide"><b>Rien n’a changé</b> depuis la dernière relève.</div>') + "</div></div>";
    }
    function capteurs() {
      const cap = (S.rows || []).filter((r) => String(r.wkey || "").indexOf("capteur.") === 0);
      return '<div class="carte"><h3>Les capteurs eux-mêmes · ' + cap.filter(alerte).length + " en défaut</h3><p class=\"note\">Un capteur en panne ou muet ne mesure plus : ce qu’il avait relevé vieillit sans le dire. On le dit ici.</p>" +
        '<div class="liste">' + (cap.length ? cap.map(ligne).join("") : '<div class="vide">Aucun capteur déclaré.</div>') + "</div></div>";
    }
    function histoire() {
      const H = S.histo; if (!H) return "";
      const h = Array.isArray(H.donnees) ? H.donnees : H.donnees && (H.donnees.historique || H.donnees.points) || [];
      const dispo = H.donnees && H.donnees.disponibilite_30j;
      return '<div class="carte"><div class="barre"><h3 style="flex:1">' + esc(H.titre) + '</h3><button class="bt" data-a="fermer">Fermer</button></div>' +
        (dispo != null ? '<p class="note">Disponibilité sur 30 jours : <b>' + esc(dispo) + " %</b></p>" : "") +
        '<div class="liste">' + (h.length ? h.map((c) => '<div class="li"><div class="sp"><b>' + esc(CHANGE[c.change_type] || c.change_type || "") + '</b><span class="note">' + esc(c.new_value != null ? c.new_value : c.v != null ? c.v : "") + '</span></div><span class="faint mono" style="font-size:11.5px">' + esc(court(c.timestamp || c.ts)) + "</span></div>").join("") : '<div class="vide">Aucun changement en 30 jours.</div>') + "</div></div>";
    }

    function dessiner() {
      let c;
      if (S.charge) c = '<div class="carte vide">Lecture…</div>';
      else if (!S.rows) c = '<div class="carte"><h3>Le sensorium ne répond pas</h3><p class="note">' + esc(S.erreur || "Le collecteur n’a rien rendu.") + "</p></div>";
      else c = histoire() + ({ maintenant: maintenant, famille: famille, changements: changements, capteurs: capteurs }[S.scene] || maintenant)();
      racine.innerHTML = K.titre("Sensorium", "Ce que Cassandra sait de la machine et de son monde.") + barre() + c;
    }
    async function charger() {
      S.charge = true; dessiner();
      const [m, c] = await Promise.all([lire("sensorium.monde"), lire("sensorium.changements")]);
      S.rows = m ? lignesDe(m) : null; S.changes = Array.isArray(c) ? c : (c && (c.changes || c.changements)) || [];
      S.charge = false; dessiner();
    }
    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); S.scene = s.dataset.s; S.histo = null; dessiner(); return; }
      const a = e.target.closest("[data-a]"); if (!a) return; e.preventDefault();
      const k = a.dataset.a;
      if (k === "fam") { S.fam = a.dataset.k; dessiner(); }
      else if (k === "fermer") { S.histo = null; dessiner(); }
      else if (k === "histo") { const r = await lire("sensorium.historique", { cle: a.dataset.k }); S.histo = { titre: a.dataset.k, donnees: r || {} }; dessiner(); }
    });
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
