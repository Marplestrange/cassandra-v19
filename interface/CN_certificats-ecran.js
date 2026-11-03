// ═════════════════════════════════════════════════════════════════════
// TITRE      : Certificats : l'écran du module
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #91cd26
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les huit pages du module certificats (vue d'ensemble, liste et fiche, demandes, autorités, modèles, clés, rapports, réglages).
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.certificats) ; la page vient de l'écran ouvert (ctx.ecran = « certificats:c_… ») ; toutes les données par certificats.* ; le renouvellement est celui du panneau (fastpanel.ssl_renouveler), jamais un appel direct à l'autorité.
// ═════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=91cd26 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const K = CASS.kit;
  const esc = K.esc, agir = K.agir, dire = K.dire;
  const PILL = { valide: ["Valide", "ok"], proche: ["À renouveler", "al"], echu: ["Échu", "dg"], inconnu: ["Inconnu", ""], revoque: ["Révoqué", "dg"], archive: ["Archivé", ""] };
  const SRC = { fastpanel: "FastPanel", importe: "Importé", sonde: "Sondé seulement" };
  const DEM = { brouillon: ["Brouillon", ""], a_valider: ["À valider", "al"], validee: ["Validée", "ac"], emise: ["Émise", "ok"], refusee: ["Refusée", "dg"], echec: ["Échec d’émission", "dg"] };
  const PAGES = { c_vue: "vue", c_liste: "liste", c_demandes: "demandes", c_autorites: "autorites", c_modeles: "modeles", c_cles: "cles", c_rapports: "rapports", c_reglages: "reglages" };
  const TITRES = { vue: "Vue d’ensemble", liste: "Certificats", demandes: "Demandes", autorites: "Autorités", modeles: "Modèles", cles: "Clés", rapports: "Rapports", reglages: "Réglages" };
  const PAR = 10;
  const CSS = ".ce table{width:100%;border-collapse:collapse;font-size:13.5px}.ce th{font:650 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}" +
    ".ce th.tri{cursor:pointer}.ce th.tri:hover{color:var(--accent)}.ce td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:middle}.ce tr:last-child td{border-bottom:0}.ce tbody tr:hover td{background:color-mix(in srgb,var(--accent) 5%,transparent)}.ce tr.sel td{background:color-mix(in srgb,var(--accent) 9%,transparent)}" +
    ".ce .h{font:500 13px ui-monospace,'JetBrains Mono',Menlo,monospace}.ce .h a{cursor:pointer;color:var(--txt)}.ce .h a:hover{color:var(--accent);text-decoration:underline}.ce .num{text-align:right;font-variant-numeric:tabular-nums}.ce .act{display:flex;gap:6px;justify-content:flex-end}" +
    ".ce .lot{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 12px;border-radius:12px;background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--accent);font-weight:600;font-size:13px}" +
    ".ce .pied-t{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;font-size:12.5px;color:var(--txt-soft)}.ce .pag{display:flex;gap:4px}.ce .pag button{min-width:30px;height:30px;border-radius:8px;border:1px solid var(--line);background:var(--surface);cursor:pointer;color:var(--txt)}.ce .pag button.on{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.ce .pag button[disabled]{opacity:.4;cursor:not-allowed}" +
    ".ce .histo{display:flex;align-items:flex-end;gap:10px;height:130px}.ce .histo div{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:4px;height:100%;font:500 10.5px ui-monospace,Menlo,monospace;color:var(--txt-faint);text-align:center}.ce .histo i{display:block;width:100%;max-width:46px;border-radius:6px 6px 0 0;background:var(--accent);min-height:2px}.ce .histo .d i{background:var(--danger)}.ce .histo .a i{background:var(--warn)}.ce .histo b{color:var(--txt);font-size:12px}" +
    ".ce .kanban{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.ce .col{background:color-mix(in srgb,var(--txt-soft) 5%,transparent);border-radius:14px;padding:10px;min-height:110px}.ce .col h4{font:600 11px 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint);margin:0 0 8px;display:flex;justify-content:space-between}" +
    ".ce .fiche{background:var(--surface-solid,var(--surface));border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:8px;font-size:13px}.ce .fiche b{font:500 12.5px ui-monospace,Menlo,monospace;display:block;overflow-wrap:anywhere}.ce .fiche small{display:block;color:var(--txt-faint);font-size:11.5px;margin:2px 0 8px}.ce .fiche .act{justify-content:flex-start;flex-wrap:wrap}" +
    ".ce dl.g{display:grid;grid-template-columns:max-content 1fr;gap:7px 22px;font-size:13.5px;margin:0}.ce dl.g dt{font:500 12px ui-monospace,Menlo,monospace;color:var(--txt-faint)}.ce dl.g dd{margin:0;overflow-wrap:anywhere}" +
    ".ce .chaine .n{border:1px solid var(--line);border-radius:12px;padding:10px 14px;background:var(--surface-solid,var(--surface));margin:0 0 8px calc(var(--d)*22px)}.ce .chaine .n b{font:600 13px ui-monospace,Menlo,monospace}.ce .chaine .n small{display:block;color:var(--txt-faint);font-size:12px}" +
    ".ce .bandeau{padding:10px 14px;border-radius:12px;font-size:13px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.ce .bandeau .sp{flex:1;min-width:200px}.ce .bandeau.da{background:color-mix(in srgb,var(--danger) 10%,transparent);color:var(--danger)}.ce .bandeau.al{background:color-mix(in srgb,var(--warn) 12%,transparent);color:var(--warn)}.ce .bandeau.in{background:color-mix(in srgb,var(--info,var(--accent)) 10%,transparent);color:var(--info,var(--accent))}" +
    ".ce .champ{display:grid;gap:4px;margin-bottom:12px}.ce .champ label,.kit-m .champ label{font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft)}.ce .champ .aide,.kit-m .champ .aide{font-size:12px;color:var(--txt-faint)}.ce .err,.kit-m .err{font-size:12px;color:var(--danger)}" +
    ".ce input[type=text],.ce input[type=number],.ce input[type=search],.ce select,.ce textarea,.kit-m input[type=text],.kit-m select,.kit-m textarea{font:13.5px 'Inter',system-ui,sans-serif;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 11px;max-width:100%}.kit-m textarea,.ce textarea{width:100%}" +
    ".ce input.inv,.kit-m .inv{border-color:var(--danger)}.ce .etapes{list-style:none;padding:0;margin:8px 0}.ce .etapes li{display:flex;gap:10px;padding:5px 0}.ce .etapes li::before{content:'○';color:var(--txt-faint)}.ce .etapes li.ok::before{content:'✓';color:var(--ok)}.ce .etapes li.ko::before{content:'✕';color:var(--danger)}.ce .etapes li.en::before{content:'…';color:var(--accent)}" +
    ".ce .sk{height:14px;border-radius:7px;background:linear-gradient(90deg,var(--line),var(--line-strong,var(--line)),var(--line));background-size:200% 100%;animation:ce-sk 1.2s infinite;margin:12px 0}@keyframes ce-sk{to{background-position:-200% 0}}" +
    "@media (max-width:640px){.ce table.cartes thead{display:none}.ce table.cartes,.ce table.cartes tbody,.ce table.cartes tr{display:block;width:100%}.ce table.cartes tr{border:1px solid var(--line);border-radius:12px;margin-bottom:10px;padding:6px 10px}.ce table.cartes td{display:flex;justify-content:space-between;gap:10px;border:0;padding:5px 0;text-align:right;overflow-wrap:anywhere}.ce table.cartes td::before{content:attr(data-l);font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left}.ce table.cartes td.cm{display:none}.ce table.cartes td.ac::before{content:none}}" +
    "@media (prefers-reduced-motion:reduce){.ce .sk{animation:none}}";
  const jours = (j) => (j == null ? "—" : j <= 0 ? "échu depuis " + (-j) + " j" : j + " j");
  const dateFr = (iso) => { const s = String(iso || "").slice(0, 10).split("-"); return s.length === 3 ? s[2] + "/" + s[1] + "/" + s[0] : "—"; };
  const quand = (ts) => { const d = new Date(ts * 1000); return d.toLocaleDateString("fr-FR") + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }); };
  const pill = (f) => { const p = PILL[f.etat] || ["?", ""]; return K.pill(p[0], p[1]); };
  const msg = (e) => String((e && e.message) || e || "erreur");

  // ── une petite fenêtre (les classes kit-v / kit-m du kit) ──────────────────────────────────────────────
  function fenetre(titre, corps, boutons) {
    return new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre);
      m.innerHTML = "<h2>" + esc(titre) + "</h2>" + corps + '<div class="acts">' + boutons.map((b) => '<button class="btn ' + (b.cl || "") + '" data-c="' + esc(b.id) + '"' + (b.off ? " disabled" : "") + ">" + esc(b.t) + "</button>").join("") + "</div>";
      const clore = (r) => { v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(null));
      m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b && !b.disabled) clore({ id: b.dataset.c, m: m }); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(null); });
      document.body.appendChild(v); document.body.appendChild(m);
      fenetre.derniere = m;
      const f = m.querySelector("input,select,textarea,[data-c]"); if (f) f.focus();
    });
  }
  const val = (m, sel) => String((m.querySelector(sel) || {}).value || "").trim();

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.certificats = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("ce-css")) { const st = document.createElement("style"); st.id = "ce-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "kit ce"; corps.appendChild(racine);
    const S = { page: PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "vue", d: null, sel: null, fiche: null, tab: "Résumé", f: { q: "", etat: "", source: "", archives: false }, tri: ["jours", 1], p: 1, sels: new Set(), travail: null, reg: "Seuils et sonde", erreur: "", chargement: true };
    const peut = (d) => K.peut("certificats." + d);
    const lire = async (cap, args) => { try { return await agir(cap, args || {}); } catch (e) { S.erreur = msg(e); return null; } };
    const geste = async (cap, args, ok) => { try { const r = await agir(cap, args || {}); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(msg(e), "err"); return false; } };
    const entete = (acts) => K.titre(TITRES[S.page], { vue: "Ce que voient les visiteurs, ce qui expire, et combien d’émissions il reste. Le certificat servi sur le port 443 fait foi.", liste: "Tous les certificats suivis, quelle que soit leur origine. Ce qu’on peut faire dépend de la source.", demandes: "Le parcours d’un nouveau certificat : demande, validation, émission.", autorites: "Qui signe les certificats, par quelle voie, et ce que chacune permet.", modeles: "Des profils prêts à l’emploi.", cles: "Les métadonnées des clés : jamais la clé elle-même.", rapports: "Des exports pour l’audit et la conformité, et le journal de ce qui s’est passé.", reglages: "Les seuils, la sonde et l’intégration du panneau." }[S.page], acts || "");
    const bandeaux = () => (S.erreur ? '<div class="bandeau da"><div class="sp">' + esc(S.erreur) + '</div><button class="btn mini" data-a="recharger">Réessayer</button></div>' : "") +
      (S.d && S.d.panneau && S.d.panneau.joignable === false ? '<div class="bandeau al"><div class="sp"><b>FastPanel est injoignable.</b> Les valeurs sont celles de la dernière relève ; aucun renouvellement n’est possible.</div></div>' : "");
    const squelette = () => '<div class="carte"><div class="sk" style="width:90%"></div><div class="sk" style="width:70%"></div><div class="sk" style="width:80%"></div></div>';
    const refus = (d, txt) => entete() + '<div class="carte vide"><b>Permission refusée</b><p class="note">' + esc(txt) + '</p><span class="mono note">droit requis : certificats.' + esc(d) + "</span></div>";

    // ── la vue d'ensemble ─────────────────────────────────────────────────────────────────────────────────
    async function vue() {
      const s = await lire("certificats.synthese");
      if (!s) return entete() + bandeaux();
      S.d = s;
      const mx = Math.max(1, ...s.histogramme.map((x) => x.n));
      const t = (l, n, cl, note, a) => '<button class="stat ' + cl + '" data-a="filtre" data-e="' + a + '" style="text-align:left;cursor:pointer"><b>' + n + "</b><span>" + l + '</span><span class="note">' + note + "</span></button>";
      const vide = s.suivis === 0 && !S.erreur;
      return entete() + bandeaux() + (vide ? '<div class="carte vide"><b>Aucun certificat suivi</b><p class="note">Les hôtes viennent des sites du panneau et de la liste « hôtes supplémentaires » des réglages.</p></div>' :
        '<div class="stats">' + t("Suivis", s.suivis, "", "hors archivés et révoqués", "") + t("Valides", s.valides, "ok", "au-delà de " + s.seuil + " jours", "valide") + t("À renouveler", s.proches, "al", "sous le seuil de " + s.seuil + " j", "proche") + t("Échus", s.echus, "dg", "action immédiate", "echu") + t("Inconnus", s.inconnus, "", "sonde sans réponse", "inconnu") + "</div>" +
        '<div class="g2"><div class="carte"><h3>Échéancier</h3><div class="histo">' + s.histogramme.map((x, i) => '<div class="' + (i < 2 ? "d" : i === 2 ? "a" : "") + '"><b>' + x.n + '</b><i style="height:' + (Math.round(x.n / mx * 80) + 2) + 'px"></i>' + esc(x.tranche) + "</div>").join("") + "</div></div>" +
        '<div class="carte"><h3>Conformité · ' + s.conformite + " %</h3><div class=\"jauge\"><i style=\"width:" + s.conformite + '%"></i></div>' + s.criteres.map((k) => '<div class="li"><span class="p ' + (k.ok ? "ok" : "dg") + '">' + (k.ok ? "conforme" : "non conforme") + "</span><span>" + esc(k.texte) + "</span></div>").join("") + "</div></div>" +
        '<div class="g2"><div class="carte"><h3>À traiter (' + s.a_traiter.length + ")</h3>" + (s.a_traiter.length ? s.a_traiter.map((f) => '<div class="li"><span class="sp" style="flex:1;min-width:180px"><a class="mono" data-a="ouvrir" data-h="' + esc(f.hote) + '" style="cursor:pointer;color:var(--accent)">' + esc(f.hote) + '</a><br><span class="note">' + esc(f.etat === "inconnu" ? (f.erreur || "non lisible") : jours(f.jours)) + " · " + SRC[f.source] + "</span></span>" + (f.source === "fastpanel" ? '<button class="btn mini" data-a="renouveler" data-h="' + esc(f.hote) + '"' + (peut("renouveler") ? "" : " disabled") + ">Renouveler</button>" : '<button class="btn mini" data-a="ouvrir" data-h="' + esc(f.hote) + '">Ouvrir</button>') + "</div>").join("") : '<div class="vide">Rien à traiter : tout est au-dessus du seuil.</div>') + "</div>" +
        '<div class="carte"><h3>Quota Let’s Encrypt (7 jours glissants)</h3>' + (s.quotas.length ? s.quotas.map((q) => '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between"><span class="mono">' + esc(q.domaine) + "</span><span>" + q.utilisees + " / " + q.limite + (q.bloque ? ' <span class="p dg">bloqué</span>' : "") + '</span></div><div class="jauge"><i style="width:' + Math.min(100, q.utilisees * 20) + "%;" + (q.bloque ? "background:var(--danger)" : "") + '"></i></div>' + (q.bloque ? '<span class="note" style="color:var(--danger)">Libre le ' + esc(q.libre_le) + ". Ce n’est pas contournable ; le certificat en place reste valide.</span>" : "") + (q.echecs_heure ? '<span class="note"> · ' + q.echecs_heure + " échec(s) cette heure</span>" : "") + "</div>").join("") : '<div class="vide">Aucun domaine du panneau suivi.</div>') + '<h3 style="margin-top:14px">FastPanel</h3><div class="li"><span class="p ' + (s.panneau.joignable ? "ok" : "dg") + '">' + (s.panneau.joignable ? "joignable" : "injoignable") + "</span><span>" + s.panneau.sites + " site(s) du panneau</span></div></div></div>");
    }

    // ── la liste et la fiche ──────────────────────────────────────────────────────────────────────────────
    function filtrer() {
      const f = S.f; let l = S.d.certificats.filter((c) => (f.archives ? ["archive", "revoque"].includes(c.force) : c.force !== "archive"));
      if (f.q) { const q = f.q.toLowerCase(); l = l.filter((c) => (c.hote + " " + c.noms.join(" ") + " " + c.emetteur).toLowerCase().includes(q)); }
      if (f.etat) l = l.filter((c) => c.etat === f.etat); if (f.source) l = l.filter((c) => c.source === f.source);
      const [k, d] = S.tri; return l.sort((a, b) => { const va = k === "jours" ? (a.jours == null ? -99999 : a.jours) : String(a[k] || ""), vb = k === "jours" ? (b.jours == null ? -99999 : b.jours) : String(b[k] || ""); return (va > vb ? 1 : va < vb ? -1 : 0) * d; });
    }
    async function liste() {
      if (S.sel) return fichePage();
      const r = await lire("certificats.lister"); if (!r) return entete() + bandeaux();
      S.d = r;
      const acts = '<div class="acts"><button class="btn pri" data-a="nouvelle"' + (peut("demander") ? "" : " disabled title=\"Droit requis : certificats.demander\"") + '>Demander un certificat</button><button class="btn" data-a="importer"' + (peut("importer") ? "" : " disabled") + '>Importer</button><button class="btn" data-a="exporter">Exporter (CSV)</button></div>';
      if (!r.certificats.length) return entete(acts) + bandeaux() + '<div class="carte vide"><b>Aucun certificat suivi</b><p class="note">Ajoutez des hôtes dans Réglages, ou demandez un certificat.</p></div>';
      const tout = filtrer(), pages = Math.max(1, Math.ceil(tout.length / PAR)); S.p = Math.min(S.p, pages); const l = tout.slice((S.p - 1) * PAR, S.p * PAR);
      const th = (k, t) => '<th class="tri" data-a="tri" data-k="' + k + '">' + t + (S.tri[0] === k ? (S.tri[1] > 0 ? " ▲" : " ▼") : "") + "</th>";
      const lot = S.sels.size ? '<div class="lot"><span>' + S.sels.size + ' sélectionné(s)</span><button class="btn mini" data-a="lot-relire">Relire maintenant</button><button class="btn mini" data-a="lot-renouveler"' + (peut("renouveler") ? "" : " disabled") + '>Renouveler</button><button class="btn mini" data-a="lot-exporter">Exporter la sélection</button><button class="btn mini" data-a="lot-archiver"' + (peut("administrer") ? "" : " disabled") + '>Archiver</button><button class="btn mini" data-a="lot-vider">Désélectionner</button></div>' : "";
      return entete(acts) + bandeaux() + '<div class="carte"><div class="barre"><input type="search" id="ce-q" placeholder="Rechercher un hôte, un nom, une autorité" value="' + esc(S.f.q) + '" aria-label="Rechercher">' +
        '<select data-f="etat" aria-label="État" class="sel"><option value="">Tous les états</option>' + Object.keys(PILL).filter((k) => k !== "archive").map((k) => '<option value="' + k + '"' + (S.f.etat === k ? " selected" : "") + ">" + PILL[k][0] + "</option>").join("") + "</select>" +
        '<select data-f="source" aria-label="Source" class="sel"><option value="">Toutes les sources</option>' + Object.keys(SRC).map((k) => '<option value="' + k + '"' + (S.f.source === k ? " selected" : "") + ">" + SRC[k] + "</option>").join("") + "</select>" +
        '<label class="note"><input type="checkbox" data-f="archives"' + (S.f.archives ? " checked" : "") + "> Archivés et révoqués</label></div>" + lot +
        (l.length ? '<div style="overflow-x:auto"><table class="cartes"><thead><tr><th><input type="checkbox" data-a="tout" aria-label="Tout sélectionner"' + (l.every((c) => S.sels.has(c.hote)) ? " checked" : "") + ">" + "</th>" + th("hote", "Hôte") + "<th>État</th>" + th("jours", "Jours") + "<th>Échéance</th>" + th("source", "Source") + th("emetteur", "Émetteur") + "<th></th></tr></thead><tbody>" +
          l.map((c) => '<tr class="' + (S.sels.has(c.hote) ? "sel" : "") + '"><td data-l="Sélection"><input type="checkbox" data-a="sel" data-h="' + esc(c.hote) + '"' + (S.sels.has(c.hote) ? " checked" : "") + ' aria-label="Sélectionner ' + esc(c.hote) + '"></td><td class="h" data-l="Hôte"><a data-a="ouvrir" data-h="' + esc(c.hote) + '" tabindex="0">' + esc(c.hote) + "</a>" + (c.noms.length > 1 ? '<br><small class="faint">+' + (c.noms.length - 1) + " nom(s)</small>" : "") + '</td><td data-l="État">' + pill(c) + '</td><td class="num" data-l="Jours">' + (c.jours == null ? "—" : c.jours) + '</td><td class="cm" data-l="Échéance">' + dateFr(c.echeance) + '</td><td class="cm" data-l="Source">' + SRC[c.source] + '</td><td class="cm" data-l="Émetteur">' + esc(c.emetteur || "—") + '</td><td class="ac"><div class="act"><button class="btn mini" data-a="relire" data-h="' + esc(c.hote) + '">Relire</button><button class="btn mini" data-a="renouveler" data-h="' + esc(c.hote) + '"' + (peut("renouveler") && c.source === "fastpanel" && !c.force ? "" : " disabled") + ">Renouveler</button></div></td></tr>").join("") + "</tbody></table></div>" +
          '<div class="pied-t"><span>' + tout.length + " certificat(s) · " + ((S.p - 1) * PAR + 1) + "–" + Math.min(tout.length, S.p * PAR) + '</span><div class="pag"><button data-a="page" data-p="' + (S.p - 1) + '"' + (S.p <= 1 ? " disabled" : "") + '>‹</button>' + Array.from({ length: pages }, (_, i) => '<button data-a="page" data-p="' + (i + 1) + '" class="' + (i + 1 === S.p ? "on" : "") + '">' + (i + 1) + "</button>").join("") + '<button data-a="page" data-p="' + (S.p + 1) + '"' + (S.p >= pages ? " disabled" : "") + ">›</button></div></div>" : '<div class="vide">Aucun certificat ne correspond à ces filtres.<br><button class="btn" data-a="raz">Effacer les filtres</button></div>') + "</div>";
    }
    async function fichePage() {
      const r = await lire("certificats.lire", { hote: S.sel }); if (!r) { S.sel = null; return entete() + bandeaux(); }
      const c = r.certificat; S.fiche = c;
      const mod = !c.force && c.source !== "sonde";
      const onglets = ["Résumé", "Chaîne", "Historique", "Liens", "Clé"];
      const q = r.quota;
      const corps = {
        "Résumé": '<div class="carte"><dl class="g"><dt>Hôte</dt><dd class="mono">' + esc(c.hote) + "</dd><dt>Noms</dt><dd class=\"mono\">" + (c.noms.map(esc).join("<br>") || "—") + "</dd><dt>État</dt><dd>" + pill(c) + (c.etat === "inconnu" ? '<br><span class="note" style="color:var(--danger)">' + esc(c.erreur) + ". « Inconnu » n’est pas « sans certificat » : on n’a pas pu le lire.</span>" : "") + (c.verif ? '<br><span class="note" style="color:var(--warn)">Vérification TLS refusée : ' + esc(c.verif) + "</span>" : "") + "</dd><dt>Jours restants</dt><dd>" + jours(c.jours) + "</dd><dt>Échéance</dt><dd>" + dateFr(c.echeance) + "</dd><dt>Émis le</dt><dd>" + dateFr(c.emis) + "</dd><dt>Émetteur</dt><dd>" + esc(c.emetteur || "—") + "</dd><dt>Source</dt><dd>" + SRC[c.source] + "</dd><dt>Algorithme</dt><dd>" + esc(c.algo || "—") + '</dd><dt>Empreinte SHA-256</dt><dd class="mono">' + esc(c.empreinte || "—") + "</dd><dt>Quota " + esc(q.domaine) + "</dt><dd>" + q.utilisees + " / " + q.limite + " cette semaine" + (q.echecs_heure ? " · " + q.echecs_heure + " échec(s) cette heure" : "") + "</dd>" + (c.note ? "<dt>Note</dt><dd>" + esc(c.note) + "</dd>" : "") + "</dl></div>",
        "Chaîne": c.jours == null ? '<div class="carte vide">La sonde n’a pas pu lire le certificat servi.</div>' : '<div class="carte"><div class="chaine"><div class="n" style="--d:0"><b>' + esc(c.hote) + "</b><small>feuille · " + esc(c.algo || "?") + " · échéance " + dateFr(c.echeance) + '</small></div><div class="n" style="--d:1"><b>' + esc(c.emetteur || "émetteur inconnu") + "</b><small>intermédiaire</small></div></div>" + (c.verif ? '<p class="note">Le client a refusé la chaîne : ' + esc(c.verif) + ".</p>" : '<p class="note">Chaîne acceptée par un client (vérification TLS réussie).</p>') + "</div>",
        "Historique": '<div class="carte">' + (r.historique.length ? r.historique.map((h) => '<div class="li"><span class="p ' + (h.resultat === "ok" ? "ok" : h.resultat === "echec" ? "dg" : "al") + '">' + esc(h.resultat) + '</span><span class="sp" style="flex:1"><b>' + esc(h.action) + '</b><br><span class="note">' + esc(h.acteur) + (h.note ? " · " + esc(h.note) : "") + "</span></span><span class=\"note\">" + quand(h.ts) + "</span></div>").join("") : '<div class="vide">Rien n’est encore inscrit au journal pour cet hôte.</div>') + "</div>",
        "Liens": '<div class="carte"><h3>Ce que ce certificat touche</h3><p class="note">Site : ' + esc(c.site || "aucun site rattaché") + ". Les renvois ci-dessous ouvrent l’écran de l’autre module.</p>" + [["Hébergement FastPanel (Parc › Sites)", "sites"], ["Enregistrements DNS et CAA", "dns"], ["Journal letsencrypt (Observatoire › Journaux)", "journal"]].map((x) => '<div class="li"><span style="flex:1">' + x[0] + '</span><button class="btn mini" data-a="aller" data-m="' + x[1] + '">Ouvrir</button></div>').join("") + "</div>",
        "Clé": peut("voir_cles") ? '<div class="carte"><div class="bandeau in"><div class="sp">Cassandra n’affiche, n’exporte et ne stocke jamais de clé privée. Seules ses métadonnées sont visibles.</div></div><dl class="g" style="margin-top:12px"><dt>Algorithme</dt><dd>' + esc(c.algo || "—") + "</dd><dt>Emplacement</dt><dd>" + ({ fastpanel: "sur le serveur, géré par le panneau", importe: "chez le propriétaire de l’hôte (non connu)" }[c.source] || "inconnu (certificat sondé)") + "</dd></dl></div>" : '<div class="carte vide"><b>Permission refusée</b><p class="note">Les métadonnées des clés sont réservées aux administrateurs.</p><span class="mono note">droit requis : certificats.voir_cles</span></div>'
      }[S.tab];
      return '<div class="barre"><button class="btn mini" data-a="retour">‹ Liste</button><div class="titre" style="flex:1;min-width:0"><h1 class="mono">' + esc(c.hote) + "</h1></div>" + pill(c) + "</div>" + bandeaux() +
        '<div class="acts"><button class="btn" data-a="relire" data-h="' + esc(c.hote) + '">Relire maintenant</button><button class="btn pri" data-a="renouveler" data-h="' + esc(c.hote) + '"' + (peut("renouveler") && c.source === "fastpanel" && !c.force ? "" : ' disabled title="' + (c.source !== "fastpanel" ? "Se renouvelle hors de Cassandra" : "Droit requis : certificats.renouveler") + '"') + ">Renouveler</button>" +
        (c.force === "archive" ? '<button class="btn" data-a="desarchiver" data-h="' + esc(c.hote) + '"' + (peut("administrer") ? "" : " disabled") + ">Désarchiver</button>" : '<button class="btn" data-a="archiver" data-h="' + esc(c.hote) + '"' + (peut("administrer") && (!c.force || c.force === "revoque") ? "" : " disabled") + ">Archiver</button>") +
        '<button class="btn dng" data-a="revoquer" data-h="' + esc(c.hote) + '"' + (peut("revoquer") && mod ? "" : " disabled") + ">Révoquer…</button></div>" +
        (c.source === "sonde" ? '<div class="bandeau in"><div class="sp">Ce certificat est seulement observé : il se renouvelle dans l’outil qui le gère.</div></div>' : "") +
        '<div class="onglets" role="tablist">' + onglets.map((t) => '<button role="tab" aria-selected="' + (t === S.tab) + '" class="' + (t === S.tab ? "on" : "") + '" data-a="onglet" data-t="' + t + '">' + t + "</button>").join("") + "</div>" + corps;
    }

    // ── les demandes ──────────────────────────────────────────────────────────────────────────────────────
    async function demandes() {
      const r = await lire("certificats.demandes"); if (!r) return entete() + bandeaux();
      S.demandes = r.demandes; S.modeles = r.modeles;
      const cols = [["brouillon", "Brouillon"], ["a_valider", "À valider"], ["validee", "Validée"], ["emise", "Émise"], ["refusee", "Refusée"], ["echec", "En échec"]];
      const acts = '<div class="acts"><button class="btn pri" data-a="nouvelle"' + (peut("demander") ? "" : " disabled title=\"Droit requis : certificats.demander\"") + ">Nouvelle demande</button></div>";
      if (!r.demandes.length) return entete(acts) + bandeaux() + '<div class="carte vide"><b>Aucune demande</b><p class="note">Une demande suit un modèle : certains exigent une validation par une autre personne.</p></div>';
      return entete(acts) + bandeaux() + '<div class="kanban">' + cols.map(([k, t]) => { const l = r.demandes.filter((d) => d.etat === k); return '<div class="col"><h4>' + t + "<span>" + l.length + "</span></h4>" + l.map((d) => '<div class="fiche"><b>' + esc(d.hote) + "</b><small>#" + d.id + " · " + esc(d.modele) + " · " + esc(d.demandeur) + " · " + quand(d.cree) + (d.motif ? "<br>Motif : " + esc(d.motif) : "") + (d.valideur ? "<br>Validée par : " + esc(d.valideur) : "") + '</small><div class="act">' +
        (k === "a_valider" ? '<button class="btn mini pri" data-a="d-valider" data-i="' + d.id + '"' + (peut("valider") ? "" : " disabled") + '>Valider</button><button class="btn mini dng" data-a="d-refuser" data-i="' + d.id + '"' + (peut("valider") ? "" : " disabled") + ">Refuser</button>" : "") +
        (k === "validee" ? '<button class="btn mini pri" data-a="d-emettre" data-i="' + d.id + '" data-h="' + esc(d.hote) + '"' + (peut("renouveler") ? "" : " disabled") + ">Émettre</button>" : "") +
        (k === "brouillon" ? '<button class="btn mini" data-a="d-soumettre" data-i="' + d.id + '"' + (peut("demander") ? "" : " disabled") + ">Soumettre</button>" : "") +
        (k === "refusee" || k === "echec" ? '<button class="btn mini" data-a="d-rouvrir" data-i="' + d.id + '"' + (peut("demander") ? "" : " disabled") + ">Rouvrir</button>" : "") + "</div></div>").join("") + "</div>"; }).join("") + "</div>";
    }

    // ── autorités, modèles, clés ──────────────────────────────────────────────────────────────────────────
    async function autorites() {
      const r = await lire("certificats.autorites"); if (!r) return entete() + bandeaux();
      return entete() + bandeaux() + '<div class="grille">' + r.autorites.map((a) => '<div class="carte"><div class="barre"><b class="mono" style="flex:1">' + esc(a.nom) + "</b>" + K.pill(a.etat, a.etat === "actif" ? "ok" : "dg") + '</div><dl class="g"><dt>Voie</dt><dd>' + esc(a.voie) + "</dd><dt>Gestes</dt><dd>" + a.gestes.map(esc).join(" · ") + "</dd><dt>Révocation</dt><dd>" + esc(a.revocation) + "</dd><dt>Quota</dt><dd>" + esc(a.quota) + "</dd></dl></div>").join("") + '<div class="carte"><div class="barre"><b class="mono" style="flex:1">Autorité interne</b>' + K.pill("Non retenue", "") + '</div><p class="note">' + esc(r.interne) + ". Rouverte seulement sur demande.</p></div></div>";
    }
    async function modeles() {
      const r = await lire("certificats.modeles"); if (!r) return entete() + bandeaux();
      return entete() + bandeaux() + '<div class="carte"><div style="overflow-x:auto"><table class="cartes"><thead><tr><th>Modèle</th><th>Validité</th><th>Algorithme</th><th>Noms</th><th>Renouvellement</th><th>Approbation</th><th>Autorité</th></tr></thead><tbody>' + r.modeles.map((m) => '<tr><td data-l="Modèle"><b>' + esc(m.nom) + '</b></td><td data-l="Validité">' + m.validite_j + ' j</td><td class="cm" data-l="Algorithme">' + esc(m.algo) + '</td><td class="cm" data-l="Noms">jusqu’à ' + m.max_sans + '</td><td class="cm" data-l="Renouvellement">' + (m.renouvelle_a_j ? "à " + m.renouvelle_a_j + " j" : "rappel seul") + '</td><td class="cm" data-l="Approbation">' + (m.approbation ? "oui" : "non (hôte déjà suivi)") + '</td><td data-l="Autorité">' + esc(m.autorite) + "</td></tr>").join("") + '</tbody></table></div><p class="note">Les modèles sont ceux du module ; leur édition viendra avec un stockage dédié.</p></div>';
    }
    async function cles() {
      if (!peut("voir_cles")) return refus("voir_cles", "Les métadonnées des clés sont réservées aux administrateurs.");
      const r = await lire("certificats.cles"); if (!r) return entete() + bandeaux();
      return entete() + bandeaux() + '<div class="bandeau in"><div class="sp">Cassandra n’affiche, n’exporte et ne stocke jamais une clé privée. Ici : algorithme, empreinte, emplacement et âge.</div></div><div class="carte"><div style="overflow-x:auto"><table class="cartes"><thead><tr><th>Hôte</th><th>Algorithme</th><th>Empreinte</th><th>Emplacement</th><th>Âge</th></tr></thead><tbody>' + (r.cles.length ? r.cles.map((c) => '<tr><td class="h" data-l="Hôte"><a data-a="ouvrir" data-h="' + esc(c.hote) + '">' + esc(c.hote) + '</a></td><td data-l="Algorithme">' + esc(c.algo) + '</td><td class="cm mono" data-l="Empreinte">' + esc(c.empreinte) + '</td><td class="cm" data-l="Emplacement">' + esc(c.emplacement) + '</td><td class="num" data-l="Âge">' + (c.age_j == null ? "—" : c.age_j + " j") + "</td></tr>").join("") : '<tr><td colspan="5" class="vide">Aucune clé à montrer.</td></tr>') + "</tbody></table></div></div>";
    }

    // ── rapports et audit ─────────────────────────────────────────────────────────────────────────────────
    async function rapports() {
      const a = await lire("certificats.audit", { resultat: S.audf || "" }); if (!a) return entete() + bandeaux();
      S.audit = a.audit;
      const R = [["Conformité", "Synthèse des critères et des écarts"], ["Échéances à 90 jours", "Qui expire quand, par source"], ["Quotas d'émission", "Émissions par domaine enregistré"], ["Inventaire complet", "Tous les certificats et leurs noms"]];
      return entete() + bandeaux() + '<div class="stats">' + R.map((x) => '<div class="stat"><b style="font-size:15px">' + esc(x[0]) + '</b><span class="note">' + x[1] + '</span><span><button class="btn mini" data-a="rapport" data-n="' + esc(x[0]) + '">CSV</button></span></div>').join("") + '</div><div class="carte"><h3>Journal d’audit</h3><div class="barre"><select data-f="audf" class="sel" aria-label="Résultat"><option value="">Tous les résultats</option><option value="ok"' + (S.audf === "ok" ? " selected" : "") + '>Réussis</option><option value="echec"' + (S.audf === "echec" ? " selected" : "") + '>Échecs</option><option value="refus"' + (S.audf === "refus" ? " selected" : "") + '>Refus de permission</option></select><button class="btn mini" data-a="audit-csv">Exporter</button></div>' +
        (a.audit.length ? '<div style="overflow-x:auto"><table class="cartes"><thead><tr><th>Quand</th><th>Action</th><th>Objet</th><th>Acteur</th><th>Résultat</th></tr></thead><tbody>' + a.audit.map((x) => '<tr><td class="mono" data-l="Quand" style="font-size:12px">' + quand(x.ts) + '</td><td data-l="Action"><span class="mono" style="font-size:12.5px">' + esc(x.action) + "</span>" + (x.note ? '<br><small class="faint">' + esc(x.note) + "</small>" : "") + '</td><td class="cm mono" data-l="Objet" style="font-size:12.5px">' + esc(x.objet) + '</td><td class="cm" data-l="Acteur">' + esc(x.acteur) + '</td><td data-l="Résultat">' + K.pill(x.resultat === "ok" ? "réussi" : x.resultat === "echec" ? "échec" : "refusé", x.resultat === "ok" ? "ok" : x.resultat === "echec" ? "dg" : "al") + "</td></tr>").join("") + "</tbody></table></div>" : '<div class="vide">Rien n’est inscrit pour ce filtre.</div>') + "</div>";
    }

    // ── réglages ──────────────────────────────────────────────────────────────────────────────────────────
    async function reglages() {
      if (!peut("administrer")) return refus("administrer", "Les réglages du module sont réservés aux administrateurs.");
      const R = ["Seuils et sonde", "Rôles et droits", "Intégration FastPanel"];
      const onglets = '<div class="onglets" role="tablist">' + R.map((t) => '<button role="tab" aria-selected="' + (t === S.reg) + '" class="' + (t === S.reg ? "on" : "") + '" data-a="regl" data-t="' + t + '">' + t + "</button>").join("") + "</div>";
      let c = "";
      if (S.reg === "Seuils et sonde") {
        const v = (await lire("certificats.parametres")) || {};
        const s = await lire("certificats.seuil");
        c = '<div class="carte"><div class="champ"><label for="ce-seuil">Jours restants sous lesquels un certificat est signalé</label><input type="number" id="ce-seuil" min="3" max="90" value="' + esc(v.seuil_jours != null ? v.seuil_jours : (s ? s.jours : 21)) + '" style="width:110px"><span class="aide">Entre 3 et 90 (défaut 21). Réglage unique : les autres modules le lisent ici.</span><span class="err" id="ce-e1"></span></div>' +
          '<div class="champ"><label for="ce-delai">Délai d’attente de la connexion au port 443 (secondes)</label><input type="number" id="ce-delai" min="1" max="30" value="' + esc(v.delai_s != null ? v.delai_s : 5) + '" style="width:110px"><span class="aide">Entre 1 et 30 (défaut 5).</span><span class="err" id="ce-e2"></span></div>' +
          '<div class="champ"><label for="ce-hotes">Hôtes suivis en plus de ceux du panneau (séparés par des virgules)</label><textarea id="ce-hotes" rows="3">' + esc(v.hotes || "") + '</textarea><span class="aide">Les services derrière nginx qui ne sont pas des sites du panneau. Un hôte injoignable est « inconnu », jamais « sans certificat ».</span><span class="err" id="ce-e3"></span></div><button class="btn pri" data-a="enregistrer">Enregistrer</button></div>';
      } else if (S.reg === "Rôles et droits") {
        const D = [["utiliser", "Consulter"], ["demander", "Demander un certificat"], ["valider", "Valider une demande"], ["renouveler", "Renouveler / émettre"], ["revoquer", "Révoquer"], ["importer", "Importer"], ["voir_cles", "Voir les métadonnées des clés"], ["administrer", "Administrer"]];
        c = '<div class="carte"><p class="note">Vos droits sur ce module. Les droits s’attribuent dans Paramètres › Utilisateurs et groupes ; le serveur refuse tout geste sans droit, même si le bouton est visible.</p>' + D.map((d) => '<div class="li"><span class="mono" style="flex:1">certificats.' + d[0] + "<br><span class=\"note\">" + d[1] + "</span></span>" + K.pill(peut(d[0]) ? "accordé" : "absent", peut(d[0]) ? "ok" : "") + "</div>").join("") + "</div>";
      } else {
        const r = S.d && S.d.panneau ? S.d : await lire("certificats.lister");
        c = '<div class="carte"><div class="bandeau ' + (r && r.panneau.joignable ? "in" : "da") + '"><div class="sp">' + (r && r.panneau.joignable ? "FastPanel est joignable : " + r.panneau.sites + " site(s)." : "FastPanel est injoignable : valeurs de la dernière relève, aucun geste possible.") + '</div></div><h3 style="margin-top:12px">Points d’entrée utilisés</h3><div class="li"><span class="mono" style="flex:1">GET /api/certificates</span><span class="note">lister</span>' + K.pill("dans le code", "ok") + '</div><div class="li"><span class="mono" style="flex:1">PUT /api/certificates/{id}/renew/external</span><span class="note">renouveler</span>' + K.pill("dans le code", "ok") + '</div><div class="li"><span class="mono" style="flex:1">émission initiale · import · suppression</span><span class="note">non branchés</span>' + K.pill("à vérifier", "al") + '</div><p class="note">Le renouvellement n’est réussi que si la date d’émission change (≤ 60 s). Un échec est inscrit au registre du quota.</p><button class="btn" data-a="aller" data-m="sites">Ouvrir Hébergement</button></div>';
      }
      return entete() + bandeaux() + onglets + c;
    }

    const FONC = { vue: vue, liste: liste, demandes: demandes, autorites: autorites, modeles: modeles, cles: cles, rapports: rapports, reglages: reglages };
    S.rendre = async (silence) => {
      await K.droits(); S.erreur = "";
      if (!silence) racine.innerHTML = entete() + squelette();
      try { racine.innerHTML = await FONC[S.page](); } catch (e) { racine.innerHTML = '<div class="carte"><span style="color:var(--danger)">' + esc(msg(e)) + "</span></div>"; }
      if (S.travail) racine.insertAdjacentHTML("afterbegin", S.travail);
    };

    // ── les gestes ────────────────────────────────────────────────────────────────────────────────────────
    const fiche_de = (h) => (S.d && S.d.certificats ? S.d.certificats.find((c) => c.hote === h) : null) || (S.fiche && S.fiche.hote === h ? S.fiche : null);
    async function renouveler(hotes) {
      if (!peut("renouveler")) { dire("Permission refusée : droit certificats.renouveler.", "err"); return; }
      const L = (await lire("certificats.lister")) || S.d; const cs = hotes.map((h) => L.certificats.find((c) => c.hote === h)).filter(Boolean);
      const ok = cs.filter((c) => c.source === "fastpanel" && !c.force), ign = cs.filter((c) => !ok.includes(c));
      if (!ok.length) { dire("Rien à renouveler d’ici : " + ign.map((c) => c.hote + " (" + (c.force ? PILL[c.force][0] : SRC[c.source]) + ")").join(", "), "err"); return; }
      if (L.panneau && L.panneau.joignable === false) { dire("FastPanel est injoignable : la demande ne peut pas partir. Le certificat en place reste valide.", "err"); return; }
      const need = {}; ok.forEach((c) => { const d = c.hote.split(".").slice(-2).join("."); need[d] = (need[d] || 0) + 1; });
      const qs = Object.keys(need).map((d) => { const q = (L.quotas || []).find((x) => x.domaine === d) || { domaine: d, utilisees: 0, restantes: 5, bloque: false }; return Object.assign({}, q, { n: need[d] }); });
      const bloque = qs.filter((q) => q.bloque || q.bloque_echecs || q.n > q.restantes);
      const corps = '<p class="note">Le panneau demande un nouveau certificat à Let’s Encrypt. Le geste n’est réussi que si la date d’émission change.</p>' + ok.map((c) => '<div class="li"><span class="mono" style="flex:1">' + esc(c.hote) + "</span><span class=\"note\">" + esc(jours(c.jours)) + "</span></div>").join("") + (ign.length ? '<p class="note" style="color:var(--warn)">' + ign.length + " ignoré(s) : " + ign.map((c) => esc(c.hote)).join(", ") + " (non renouvelable(s) d’ici).</p>" : "") + qs.map((q) => '<div class="li"><span>' + esc(q.domaine) + " : " + q.utilisees + " / 5 utilisées, " + q.n + " demandée(s)" + ((q.bloque || q.n > q.restantes) ? '<br><span class="note" style="color:var(--danger)">Quota atteint' + (q.libre_le ? ", libre le " + esc(q.libre_le) : "") + ". Ce n’est pas contournable.</span>" : "") + "</span></div>").join("");
      const r = await fenetre("Renouveler " + ok.length + " certificat(s)", corps, [{ id: "non", t: "Annuler" }, { id: "oui", t: "Demander le renouvellement", cl: "pri", off: bloque.length > 0 }]);
      if (!r || r.id !== "oui") return;
      const fait = [], rate = [];
      for (const c of ok) {
        S.travail = '<div class="bandeau in" role="status"><div class="sp">Renouvellement de <b>' + esc(c.hote) + "</b> par le panneau… (preuve : la date d’émission doit changer, jusqu’à 60 s)</div></div>"; S.rendre(true);
        try { await agir("fastpanel.ssl_renouveler", { domaine: c.hote }); fait.push(c.hote); }
        catch (e) { rate.push(c.hote + " : " + msg(e)); await geste("certificats.noter_echec", { hote: c.hote, motif: msg(e).slice(0, 180) }); }
      }
      S.travail = null; S.sels.clear();
      if (fait.length) dire(fait.length + " certificat(s) renouvelé(s) : " + fait.join(", "), "ok");
      if (rate.length) dire("Échec : " + rate.join(" ; "), "err");
      await S.rendre(true);
    }
    async function revoquer(h) {
      const r = await fenetre("Révoquer " + h, '<p class="note">Geste sensible : le certificat est marqué « révoqué » et sort du suivi. Cassandra n’appelle pas l’autorité : la révocation chez elle reste à faire (le panneau ne la propose pas).</p><div class="champ"><label for="rv-r">Raison</label><select id="rv-r"><option>Compromission de la clé</option><option>Cessation d’activité</option><option>Remplacé par un autre certificat</option><option>Autre</option></select></div><div class="champ"><label for="rv-c">Pour confirmer, tapez le nom de l’hôte</label><input type="text" id="rv-c" placeholder="' + esc(h) + '" autocomplete="off"></div>', [{ id: "non", t: "Annuler" }, { id: "oui", t: "Révoquer", cl: "dng", off: true }]);
      return r;
    }
    async function nouvelle() {
      if (!peut("demander")) { dire("Permission refusée : droit certificats.demander.", "err"); return; }
      const M = (S.modeles && S.modeles.length ? S.modeles : ((await lire("certificats.modeles")) || {}).modeles) || [];
      const corps = '<p class="note">La demande suit le modèle choisi : certains exigent une validation par une autre personne.</p><div class="champ"><label for="n-h">Hôte principal</label><input type="text" id="n-h" placeholder="www.exemple.fr" autocomplete="off"><span class="err" id="n-eh"></span></div><div class="champ"><label for="n-s">Noms alternatifs (un par ligne, 20 au plus)</label><textarea id="n-s" rows="2"></textarea><span class="err" id="n-es"></span></div><div class="champ"><label for="n-m">Modèle</label><select id="n-m">' + M.map((m) => '<option value="' + esc(m.id) + '">' + esc(m.nom) + "</option>").join("") + '</select></div><div class="champ"><label for="n-site">Site du panneau rattaché (facultatif)</label><input type="text" id="n-site" placeholder="exemple.fr"></div><div class="champ"><label for="n-j">Justification (obligatoire pour un wildcard)</label><textarea id="n-j" rows="2"></textarea></div><span class="err" id="n-err"></span>';
      const r = await fenetre("Demander un certificat", corps, [{ id: "non", t: "Annuler" }, { id: "br", t: "Enregistrer en brouillon" }, { id: "oui", t: "Soumettre", cl: "pri" }]);
      if (!r || r.id === "non") return;
      const m = r.m; const hote = val(m, "#n-h").toLowerCase();
      const ok = await geste("certificats.demander", { hote: hote, sans: val(m, "#n-s").split(/\n+/).filter(Boolean), modele: val(m, "#n-m"), site: val(m, "#n-site"), justification: val(m, "#n-j"), brouillon: r.id === "br" }, r.id === "br" ? "Brouillon enregistré." : "Demande soumise.");
      if (ok) { S.page = "demandes"; S.rendre(); } else nouvelle.reprise = hote;
    }
    async function importer() {
      const r = await fenetre("Importer un certificat", '<p class="note">Collez le certificat public (PEM). La clé privée n’est jamais demandée : elle reste sur le serveur qui la sert.</p><div class="champ"><label for="i-h">Hôte</label><input type="text" id="i-h" placeholder="boutique.exemple.com"></div><div class="champ"><label for="i-p">Certificat (PEM)</label><textarea id="i-p" rows="6" class="mono" placeholder="-----BEGIN CERTIFICATE-----"></textarea></div>', [{ id: "non", t: "Annuler" }, { id: "oui", t: "Importer", cl: "pri" }]);
      if (!r || r.id !== "oui") return;
      if (await geste("certificats.importer", { hote: val(r.m, "#i-h").toLowerCase(), pem: val(r.m, "#i-p") }, "Certificat importé.")) S.rendre();
    }
    function csv(lignes, nom) { const t = lignes.map((l) => l.map((v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"').join(";")).join("\n"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿" + t], { type: "text/csv" })); a.download = nom; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 500); }

    racine.addEventListener("click", async (ev) => {
      const b = ev.target.closest("[data-a]"); if (!b || b.disabled) return;
      const a = b.dataset.a, h = b.dataset.h;
      if (a === "recharger") return S.rendre();
      if (a === "filtre") { S.page = "liste"; S.f.etat = b.dataset.e || ""; S.sel = null; return S.rendre(); }
      if (a === "ouvrir") { S.page = "liste"; S.sel = h; S.tab = "Résumé"; return S.rendre(); }
      if (a === "retour") { S.sel = null; return S.rendre(); }
      if (a === "onglet") { S.tab = b.dataset.t; return S.rendre(true); }
      if (a === "regl") { S.reg = b.dataset.t; return S.rendre(true); }
      if (a === "tri") { S.tri = [b.dataset.k, S.tri[0] === b.dataset.k ? -S.tri[1] : 1]; return S.rendre(true); }
      if (a === "page") { S.p = Number(b.dataset.p); return S.rendre(true); }
      if (a === "raz") { S.f = { q: "", etat: "", source: "", archives: false }; return S.rendre(true); }
      if (a === "sel") { b.checked ? S.sels.add(h) : S.sels.delete(h); return S.rendre(true); }
      if (a === "tout") { filtrer().slice((S.p - 1) * PAR, S.p * PAR).forEach((c) => (b.checked ? S.sels.add(c.hote) : S.sels.delete(c.hote))); return S.rendre(true); }
      if (a === "lot-vider") { S.sels.clear(); return S.rendre(true); }
      if (a === "lot-relire") { for (const x of S.sels) await geste("certificats.relire_expiration", { hote: x }); dire("Relecture faite : " + S.sels.size + " hôte(s).", "ok"); return S.rendre(); }
      if (a === "lot-renouveler") return renouveler([...S.sels]);
      if (a === "lot-exporter") { csv([["Hôte", "État", "Jours", "Échéance", "Source", "Émetteur"]].concat(S.d.certificats.filter((c) => S.sels.has(c.hote)).map((c) => [c.hote, c.etat, c.jours, c.echeance, SRC[c.source], c.emetteur])), "certificats-selection.csv"); return; }
      if (a === "lot-archiver") { const r = await fenetre("Archiver " + S.sels.size + " certificat(s)", '<p class="note">Ils sortent de la liste, de la sonde et des constats. L’historique est conservé et l’archivage se défait.</p>', [{ id: "non", t: "Annuler" }, { id: "oui", t: "Archiver", cl: "pri" }]); if (r && r.id === "oui") { for (const x of S.sels) await geste("certificats.archiver", { hote: x }); S.sels.clear(); dire("Archivé.", "ok"); S.rendre(); } return; }
      if (a === "relire") { const r = await geste("certificats.relire_expiration", { hote: h }); if (r && r.erreur) dire("Relecture de " + h + " : " + r.erreur, "err"); else if (r) dire("Certificat servi par " + h + " relu : " + jours(r.jours), "ok"); return S.rendre(true); }
      if (a === "renouveler") return renouveler([h]);
      if (a === "archiver") { if (await geste("certificats.archiver", { hote: h }, "Certificat archivé.")) { S.sel = null; S.rendre(); } return; }
      if (a === "desarchiver") { if (await geste("certificats.desarchiver", { hote: h }, "Certificat désarchivé.")) S.rendre(); return; }
      if (a === "revoquer") {
        const pr = revoquer(h); const m = fenetre.derniere; const go = m.querySelector("[data-c=oui]"), inp = m.querySelector("#rv-c");
        inp.addEventListener("input", () => { go.disabled = inp.value.trim() !== h; });
        const r = await pr; if (r && r.id === "oui") { if (await geste("certificats.revoquer", { hote: h, raison: val(r.m, "#rv-r") }, "Certificat révoqué.")) S.rendre(); } return;
      }
      if (a === "nouvelle") return nouvelle();
      if (a === "importer") return importer();
      if (a === "exporter") { csv([["Hôte", "État", "Jours", "Échéance", "Source", "Émetteur", "Algorithme"]].concat(filtrer().map((c) => [c.hote, c.etat, c.jours, c.echeance, SRC[c.source], c.emetteur, c.algo])), "certificats.csv"); return; }
      if (a === "rapport") { const r = await lire("certificats.rapport", { nom: b.dataset.n }); if (r) csv([r.colonnes].concat(r.lignes), "rapport-" + b.dataset.n.toLowerCase().replace(/\W+/g, "-") + ".csv"); return; }
      if (a === "audit-csv") { csv([["Quand", "Action", "Objet", "Acteur", "Résultat", "Note"]].concat((S.audit || []).map((x) => [quand(x.ts), x.action, x.objet, x.acteur, x.resultat, x.note])), "journal-audit.csv"); return; }
      if (a === "aller") { dire("Écran d’un autre module : ouvrez-le depuis le menu (« " + ({ sites: "Parc › Sites", dns: "Parc › Sites › DNS", journal: "Observatoire › Journaux" }[b.dataset.m] || b.dataset.m) + " »).", ""); return; }
      if (a === "d-valider") { if (await geste("certificats.valider", { id: Number(b.dataset.i) }, "Demande validée.")) S.rendre(); return; }
      if (a === "d-soumettre") { if (await geste("certificats.soumettre", { id: Number(b.dataset.i) }, "Demande soumise.")) S.rendre(); return; }
      if (a === "d-rouvrir") { if (await geste("certificats.rouvrir", { id: Number(b.dataset.i) }, "Demande rouverte.")) S.rendre(); return; }
      if (a === "d-refuser") { const r = await fenetre("Refuser la demande #" + b.dataset.i, '<div class="champ"><label for="mo">Motif (obligatoire, transmis au demandeur)</label><textarea id="mo" rows="3"></textarea></div>', [{ id: "non", t: "Annuler" }, { id: "oui", t: "Refuser", cl: "dng" }]); if (r && r.id === "oui" && await geste("certificats.refuser", { id: Number(b.dataset.i), motif: val(r.m, "#mo") }, "Demande refusée.")) S.rendre(); return; }
      if (a === "d-emettre") {
        const i = Number(b.dataset.i), hh = b.dataset.h;
        const r = await fenetre("Émettre le certificat de " + hh, '<p class="note">Le panneau doit déjà porter un certificat pour cet hôte : l’émission initiale n’est pas encore branchée, seul le renouvellement l’est. Un échec est inscrit au registre du quota.</p>', [{ id: "non", t: "Annuler" }, { id: "oui", t: "Émettre par le panneau", cl: "pri" }]);
        if (!r || r.id !== "oui") return;
        try { await agir("fastpanel.ssl_renouveler", { domaine: hh }); await geste("certificats.cloturer_demande", { id: i, ok: true }, "Certificat de " + hh + " émis."); }
        catch (e) { await geste("certificats.cloturer_demande", { id: i, ok: false, motif: msg(e).slice(0, 200) }); dire("Échec de l’émission : " + msg(e), "err"); }
        return S.rendre();
      }
      if (a === "enregistrer") {
        const s = Number((racine.querySelector("#ce-seuil") || {}).value), d = Number((racine.querySelector("#ce-delai") || {}).value), h2 = String((racine.querySelector("#ce-hotes") || {}).value || "");
        const e1 = !(s >= 3 && s <= 90), e2 = !(d >= 1 && d <= 30), mauv = h2.split(",").map((x) => x.trim()).filter(Boolean).find((x) => !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(x));
        racine.querySelector("#ce-e1").textContent = e1 ? "Entre 3 et 90 jours." : ""; racine.querySelector("#ce-e2").textContent = e2 ? "Entre 1 et 30 secondes." : ""; racine.querySelector("#ce-e3").textContent = mauv ? "« " + mauv + " » n’est pas un nom d’hôte." : "";
        if (e1 || e2 || mauv) return;
        await geste("reglages.regler", { cle: "certificats.seuil_jours", valeur: s }); await geste("reglages.regler", { cle: "certificats.delai_s", valeur: d }); await geste("reglages.regler", { cle: "certificats.hotes", valeur: h2.split(",").map((x) => x.trim()).filter(Boolean).join(",") });
        dire("Réglages enregistrés.", "ok"); return S.rendre(true);
      }
    });
    racine.addEventListener("change", (ev) => {
      const t = ev.target; if (!t.dataset.f) return;
      if (t.dataset.f === "archives") S.f.archives = t.checked; else if (t.dataset.f === "audf") S.audf = t.value; else S.f[t.dataset.f] = t.value;
      S.p = 1; S.rendre(true);
    });
    let minut; racine.addEventListener("input", (ev) => { if (ev.target.id !== "ce-q") return; S.f.q = ev.target.value; S.p = 1; clearTimeout(minut); minut = setTimeout(async () => { await S.rendre(true); const q = racine.querySelector("#ce-q"); if (q) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); } }, 200); });
    const onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const a = onglet.classList.contains("active"); if (a && !etait) S.rendre(true); etait = a; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    await S.rendre();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : l'écran des certificats
// EC : néant (aucun point d'évolution)
// LIEN : modules/certificats (le module), interface/CN_kit.js (le kit), interface/CN_dns-ecran.js (l'écran dont celui-ci suit la forme), docs/maquettes/CN_maquette-certificats.html (la maquette)
