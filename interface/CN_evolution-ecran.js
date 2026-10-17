// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Évolution : l'écran (Cockpit et Atelier)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.2.0  #ab6fa8
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l'écran du module Évolution à la ressemblance de la maquette : Cockpit (l'organisme vu de haut) et Atelier (une cible, ses pièces, ses preuves).
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.evolution) ; données par evolution.etat, gestes par evolution.proposer / retour / visiter ; tout texte dynamique est échappé ; ce qui n'est pas encore construit garde sa place, porte la pastille « non branché » et n'affiche aucun chiffre.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.2.0 empreinte=ab6fa8 ▼▼▼
/* La mise en page est celle de docs/CN_maquette-evolution.html (bandeau, héros, cartes numérotées, trois colonnes, tiroir du moteur).
   Règle : un chiffre affiché vient de evolution.etat ; une carte dont le moteur n'existe pas encore garde sa phrase de conception et la pastille « non branché ». */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const token = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };
  const MONO = "ui-monospace,Menlo,Consolas,monospace";

  const CSS = ".ev{--e-verre:var(--surface);--e-filet:var(--line);--e-encre:var(--txt-strong);--e-encre2:var(--txt-soft);--e-encre3:var(--txt-muted);--e-doux:var(--ov-06);--e-ok:var(--ok);--e-al:var(--warn);--e-dg:var(--danger);" +
    "--e-okd:rgba(4,120,87,.11);--e-ald:rgba(180,83,9,.12);--e-dgd:var(--danger-soft,rgba(190,18,60,.1));display:flex;flex-direction:column;gap:14px;color:var(--txt);font-size:13.5px;line-height:1.5}" +
    ".ev *{box-sizing:border-box}.ev h1,.ev h2,.ev h3{margin:0;font-weight:600}.ev h1{font:600 19px/1.2 " + MONO + ";color:var(--e-encre)}" +
    ".ev h2{font:600 12px/1.3 " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--e-encre2)}" +
    ".ev .verre{background:var(--e-verre);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--e-filet);border-radius:16px;box-shadow:var(--shadow-glass)}" +
    ".ev .mono{font-family:" + MONO + "}.ev .lib{font:600 10.5px/1.2 " + MONO + ";letter-spacing:.09em;text-transform:uppercase;color:var(--e-encre3)}.ev .note{font-size:11.5px;color:var(--e-encre3);line-height:1.5}" +
    ".ev .btn{border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt);border-radius:10px;padding:7px 12px;font:600 12px " + MONO + ";cursor:pointer}.ev .btn:hover:not([disabled]){border-color:var(--accent)}" +
    ".ev .btn.prim{background:var(--accent);color:var(--on-accent);border-color:transparent}.ev .btn.dng{color:var(--e-dg);border-color:var(--e-dg)}.ev .btn[disabled]{opacity:.45;cursor:not-allowed}" +
    ".ev .puce{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:3px 9px;font:600 10.5px " + MONO + ";background:var(--e-doux);color:var(--accent);white-space:nowrap}" +
    ".ev .puce.ok{background:var(--e-okd);color:var(--e-ok)}.ev .puce.al{background:var(--e-ald);color:var(--e-al)}.ev .puce.dg{background:var(--e-dgd);color:var(--e-dg)}.ev .puce.mu{background:var(--e-doux);color:var(--e-encre3)}" +
    ".ev .nb{font:600 9.5px " + MONO + ";letter-spacing:.07em;text-transform:uppercase;border:1px dashed var(--e-filet);border-radius:99px;padding:2px 8px;color:var(--e-encre3);white-space:nowrap}" +
    ".ev .entete{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.ev .entete .d{display:flex;gap:8px;align-items:center;flex-wrap:wrap}" +
    ".ev .vues{display:flex;gap:4px;padding:4px;border-radius:12px;width:max-content;max-width:100%}.ev .vues button{border:0;background:transparent;border-radius:9px;padding:7px 16px;font:600 12px " + MONO + ";color:var(--e-encre2);cursor:pointer}" +
    ".ev .vues button.on{background:var(--accent);color:var(--on-accent)}" +
    ".ev .hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1px;background:var(--e-filet);overflow:hidden}.ev .hero>div{background:var(--e-verre);padding:18px 18px 16px;display:flex;flex-direction:column;gap:4px;min-width:0}" +
    ".ev .hero .big{font:600 38px/1 " + MONO + ";letter-spacing:-.02em;color:var(--accent)}.ev .hero .big.ok{color:var(--e-ok)}.ev .hero .big.mu{color:var(--e-encre3)}" +
    ".ev .carte{padding:14px;display:flex;flex-direction:column;gap:9px;min-width:0}.ev .large{grid-column:1/-1}.ev .idee{font:600 10px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}" +
    ".ev .cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:14px}.ev .tete{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}" +
    ".ev .intention{display:flex;gap:8px;flex-wrap:wrap}.ev .intention input{flex:1;min-width:220px;font:13.5px inherit;padding:10px 12px;border-radius:11px;border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt)}" +
    ".ev .sugg-t{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:11.5px;color:var(--e-encre3)}.ev .sugg-t i{width:7px;height:7px;border-radius:50%;background:var(--e-ok);animation:evbat 2s infinite}" +
    "@keyframes evbat{0%{box-shadow:0 0 0 0 var(--e-ok)}70%{box-shadow:0 0 0 7px transparent}100%{box-shadow:0 0 0 0 transparent}}" +
    ".ev .pastilles{display:flex;gap:8px;flex-wrap:wrap}.ev .pas{position:relative;display:flex;flex-direction:column;gap:2px;text-align:left;border:1px solid var(--e-filet);background:var(--e-verre);color:var(--txt);border-radius:14px;padding:8px 12px;max-width:340px;cursor:pointer;animation:event .45s ease both}" +
    ".ev .pas:hover{border-color:var(--accent)}.ev .pas b{font:600 12.5px inherit}.ev .pas small{font:11px " + MONO + ";color:var(--e-encre3)}.ev .pas .ty{font:600 9.5px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}" +
    "@keyframes event{from{opacity:0;transform:translateY(8px) scale(.96)}to{opacity:1;transform:none}}" +
    ".ev .compile{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.ev .compile>div,.ev .tuile{border:1px solid var(--e-filet);border-radius:12px;padding:10px;background:var(--e-verre);display:flex;flex-direction:column;gap:4px;font-size:12.5px;min-width:0}" +
    ".ev .piste{display:grid;grid-template-columns:150px 1fr 120px;gap:10px;align-items:center;font:600 11.5px " + MONO + "}.ev .piste .t{height:22px;border-radius:7px;background:var(--e-filet);position:relative;overflow:hidden}" +
    ".ev .piste .t i{position:absolute;inset:0 auto 0 0;background:var(--e-doux);border-right:2px solid var(--accent)}.ev .piste .t i.r{background:var(--e-okd);border-color:var(--e-ok);opacity:.7}" +
    ".ev .chrono{display:flex;flex-direction:column;border-left:2px solid var(--e-filet);margin-left:7px}.ev .chrono>div{position:relative;padding:5px 0 9px 16px;font-size:12.5px}" +
    ".ev .chrono>div:before{content:'';position:absolute;left:-7px;top:9px;width:12px;height:12px;border-radius:50%;background:var(--accent);border:2px solid var(--surface)}.ev .chrono .rouge:before{background:var(--e-dg)}.ev .chrono .vert:before{background:var(--e-ok)}" +
    ".ev .chrono time{font:600 11px " + MONO + ";color:var(--e-encre3);margin-right:8px}" +
    ".ev .mat{display:grid;grid-template-columns:150px repeat(3,1fr);gap:6px;font-size:12px;align-items:center}.ev .mat .c{border-radius:9px;padding:6px 8px;text-align:center;font:600 11.5px " + MONO + ";background:var(--e-doux);color:var(--accent)}.ev .mat .c.b{background:var(--e-okd);color:var(--e-ok)}" +
    ".ev .genomes{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.ev .genomes>div{border:1px solid var(--e-filet);border-radius:12px;padding:10px;background:var(--e-verre);display:flex;flex-direction:column;gap:4px;font-size:12.5px}" +
    ".ev .bandeau{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;background:var(--e-filet);overflow:hidden}.ev .bandeau>div{background:var(--e-verre);padding:12px 14px;display:flex;flex-direction:column;gap:6px;min-width:0}" +
    ".ev .bandeau .v{font:600 17px/1.1 " + MONO + ";color:var(--e-encre)}.ev .barre{height:6px;border-radius:99px;background:var(--e-filet);overflow:hidden}.ev .barre i{display:block;height:100%;background:var(--accent)}" +
    ".ev .trois{display:grid;grid-template-columns:270px minmax(0,1fr) 330px;gap:14px;align-items:start}@media(max-width:1100px){.ev .trois{grid-template-columns:1fr}}" +
    ".ev .rail{padding:12px;display:flex;flex-direction:column;gap:6px}.ev .cap{border:1px solid transparent;border-radius:12px;padding:9px 10px;text-align:left;background:transparent;color:inherit;display:flex;flex-direction:column;gap:4px;width:100%;cursor:pointer;font:inherit}" +
    ".ev .cap:hover{background:var(--e-doux)}.ev .cap.sel{background:var(--e-verre);border-color:var(--accent)}.ev .cap .n{font:600 12px " + MONO + ";word-break:break-all}.ev .cap .s{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:11.5px;color:var(--e-encre2)}" +
    ".ev .centre{padding:14px;display:flex;flex-direction:column;gap:12px;min-width:0}.ev .onglets{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--e-filet);padding-bottom:8px}" +
    ".ev .onglets button{border:0;background:transparent;border-radius:9px;padding:6px 11px;font:600 12px " + MONO + ";color:var(--e-encre2);cursor:pointer}.ev .onglets button.on{background:var(--e-doux);color:var(--accent)}.ev .zone{overflow-x:auto}" +
    ".ev .cadran{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}.ev .cadran>div{border:1px solid var(--e-filet);border-radius:12px;padding:9px;background:var(--e-verre);display:flex;flex-direction:column;gap:3px}.ev .cadran .v{font:600 16px " + MONO + ";color:var(--e-encre)}.ev .gain{color:var(--e-ok)}" +
    ".ev .analyse{padding:14px;display:flex;flex-direction:column;gap:11px}.ev .preuve{display:grid;grid-template-columns:22px 1fr;gap:8px;align-items:start;font-size:12.5px}" +
    ".ev .preuve .k{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font:700 11px " + MONO + ";background:var(--e-okd);color:var(--e-ok)}.ev .preuve.al .k{background:var(--e-ald);color:var(--e-al)}.ev .preuve.mu .k{background:var(--e-doux);color:var(--e-encre3)}.ev .preuve small{display:block;color:var(--e-encre3);font-size:11.5px}" +
    ".ev .verdict{border-radius:12px;padding:10px 12px;font:600 12.5px/1.45 " + MONO + ";background:var(--e-okd);color:var(--e-ok)}.ev .verdict.al{background:var(--e-ald);color:var(--e-al)}.ev .verdict.dg{background:var(--e-dgd);color:var(--e-dg)}.ev .verdict.mu{background:var(--e-doux);color:var(--e-encre2)}" +
    ".ev .routage{display:flex;gap:4px;flex-wrap:wrap}.ev .routage button{flex:1;min-width:46px;border:1px solid var(--e-filet);background:var(--e-verre);color:var(--txt);border-radius:8px;padding:6px 4px;font:600 11.5px " + MONO + ";cursor:pointer}" +
    ".ev .routage button.on{background:var(--accent);color:var(--on-accent);border-color:transparent}.ev .routage button[disabled]{opacity:.45;cursor:not-allowed}" +
    ".ev .bas{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}.ev .ligne{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--e-filet);font-size:12.5px}.ev .ligne:first-of-type{border-top:0}.ev .ligne .g{color:var(--e-encre3);font-size:11.5px}" +
    ".ev table{border-collapse:collapse;width:100%;font-size:12.5px}.ev th,.ev td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--e-filet);vertical-align:top}.ev th{font:600 10.5px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--e-encre3)}" +
    ".ev .oui{color:var(--e-ok);font-weight:600}.ev .non{color:var(--e-encre3)}.ev .cons{color:var(--accent);font-weight:600}.ev .preu{border-left:2px solid var(--line-strong);padding-left:10px;font-size:12px;color:var(--e-encre2);line-height:1.5}" +
    ".ev select,.ev input[type=number],.ev input[type=text]{border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt);border-radius:9px;padding:6px 9px;font:12.5px " + MONO + "}.ev .lg{display:flex;gap:8px;flex-wrap:wrap;align-items:center}" +
    ".ev .tiroir{position:fixed;inset:0;background:rgba(16,24,40,.38);display:none;align-items:flex-start;justify-content:center;padding:60px 16px;overflow:auto;z-index:50}.ev .tiroir.on{display:flex}.ev .tiroir .verre{background:var(--surface-solid,var(--surface));max-width:980px;width:100%;padding:18px;display:flex;flex-direction:column;gap:12px}" +
    ".ev .choix{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.ev .opt{border:1.5px solid var(--e-filet);border-radius:12px;padding:11px;background:transparent;color:inherit;text-align:left;display:flex;flex-direction:column;gap:5px;font:inherit}.ev .opt.on{border-color:var(--accent);background:var(--e-doux)}" +
    ".ev svg text{font-family:" + MONO + ";fill:var(--e-encre2);font-size:10.5px}";

  // ce que chaque geste dit AVANT d'agir (le miroir du manifeste du module)
  const GESTES = {
    proposer: { risque: "moyen", perimetre: "le stock d'EC du point visé : une variante prouvée y est écrite et mise en OMBRE ; rien n'est servi à personne",
                preuve: "la pièce est dans le stock, en ombre, et la chaîne d'empreintes est intacte (ou rien n'a été écrit)", retour: "retirer la pièce : un aiguillage vers la référence ; l'EC reste dans le stock, jamais détruite" },
    retour: { risque: "moyen", perimetre: "le routage du point visé et ses pièces vivantes", preuve: "le routage du point est à l'arrêt", retour: "proposer de nouveau une variante : une pièce retirée ne se remet pas en service seule" },
    visiter: { risque: "moyen", perimetre: "les pièces en service depuis plus de 30 jours, une fois chacune", preuve: "chaque pièce visitée porte son verdict", retour: "aucun : une pièce retirée à la visite se propose de nouveau" }
  };
  const ETATS = { ombre: ["en ombre", "al"], palier_10: ["10 % du trafic", "al"], palier_50: ["50 % du trafic", "al"], en_service: ["en service", "ok"], retiree: ["retirée", "dg"] };
  const VIVANTES = ["ombre", "palier_10", "palier_50", "en_service"];
  const PARTS = { ombre: 0, palier_10: 10, palier_50: 50, en_service: 100 };
  const ONGLETS = [["carte", "Carte"], ["lignee", "Lignée"], ["ombre", "Ombre"], ["contrat", "Contrat de rejeu"], ["versions", "Versions"]];
  const MOTEURS = [
    ["Orfan", "Projet à part, avec sa R&D. v1 : règles déterministes gratuites d'abord, puis modèle (stratège et exécutant).", "moteur de Cassandra · v1 construit", "ok", true],
    ["OpenEvolve", "Code. Îlots, MAP-Elites, multi-objectifs, évaluation parallèle.", "adaptateur · pas branché", "mu", false],
    ["ShinkaEvolve", "Code. Sobre en essais, modèles locaux, mutation par agent en ligne de commande.", "adaptateur · pas branché", "mu", false],
    ["CodeEvolve", "Code. Meilleurs résultats publiés ; Python ≥ 3.13.5 exigé (le noyau est en 3.11).", "adaptateur · pas branché", "mu", false],
    ["GEPA", "Prompts et politiques d'agents, par réflexion sur les traces et frontière de Pareto.", "adaptateur · pas branché", "mu", false],
    ["FrugalEvo", "Code, attentif au coût : un modèle fort propose, un modèle économe implémente.", "article seul · pas branché", "mu", false]];
  const GENOMES = [["Génome code", "moteurs et capacités des modules", "v1", "ok"], ["Seuils du Sensorium", "la fitness est ce que tu acquittes sans agir", "non branché", "mu"],
    ["Prompts des agents", "évalués sur ce qui a été corrigé ou relancé", "non branché", "mu"], ["Règles de la Proactivité", "quand déranger, quand se taire", "non branché", "mu"]];

  const date = (t) => { try { return new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };
  const ms = (v) => (v == null ? "—" : (v < 1 ? v.toFixed(3) : v.toFixed(2)) + " ms");
  const pct = (v) => (v == null ? "—" : (v > 0 ? "−" : v < 0 ? "+" : "") + Math.abs(v).toFixed(1) + " %");
  const nb = (v) => String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const puce = (txt, cls) => '<span class="puce' + (cls ? " " + cls : "") + '">' + esc(txt) + "</span>";
  const NB = '<span class="nb">non branché</span>';
  const evalDe = (p) => { try { return p && p.evaluation ? JSON.parse(p.evaluation) : {}; } catch (e) { return {}; } };

  function style() {
    if (document.getElementById("ev-css")) document.getElementById("ev-css").remove();
    const s = document.createElement("style");
    s.id = "ev-css"; s.textContent = CSS; document.head.appendChild(s);
  }

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.evolution = async function (corps, ctx) {
    style();
    const S = { etat: null, versions: {}, sel: null, onglet: "carte", vue: "cockpit", resultat: null, confirmer: null, occupe: false, erreur: "", tiroir: false, moteur: "Orfan", intention: "", compile: null, t: null };
    const racine = document.createElement("div");
    racine.className = "ev";
    corps.appendChild(racine);

    const point = (gid) => (S.etat.points || []).find((p) => p.point === gid);
    const cible = (gid) => (S.etat.cibles || []).find((c) => c.point === gid) || {};
    const pieces = (gid) => (S.etat.pieces || []).filter((p) => p.gid === gid);
    const vivante = (gid) => pieces(gid).find((p) => VIVANTES.indexOf(p.etat) >= 0);
    const module = (gid) => gid.split(".")[0];
    const version = (gid) => { const p = vivante(gid); const v = S.versions[module(gid)] || "?"; return p ? v + "+EC" + p.num + "." + p.empreinte : v; };
    const tousVivants = () => (S.etat.pieces || []).filter((p) => VIVANTES.indexOf(p.etat) >= 0);

    async function charger() {
      try {
        S.etat = await CASS.agir("evolution.etat", {});
        if (!S.sel && S.etat.cibles.length) S.sel = S.etat.cibles[0].point;
        if (S.sel && !S.etat.cibles.some((c) => c.point === S.sel)) S.sel = S.etat.cibles.length ? S.etat.cibles[0].point : null;
        S.erreur = "";
      } catch (e) { S.erreur = e.message || String(e); }
      try {
        const d = await (await fetch("/api/modules", { headers: { "X-Session-Token": token() } })).json();
        (d.modules || []).forEach((m) => { S.versions[m.id] = m.version; });
      } catch (e) { /* les versions restent « ? » : dites, pas inventées */ }
    }

    // ── les suggestions vivantes : tirées de ce que le noyau observe en ce moment ──
    function suggestions() {
      const out = [], seuil = (S.etat.seuils || {});
      (S.etat.cibles || []).forEach((c) => {
        const v = vivante(c.point), p = point(c.point) || {}, corpus = p.corpus || {};
        if (c.muet) out.push({ type: "mesure muette", titre: "Mesurer " + c.point, sous: "jamais mesuré : ni stable, ni zéro", point: c.point, objectif: "mesurer " + c.point });
        else if (!v && (corpus.distincts || 0) >= (seuil.corpus_min || 10)) out.push({ type: "gain possible", titre: "Accélérer " + c.point, sous: nb(c.appels) + " appels · " + (c.duree_moyenne_ms == null ? "?" : c.duree_moyenne_ms) + " ms en moyenne", point: c.point, objectif: "accélérer " + c.point, v: c.valeur_ms || 0 });
        else if (!v) out.push({ type: "corpus étroit", titre: "Renforcer le corpus de " + c.point, sous: (corpus.distincts || 0) + " entrées, il en faut " + (seuil.corpus_min || "plus"), point: c.point, objectif: "renforcer " + c.point });
        if (v && v.etat === "ombre") out.push({ type: "en ombre", titre: "Suivre " + c.point, sous: "EC" + v.num + " compare à la référence", point: c.point, objectif: "suivre " + c.point });
        const p30 = pieces(c.point).find((x) => x.etat === "en_service" && !x.visite && x.mise_en_service && Date.now() / 1000 - x.mise_en_service > 30 * 86400);
        if (p30) out.push({ type: "visite échue", titre: "Visiter EC" + p30.num + " de " + c.point, sous: "30 jours de service : le gain est-il resté ?", point: c.point, objectif: "visiter " + c.point });
      });
      if (S.etat.chaine && !S.etat.chaine.ok) out.unshift({ type: "chaîne rompue", titre: "Rupture à la maille " + S.etat.chaine.rupture_a, sous: "rien ne doit avancer", point: S.sel, objectif: "chaîne" });
      return out.sort((a, b) => (b.v || 0) - (a.v || 0)).slice(0, 6);
    }
    function compiler(texte) {
      const t = String(texte || "").toLowerCase();
      const trouve = (S.etat.cibles || []).find((c) => t.indexOf(c.point.toLowerCase()) >= 0 || t.indexOf(c.point.split(".")[1].toLowerCase()) >= 0);
      if (!trouve) return { libre: true };
      const s = S.etat.seuils || {}, p = point(trouve.point) || {};
      return { point: trouve.point, mesure: "durée d'un appel (médiane, passes à froid)", garde: "équivalence sur " + ((p.corpus || {}).distincts || 0) + " entrées, gain ≥ " + (s.gain_min_pct || "?") + " % et 2× le bruit, tenu hors du vu", geste: "proposer une variante, en ombre d'abord" };
    }

    function entete() {
      const ch = S.etat.chaine || {};
      return '<div class="entete"><div><div class="note mono">' + (S.etat.cibles || []).length + " points déclarés · " + tousVivants().length + " pièces vivantes · " + (S.versions.evolution ? "module " + esc(S.versions.evolution) : "") + '</div></div>' +
        '<div class="d">' + puce(ch.ok ? "chaîne scellée · " + (ch.mailles || 0) + " maillons ✓" : "chaîne ROMPUE à la maille " + ch.rupture_a, ch.ok ? "ok" : "dg") +
        '<button class="btn" data-a="tiroir">Moteur : ' + esc(S.moteur) + ' ▾</button><button class="btn" data-a="actualiser">Actualiser</button></div></div>' +
        '<nav class="verre vues"><button data-vue="cockpit" class="' + (S.vue === "cockpit" ? "on" : "") + '">Cockpit</button><button data-vue="atelier" class="' + (S.vue === "atelier" ? "on" : "") + '">Atelier</button></nav>';
    }

    // ═══ COCKPIT ═══════════════════════════════════════════════════════════
    function cockpit() {
      const tous = S.etat.pieces || [], serv = tous.filter((p) => p.etat === "en_service");
      const retraits = (S.etat.journal || []).filter((e) => e.verbe === "retiree" || e.verbe === "retour").length;
      const meilleur = tousVivants().reduce((m, p) => (p.gain_annonce != null && p.gain_annonce > m ? p.gain_annonce : m), 0);
      const x = meilleur > 0 ? (1 / (1 - Math.min(meilleur, 95) / 100)) : null;
      const tombes = Object.values(S.etat.tombes || {}).reduce((a, b) => a + b, 0);
      const dores = (S.etat.points || []).reduce((a, p) => a + ((p.corpus || {}).dores || 0), 0);
      const hero = '<div class="verre hero">' +
        '<div><span class="lib">Meilleur gain d\'une pièce vivante</span><span class="big' + (x ? "" : " mu") + '">' + (x ? x.toFixed(2).replace(".", ",") + "×" : "—") + '</span><span class="note">' + (x ? "annoncé à l'évaluation (" + pct(meilleur) + " de durée), pas encore confirmé à 30 jours" : "aucune pièce vivante : la référence du dépôt sert partout") + "</span></div>" +
        '<div><span class="lib">Appels de modèle par jour</span><span class="big mu">—</span><span class="note">' + NB + " la fossilisation des décisions de modèle n'existe pas encore</span></div>" +
        '<div><span class="lib">Retours effectués</span><span class="big ok">' + retraits + '</span><span class="note">pièces retirées par un retour ou une visite, journalisées dans la chaîne</span></div>' +
        '<div><span class="lib">Pannes guéries sans humain</span><span class="big mu">—</span><span class="note">' + NB + " la guérison (test rouge puis correction) n'existe pas encore</span></div></div>";
      const sg = suggestions();
      const pastilles = sg.length ? sg.map((s, i) => '<button class="pas" data-sug="' + i + '" style="animation-delay:' + i * 60 + 'ms"><span class="ty">' + esc(s.type) + "</span><b>" + esc(s.titre) + "</b><small>" + esc(s.sous) + "</small></button>").join("") : '<div class="note">Rien à proposer : aucun point ne demande d\'attention en ce moment.</div>';
      let comp = "";
      if (S.compile) {
        const c = S.compile;
        comp = c.libre ? '<div class="compile"><div><span class="lib">Compilation</span>Texte libre : ' + NB + '<span class="note">Écrire l\'objectif en français et le compiler en mesure demande un rôle de modèle, non branché ici. Cite un point (par ex. <span class="mono">' + esc(((S.etat.cibles || [])[0] || {}).point || "module.point") + "</span>) ou clique une suggestion.</span></div></div>"
          : '<div class="compile"><div><span class="lib">Point visé</span><b class="mono">' + esc(c.point) + '</b></div><div><span class="lib">Mesure</span>' + esc(c.mesure) + '</div><div><span class="lib">Garde-fous</span>' + esc(c.garde) + '</div><div><span class="lib">Geste</span>' + esc(c.geste) + '<button class="btn prim" data-a="ouvrir-atelier" data-p="' + esc(c.point) + '">Ouvrir dans l\'Atelier</button></div></div>';
      }
      const intention = '<div class="verre carte large"><span class="idee">1 · L\'intention</span><h2>Dis ce que tu veux. Cassandra regarde ce qui compte.</h2>' +
        '<div class="intention"><input id="ev-intent" type="text" placeholder="ex. : accélérer contacts.signaux sans rien casser" value="' + esc(S.intention) + '"><button class="btn prim" data-a="compiler">Compiler l\'objectif</button></div>' +
        '<div class="sugg-t"><i></i><span><b>Cassandra te propose</b> d\'après ce qu\'elle observe en ce moment</span><span class="mono">' + sg.length + '</span></div><div class="pastilles">' + pastilles + "</div>" + comp + "</div>";
      // la nuit : le rejeu existe, la course nocturne non
      const maxC = Math.max(1, ...(S.etat.points || []).map((p) => (p.corpus || {}).distincts || 0));
      const lanes = (S.etat.points || []).map((p) => { const c = p.corpus || {}; return '<div class="piste"><span>' + esc(p.point) + '</span><span class="t"><i style="width:' + Math.round(100 * (c.distincts || 0) / maxC) + '%"></i><i class="r" style="width:' + Math.round(100 * (c.reserve || 0) / maxC) + '%"></i></span><span>' + (c.distincts || 0) + " entrées</span></div>"; }).join("");
      const nuit = '<div class="verre carte large"><div class="tete"><span class="idee">2 · La nuit</span>' + NB + "</div><h2>Chaque nuit, elle rejouera sa journée vécue contre toutes ses variantes</h2>" +
        '<div class="note">Le rejeu accéléré de la nuit, contre un grand nombre de variantes, n\'est pas encore construit. Ce qui existe : le corpus de rejeu, tiré des appels réels (un cinquième réservé, jamais montré au générateur), que chaque proposition rejoue en entier.</div>' +
        (lanes || '<div class="note">Aucun point actif.</div>') + '<div class="note"><span class="mono">▌</span> corpus · <span class="mono" style="color:var(--e-ok)">▌</span> dont le jeu réservé</div></div>';
      const gueri = '<div class="verre carte"><div class="tete"><span class="idee">3 · La guérison</span>' + NB + "</div><h2>Une panne ne se produit jamais deux fois</h2>" +
        '<div class="chrono"><div class="rouge"><time>1</time>Une erreur en service est journalisée</div><div><time>2</time>Elle est reproduite à partir du journal : un test <b>rouge</b> est écrit tout seul</div><div><time>3</time>Des variantes sont cherchées contre ce test et tout le rejeu, sans humain</div><div class="vert"><time>4</time>La meilleure passe en ombre, puis en service. Le test reste pour toujours</div></div>' +
        '<div class="note">Conception seulement. Ce qui tourne déjà : le disjoncteur suspend une EC qui s\'écarte de la référence et la référence répond dans le même appel.</div></div>';
      const cliquet = '<div class="verre carte"><span class="idee">4 · Le cliquet</span><h2>Son évaluateur ne peut que se durcir</h2>' +
        '<div class="lg" style="align-items:baseline"><span class="mono" style="font-size:34px;font-weight:600;color:var(--accent)">' + (dores + tombes) + '</span><span class="note">tests permanents : ' + dores + " cas dorés + " + tombes + " tombes</span></div>" +
        '<div class="note">Chaque cas doré (sortie de la référence, jamais évincé) et chaque tombe (variante échouée, jamais reproposée) est gardé pour toujours. Elle ne peut pas oublier une erreur, ni relâcher son juge pour mieux réussir.</div></div>';
      const fossile = '<div class="verre carte"><div class="tete"><span class="idee">5 · La fossilisation</span>' + NB + "</div><h2>Plus elle vit, moins elle coûte</h2>" +
        '<div class="note">Quand un modèle prend toujours la même décision sur un motif, elle l\'écrit en règle de code, la rejoue contre toutes les décisions passées, et ne garde le modèle que pour l\'exception. Aucune règle n\'est encore distillée : aucun chiffre n\'est affiché.</div></div>';
      const route = (S.etat.points || []).map((p) => { const r = p.routage; return '<span>' + esc(p.point) + '</span><span class="c' + (r && r.mode === "service" ? " b" : "") + '" style="grid-column:span 3">' + (r ? esc(r.mode) + (r.mode === "service" ? " · " + r.part + " %" : "") : "référence seule") + "</span>"; }).join("");
      const routage = '<div class="verre carte"><span class="idee">6 · Le routage sur mesure</span><h2>Elle choisit pour cet appel</h2><div class="mat">' + (route || "") + "</div>" +
        '<div class="note">Aujourd\'hui : un aiguillage par point (référence, ombre, part du trafic stable par appel). ' + NB + " le choix par contexte (petit compte, heure de pointe…) avec un aiguilleur qui apprend.</div></div>";
      const comport = '<div class="verre carte"><span class="idee">7 · Ce qu\'elle fait évoluer</span><h2>Pas seulement du code : son comportement</h2><div class="genomes">' +
        GENOMES.map((g) => '<div><b class="mono">' + esc(g[0]) + '</b><span class="note">' + esc(g[1]) + "</span>" + puce(g[2], g[3]) + "</div>").join("") + "</div></div>";
      const jr = S.etat.journal || [], i = S.t == null ? 0 : S.t;
      const ev = jr.length ? jr[Math.min(jr.length - 1, jr.length - 1 - i)] : null;
      const temps = '<div class="verre carte"><span class="idee">8 · La machine à remonter le temps</span><h2>Tout est immuable et chaîné</h2>' +
        '<input id="ev-temps" type="range" min="0" max="' + Math.max(0, jr.length - 1) + '" value="' + i + '" style="width:100%"><div class="compile" style="grid-template-columns:1fr 1fr"><div><span class="lib">Événement</span><b class="mono">' + (ev ? "#" + ev.seq + " · " + esc(ev.verbe) : "—") + '</b></div>' +
        '<div><span class="lib">Quand · point</span><b class="mono">' + (ev ? date(ev.ts) + " · " + esc(ev.gid) : "—") + "</b></div></div>" +
        '<div class="lg"><button class="btn" disabled>Aperçu de la restauration à cette date</button>' + NB + '</div><div class="note">Le journal est lisible à chaque maillon. La restauration complète n\'est pas construite : un retour se fait aujourd\'hui par point.</div></div>';
      const autres = '<div class="verre carte large"><div class="tete"><span class="idee">9 · Les autres instances</span>' + NB + "</div><h2>Une amélioration trouvée ici profite aux autres, sans qu'on leur fasse confiance</h2>" +
        '<div class="note">Une variante validée serait signée et proposée au réseau ; chaque instance la rejouerait sur son propre trafic, en ombre, avant d\'en dire quoi que ce soit. La preuve se refait chez le receveur. Non construit.</div></div>';
      return hero + intention + nuit + '<div class="cgrid">' + gueri + cliquet + fossile + routage + comport + temps + "</div>" + autres;
    }

    // ═══ ATELIER ═══════════════════════════════════════════════════════════
    function bandeau() {
      const tous = S.etat.pieces || [], viv = tousVivants(), enServ = tous.filter((p) => p.etat === "en_service"), ret = tous.filter((p) => p.etat === "retiree");
      const tombes = Object.values(S.etat.tombes || {}).reduce((a, b) => a + b, 0);
      const corpus = (S.etat.points || []).reduce((a, p) => a + ((p.corpus || {}).distincts || 0), 0);
      const pcs = tous.map((p) => evalDe(p).pieges).filter((x) => x && x.score != null);
      const pg = pcs.length ? Math.round(100 * Math.min.apply(null, pcs.map((x) => x.score))) + " %" : "—";
      const s = S.etat.seuils || {};
      return '<div class="verre bandeau">' +
        '<div><span class="lib">Points d\'évolution</span><span class="v">' + (S.etat.cibles || []).length + '</span><span class="note">déclarés par les modules actifs</span></div>' +
        '<div><span class="lib">Évaluateur évalué</span><span class="v">' + pg + '</span><span class="note">' + (pcs.length ? "plus faible part de variantes volontairement fausses attrapées, sur " + pcs.length + " pièce(s) ; seuil " + Math.round(100 * (s.pieges_min || 0)) + " %" : "aucune pièce encore : le test se fait avant chaque écriture") + "</span></div>" +
        '<div><span class="lib">Variantes en service</span><span class="v">' + viv.filter((p) => p.etat === "ombre").length + " en ombre · " + enServ.length + ' promues</span><span class="note">retour instantané disponible sur chaque point</span></div>' +
        '<div><span class="lib">Retirées · tombes</span><span class="v">' + ret.length + " · " + tombes + '</span><span class="note">une variante échouée n\'est jamais reproposée</span></div>' +
        '<div><span class="lib">Corpus de rejeu</span><span class="v">' + nb(corpus) + '</span><span class="note">appels réels gardés, un cinquième réservé</span></div>' +
        '<div><span class="lib">Budget · autonomie</span><span class="v mono">—</span><span class="note">' + NB + " le capital en jetons et le niveau d'autonomie gagnée</span></div></div>";
    }
    function rail() {
      const l = (S.etat.cibles || []).map((c) => {
        const v = vivante(c.point), e = v ? ETATS[v.etat] : null;
        return '<button class="cap' + (c.point === S.sel ? " sel" : "") + '" data-cible="' + esc(c.point) + '"><span class="n">' + esc(c.point) + '</span><span class="s">' + (e ? puce(e[0], e[1]) : c.muet ? puce("muette", "mu") : puce("référence")) + "<span>" + nb(c.appels || 0) + " appels</span></span>" +
          (c.muet ? "" : '<span class="s">valeur <b class="mono">' + (c.valeur_ms == null ? "—" : c.valeur_ms + " ms") + "</b></span>") + "</button>";
      }).join("");
      return '<div class="verre rail"><div class="lib" style="padding:2px 4px 6px">Cibles vivantes — classées par valeur espérée</div>' + (l || '<div class="note" style="padding:8px 4px">Aucun module actif ne déclare de point d\'évolution.</div>') +
        '<div class="note" style="padding:6px 4px 0">Valeur = appels réels × durée moyenne. Un point sans mesure est dit <b>muet</b> : il n\'est pas « à zéro », il n\'est pas mesuré.</div></div>';
    }
    function centre() {
      if (!S.sel) return '<div class="verre centre"><div class="note">Choisis un point à gauche.</div></div>';
      const c = cible(S.sel), p = point(S.sel) || {}, corpus = p.corpus || {}, v = vivante(S.sel), o = p.ombre;
      const cadran = c.muet ? "" : '<div class="cadran"><div><span class="lib">Durée moyenne</span><span class="v">' + (c.duree_moyenne_ms == null ? "—" : c.duree_moyenne_ms + " ms") + '</span><span class="note">de la référence</span></div>' +
        '<div><span class="lib">Gain annoncé</span><span class="v gain">' + (v ? pct(v.gain_annonce) : "—") + '</span><span class="note">' + (v ? "à l'évaluation, sur le jeu réservé" : "aucune pièce") + "</span></div>" +
        '<div><span class="lib">Écarts en ombre</span><span class="v">' + (o ? o.ecarts : "—") + '</span><span class="note">' + (o ? "sur " + o.appels + " appels comparés" : "pas d'ombre en cours") + "</span></div>" +
        '<div><span class="lib">Corpus</span><span class="v">' + (corpus.distincts || 0) + '</span><span class="note">' + (corpus.visible || 0) + " vus · " + (corpus.reserve || 0) + " réservés · " + (corpus.dores || 0) + " dorés</span></div></div>";
      const z = c.muet ? '<div class="note" style="padding:20px 4px">Cette capacité ne déclare aucune mesure. Le moteur ne la touche pas et ne la compte pas parmi les stables : elle est dite muette.</div>' : onglet(c, p, corpus, v, o);
      return '<div class="verre centre"><div class="tete"><div><h3 class="mono" style="font-size:15px">' + esc(S.sel) + '</h3><div class="note">contrat ' + esc(p.contrat || "?") + " · " + nb(c.appels || 0) + ' appels réels</div></div>' +
        '<div class="lg">' + (c.muet ? puce("non ciblée", "mu") : puce("cible vivante", "ok")) + puce(version(S.sel)) + (p.suspendue ? puce("suspendue", "dg") : "") + "</div></div>" + cadran +
        (c.muet ? "" : '<div class="onglets">' + ONGLETS.map((o) => '<button data-onglet="' + o[0] + '" class="' + (o[0] === S.onglet ? "on" : "") + '">' + o[1] + "</button>").join("") + "</div>") + '<div class="zone">' + z + "</div></div>";
    }
    function onglet(c, p, corpus, v, o) {
      if (S.onglet === "lignee") return lignee();
      if (S.onglet === "ombre") return ombre(p, v, o);
      if (S.onglet === "contrat") return contrat(p, corpus);
      if (S.onglet === "versions") return versions();
      return carte();
    }
    function carte() {
      const l = pieces(S.sel).filter((p) => p.gain_annonce != null), W = 560, H = 120, L = 40, mx = Math.max(10, ...l.map((p) => Math.abs(p.gain_annonce)));
      const tombes = (S.etat.tombes || {})[S.sel] || 0;
      let s = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" style="max-width:720px"><line x1="' + L + '" y1="70" x2="' + (W - 10) + '" y2="70" stroke="var(--line-strong)"/>';
      l.forEach((p, i) => { const x = L + (W - L - 30) * (Math.max(0, p.gain_annonce) / mx), col = p.etat === "retiree" ? "var(--e-dg)" : p.etat === "ombre" ? "var(--e-al)" : "var(--e-ok)";
        s += '<g data-p="' + p.num + '"><circle cx="' + x + '" cy="' + (70 - (i % 3) * 18) + '" r="9" fill="' + col + '" opacity="' + (p.etat === "retiree" ? ".4" : "1") + '"/><text x="' + (x + 13) + '" y="' + (73 - (i % 3) * 18) + '">EC' + p.num + " · " + pct(p.gain_annonce) + "</text></g>"; });
      s += '<text x="' + L + '" y="100">gain annoncé croissant →</text></svg>';
      return s + '<div class="note" style="margin-top:6px">Chaque pièce posée selon son gain annoncé (vert : en service ou palier · ambre : en ombre · pâle : retirée). ' + tombes + " tombe(s) gardée(s) avec leur raison. " + NB +
        " la carte qualité-diversité (une case par genre de variante) demande que les variantes écartées soient archivées avec leur profil ; aujourd'hui seules les pièces prouvées le sont.</div>";
    }
    function lignee() {
      const l = pieces(S.sel);
      if (!l.length) return '<div class="note" style="padding:16px 4px">Aucune pièce sur ce point. Une pièce naît quand le noyau prouve une variante proposée.</div>';
      const H = l.length * 34 + 20;
      let s = '<svg viewBox="0 0 560 ' + H + '" width="100%" style="min-width:420px">';
      l.forEach((p, i) => { const y = i * 34 + 16, col = p.etat === "retiree" ? "var(--e-dg)" : p.etat === "ombre" ? "var(--e-al)" : "var(--e-ok)";
        if (i) s += '<path d="M' + (30) + " " + (y - 34) + " L30 " + y + '" stroke="var(--e-filet)" stroke-width="1.5" fill="none"/>';
        s += '<circle cx="30" cy="' + y + '" r="9" fill="' + col + '" opacity="' + (p.etat === "retiree" ? ".45" : "1") + '"/><text x="48" y="' + (y + 3) + '">EC' + p.num + " · " + pct(p.gain_annonce) + " · " + (ETATS[p.etat] || [p.etat])[0] + (p.etat === "retiree" ? " ✕" : "") + "</text>"; });
      return s + '</svg><div class="note" style="margin-top:6px">La suite des pièces sur ce point, de la plus ancienne en haut. Une pièce retirée reste en lignée, avec sa raison dans la chaîne.</div>';
    }
    function ombre(p, v, o) {
      if (!v || !o) return '<div class="note" style="padding:16px 4px">Aucune variante en ombre sur ce point. Une pièce entre en ombre quand le noyau l\'a prouvée.</div>';
      return '<div class="cadran"><div><span class="lib">Appels comparés</span><span class="v">' + o.appels + '</span><span class="note">appels réels depuis la mise en ombre</span></div><div><span class="lib">Écarts</span><span class="v ' + (o.ecarts ? "" : "gain") + '">' + o.ecarts + '</span><span class="note">un seul bloque la promotion</span></div>' +
        '<div><span class="lib">Référence → EC</span><span class="v" style="font-size:13px">' + ms(o.ref_ms) + " → " + ms(o.ec_ms) + '</span><span class="note">gain observé ' + pct(o.gain_pct) + '</span></div><div><span class="lib">Erreurs</span><span class="v">' + o.erreurs + '</span><span class="note">trois écarts en dix minutes suspendent l\'EC</span></div></div>' +
        '<div class="note" style="margin-top:8px">L\'EC calcule à côté ; la référence répond toujours. ' + (S.etat.seuils ? "Paliers : " + (S.etat.seuils.paliers || []).join(" % → ") + " % du trafic, " + S.etat.seuils.appels_par_palier + " appels par palier." : "") + "</div>";
    }
    function contrat(p, corpus) {
      const s = S.etat.seuils || {};
      return "<table><tr><th>Élément</th><th>État</th><th>Détail</th></tr>" +
        '<tr><td>Appels gardés</td><td class="oui">' + (corpus.distincts || 0) + "</td><td>entrées distinctes tirées des appels réels, plus les cas dorés</td></tr>" +
        '<tr><td>Jeu réservé</td><td class="oui">' + (corpus.reserve || 0) + "</td><td>jamais montré au générateur · partition stable par empreinte</td></tr>" +
        '<tr><td>Cas dorés</td><td class="oui">' + (corpus.dores || 0) + "</td><td>sorties de la référence, jamais évincés</td></tr>" +
        '<tr><td>Variantes pièges</td><td class="oui">≥ ' + Math.round(100 * (s.pieges_min || 0)) + " %</td><td>mauvaises exprès : l'évaluateur doit les attraper avant toute écriture</td></tr>" +
        '<tr><td>Gain exigé</td><td class="oui">≥ ' + (s.gain_min_pct || "?") + " %</td><td>et deux fois le bruit de mesure, tenu sur le jeu réservé</td></tr>" +
        '<tr><td>Contrat</td><td class="cons">' + esc(p.contrat || "?") + "</td><td>entrée et sortie validées à chaque frontière ; copie JSON de part et d'autre</td></tr>" +
        '<tr><td>Corpus trop étroit</td><td class="non">seuil : ' + (s.corpus_min || "?") + ' entrées</td><td>sous le seuil, aucune pièce n\'est écrite</td></tr></table>';
    }
    function versions() {
      const m = module(S.sel), dep = S.versions[m] || "?", p = vivante(S.sel);
      const l = pieces(S.sel).slice().reverse();
      return '<div class="note"><b>Version dépôt</b> : celle du dépôt, signée, que personne ne modifie. <b>Version EC</b> (Evolution Cassandra) : l\'état de la ligne évoluée posée par-dessus. Écriture : <span class="mono">' + esc(version(S.sel)) + "</span>, une version sémantique valide : l'EC ne passe jamais devant le dépôt.</div>" +
        '<div class="cadran" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-top:8px"><div><span class="lib">Version dépôt · ' + esc(m) + '</span><span class="v">' + esc(dep) + '</span></div>' +
        '<div><span class="lib">Version EC en service</span><span class="v">' + (p ? "EC" + p.num : "—") + '</span><span class="note">' + (p ? "empreinte " + esc(p.empreinte) : "aucune : la référence du dépôt sert (EC0)") + "</span></div></div>" +
        '<div class="lib" style="margin-top:10px">Versions EC de ce point</div>' + (l.length ? "<table><tr><th>EC</th><th>Empreinte</th><th>État</th><th>Gain annoncé</th><th>Créée</th><th>Visite à 30 jours</th></tr>" + l.map((q) => {
          const e = ETATS[q.etat] || [q.etat, ""], v = q.visite ? JSON.parse(q.visite) : null;
          return '<tr><td class="mono">EC' + q.num + '</td><td class="mono">' + esc(q.empreinte) + "</td><td>" + puce(e[0], e[1]) + '</td><td class="mono gain">' + pct(q.gain_annonce) + "</td><td>" + date(q.cree) + "</td><td>" + (v ? (v.tenu ? puce("gain confirmé", "ok") : puce("gain perdu : " + pct(v.gain_mesure_pct), "dg")) : '<span class="note">à 30 jours</span>') + "</td></tr>";
        }).join("") + "</table>" : '<div class="note">Aucune EC sur ce point.</div>') +
        '<div class="note" style="margin-top:10px">Une EC ne change jamais le manifeste, les signatures de capacités ni les permissions : elle ne remplace que la fonction pure du point, sous le contrat et le disjoncteur du noyau. Le numéro EC ne repart jamais à zéro ; l\'empreinte l\'accroche au contenu.</div>' +
        '<div class="lg" style="margin-top:8px"><button class="btn" disabled>Proposer au dépôt (patch git)</button>' + NB + "</div>";
    }

    function analyse() {
      if (!S.sel) return '<div class="verre analyse"><h2>Analyse</h2><div class="note">Aucun point choisi.</div></div>';
      const c = cible(S.sel), p = point(S.sel) || {}, v = vivante(S.sel), ch = S.etat.chaine || {};
      let h = '<div class="verre analyse"><div class="tete"><h2>Analyse</h2>' + puce(v ? S.sel.split(".")[1] + " · EC" + v.num : S.sel.split(".")[1]) + "</div>";
      if (c.muet) return h + '<div class="note">Rien à prouver : pas de mesure.</div><div class="verdict mu">Non ciblé : pas de mesure, donc pas de fitness. Ce n\'est ni « stable » ni « zéro ».</div></div>';
      const e = v ? evalDe(v) : null, pj = e && e.pieges;
      const pr = [
        ["Test écrit d'abord, rouge puis vert", NB.replace("non branché", "non branché") + " la génération du test rouge n'existe pas ; le rejeu en tient lieu", -1],
        ["Équivalence sur le rejeu", e ? (e.evalues != null ? e.evalues + " appels sur " + ((e.corpus || {}).distincts || e.evalues) + " identiques à la référence" : "équivalente à la référence") : "aucune pièce à juger", e ? 1 : -1],
        ["Jeu réservé", e ? (e.gain_reserve_pct != null ? "gain " + pct(e.gain_reserve_pct) + " hors du vu (annoncé " + pct(v.gain_annonce) + ")" : "non évalué") : "aucune pièce à juger", e ? (e.gain_tient === false ? 0 : e.gain_reserve_pct != null ? 1 : -1) : -1],
        ["Évaluateur sain", pj && pj.score != null ? Math.round(100 * pj.score) + " % des " + (pj.mutants || "?") + " variantes fausses attrapées" : "testé avant chaque écriture", pj && pj.score != null ? 1 : -1],
        ["Vérificateur indépendant", "une autre famille de modèle, sans le raisonnement du mutateur : non branché", -1],
        ["Chaîne scellée", ch.ok ? "chaîne vérifiée · " + (ch.mailles || 0) + " maillons" : "RUPTURE à la maille " + esc(ch.rupture_a), ch.ok ? 1 : 0]];
      h += '<div style="display:flex;flex-direction:column;gap:9px">' + pr.map((q, i) => '<div class="preuve ' + (q[2] === 1 ? "" : q[2] === 0 ? "al" : "mu") + '"><span class="k">' + (q[2] === 1 ? "✓" : q[2] === 0 ? "!" : "·") + "</span><div>" + (i + 1) + ". " + esc(q[0]) + "<small>" + (i === 0 ? q[1] : esc(q[1])) + "</small></div></div>").join("") + "</div>";
      const sv = S.etat.seuils || {};
      if (p.suspendue) h += '<div class="verdict dg">EC suspendue par le disjoncteur : ' + esc(p.suspendue.raison) + ". La référence sert ; l'EC est conservée.</div>";
      else if (!v) h += '<div class="verdict mu">Aucune pièce : toute la charge passe par la référence du dépôt. Propose une variante pour produire des preuves.</div>';
      else h += '<div class="verdict' + (v.etat === "ombre" ? " al" : "") + '">' + (v.etat === "ombre" ? "Verdict calculé : en ombre. La promotion à " + (sv.paliers || [10])[0] + " % attend " + (sv.ombre_appels || "?") + " appels sans écart." : "En " + (ETATS[v.etat] || [v.etat])[0] + ". Un écart suffit à renvoyer toute la charge à la référence.") + "</div>";
      const part = v ? PARTS[v.etat] : 0;
      h += '<div><span class="lib">Part du trafic réel</span><div class="routage" style="margin-top:6px">' + [0, 10, 50, 100].map((x) => '<button ' + (x === part ? 'class="on" ' : "") + (x === 0 && v && !S.occupe ? 'data-geste="retour"' : "disabled") + ">" + x + " %</button>").join("") + "</div>" +
        '<div class="note" style="margin-top:6px">' + (v ? (part ? part + " % des appels passent par l'EC, le reste par la référence. Seul le retour (0 %) se commande ici : la montée se fait seule, par paliers, tant que les preuves tiennent." : "En ombre : l'EC calcule à côté, la référence répond à tous.") : "Toute la charge passe par la référence.") + "</div></div>";
      h += confirmations() + resultat();
      h += '<div class="lg"><button class="btn dng" data-geste="retour"' + (v && !S.occupe ? "" : " disabled") + '>Retour instantané</button><button class="btn" disabled title="non branché">Geler cette lignée</button></div>';
      const tombes = (S.etat.journal || []).filter((x) => x.gid === S.sel && x.verbe === "tombe");
      h += '<div><span class="lib">Mémoire des échecs donnée au mutateur</span><div style="margin-top:6px;display:flex;flex-direction:column;gap:6px">' + (tombes.length ? tombes.slice(-4).map((x) => '<div class="note" style="border-left:2px solid var(--e-dg);padding-left:8px">' + esc((x.details || {}).raison || "variante tombée") + "</div>").join("") : '<div class="note">' + (((S.etat.tombes || {})[S.sel] || 0) + " tombe(s) gardée(s) ; leur raison est dans la chaîne.") + "</div>") + "</div></div>";
      h += gestesProposer() + "</div>";
      return h;
    }
    function preuveDe(nom) {
      const g = GESTES[nom];
      return '<div class="preu"><b>Risque</b> ' + esc(g.risque) + " · <b>Périmètre</b> " + esc(g.perimetre) + "<br><b>Preuve</b> " + esc(g.preuve) + "<br><b>Retour</b> " + esc(g.retour) + "</div>";
    }
    function confirmations() {
      if (S.confirmer === "retour") return preuveDe("retour") + '<div class="lg"><button class="btn dng" data-geste="retour-ok"' + (S.occupe ? " disabled" : "") + '>Confirmer : renvoyer à la référence</button><button class="btn" data-geste="annuler">Annuler</button></div>';
      if (S.confirmer === "visiter") return preuveDe("visiter") + '<div class="lg"><button class="btn prim" data-geste="visiter-ok">Confirmer : lancer les visites échues</button><button class="btn" data-geste="annuler">Annuler</button></div>';
      if (S.confirmer === "proposer") return preuveDe("proposer") + '<div class="lg"><button class="btn prim" data-geste="proposer-ok"' + (S.occupe ? " disabled" : "") + '>Confirmer : proposer</button><button class="btn" data-geste="annuler">Annuler</button></div>';
      return "";
    }
    function gestesProposer() {
      const s = S.etat.seuils || {};
      return '<div style="border-top:1px solid var(--e-filet);padding-top:10px;display:flex;flex-direction:column;gap:8px"><span class="lib">Proposer une variante</span><div class="lg"><select id="ev-moteur"><option value="deterministe">Orfan déterministe (zéro jeton)</option><option value="modele">Modèle de langage</option><option value="les_deux">Les deux, gratuit d\'abord</option></select>' +
        '<input type="number" id="ev-budget" min="1" max="10" value="3" style="width:64px" title="variantes évaluées"></div><div class="lg"><button class="btn prim" data-geste="proposer"' + (S.occupe ? " disabled" : "") + ">Proposer une variante</button>" + (S.occupe ? '<span class="note">évaluation en cours…</span>' : "") + '<button class="btn" data-geste="visiter">Lancer les visites à 30 jours</button></div>' +
        '<div class="note"><b>Avant d\'écrire quoi que ce soit, le noyau exige</b> : équivalence sur tout le corpus ; gain d\'au moins ' + (s.gain_min_pct || "?") + " % <i>et</i> deux fois le bruit de mesure, tenu sur le jeu réservé ; un corpus assez fort (" + Math.round(100 * (s.pieges_min || 0)) + " % des variantes fausses attrapées). Sinon : rien n'est écrit.</div></div>";
    }
    function resultat() {
      const r = S.resultat;
      if (!r) return "";
      if (r.erreur) return '<div class="verdict dg">' + esc(r.erreur) + "</div>";
      if (r.visites) return '<div class="verdict ' + (r.visites.length ? "" : "al") + '">' + (r.visites.length ? r.visites.map((v) => esc(v.point + " " + v.ec + " : " + (v.tenu ? "gain confirmé" : "gain perdu, pièce retirée"))).join("<br>") : "Aucune visite échue : aucune pièce n'est en service depuis 30 jours.") + "</div>";
      if (r.retraits) return '<div class="verdict">' + (r.retraits.length ? "Retour fait : " + r.retraits.map((x) => esc(x.ec)).join(", ") + " retirée(s). La référence sert." : "Rien à retirer.") + "</div>";
      let h = '<div class="verdict' + (r.ok ? "" : " al") + '">' + (r.ok ? "Variante prouvée, écrite et mise en ombre : " + esc(r.piece.ec) + " (gain annoncé " + pct(r.piece.gain_annonce_pct) + "). Rien n'est encore servi à personne." : "Rien n'a été écrit : " + esc(r.raison)) + "</div>";
      if ((r.essais || []).length) h += "<table><tr><th>Essai</th><th>Verdict</th><th>Gain</th></tr>" + r.essais.map((e, i) => "<tr><td>" + (i + 1) + "</td><td>" + esc(e.verdict) + '</td><td class="mono">' + pct(e.gain_pct) + "</td></tr>").join("") + "</table>";
      return h;
    }

    function atelierBas() {
      const visites = (S.etat.pieces || []).filter((p) => p.etat === "en_service" || p.visite).sort((a, b) => (b.cree || 0) - (a.cree || 0)).slice(0, 5);
      const vis = visites.length ? visites.map((p) => { const v = p.visite ? JSON.parse(p.visite) : null, reste = p.mise_en_service ? Math.ceil(30 - (Date.now() / 1000 - p.mise_en_service) / 86400) : null;
        return '<div class="ligne"><div><span class="mono">' + esc(p.gid) + "</span> · EC" + p.num + '<div class="g">annoncé ' + pct(p.gain_annonce) + (v ? " · mesuré " + pct(v.gain_mesure_pct) : "") + "</div></div>" +
          (v ? puce(v.tenu ? "confirmé" : "retiré · tombe", v.tenu ? "ok" : "dg") : puce(reste != null && reste > 0 ? "échéance dans " + reste + " j" : "à visiter", "al")) + "</div>"; }).join("") : '<div class="note">Aucune pièce en service : rien à visiter.</div>';
      const sem = Date.now() / 1000 - 7 * 86400, jr = (S.etat.journal || []).filter((e) => e.ts >= sem);
      const cnt = (v) => jr.filter((e) => e.verbe === v).length;
      return '<div class="bas">' +
        '<div class="verre carte"><div class="tete"><h2>Demandes restées sans réponse → module à créer</h2>' + NB + '</div><div class="note">Le journal des 501 et des « pas porté » : ce que les gens demandent et que rien ne sert. La création de brouillons de modules à partir de ces demandes n\'est pas construite.</div></div>' +
        '<div class="verre carte"><div class="tete"><h2>Constats pour le noyau</h2>' + NB + '</div><div class="note">Le moteur n\'écrit jamais le noyau. Il observera ce qui frotte (limites contournées par plusieurs modules, caches absents) et le rendra pour la prochaine version. Aucun constat n\'est inventé ici.</div></div>' +
        '<div class="verre carte"><h2>Visites à J+30 — le gain est-il resté ?</h2>' + vis + '<div class="note">Un gain annoncé qui ne tient pas fait retirer la pièce, avec sa tombe. Jamais un « neutre » : le verdict est calculé.</div></div>' +
        '<div class="verre carte"><h2>Bulletin des sept derniers jours</h2><div class="note mono">calculé sur la chaîne : le modèle ne rédige rien</div>' +
        '<div class="ligne"><div>Proposées : ' + cnt("proposee") + " · mises en ombre : " + cnt("ombre") + " · retirées : " + (cnt("retiree") + cnt("retour")) + " · tombes : " + cnt("tombe") + "</div></div>" +
        '<div class="ligne"><div>Muets : ' + ((S.etat.cibles || []).filter((c) => c.muet).map((c) => '<span class="mono">' + esc(c.point) + "</span>").join(", ") || "aucun") + '<div class="g">pas de mesure : ni « stable », ni « zéro »</div></div></div></div></div>' +
        '<div class="verre carte"><h2>Pourquoi ce n\'est pas un OpenEvolve de plus</h2><div class="note">Les moteurs ouverts évoluent un programme face à un score. Cassandra les branche sur une production vivante. La colonne « État » dit ce qui est construit aujourd\'hui.</div><div class="zone"><table><tr><th>Capacité</th><th>Moteurs ouverts seuls</th><th>Dans Cassandra</th><th>État</th></tr>' +
        [["Le banc d'essai vient du trafic réel", "non : évaluateur écrit à la main", "corpus de rejeu tiré du journal, jeu réservé", 1], ["L'évaluateur est lui-même évalué", "non", "variantes pièges avant chaque écriture", 1], ["Mise en service sans risque", "rend un fichier", "ombre, paliers du trafic, retour instantané", 1],
          ["Ne cible que du code vivant", "à vous de choisir", "valeur espérée = appels réels × durée", 1], ["Gain vérifié après coup", "non", "visite à J+30 ; un faux gain retire la pièce", 1], ["Mémoire des échecs", "archive de bons programmes", "tombes par empreinte syntaxique", 1],
          ["Chaîne d'empreintes unique", "non", "une rupture arrête tout", 1], ["Désaccord entre agents pour l'irréversible", "non", "vérificateur d'une autre famille de modèle", 0], ["Créer des modules à partir de ce qui manque", "non", "brouillons en ombre", 0], ["Échange entre instances", "non", "variantes signées, rejouées chez le receveur", 0]]
          .map((r) => "<tr><td>" + r[0] + '</td><td class="non">' + r[1] + '</td><td class="cons">' + r[2] + "</td><td>" + (r[3] ? puce("construit", "ok") : NB) + "</td></tr>").join("") + "</table></div></div>";
    }
    function atelier() {
      return bandeau() + '<div class="trois">' + rail() + centre() + analyse() + "</div>" + atelierBas();
    }

    function tiroir() {
      return '<div class="tiroir' + (S.tiroir ? " on" : "") + '" data-a="fermer-fond"><div class="verre"><div class="tete"><h3 class="mono">Moteur de recherche et rôles</h3><button class="btn" data-a="tiroir">Fermer</button></div>' +
        '<div class="note">Orfan est le moteur de Cassandra : natif, sans dépendance externe. Les autres sont des adaptateurs facultatifs prévus pour comparer et laisser le choix à l\'admin ; aucun n\'est branché aujourd\'hui.</div><div class="choix">' +
        MOTEURS.map((m) => '<button class="opt' + (m[0] === S.moteur ? " on" : "") + '"' + (m[4] ? ' data-moteur="' + esc(m[0]) + '"' : " disabled") + '><b class="mono">' + esc(m[0]) + '</b><span class="note">' + esc(m[1]) + "</span>" + puce(m[2], m[3]) + "</button>").join("") + "</div>" +
        '<div class="verre" style="padding:14px;display:flex;flex-direction:column;gap:9px;background:var(--e-doux)"><h3 class="mono" style="font-size:14px">Orfan v1, ce qui est livré</h3><div class="genomes">' +
        [["Règles déterministes", "mémoïser, sortir un invariant, liste → ensemble : gratuites, essayées d'abord", "v1", "ok"], ["Moteur à modèle", "un stratège propose, un exécutant écrit ; via le rôle modeles.completer", "v1", "ok"], ["Évaluation par le noyau", "équivalence, gain, bruit, jeu réservé : le moteur ne juge jamais lui-même", "v1", "ok"],
          ["Génome prompts et politiques", "réflexion sur les traces, recherche locale sur les acquittements", "R&D", "al"], ["Co-évolution prompt et code", "un prompt qui engendre des tombes est puni", "R&D", "al"], ["Archive sur le contexte réel", "une variante peut être la meilleure dans un contexte seulement", "R&D", "al"]]
          .map((g) => '<div><b class="mono">' + esc(g[0]) + '</b>' + puce(g[2], g[3]) + '<span class="note">' + esc(g[1]) + "</span></div>").join("") + '</div></div>' +
        '<div class="note">Le moteur ne rend que des candidats : l\'évaluation, la mise en ombre et la promotion restent à l\'étage du noyau. Le choix « déterministe / modèle / les deux » se fait au moment de proposer, dans l\'Atelier.</div></div></div>';
    }

    function dessiner() {
      if (S.erreur && !S.etat) {
        racine.innerHTML = '<div class="verdict dg">' + esc(S.erreur) + '</div><div class="note">' + (/fetch|network|réseau/i.test(S.erreur) ? "Le serveur ne répond pas pour l'instant : réessaie dans un instant." : "Le module Évolution est-il actif ? (Réglages › Modules)") + '</div><div class="lg"><button class="btn" data-a="actualiser">Réessayer</button></div>';
        lier(); return;
      }
      const fig = racine.querySelector("#ev-intent");
      if (fig) S.intention = fig.value;
      racine.innerHTML = entete() + (S.vue === "cockpit" ? cockpit() : atelier()) + tiroir();
      lier();
    }
    function lier() {
      racine.querySelectorAll("[data-vue]").forEach((b) => b.addEventListener("click", () => { S.vue = b.dataset.vue; dessiner(); }));
      racine.querySelectorAll("[data-cible]").forEach((b) => b.addEventListener("click", () => { S.sel = b.dataset.cible; S.resultat = null; S.confirmer = null; dessiner(); }));
      racine.querySelectorAll("[data-onglet]").forEach((b) => b.addEventListener("click", () => { S.onglet = b.dataset.onglet; dessiner(); }));
      racine.querySelectorAll("[data-geste]").forEach((b) => b.addEventListener("click", () => geste(b.dataset.geste)));
      racine.querySelectorAll("[data-moteur]").forEach((b) => b.addEventListener("click", () => { S.moteur = b.dataset.moteur; dessiner(); }));
      racine.querySelectorAll("[data-sug]").forEach((b) => b.addEventListener("click", () => {
        const s = suggestions()[parseInt(b.dataset.sug, 10)]; if (!s) return;
        S.intention = s.objectif; S.compile = compiler(s.objectif); if (s.point) S.sel = s.point; dessiner(); }));
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", async (ev) => {
        const a = b.dataset.a;
        if (a === "fermer-fond" && ev.target !== b) return;
        if (a === "tiroir" || a === "fermer-fond") { S.tiroir = !S.tiroir; dessiner(); }
        else if (a === "actualiser") { await charger(); dessiner(); }
        else if (a === "compiler") { const t = (racine.querySelector("#ev-intent") || {}).value || ""; S.intention = t; S.compile = compiler(t); dessiner(); }
        else if (a === "ouvrir-atelier") { S.sel = b.dataset.p; S.vue = "atelier"; dessiner(); }
      }));
      const tmp = racine.querySelector("#ev-temps");
      if (tmp) tmp.addEventListener("input", () => { S.t = parseInt(tmp.value, 10); const y = tmp.parentNode.scrollTop; dessiner(); const n = racine.querySelector("#ev-temps"); if (n) n.focus(); });
    }

    async function geste(nom) {
      if (nom === "annuler") { S.confirmer = null; return dessiner(); }
      if (nom === "proposer" || nom === "retour" || nom === "visiter") { S.confirmer = nom; S.vue = "atelier"; return dessiner(); }
      const moteur = (racine.querySelector("#ev-moteur") || {}).value || "deterministe", budget = parseInt((racine.querySelector("#ev-budget") || {}).value, 10) || 3;
      S.confirmer = null; S.occupe = true; S.resultat = null; dessiner();
      try {
        if (nom === "proposer-ok") S.resultat = await CASS.agir("evolution.proposer", { point: S.sel, moteur: moteur, budget: budget });
        else if (nom === "retour-ok") S.resultat = await CASS.agir("evolution.retour", { point: S.sel, raison: "retour demandé depuis l'écran" });
        else if (nom === "visiter-ok") S.resultat = await CASS.agir("evolution.visiter", {});
      } catch (e) { S.resultat = { erreur: e.message || String(e) }; }
      S.occupe = false;
      await charger();
      dessiner();
    }

    await charger();
    dessiner();
    const minuteur = setInterval(async () => { if (!document.body.contains(racine)) return clearInterval(minuteur); if (S.occupe || S.confirmer || S.tiroir) return; const f = document.activeElement; if (f && racine.contains(f) && /INPUT|SELECT/.test(f.tagName)) return; await charger(); dessiner(); }, 20000);
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : l'écran du module Évolution. Il n'appelle que les capacités du module (etat, proposer, retour, visiter) et n'invente aucune donnée :
//      une carte de la maquette dont le moteur n'existe pas garde sa place avec la pastille « non branché » et sans chiffre.
// EC : néant. Une vue évolutive serait déclarative (jamais du script) : docs/CN_NEXUS.md §5 bis.
// LIEN : modules/evolution (le module), docs/CN_maquette-evolution.html (la maquette), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce script).
