// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : ▼▼▼ BORNE CN version=0
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #b3cc1a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=b3cc1a ▼▼▼
// ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
// L'écran « Hébergement » du module fastpanel : l'état du panneau et ses audits, les sites et leurs certificats, PHP, les bases, les sauvegardes (copies, plans, stockages), le courriel, le FTP, le DNS, les comptes, les services.
// Les données viennent des capacités du module (fastpanel.resume, audit, sites, certificats, ssl_sonder, php, bases, sauvegardes, plans, stockages, ftp, mail, dns, utilisateurs, services) ; les gestes : ssl_renouveler, base_creer, service_relancer/arreter, stockage_local_creer, plan_creer.
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, pill = K.pill, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const SCENES = [["vue", "Vue d’ensemble"], ["sites", "Sites"], ["certificats", "Certificats"], ["php", "PHP"], ["bases", "Bases"], ["sauvegardes", "Sauvegardes"], ["courriel", "Courriel et FTP"], ["dns", "DNS"], ["comptes", "Comptes"], ["services", "Services"]];
  const SSL = { actif: ["actif", "", "check"], proche: ["proche", "al", "warn"], echu: ["échu", "dg", "warn"], aucun: ["sans certificat", "", ""], inconnu: ["date illisible", "al", ""] };
  const COPIE = { reussie: ["réussie", "", "check"], en_cours: ["en cours", "", ""], echec: ["échec", "dg", "warn"] };
  const court = (t) => String(t || "").replace("T", " ").slice(0, 16);
  const fiche = (titre, note, cote) => '<div class="li"><div class="sp"><b>' + titre + "</b>" + (note ? '<span class="note">' + esc(note) + "</span>" : "") + "</div>" + (cote || "") + "</div>";

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.fastpanel = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("fastpanel", corps); return; }
    K.injecter();
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit"; corps.appendChild(racine);
    const S = { scene: "vue", D: {}, q: "", sonde: null, charge: true, erreur: "", chargeScene: false };
    const val = (id) => ((racine.querySelector(id) || {}).value || "").trim();

    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { await agir(cap, args); if (ok) dire(ok, "ok"); return true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const barre = () => '<div class="onglets" role="tablist">' + SCENES.map((s) => '<button role="tab" class="' + (S.scene === s[0] ? "on" : "") + '" data-s="' + s[0] + '" aria-selected="' + (S.scene === s[0]) + '">' + esc(s[1]) + "</button>").join("") + "</div>";
    const filtre = (rows, ...cles) => { const q = S.q.toLowerCase(); return q ? rows.filter((r) => cles.some((c) => String(r[c] == null ? "" : r[c]).toLowerCase().indexOf(q) >= 0)) : rows; };
    const recherche = () => '<div class="barre"><input type="search" id="fp-q" placeholder="Chercher dans cette section (Entrée)…" value="' + esc(S.q) + '" aria-label="Chercher"></div>';
    const liste = (rows, f, vide) => '<div class="carte"><div class="liste">' + (rows.length ? rows.map(f).join("") : '<div class="vide">' + esc(vide) + "</div>") + "</div></div>";
    const sl = (cle) => S.D[cle] || [];

    function vue() {
      const r = S.D.resume, a = S.D.audit;
      if (!r) return '<div class="carte"><h3>Le panneau n’est pas relevé</h3><p class="note">' + esc(S.erreur || "Aucun relevé : le panneau n’est pas configuré, ou la relève n’a pas encore tourné.") + "</p></div>";
      const bon = r.etat === "ok";
      const haut = '<div class="carte"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h3 style="flex:1;min-width:200px">' + (bon ? "Le panneau répond" : "Le panneau ne répond pas") + "</h3>" + pill(String(r.etat || "?").replace("_", " "), bon ? "" : "dg", bon ? "check" : "warn") + "</div>" + (r.erreur ? '<p class="note">' + esc(r.erreur) + "</p>" : "") + (r.services ? '<p class="note">' + esc(r.services.total + " services connus" + (r.services.tombes ? " · " + r.services.tombes + " arrêté(s) sans qu’on l’ait demandé" : "")) + "</p>" : "") + "</div>";
      const cart = (a && a.certificats) || {}, sau = (a && a.sauvegardes) || {}, ph = (a && a.php) || {};
      const lignes = [];
      (cart.echus || []).forEach((d) => lignes.push(["dg", "Certificat échu : " + d, ""]));
      (cart.proches || []).forEach((x) => lignes.push(["al", "Certificat de " + x.domaine + " : " + x.jours + " jour(s)", "échéance le " + x.echeance]));
      (sau.sans || []).forEach((d) => lignes.push(["dg", "Aucune sauvegarde réussie pour " + d, ""]));
      (sau.perimees || []).forEach((x) => lignes.push(["al", "Sauvegarde périmée : " + x.domaine, "dernière copie le " + x.derniere + " (seuil : " + sau.seuil_j + " j)"]));
      (ph.fin_de_support || []).forEach((x) => lignes.push(["dg", "PHP " + x.php + " sans correctifs : " + x.domaine, "support terminé le " + x.fin]));
      (ph.bientot || []).forEach((x) => lignes.push(["al", "PHP " + x.php + " bientôt en fin de support : " + x.domaine, x.fin]));
      const audit = a && a.erreur ? '<div class="carte"><p class="note">' + esc(a.erreur) + "</p></div>" : '<div class="carte"><h3>Ce que dit l’audit</h3><div class="liste">' + (lignes.length ? lignes.map((l) => fiche(esc(l[1]), l[2], pill(l[0] === "dg" ? "à régler" : "à regarder", l[0], "warn"))).join("") : '<div class="vide"><b>Rien à signaler</b> : certificats, sauvegardes et PHP sont en règle.</div>') + "</div></div>";
      const tuiles = a && a.certificats ? '<div class="grille-m">' + [["Sites", cart.total], ["Certificats actifs", cart.actifs], ["Sans certificat", (cart.sans || []).length], ["Sauvegardes périmées", (sau.sans || []).length + (sau.perimees || []).length]].map((x) => '<div class="carte"><span class="note">' + esc(x[0]) + '</span><div style="font-size:22px;font-weight:600">' + esc(x[1] == null ? "—" : x[1]) + "</div></div>").join("") + "</div>" : "";
      return haut + tuiles + audit;
    }
    function sites() {
      const l = filtre(sl("sites"), "domaine", "proprietaire", "php");
      return recherche() + liste(l, (s) => { const e = SSL[s.ssl.etat] || SSL.inconnu; return fiche(esc(s.domaine) + " " + pill(e[0] + (typeof s.ssl.jours === "number" ? " · " + s.ssl.jours + " j" : ""), e[1], e[2]), [s.proprietaire, s.php ? "PHP " + s.php : "", s.gestionnaire, s.fichiers_mo != null ? s.fichiers_mo + " Mo de fichiers" : ""].filter(Boolean).join(" · "), '<button class="p" data-a="renouveler" data-k="' + esc(s.domaine) + '">Renouveler le certificat</button>'); }, "Aucun site.");
    }
    function certificats() {
      const c = S.D.certificats || {};
      const bloc = (titre, rows, f) => (rows && rows.length ? '<div class="carte"><h3>' + esc(titre) + " · " + rows.length + '</h3><div class="liste">' + rows.map(f).join("") + "</div></div>" : "");
      const sonde = '<div class="carte"><h3>Ce que présente vraiment un domaine</h3><div class="barre"><input id="fp-dom" placeholder="exemple.fr" aria-label="Domaine"><button class="btn pri" data-a="sonder">Sonder le port 443</button></div>' +
        (S.sonde ? (S.sonde.ok ? '<p class="note">' + esc("Émis par " + (S.sonde.emetteur || "?") + " · échéance " + S.sonde.echeance + " (" + S.sonde.jours + " j) · " + (S.sonde.noms || []).join(", ")) + "</p>" : '<p class="note">' + esc("Pas de certificat lisible : " + S.sonde.erreur) + "</p>") : "") + "</div>";
      return bloc("Échus", c.echus, (d) => fiche(esc(d), "", '<button class="p" data-a="renouveler" data-k="' + esc(d) + '">Renouveler</button>')) + bloc("Proches de l’échéance", c.proches, (x) => fiche(esc(x.domaine), x.jours + " jour(s) · échéance " + x.echeance, '<button class="p" data-a="renouveler" data-k="' + esc(x.domaine) + '">Renouveler</button>')) +
        bloc("Sans certificat", c.sans, (d) => fiche(esc(d), "")) + bloc("Date illisible", c.inconnus, (d) => fiche(esc(d), "")) + (c.total != null ? '<div class="carte"><p class="note">' + esc(c.actifs + " certificat(s) actif(s) sur " + c.total + " site(s).") + "</p></div>" : "") + sonde;
    }
    function php() {
      const p = S.D.php || {};
      const bloc = (titre, rows, f, cl) => (rows && rows.length ? '<div class="carte"><h3>' + esc(titre) + " · " + rows.length + '</h3><div class="liste">' + rows.map(f).join("") + "</div></div>" : "");
      const rien = !(p.fin_de_support || []).length && !(p.bientot || []).length && !(p.version_non_lue || []).length;
      return bloc("Fin de support", p.fin_de_support, (x) => fiche(esc(x.domaine), "PHP " + x.php + " · support terminé le " + x.fin, pill("à mettre à jour", "dg", "warn"))) + bloc("Bientôt en fin de support", p.bientot, (x) => fiche(esc(x.domaine), "PHP " + x.php + " · " + x.fin, pill("à prévoir", "al", ""))) +
        bloc("Version non lue", p.version_non_lue, (x) => fiche(esc(x.domaine), x.gestionnaire)) + (rien ? '<div class="carte vide"><b>Toutes les versions de PHP sont encore soutenues.</b></div>' : "");
    }
    function bases() {
      const l = filtre(sl("bases"), "nom", "proprietaire", "site");
      const cr = '<div class="carte"><h3>Créer une base</h3><div class="barre"><input id="fp-base" placeholder="nom_de_la_base" aria-label="Nom"><button class="btn pri" data-a="base">Créer</button></div><p class="note">Son utilisateur est créé avec elle.</p></div>';
      return recherche() + liste(l, (b) => fiche(esc(b.nom) + " " + pill(b.moteur, "", ""), [b.site, b.proprietaire, b.taille_mo + " Mo", b.derniere_copie ? "copie du " + court(b.derniere_copie) : "jamais copiée"].filter(Boolean).join(" · ")), "Aucune base.") + cr;
    }
    function sauvegardes() {
      const c = filtre(sl("copies"), "plan", "compte", "destination"), p = sl("plans"), st = sl("stockages");
      const copies = liste(c, (x) => { const e = COPIE[x.etat] || COPIE.echec; return fiche(esc(x.compte || x.plan) + " " + pill(e[0], e[1], e[2]) + (x.partielle ? " " + pill("partielle", "al", "") : ""), [x.plan, x.destination, x.envoye_mo + " Mo", x.duree_min != null ? x.duree_min + " min" : "", x.erreur].filter(Boolean).join(" · "), '<span class="faint mono" style="font-size:11.5px">' + esc(court(x.debut)) + "</span>"); }, "Aucune copie.");
      const plans = '<div class="carte"><h3>Les plans</h3><div class="liste">' + (p.length ? p.map((x) => fiche(esc(x.name || x.nom || "plan"), [x.storage || x.account_name, x.enabled === false ? "suspendu" : "", x.keep ? "garde " + x.keep : ""].filter(Boolean).join(" · "))).join("") : '<div class="vide">Aucun plan.</div>') + "</div></div>";
      const stock = '<div class="carte"><h3>Les stockages</h3><div class="liste">' + (st.length ? st.map((x) => fiche(esc(x.name || x.nom || "stockage"), [x.type, x.path].filter(Boolean).join(" · "))).join("") : '<div class="vide">Aucun stockage.</div>') + '</div><div class="barre"><input id="fp-sn" placeholder="nom" aria-label="Nom du stockage"><input id="fp-sc" placeholder="/dossier/sauvegardes" aria-label="Dossier"><button class="btn" data-a="stockage">Déclarer un dossier</button></div></div>';
      const nouveau = '<div class="carte"><h3>Créer un plan</h3><div class="barre"><input id="fp-pn" placeholder="nom du plan" aria-label="Nom du plan"><input id="fp-ps" placeholder="stockage" aria-label="Stockage"><input id="fp-pg" type="number" min="1" value="7" aria-label="Copies gardées" style="max-width:90px"><button class="btn pri" data-a="plan">Créer</button></div><p class="note">Une copie par jour à 4 h ; les plus anciennes sont effacées au-delà du nombre gardé.</p></div>';
      return recherche() + copies + plans + stock + nouveau;
    }
    function courriel() {
      const m = filtre(sl("mail"), "adresse", "domaine"), f = filtre(sl("ftp"), "compte", "site");
      return recherche() + '<div class="carte"><h3>Boîtes courriel · ' + m.length + '</h3><div class="liste">' + (m.length ? m.map((x) => fiche(esc(x.adresse) + (x.statut !== "active" ? " " + pill("suspendue", "al", "") : ""), x.utilise_mo + " Mo utilisés sur " + x.quota_mo + " Mo")).join("") : '<div class="vide">Aucune boîte.</div>') + "</div></div>" +
        '<div class="carte"><h3>Comptes FTP · ' + f.length + '</h3><div class="liste">' + (f.length ? f.map((x) => fiche(esc(x.compte) + (x.statut !== "active" ? " " + pill("suspendu", "al", "") : ""), [x.site, x.dossier].filter(Boolean).join(" · "))).join("") : '<div class="vide">Aucun compte FTP.</div>') + "</div></div>";
    }
    function dns() {
      const l = filtre(sl("dns"), "zone", "nom", "valeur", "type");
      return recherche() + liste(l, (x) => fiche(esc(x.nom || "@") + " " + pill(x.type, "", ""), x.zone + " → " + x.valeur, '<span class="faint mono" style="font-size:11.5px">ttl ' + esc(x.ttl) + "</span>"), "Aucun enregistrement.");
    }
    function comptes() {
      const l = filtre(sl("comptes"), "compte", "roles", "courriel");
      return recherche() + liste(l, (x) => fiche(esc(x.compte) + (x.ssh ? " " + pill("SSH", "", "") : "") + (x.statut !== "active" ? " " + pill(x.statut, "al", "") : ""), [x.roles, x.sites != null ? x.sites + " site(s)" : "", x.bases != null ? x.bases + " base(s)" : "", x.quota_go ? x.quota_go + " Go" : "", x.courriel].filter(Boolean).join(" · ")), "Aucun compte.");
    }
    function services() {
      const l = filtre(sl("services"), "nom");
      return recherche() + liste(l, (x) => fiche(esc(x.nom) + " " + pill(x.actif ? "actif" : "arrêté", x.actif ? "" : "al", x.actif ? "check" : ""), x.etat, '<div class="chips"><button class="p" data-a="svc" data-k="' + esc(x.nom) + '" data-c="relancer">Redémarrer</button>' + (x.actif ? '<button class="p dg" data-a="svc" data-k="' + esc(x.nom) + '" data-c="arreter">Arrêter</button>' : "") + "</div>"), "Aucun service.");
    }

    function dessiner() {
      let c;
      if (S.charge || S.chargeScene) c = '<div class="carte vide">Lecture…</div>';
      else c = ({ vue: vue, sites: sites, certificats: certificats, php: php, bases: bases, sauvegardes: sauvegardes, courriel: courriel, dns: dns, comptes: comptes, services: services }[S.scene] || vue)();
      const e = S.erreur && !S.charge && !S.chargeScene && S.scene !== "vue" ? '<div class="carte"><p class="note">' + esc(S.erreur) + "</p></div>" : "";
      racine.innerHTML = K.titre("Hébergement", "Le panneau du serveur : sites, certificats, bases, sauvegardes, courriel, services.") + barre() + e + c;
    }
    const LECTURES = {
      vue: [["resume", "fastpanel.resume"], ["audit", "fastpanel.audit"]], sites: [["sites", "fastpanel.sites"]], certificats: [["certificats", "fastpanel.certificats"]], php: [["php", "fastpanel.php"]], bases: [["bases", "fastpanel.bases"]],
      sauvegardes: [["copies", "fastpanel.sauvegardes"], ["plans", "fastpanel.plans"], ["stockages", "fastpanel.stockages"]], courriel: [["mail", "fastpanel.mail"], ["ftp", "fastpanel.ftp"]], dns: [["dns", "fastpanel.dns"]], comptes: [["comptes", "fastpanel.utilisateurs"]], services: [["services", "fastpanel.services"]],
    };
    async function charger(scene) {
      S.erreur = ""; S.chargeScene = true; dessiner();
      const rs = await Promise.all((LECTURES[scene] || []).map((l) => lire(l[1])));
      (LECTURES[scene] || []).forEach((l, i) => { S.D[l[0]] = rs[i]; });
      S.chargeScene = false; dessiner();
    }
    async function aller(scene) { S.scene = scene; S.q = ""; S.sonde = null; await charger(scene); }

    racine.addEventListener("click", async (e) => {
      const s = e.target.closest("[data-s]"); if (s) { e.preventDefault(); aller(s.dataset.s); return; }
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a, nom = a.dataset.k;
      if (k === "renouveler") { if (!await confirmer("Renouveler le certificat de « " + nom + " » ?", '<p class="note">Let’s Encrypt en émet un nouveau par le panneau. L’ancien reste valable jusqu’à son terme.</p>', "Renouveler")) return; if (await geste("fastpanel.ssl_renouveler", { domaine: nom }, "Renouvellement demandé.")) charger(S.scene); }
      else if (k === "sonder") { const d = val("#fp-dom"); if (!d) return; S.sonde = await lire("fastpanel.ssl_sonder", { domaine: d }); dessiner(); const i = racine.querySelector("#fp-dom"); if (i) i.value = d; }
      else if (k === "base") { const n = val("#fp-base"); if (!n) { dire("Il faut un nom.", "err"); return; } if (await geste("fastpanel.base_creer", { nom: n }, "Base créée.")) charger("bases"); }
      else if (k === "stockage") { const n = val("#fp-sn"), c = val("#fp-sc"); if (!n || !c) { dire("Il faut un nom et un dossier.", "err"); return; } if (await geste("fastpanel.stockage_local_creer", { nom: n, chemin: c }, "Stockage déclaré.")) charger("sauvegardes"); }
      else if (k === "plan") { const n = val("#fp-pn"); if (!n) { dire("Il faut un nom.", "err"); return; } if (await geste("fastpanel.plan_creer", { nom: n, stockage: val("#fp-ps"), garder: +val("#fp-pg") || 7 }, "Plan créé.")) charger("sauvegardes"); }
      else if (k === "svc") {
        const arret = a.dataset.c === "arreter";
        if (!await confirmer((arret ? "Arrêter « " : "Redémarrer « ") + nom + " » ?", '<p class="note">Par le panneau. Si le service ne revient pas, Cassandra le remet comme avant.</p>', arret ? "Arrêter" : "Redémarrer", arret)) return;
        if (await geste("fastpanel.service_" + a.dataset.c, { service: nom }, "Fait.")) charger("services");
      }
    });
    racine.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "fp-q") { e.preventDefault(); S.q = e.target.value.trim(); dessiner(); const i = racine.querySelector("#fp-q"); if (i) { i.focus(); i.setSelectionRange(S.q.length, S.q.length); } } });
    S.charge = false; await charger("vue");
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
