// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : DNS : l'écran des zones
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #d37a23
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l'écran « Zones DNS » du module dns : l'adresse publique face à sa référence, une carte par zone, et pour la zone choisie ses enregistrements, ses dérives (avec les gestes), la santé de son courrier et l'historique de sa référence.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.dns) ; données par dns.etat et dns.reference (lectures en base, jamais de réseau à l'ouverture), le relevé en direct (dns.relever_zone) ne part qu'au clic ; gestes par dns.accepter_reference et dns.corriger_enregistrement, après une confirmation sur place ; les domaines suivis s'écrivent dans le réglage dns.domaines ; tout texte dynamique est échappé
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=d37a23 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };

  const CSS = ".dz{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.dz *{box-sizing:border-box}" +
    ".dz h1,.dz h2,.dz h3,.dz p{margin:0}.dz .mono{font-family:" + MONO + "}" +
    ".dz .carte{background:var(--surface);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass)}" +
    ".dz .tete{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:flex-end;justify-content:space-between}.dz .tete h1{font:650 22px/1.2 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".dz .sous{color:var(--txt-soft);font-size:13px;margin-top:3px;max-width:62ch}.dz .acts{display:flex;gap:8px;flex-wrap:wrap}" +
    ".dz .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 13px;font:600 12.5px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}" +
    ".dz .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.dz .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.dz .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}" +
    ".dz .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.dz .btn[disabled]{opacity:.45;cursor:not-allowed}.dz .btn.mini{padding:4px 9px;font-size:11.5px}" +
    ".dz .pastille{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;white-space:nowrap;background:var(--surface-solid,var(--surface));color:var(--txt-soft);border:1px solid var(--line)}" +
    ".dz .pastille::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}" +
    ".dz .pastille.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 28%,transparent)}" +
    ".dz .pastille.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}" +
    ".dz .pastille.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent);border-color:color-mix(in srgb,var(--danger) 28%,transparent)}" +
    ".dz .pastille.mu::before{opacity:.45}" +
    ".dz .hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));overflow:hidden}.dz .hero>div{padding:16px 18px;display:flex;flex-direction:column;gap:5px;border-left:1px solid var(--line)}.dz .hero>div:first-child{border-left:0}" +
    ".dz .lib{font:600 10.5px 'Inter',system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}.dz .gros{font:600 24px/1.15 " + MONO + ";color:var(--txt-strong,var(--txt));overflow-wrap:anywhere}.dz .gros.al{color:var(--warn)}.dz .gros.dg{color:var(--danger)}.dz .gros.ok{color:var(--ok)}" +
    ".dz .note{font-size:12px;color:var(--txt-soft)}.dz .corps{display:grid;grid-template-columns:minmax(250px,320px) minmax(0,1fr);gap:16px;align-items:start}" +
    ".dz .liste{display:flex;flex-direction:column;gap:8px}.dz .zone{display:flex;flex-direction:column;gap:6px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface);cursor:pointer;text-align:left;font:inherit;color:inherit;width:100%}" +
    ".dz .zone:hover{border-color:var(--accent)}.dz .zone.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}.dz .zone b{font:650 14px " + MONO + ";overflow-wrap:anywhere}.dz .zone .l1{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}" +
    ".dz .barre{height:5px;border-radius:99px;background:var(--line);overflow:hidden}.dz .barre i{display:block;height:100%;border-radius:99px;background:var(--ok)}.dz .barre i.al{background:var(--warn)}.dz .barre i.dg{background:var(--danger)}" +
    ".dz .detail{padding:0;overflow:hidden}.dz .dt{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--line)}.dz .dt h2{font:650 17px " + MONO + ";overflow-wrap:anywhere}" +
    ".dz .onglets{display:flex;gap:2px;padding:8px 12px 0;border-bottom:1px solid var(--line);overflow-x:auto}.dz .onglets button{border:0;background:transparent;padding:8px 13px;font:600 12.5px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}" +
    ".dz .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}.dz .onglets .n{margin-left:5px;font:600 10.5px 'Inter',sans-serif;background:var(--line);border-radius:99px;padding:1px 6px;color:var(--txt-soft)}.dz .onglets .n.al{background:color-mix(in srgb,var(--danger) 16%,transparent);color:var(--danger)}" +
    ".dz .pan{padding:14px 18px 18px;display:flex;flex-direction:column;gap:12px}.dz .barre-out{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between}" +
    ".dz .grp{display:flex;flex-direction:column;gap:2px}.dz .grp h3{font:600 10.5px 'Inter',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint);padding:6px 0 4px}" +
    ".dz .rang{display:grid;grid-template-columns:minmax(120px,.8fr) 58px minmax(0,2fr) auto;gap:6px 12px;align-items:start;padding:8px 0;border-top:1px solid var(--line)}.dz .rang .nom{font:600 12.5px " + MONO + ";overflow-wrap:anywhere}" +
    ".dz .rang .typ{font:700 10.5px " + MONO + ";color:var(--accent);background:color-mix(in srgb,var(--accent) 11%,transparent);border-radius:6px;padding:2px 6px;text-align:center;justify-self:start}.dz .rang .val{font:12px/1.5 " + MONO + ";color:var(--txt-soft);overflow-wrap:anywhere;display:flex;flex-direction:column;gap:2px}" +
    ".dz .rang .val s{opacity:.55}.dz .verif{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--line)}.dz .verif .pic{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font:700 12px 'Inter',sans-serif;color:#fff;background:var(--txt-faint)}" +
    ".dz .verif .pic.ok{background:var(--ok)}.dz .verif .pic.al{background:var(--warn)}.dz .verif .pic.dg{background:var(--danger)}.dz .verif b{font-weight:650}.dz .verif .l{flex:1;min-width:0}.dz .verif .d{font-size:12px;color:var(--txt-soft)}.dz .verif code{font:11.5px " + MONO + ";overflow-wrap:anywhere}" +
    ".dz .drv{padding:12px 14px;border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;gap:8px;background:var(--surface-solid,transparent)}.dz .drv .diff{display:grid;grid-template-columns:auto minmax(0,1fr);gap:3px 10px;font:12px " + MONO + "}.dz .drv .diff em{font-style:normal;color:var(--txt-faint)}" +
    ".dz .vide{padding:34px 20px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:12px}.dz .vide svg{width:42px;height:42px;stroke:var(--accent);fill:none;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}.dz .vide h2{font:650 18px 'Inter',sans-serif}.dz .vide p{max-width:56ch;color:var(--txt-soft)}" +
    ".dz .ajout{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;width:100%;max-width:520px}.dz input[type=text]{flex:1 1 220px;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:8px 12px;font:13px " + MONO + "}" +
    ".dz input[type=text]:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}.dz .hist{display:flex;flex-direction:column}.dz .hist .v{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:9px 0;border-top:1px solid var(--line);font-size:12.5px}" +
    ".dz .attente{padding:30px;text-align:center;color:var(--txt-soft)}.dz .puces{display:flex;gap:6px;flex-wrap:wrap}.dz .confirme{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px;color:var(--txt-soft)}" +
    ".sh-scene:has(>.sh-corps>.dz)>.sh-titre{display:none}" +
    "@media (max-width:820px){.dz .corps{grid-template-columns:minmax(0,1fr)}.dz .rang{grid-template-columns:minmax(0,1fr) auto}.dz .rang .val{grid-column:1 / -1}.dz .hero>div{border-left:0;border-top:1px solid var(--line)}.dz .hero>div:first-child{border-top:0}}";

  // ── les petits calculs ───────────────────────────────────────────────────────
  const jours = (iso) => { if (!iso) return null; const d = new Date(String(iso).slice(0, 10) + "T00:00:00Z"); return isNaN(d) ? null : Math.floor((d - Date.now()) / 86400000); };
  const age = (ts) => { if (!ts) return "jamais"; const s = Math.max(0, Math.floor(Date.now() / 1000 - ts)); return s < 90 ? "à l’instant" : s < 5400 ? "il y a " + Math.round(s / 60) + " min" : s < 129600 ? "il y a " + Math.round(s / 3600) + " h" : "il y a " + Math.round(s / 86400) + " j"; };
  const date = (ts) => { if (!ts) return "—"; const d = new Date(ts * 1000); return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" }) + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }); };
  const cle = (k) => { const i = k.lastIndexOf("|"); return { nom: k.slice(0, i), type: k.slice(i + 1) }; };
  const ORDRE = { A: 1, AAAA: 2, CNAME: 3, MX: 4, TXT: 5, CAA: 6 };
  const mot = (n, s, p) => n + " " + (n > 1 ? p : s);

  function etatZone(z, seuil) {
    const j = jours(z.expiration);
    if (z.releve == null) return { cls: "mu", txt: "pas encore relevée", ordre: 3 };
    if ((z.derives || []).some((d) => d.ip_derivee)) return { cls: "dg", txt: "adresse à corriger", ordre: 0 };
    if (j != null && j <= 14) return { cls: "dg", txt: "expire dans " + Math.max(j, 0) + " j", ordre: 0 };
    if ((z.derives || []).length) return { cls: "al", txt: mot(z.derives.length, "dérive", "dérives"), ordre: 1 };
    if (j != null && j <= seuil) return { cls: "al", txt: "expire dans " + j + " j", ordre: 1 };
    return { cls: "ok", txt: "conforme", ordre: 2 };
  }

  // La santé du courrier et du reste, lue dans une carte d'enregistrements { "nom|TYPE": [valeurs] } : ce que les bonnes pratiques attendent d'un domaine.
  function verifs(dom, rec) {
    const v = (nom, type) => rec[nom + "|" + type] || [];
    const sortie = [];
    const mx = v(dom, "MX");
    sortie.push(mx.length ? { n: "ok", t: "Réception du courrier (MX)", d: "Le domaine reçoit son courrier.", c: mx } : { n: "al", t: "Réception du courrier (MX)", d: "Aucun enregistrement MX : ce domaine ne peut pas recevoir de courrier. Normal s'il n'en doit pas." });
    const spf = v(dom, "TXT").filter((x) => /v=spf1/i.test(x));
    if (!spf.length) sortie.push({ n: "al", t: "SPF", d: "Aucun SPF : n'importe quel serveur peut se faire passer pour ce domaine auprès des destinataires.", c: [] });
    else if (spf.length > 1) sortie.push({ n: "dg", t: "SPF", d: "Plusieurs SPF : la norme n'en admet qu'un, les destinataires peuvent rejeter vos messages.", c: spf });
    else if (/\+all\b/i.test(spf[0])) sortie.push({ n: "dg", t: "SPF", d: "« +all » autorise le monde entier à écrire en votre nom.", c: spf });
    else sortie.push({ n: /[~-]all\b/i.test(spf[0]) ? "ok" : "al", t: "SPF", d: /[~-]all\b/i.test(spf[0]) ? "Un SPF cadre les serveurs autorisés." : "Le SPF ne se termine pas par « ~all » ou « -all » : il ne tranche pas.", c: spf });
    const dm = v("_dmarc." + dom, "TXT").filter((x) => /v=DMARC1/i.test(x));
    if (!dm.length) sortie.push({ n: "al", t: "DMARC", d: "Aucune politique DMARC : rien n'indique quoi faire des messages usurpés.", c: [] });
    else { const p = (/;\s*p=([a-z]+)/i.exec(";" + dm[0].replace(/\s/g, "")) || [])[1] || ""; sortie.push({ n: /^(quarantine|reject)$/i.test(p) ? "ok" : "al", t: "DMARC", d: /^(quarantine|reject)$/i.test(p) ? "Politique « " + p.toLowerCase() + " » : les messages usurpés sont écartés." : "Politique « " + (p || "?") + " » : surveillance seule, rien n'est écarté.", c: dm }); }
    const dk = Object.keys(rec).filter((k) => k.indexOf("._domainkey.") > 0);
    sortie.push(dk.length ? { n: "ok", t: "Signature DKIM", d: mot(dk.length, "clé trouvée", "clés trouvées") + " (" + dk.map((k) => cle(k).nom.split(".")[0]).join(", ") + ").", c: [] } : { n: "al", t: "Signature DKIM", d: "Aucune clé trouvée parmi les sélecteurs usuels : vos messages ne sont peut-être pas signés (ou le sélecteur est inhabituel).", c: [] });
    const caa = v(dom, "CAA");
    sortie.push(caa.length ? { n: "ok", t: "Autorités de certification (CAA)", d: "Seules les autorités listées peuvent émettre un certificat.", c: caa } : { n: "mu", t: "Autorités de certification (CAA)", d: "Aucun CAA : facultatif, il limite qui peut émettre des certificats pour ce domaine.", c: [] });
    const www = v("www." + dom, "A").length || v("www." + dom, "CNAME").length;
    sortie.push(www ? { n: "ok", t: "Adresse « www »", d: "Le nom www répond.", c: [] } : { n: "mu", t: "Adresse « www »", d: "Pas de www : un visiteur qui l'écrit n'arrive nulle part.", c: [] });
    return sortie;
  }

  const SVG_GLOBE = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3 3.2 15 0 18M12 3c-3.2 3-3.2 15 0 18"/></svg>';

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.dns = async function (corps) {
    const anc = document.getElementById("dz-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "dz-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "dz"; corps.appendChild(racine);

    const S = { etat: null, domaines: [], jeton: false, seuil: 45, sel: null, onglet: "enreg", ref: {}, hist: {}, live: {}, confirme: null, occupe: false, ajout: false, erreur: "" };
    const zone = () => (S.etat.zones || []).find((z) => z.domaine === S.sel);

    async function charger() {
      try {
        S.etat = await agir("dns.etat");
        let rg = []; try { rg = ((await agir("reglages.lire")) || {}).reglages || []; } catch (e) {}
        const r = (k) => rg.find((x) => x.cle === k) || {};
        S.domaines = String(r("dns.domaines").valeur || "").split(",").map((x) => x.trim()).filter(Boolean);
        S.jeton = !!r("dns.jeton_cloudflare").pose; S.seuil = Number(r("dns.expire_jours").valeur) || 45;
        S.erreur = "";
        const zs = S.etat.zones || [];
        if (!zs.some((z) => z.domaine === S.sel)) S.sel = zs.length ? zs.slice().sort((a, b) => etatZone(a, S.seuil).ordre - etatZone(b, S.seuil).ordre)[0].domaine : null;
        if (S.sel) await chargerZone(S.sel);
      } catch (e) { S.erreur = e.message || String(e); }
      dessiner();
    }
    async function chargerZone(d) {
      try { S.ref[d] = await agir("dns.reference", { domaine: d }); } catch (e) { S.ref[d] = { erreur: e.message }; }
    }
    async function histoire(d) {
      if (S.hist[d]) return;
      try { S.hist[d] = (await agir("dns.reference", { domaine: d, historique: true })).versions || []; } catch (e) { S.hist[d] = []; }
    }
    const occupe = async (f, ok) => {
      if (S.occupe) return; S.occupe = true; dessiner();
      try { const r = await f(); if (ok) dire(ok); S.confirme = null; S.hist = {}; await charger(); return r; }
      catch (e) { dire(e.message || String(e), "err"); }
      finally { S.occupe = false; dessiner(); }
    };

    // ── dessin ────────────────────────────────────────────────────────────────
    function dessiner() {
      if (!S.etat) { racine.innerHTML = '<div class="attente">Lecture des zones…</div>'; return; }
      const zs = S.etat.zones || [];
      let h = '<div class="tete"><div><h1>Zones DNS</h1><p class="sous">Ce que Cassandra surveille de vos domaines : où ils pointent, si leur courrier est bien configuré, et quand ils expirent.</p></div>' +
        '<div class="acts"><button class="btn pri" data-a="suivre">＋ Suivre un domaine</button><button class="btn" data-a="reglages">Réglages</button></div></div>';
      if (S.erreur) h += '<div class="carte" style="padding:14px 18px;color:var(--danger)">' + esc(S.erreur) + "</div>";
      h += hero(zs);
      if (S.ajout || !zs.length) h += formulaire(!zs.length);
      if (zs.length) h += '<div class="corps"><div class="liste">' + zs.slice().sort((a, b) => etatZone(a, S.seuil).ordre - etatZone(b, S.seuil).ordre || a.domaine.localeCompare(b.domaine)).map(carteZone).join("") + "</div>" + detail() + "</div>";
      racine.innerHTML = h;
      lier();
    }

    function hero(zs) {
      const e = S.etat, ip = e.ip_publique, ref = e.ip_reference, change = ip && ref && ip !== ref;
      const nip = zs.reduce((n, z) => n + (z.derives || []).filter((d) => d.ip_derivee).length, 0);
      const sts = zs.map((z) => etatZone(z, S.seuil)), c = (k) => sts.filter((s) => s.cls === k).length;
      const ech = zs.map((z) => ({ d: z.domaine, j: jours(z.expiration) })).filter((x) => x.j != null).sort((a, b) => a.j - b.j)[0];
      return '<div class="carte hero">' +
        '<div><span class="lib">Adresse publique du serveur</span><span class="gros' + (change ? " al" : "") + '">' + esc(ip || "inconnue") + "</span>" +
        (change ? '<span class="note"><span class="pastille al">a changé</span> Elle était <span class="mono">' + esc(ref) + "</span>." + (nip ? " " + mot(nip, "enregistrement pointe", "enregistrements pointent") + " encore sur l’ancienne." : "") + "</span>"
          : '<span class="note">' + (ip ? '<span class="pastille ok">inchangée</span> Les enregistrements qui la portent n’ont pas à bouger.' : "Pas encore mesurée : deux services d’adresse sont interrogés à chaque relève.") + "</span>") + "</div>" +
        '<div><span class="lib">Zones suivies</span><span class="gros">' + zs.length + '</span><span class="puces">' +
        (zs.length ? (c("ok") ? '<span class="pastille ok">' + c("ok") + " conforme" + (c("ok") > 1 ? "s" : "") + "</span>" : "") + (c("al") ? '<span class="pastille al">' + c("al") + " à regarder</span>" : "") + (c("dg") ? '<span class="pastille dg">' + c("dg") + " à corriger</span>" : "") + (c("mu") ? '<span class="pastille mu">' + c("mu") + " sans relevé</span>" : "") : '<span class="note">Aucun domaine suivi pour l’instant.</span>') + "</span></div>" +
        '<div><span class="lib">Prochaine échéance</span>' + (ech ? '<span class="gros ' + (ech.j <= 14 ? "dg" : ech.j <= S.seuil ? "al" : "ok") + '">' + (ech.j < 0 ? "expiré" : "dans " + ech.j + " j") + '</span><span class="note mono">' + esc(ech.d) + "</span>"
          : '<span class="gros" style="color:var(--txt-faint)">—</span><span class="note">Aucune expiration lue (une lecture par jour et par domaine, auprès du registre).</span>') + "</div></div>";
    }

    function formulaire(vide) {
      return '<div class="carte ' + (vide ? "vide" : "pan") + '">' + (vide ? SVG_GLOBE + "<h2>Aucun domaine suivi</h2><p>Dites à Cassandra quels domaines surveiller. Elle relève leurs enregistrements toutes les heures, garde la première lecture comme référence, vous signale ce qui change et l’échéance du domaine. Les domaines de votre panneau d’hébergement, s’il y en a, sont suivis d’office.</p>" : '<span class="lib">Suivre un domaine</span>') +
        '<div class="ajout"><input type="text" id="dz-nv" placeholder="exemple.org" autocomplete="off" spellcheck="false" aria-label="Nom du domaine"><button class="btn pri" data-a="ajouter"' + (S.occupe ? " disabled" : "") + ">Suivre</button>" + (!vide ? '<button class="btn" data-a="annuler">Annuler</button>' : "") + "</div></div>";
    }

    function carteZone(z) {
      const s = etatZone(z, S.seuil), j = jours(z.expiration), pct = j == null ? 0 : Math.max(4, Math.min(100, Math.round(j / 365 * 100)));
      return '<button type="button" class="zone' + (z.domaine === S.sel ? " on" : "") + '" data-z="' + esc(z.domaine) + '"><div class="l1"><b>' + esc(z.domaine) + '</b><span class="pastille ' + s.cls + '">' + esc(s.txt) + "</span></div>" +
        '<span class="note">' + (z.releve ? "relevée " + age(z.releve) + " · " : "") + (z.version ? "référence v" + z.version : "pas de référence") + "</span>" +
        (j != null ? '<div class="barre" title="Expiration du domaine"><i class="' + (j <= 14 ? "dg" : j <= S.seuil ? "al" : "") + '" style="width:' + pct + '%"></i></div><span class="note">' + (j < 0 ? "domaine expiré" : "expire dans " + j + " j (" + esc(String(z.expiration).slice(0, 10)) + ")") + "</span>" : '<span class="note">expiration non lue</span>') + "</button>";
    }

    function detail() {
      const z = zone(); if (!z) return "";
      const rec = (S.live[z.domaine] && S.live[z.domaine].enregistrements) || ((S.ref[z.domaine] || {}).contenu) || {};
      const nd = (z.derives || []).length;
      const tabs = [["enreg", "Enregistrements"], ["derives", "Dérives", nd], ["courrier", "Courrier et sécurité"], ["hist", "Historique"]];
      let h = '<div class="carte detail"><div class="dt"><div><h2>' + esc(z.domaine) + '</h2><span class="note">' + (z.serveur ? "serveur de noms : <span class=\"mono\">" + esc(z.serveur) + "</span> · " : "") + (z.releve ? "relevée " + age(z.releve) : "jamais relevée") + '</span></div>' +
        '<div class="acts"><button class="btn" data-a="relever"' + (S.occupe ? " disabled" : "") + ">" + (S.occupe ? "Relevé en cours…" : "Relever maintenant") + "</button></div></div>" +
        '<div class="onglets" role="tablist">' + tabs.map((t) => '<button type="button" role="tab" data-o="' + t[0] + '" class="' + (S.onglet === t[0] ? "on" : "") + '">' + t[1] + (t[2] ? '<span class="n al">' + t[2] + "</span>" : "") + "</button>").join("") + "</div>";
      h += '<div class="pan">' + (S.onglet === "enreg" ? ongletEnreg(z, rec) : S.onglet === "derives" ? ongletDerives(z) : S.onglet === "courrier" ? ongletCourrier(z, rec) : ongletHist(z)) + "</div></div>";
      return h;
    }

    function ongletEnreg(z, rec) {
      const live = S.live[z.domaine], ref = (S.ref[z.domaine] || {}).contenu || null, keys = Object.keys(rec);
      let h = '<div class="barre-out"><span class="note">' + (live ? "Relevé en direct à " + new Date(live.t).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) + (ref ? " · comparé à la référence v" + z.version : "") : ref ? "Référence v" + z.version + " (la dernière lecture acceptée). Relevez pour voir l’état actuel." : "Pas de référence : relevez la zone pour la lire.") + "</span>" +
        (live && live.non_lus && live.non_lus.length ? '<span class="pastille al" title="' + esc(live.non_lus.join(", ")) + '">' + mot(live.non_lus.length, "nom illisible", "noms illisibles") + "</span>" : "") + "</div>";
      if (!keys.length && !(live && ref)) return h + '<div class="attente">Aucun enregistrement connu pour cette zone.<br><br><button class="btn pri" data-a="relever">Relever maintenant</button></div>';
      const toutes = Array.from(new Set(keys.concat(live && ref ? Object.keys(ref) : [])));
      const GROUPES = [["Adresses", (t) => t === "A" || t === "AAAA" || t === "CNAME"], ["Courrier", (t, n) => t === "MX" || (t === "TXT" && (/^_dmarc\./.test(n) || /_domainkey\./.test(n) || /v=spf1/i.test(((rec[n + "|TXT"] || [])[0]) || "")))], ["Autres", () => true]];
      const pris = new Set();
      GROUPES.forEach(([titre, ok]) => {
        const ks = toutes.filter((k) => { if (pris.has(k)) return false; const c = cle(k); return ok(c.type, c.nom); }).sort((a, b) => { const x = cle(a), y = cle(b); return (ORDRE[x.type] || 9) - (ORDRE[y.type] || 9) || x.nom.length - y.nom.length || x.nom.localeCompare(y.nom); });
        if (!ks.length) return; ks.forEach((k) => pris.add(k));
        h += '<div class="grp"><h3>' + titre + "</h3>" + ks.map((k) => {
          const c = cle(k), obs = (live ? live.enregistrements[k] : rec[k]) || [], att = ref ? ref[k] || [] : null; let ch = "";
          if (live && ref) ch = !att.length ? '<span class="pastille al">nouveau</span>' : !obs.length ? '<span class="pastille dg">disparu</span>' : JSON.stringify(att) !== JSON.stringify(obs) ? '<span class="pastille al">changé</span>' : '<span class="pastille ok">identique</span>';
          return '<div class="rang"><span class="nom">' + esc(c.nom === z.domaine ? "@ " + c.nom : c.nom) + '</span><span class="typ">' + esc(c.type) + '</span><span class="val">' + (obs.length ? obs.map((x) => "<span>" + esc(x) + "</span>").join("") : "<span>—</span>") + (live && ref && att.length && JSON.stringify(att) !== JSON.stringify(obs) ? att.map((x) => "<s>" + esc(x) + "</s>").join("") : "") + "</span><span>" + ch + "</span></div>";
        }).join("") + "</div>";
      });
      return h;
    }

    function ongletDerives(z) {
      const dv = z.derives || [];
      if (!dv.length) return '<div class="attente"><span class="pastille ok">rien à signaler</span><br><br>La dernière relève ne montre aucun écart avec la référence' + (z.version ? " v" + z.version : "") + ".</div>";
      let h = '<p class="note">Une dérive est un enregistrement qui ne correspond plus à la référence. Si le changement est voulu, acceptez-le : il devient la nouvelle référence (les anciennes versions restent). Sinon, il est à rétablir chez votre fournisseur de DNS.</p>';
      dv.forEach((d, i) => {
        const aCorriger = d.ip_derivee && d.type === "A", id = z.domaine + "|" + i;
        h += '<div class="drv"><div class="barre-out"><b class="mono">' + esc(d.nom) + ' <span class="pastille ' + (d.ip_derivee ? "dg" : "al") + '">' + esc(d.type) + (d.ip_derivee ? " · ancienne adresse" : "") + '</span></b></div><div class="diff"><em>référence</em><span>' + esc((d.attendu || []).join(", ") || "absent") + "</span><em>observé</em><span>" + esc((d.observe || []).join(", ") || "absent") + "</span></div>";
        if (aCorriger) h += S.jeton ? (S.confirme === "c" + id ? '<div class="confirme">Écrire <b class="mono">' + esc(S.etat.ip_publique) + '</b> chez Cloudflare ? <button class="btn pri mini" data-a="corriger" data-i="' + i + '">Oui, corriger</button><button class="btn mini" data-a="non">Non</button></div>' : '<div class="acts"><button class="btn pri mini" data-a="demander-c" data-id="c' + id + '">Corriger vers ' + esc(S.etat.ip_publique || "l’adresse actuelle") + "</button></div>") : '<p class="note">Pas de jeton Cloudflare : à corriger chez votre fournisseur, ou ajoutez le jeton dans les réglages du module pour que Cassandra le fasse.</p>';
        h += "</div>";
      });
      h += S.confirme === "a" ? '<div class="confirme">Prendre l’état actuel comme nouvelle référence ? <button class="btn pri mini" data-a="accepter">Oui, accepter</button><button class="btn mini" data-a="non">Non</button></div>' : '<div class="acts"><button class="btn" data-a="demander-a">Accepter l’état actuel comme référence</button></div>';
      return h;
    }

    function ongletCourrier(z, rec) {
      if (!Object.keys(rec).length) return '<div class="attente">Rien à vérifier tant que la zone n’a pas été lue.<br><br><button class="btn pri" data-a="relever">Relever maintenant</button></div>';
      const v = verifs(z.domaine, rec), bons = v.filter((x) => x.n === "ok").length;
      return '<div class="barre-out"><span class="note"><b>' + bons + " sur " + v.length + "</b> bonnes pratiques en place" + (S.live[z.domaine] ? " (relevé en direct)" : " (d’après la référence)") + "</span></div>" +
        v.map((x) => '<div class="verif"><span class="pic ' + x.n + '" aria-hidden="true">' + (x.n === "ok" ? "✓" : x.n === "dg" ? "!" : x.n === "al" ? "!" : "–") + '</span><div class="l"><b>' + esc(x.t) + '</b><div class="d">' + esc(x.d) + "</div>" + ((x.c || []).length ? '<div class="d">' + x.c.map((c) => "<code>" + esc(c) + "</code>").join("<br>") + "</div>" : "") + "</div></div>").join("");
    }

    function ongletHist(z) {
      const l = S.hist[z.domaine];
      if (!l) { histoire(z.domaine).then(dessiner); return '<div class="attente">Lecture de l’historique…</div>'; }
      if (!l.length) return '<div class="attente">Aucune version de référence : la première relève en posera une.</div>';
      return '<p class="note">Chaque référence acceptée est une version ; rien n’est jamais écrasé.</p><div class="hist">' + l.map((v, i) => '<div class="v"><span><b class="mono">v' + v.id + "</b> · " + esc(date(v.ts)) + '</span><span class="note">' + esc(v.auteur || "") + "</span>" + (v.annulee ? '<span class="pastille mu">annulée</span>' : i === 0 || !l.slice(0, i).some((x) => !x.annulee) ? '<span class="pastille ok">courante</span>' : "") + "</div>").join("") + "</div>";
    }

    // ── les gestes ────────────────────────────────────────────────────────────
    function lier() {
      racine.querySelectorAll("[data-z]").forEach((b) => b.addEventListener("click", async () => { S.sel = b.dataset.z; S.confirme = null; if (!S.ref[S.sel]) await chargerZone(S.sel); dessiner(); }));
      racine.querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", () => { S.onglet = b.dataset.o; S.confirme = null; dessiner(); }));
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => geste(b)));
      const nv = racine.querySelector("#dz-nv"); if (nv) { nv.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); geste({ dataset: { a: "ajouter" } }); } }); if (S.ajout) nv.focus(); }
    }
    async function geste(b) {
      const a = b.dataset.a, z = S.sel;
      if (a === "suivre") { S.ajout = true; dessiner(); return; }
      if (a === "annuler") { S.ajout = false; dessiner(); return; }
      if (a === "reglages") { if (CASS.ouvrirConsole) CASS.ouvrirConsole("dns", "Zones DNS"); return; }
      if (a === "non") { S.confirme = null; dessiner(); return; }
      if (a === "demander-a") { S.confirme = "a"; dessiner(); return; }
      if (a === "demander-c") { S.confirme = b.dataset.id; dessiner(); return; }
      if (a === "ajouter") {
        const v = String((racine.querySelector("#dz-nv") || {}).value || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
        if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(v)) { dire("Un nom de domaine, comme exemple.org", "err"); return; }
        if (S.domaines.indexOf(v) >= 0) { dire("Ce domaine est déjà suivi.", "err"); return; }
        S.ajout = false; S.sel = v;
        return occupe(() => agir("reglages.regler", { cle: "dns.domaines", valeur: S.domaines.concat(v).join(",") }), "Domaine suivi : " + v + ". Relevez-le pour poser sa référence.");
      }
      if (a === "relever") {
        if (!z) return; S.occupe = true; dessiner();
        try { const r = await agir("dns.relever_zone", { domaine: z }); S.live[z] = Object.assign({ t: Date.now() }, r); dire("Zone relevée : " + z); }
        catch (e) { dire(e.message || String(e), "err"); }
        S.occupe = false; dessiner(); return;
      }
      if (a === "accepter") return occupe(() => agir("dns.accepter_reference", { domaine: z }), "État accepté comme nouvelle référence.").then(() => { delete S.live[z]; });
      if (a === "corriger") {
        const d = (zone().derives || [])[+b.dataset.i]; if (!d) return;
        return occupe(() => agir("dns.corriger_enregistrement", { nom: d.nom, type: "A", valeur: S.etat.ip_publique }), "Enregistrement corrigé : " + d.nom);
      }
    }

    racine.innerHTML = '<div class="attente">Lecture des zones…</div>';
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l'écran et ses gestes.
// EC : néant.
// LIEN : modules/dns (le module et ses capacités), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
