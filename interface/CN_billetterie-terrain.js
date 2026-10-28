// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : stockage plein ou interdit : on continue sans
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #6b90ee
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : stockage plein ou interdit : on continue sans
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=6b90ee ▼▼▼
// Billetterie : les écrans du terrain, pensés pour le téléphone (la caisse, le contrôle à l'entrée) et « Mon espace » du revendeur et de l'artiste.
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = (c, a) => K.agir("billetterie." + c, a), confirmer = K.confirmer, dire = K.dire;
  const B = CASS.billetterie, H = B.aides, P = B.pages;
  const { eur, cts, jour, jourCourt, quand, puce, MOYENS } = H;

  const CSS = ".bl .gros{font-size:17px;padding:14px 16px}.bl .ligne-billet{display:flex;gap:12px;align-items:center;padding:12px 14px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}.bl .ligne-billet .sp{flex:1;min-width:0}.bl .ligne-billet b{display:block}" +
    ".bl .qte{display:flex;align-items:center;gap:6px}.bl .qte button{width:44px;height:44px;border-radius:12px;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));font-size:22px;font-weight:700}.bl .qte output{min-width:34px;text-align:center;font:700 20px ui-monospace,Menlo,monospace}" +
    ".bl .barre-total{position:sticky;bottom:0;z-index:5;display:grid;gap:8px;background:var(--bg,var(--surface-solid));border:1px solid var(--line-strong,var(--line));border-radius:16px;padding:12px;box-shadow:0 -10px 30px -18px rgba(0,0,0,.4)}.bl .total{font:700 26px ui-monospace,Menlo,monospace}" +
    ".bl .seg{display:flex;border:1px solid var(--line-strong,var(--line));border-radius:12px;overflow:hidden}.bl .seg button{flex:1;border:0;background:transparent;padding:11px 6px;font-weight:600;font-size:13px;color:var(--txt-soft)}.bl .seg button.on{background:var(--accent);color:var(--on-accent,#fff)}" +
    ".bl .chips{display:flex;gap:6px;flex-wrap:nowrap;overflow-x:auto;padding-bottom:2px}.bl .chips button{white-space:nowrap;flex:none}.bl .chips button{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:99px;padding:7px 13px;font-weight:600}.bl .rendu{font:700 22px ui-monospace,Menlo,monospace;color:var(--ok)}" +
    ".bl .billet-qr{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:center;padding:12px;border:1px dashed var(--line-strong,var(--line));border-radius:14px;background:#fff;color:#111}.bl .billet-qr svg{width:150px;height:150px}.bl .billet-qr .num{font:700 20px ui-monospace,Menlo,monospace}.bl .billet-qr .code{font:13px ui-monospace,Menlo,monospace;color:#444}" +
    ".bl .verdict{border-radius:18px;padding:22px 16px;text-align:center;border:2px solid var(--line);background:var(--surface)}.bl .verdict h2{font-size:28px;margin:0 0 6px}.bl .verdict.ok{background:color-mix(in srgb,var(--ok) 18%,transparent);border-color:var(--ok)}.bl .verdict.ko{background:color-mix(in srgb,var(--danger) 16%,transparent);border-color:var(--danger)}.bl .verdict.warn{background:color-mix(in srgb,var(--warn) 18%,transparent);border-color:var(--warn)}" +
    ".bl .saisie-gros{display:flex;gap:8px}.bl .saisie-gros input{font-size:18px;padding:13px 14px}.bl video.scan{width:100%;max-height:300px;border-radius:14px;background:#000;object-fit:cover}" +
    "@media(max-width:640px){.bl .billet-qr{grid-template-columns:1fr;justify-items:center;text-align:center}}";
  (function () { if (!document.getElementById("blt-css")) { const st = document.createElement("style"); st.id = "blt-css"; st.textContent = CSS; document.head.appendChild(st); } })();

  // ── la mémoire de l'appareil : ce qui doit survivre à une coupure de réseau ──
  const mem = {
    lire(cle, defaut) { try { const v = localStorage.getItem("bl." + cle); return v == null ? defaut : JSON.parse(v); } catch (e) { return defaut; } },
    ecrire(cle, v) { try { localStorage.setItem("bl." + cle, JSON.stringify(v)); } catch (e) { /* stockage plein ou interdit : on continue sans */ } },
  };
  const hors = (e) => !navigator.onLine || /fetch|network|réseau|timeout|failed to/i.test(String((e && e.message) || e));
  const tableau = (cols, lignes, vide) => '<div class="tw"><table><thead><tr>' + cols.map((c) => '<th class="' + (c[2] || "") + '">' + esc(c[1]) + "</th>").join("") + "</tr></thead><tbody>" + (lignes.length ? lignes.join("") : '<tr><td colspan="' + cols.length + '" class="vide">' + esc(vide || "Rien pour l’instant.") + "</td></tr>") + "</tbody></table></div>";
  const billetQr = (b) => '<div class="billet-qr"><div>' + CASS.qr.svg(b.qr, { taille: 150 }) + '</div><div><span class="num">' + esc(b.numero) + '</span><div class="code">Code de contrôle : ' + esc(b.code_controle) + "</div>" + (b.nom ? "<div>" + esc(b.nom) + "</div>" : "") + "</div></div>";
  B.billetQr = billetQr;

  // ═══ CAISSE ═══
  P.caisse = async (S) => {
    const R = S.racine;
    S.rechargeable = true;
    const lc = await S.lire("caisses", { etat: "ouverte" }), ouvertes = (lc && lc.caisses) || [];
    let id = mem.lire("caisse", 0);
    let cais = ouvertes.find((c) => c.id === id) || ouvertes[0];
    if (!cais) {
      const ev = await S.lire("evenements"), vend = ((ev && ev.evenements) || []).filter((e) => e.statut === "en vente" || e.statut === "complet");
      R.innerHTML = S.entetes("Caisse", "Ouvre une caisse pour vendre sur place, avec ou sans réseau.") + '<div class="carte"><div class="champs"><label>Événement<select id="co-evt">' + vend.map((e) => '<option value="' + e.id + '">' + esc(e.nom) + " · " + esc(jourCourt(e.date_iso)) + "</option>").join("") + '</select></label><label>Caissier<input type="text" id="co-qui" placeholder="Ton prénom"></label><label>Fond de caisse (€)<input type="text" inputmode="decimal" id="co-fond" value="0,00"></label><label>Appareil<input type="text" id="co-app" value="K1"></label></div><div class="row" style="margin-top:12px"><button class="btn pri gros" data-a="ouvrir"' + (vend.length ? "" : " disabled") + ">Ouvrir la caisse</button>" + (vend.length ? "" : '<span class="hint">Aucun événement n’est en vente.</span>') + "</div></div>";
      S.clic = async (k) => { if (k === "ouvrir") { const g = (i) => R.querySelector(i).value; const r = await S.geste("caisse_ouvrir", { evenement_id: Number(g("#co-evt")), caissier: g("#co-qui"), fond: cts(g("#co-fond")), appareil: g("#co-app") }, "Caisse ouverte."); if (r) { mem.ecrire("caisse", r.id); S.rendre(); } } };
      S.saisie = null; S.change = null;
      return;
    }
    mem.ecrire("caisse", cais.id);
    const [fiche, etat] = await Promise.all([S.lire("evenement_fiche", { id: cais.evenement_id }), S.lire("caisse_etat", { caisse_id: cais.id })]);
    const types = (fiche && fiche.types) || [];
    const cle = "reserve." + cais.id, file = "file." + cais.id;
    let reserve = mem.lire(cle, []), pending = mem.lire(file, []);
    const panier = {}; let moyen = "especes", recu = 0, recuBillets = null, promo = "";
    const total = () => types.reduce((n, t) => n + (panier[t.id] || 0) * t.prix, 0);
    const nb = () => types.reduce((n, t) => n + (panier[t.id] || 0), 0);
    const tot = (etat && etat.totaux) || {};
    const dessiner = () => {
      const t = total(), rendu = moyen === "especes" && recu ? Math.max(0, recu - t) : 0;
      R.innerHTML = S.entetes("Caisse · " + (fiche ? fiche.evenement.nom : ""), "Caisse " + cais.ref + " · fond " + eur(cais.fond), '<span>' + (navigator.onLine ? puce("en ligne", "ok") : puce("hors ligne", "al")) + (pending.length ? " " + puce(pending.length + " vente(s) à envoyer", "al") : "") + '</span><button class="btn" data-a="sync"' + (pending.length ? "" : " disabled") + ">Envoyer</button>") +
        '<div class="tuiles"><div class="tuile"><b>' + eur(tot.total) + "</b><span>encaissé</span></div><div class=\"tuile\"><b>" + (tot.billets || 0) + "</b><span>billets</span></div><div class=\"tuile\"><b>" + eur(tot.attendu_especes) + "</b><span>espèces attendues</span></div><div class=\"tuile" + (reserve.length < 5 ? " al" : "") + '"><b>' + reserve.length + "</b><span>numéros en réserve</span></div></div>" +
        (recuBillets ? '<div class="carte"><h2>Vente enregistrée</h2><p class="sub">' + recuBillets.texte + '</p><div style="display:grid;gap:10px">' + recuBillets.billets.map(billetQr).join("") + '</div><div class="row" style="margin-top:10px"><button class="btn pri gros" data-a="suivant">Vente suivante</button></div></div>' :
          types.map((x) => '<div class="ligne-billet"><div class="sp"><b>' + esc(x.nom) + '</b><span class="hint">' + esc(eur(x.prix)) + (x.entrees > 1 ? " · " + x.entrees + " entrées" : "") + '</span></div><div class="qte"><button data-a="moins" data-t="' + x.id + '" aria-label="Retirer un ' + esc(x.nom) + '">−</button><output>' + (panier[x.id] || 0) + '</output><button data-a="plus" data-t="' + x.id + '" aria-label="Ajouter un ' + esc(x.nom) + '">+</button></div></div>').join("") +
          '<div class="barre-total"><div class="row"><span class="total">' + eur(t) + '</span><span class="sp hint">' + nb() + " billet(s)</span><input type=\"text\" id=\"ca-promo\" placeholder=\"Code promo\" value=\"" + esc(promo) + "\" style=\"max-width:130px\"></div>" +
          '<div class="seg" role="group" aria-label="Paiement">' + [["especes", "Espèces"], ["carte_terminal", "Terminal"], ["carte_declaree", "Carte"], ["offert", "Offert"]].map((m) => '<button data-a="moyen" data-m="' + m[0] + '" class="' + (m[0] === moyen ? "on" : "") + '">' + m[1] + "</button>").join("") + "</div>" +
          (moyen === "especes" ? '<div class="chips"><button data-a="recu" data-v="' + t + '">Appoint</button>' + [500, 1000, 2000, 5000, 10000].map((v) => '<button data-a="recu" data-v="' + v + '">' + v / 100 + " €</button>").join("") + '</div><div class="row"><label class="hint">Reçu <input type="text" inputmode="decimal" id="ca-recu" value="' + (recu ? (recu / 100).toFixed(2).replace(".", ",") : "") + '" style="width:110px"></label><span class="sp"></span><span>Rendu <span class="rendu">' + eur(rendu) + "</span></span></div>" : "") +
          '<button class="btn pri gros" data-a="encaisser"' + (nb() ? "" : " disabled") + ">Encaisser " + eur(t) + "</button></div>") +
        '<div class="row"><span class="sp"></span><button class="btn dng" data-a="cloturer">Clôturer la caisse…</button></div>' +
        (etat && etat.ventes.length && !recuBillets ? "<h3>Dernières ventes</h3>" + tableau([["r", "Vente"], ["m", "Moyen"], ["t", "Total", "n"]], etat.ventes.slice(0, 8).map((v) => "<tr><td><b>" + esc(v.ref) + "</b>" + (v.hors_ligne ? ' <span class="hint">hors ligne</span>' : "") + "</td><td>" + esc(MOYENS[v.moyen] || v.moyen) + '</td><td class="n">' + eur(v.total) + "</td></tr>")) : "");
    };
    async function assurerReserve(besoin) {
      if (reserve.length >= besoin) return true;
      if (!navigator.onLine) return false;
      try { const r = await agir("caisse_reserver", { caisse_id: cais.id }); reserve = reserve.concat(r.numeros); mem.ecrire(cle, reserve); return reserve.length >= besoin; } catch (e) { return false; }
    }
    async function envoyer(args) { return await agir("caisse_vendre", args); }
    async function synchroniser() {
      const restant = [];
      for (const v of pending) { try { await envoyer(Object.assign({}, v, { hors_ligne: true })); } catch (e) { if (hors(e)) restant.push(v); else dire("Vente " + (v.numeros || []).join(", ") + " refusée : " + (e.message || e), "err"); } }
      const ok = restant.length === 0; pending = restant; mem.ecrire(file, pending);
      if (ok) dire("Ventes envoyées.", "ok");
      return ok;
    }
    S.saisie = (ev) => { if (ev.target.id === "ca-recu") { recu = cts(ev.target.value); const r = R.querySelector(".rendu"); if (r) r.textContent = eur(Math.max(0, recu - total())); } if (ev.target.id === "ca-promo") promo = ev.target.value.trim(); };
    S.change = null;
    S.clic = async (k, a) => {
      if (k === "plus") { panier[a.dataset.t] = (panier[a.dataset.t] || 0) + 1; recu = 0; dessiner(); }
      else if (k === "moins") { panier[a.dataset.t] = Math.max(0, (panier[a.dataset.t] || 0) - 1); recu = 0; dessiner(); }
      else if (k === "moyen") { moyen = a.dataset.m; dessiner(); }
      else if (k === "recu") { recu = Number(a.dataset.v); dessiner(); }
      else if (k === "suivant") { recuBillets = null; Object.keys(panier).forEach((x) => delete panier[x]); recu = 0; promo = ""; dessiner(); }
      else if (k === "sync") { if (await synchroniser()) S.rendre(); else dessiner(); }
      else if (k === "encaisser") {
        const lignes = types.filter((x) => panier[x.id]).map((x) => ({ type_billet_id: x.id, quantite: panier[x.id] })), places = nb();
        if (moyen === "especes" && recu && recu < total()) { dire("Le montant reçu est insuffisant.", "err"); return; }
        if (!(await assurerReserve(places))) { dire("Plus de numéros en réserve et pas de réseau : reconnecte-toi pour en réserver.", "err"); return; }
        const pris = reserve.slice(0, places), args = { caisse_id: cais.id, lignes: lignes, moyen: moyen, recu: moyen === "especes" ? recu : 0, numeros: pris.map((n) => n.numero) };
        if (promo) args.code_promo = promo;
        let enAttente = false;
        try { await envoyer(args); } catch (e) {
          if (!hors(e)) { dire(e.message || String(e), "err"); return; }
          args.hors_ligne = true; args.heure_appareil = new Date().toISOString(); pending.push(args); mem.ecrire(file, pending); enAttente = true;
        }
        reserve = reserve.slice(places); mem.ecrire(cle, reserve);
        const rendu = moyen === "especes" && recu ? Math.max(0, recu - total()) : 0;
        recuBillets = { texte: (enAttente ? "Vendu <b>hors ligne</b> : la vente sera envoyée au retour du réseau. " : "") + esc(eur(total())) + " · " + esc(MOYENS[moyen]) + (rendu ? " · <b>rendre " + esc(eur(rendu)) + "</b>" : ""), billets: pris };
        if (!enAttente) { const e2 = await S.lire("caisse_etat", { caisse_id: cais.id }); if (e2) Object.assign(etat, e2); Object.assign(tot, (e2 && e2.totaux) || {}); }
        dessiner();
      } else if (k === "cloturer") {
        if (pending.length && !(await synchroniser())) { dire("Des ventes n’ont pas pu être envoyées : reconnecte-toi avant de clôturer.", "err"); return; }
        const v = await B.formulaire("Clôturer la caisse", [{ n: "n", t: "note", l: "<p>Compte les espèces du tiroir (fond compris). Les numéros non vendus de ta réserve sont retirés.</p>" }, { n: "compte_especes", l: "Espèces comptées (€)", t: "eur" }], {}, "Clôturer", true);
        if (!v) return;
        const r = await S.geste("caisse_cloturer", { caisse_id: cais.id, compte_especes: v.compte_especes }, "Caisse clôturée.");
        if (r) { mem.ecrire("caisse", 0); mem.ecrire(cle, []); await confirmer("Clôture " + r.z, "<p>Attendu en espèces : <b>" + esc(eur(r.attendu)) + "</b> · compté : <b>" + esc(eur(r.compte)) + "</b></p><p>" + (r.ecart === 0 ? "Aucun écart." : "Écart : <b>" + esc(eur(r.ecart)) + "</b> (consigné).") + "</p>", "Fermer"); S.rendre(); }
      }
    };
    if (navigator.onLine && pending.length) await synchroniser();
    if (reserve.length < 10) await assurerReserve(10);
    dessiner();
  };

  // ═══ CONTRÔLE ═══
  P.controle = async (S) => {
    const R = S.racine;
    S.rechargeable = true;
    const ev = await S.lire("evenements"), evts = ((ev && ev.evenements) || []).filter((e) => e.statut !== "brouillon" && e.statut !== "annulé");
    let eid = mem.lire("controle.evt", 0);
    if (!evts.some((e) => e.id === eid)) eid = (evts.find((e) => e.statut === "en vente" || e.statut === "complet") || evts[0] || {}).id || 0;
    if (!eid) { R.innerHTML = S.entetes("Contrôle", "Lire les billets à l’entrée.") + '<div class="carte vide">Aucun événement à contrôler.</div>'; return; }
    mem.ecrire("controle.evt", eid);
    const evt = evts.find((e) => e.id === eid);
    const [etat, cfl] = await Promise.all([S.lire("controle_etat", { evenement_id: eid }), S.lire("conflits", { evenement_id: eid, etat: "a_arbitrer" })]);
    let liste = mem.lire("liste." + eid, null), file = mem.lire("entrees." + eid, []), porte = mem.lire("porte", "Entrée principale"), verdict = null, trouves = null, camera = null, local = mem.lire("local." + eid, {});
    const dessiner = () => {
      const e = etat || {}, enLigne = navigator.onLine;
      R.innerHTML = S.entetes("Contrôle · " + evt.nom, jour(evt.date_iso), '<span>' + (enLigne ? puce("en ligne", "ok") : puce("hors ligne", "al")) + (file.length ? " " + puce(file.length + " entrée(s) à envoyer", "al") : "") + '</span><select id="ct-evt" aria-label="Événement" style="max-width:220px">' + evts.map((x) => '<option value="' + x.id + '"' + (x.id === eid ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + "</select>") +
        '<div class="tuiles"><div class="tuile"><b>' + (e.entrees || 0) + "</b><span>entrés</span></div><div class=\"tuile\"><b>" + (e.restants == null ? "—" : e.restants) + "</b><span>attendus encore</span></div><div class=\"tuile\"><b>" + (e.invites_entres || 0) + "</b><span>invités entrés</span></div><div class=\"tuile" + ((e.refuses || 0) ? " al" : "") + '"><b>' + (e.refuses || 0) + "</b><span>refusés</span></div></div>" +
        (verdict ? '<div class="verdict ' + esc(verdict.niveau) + '"><h2>' + esc(verdict.titre) + "</h2><div>" + esc(verdict.detail || "") + "</div></div>" : "") +
        '<div class="carte"><div class="saisie-gros"><input type="text" id="ct-q" placeholder="Scanner ou saisir le code du billet" autocomplete="off" autocapitalize="characters" inputmode="text"><button class="btn pri" data-a="valider">Valider</button></div>' +
        '<div class="row" style="margin-top:8px"><button class="btn" data-a="camera">' + (camera ? "Arrêter la caméra" : "📷 Scanner avec la caméra") + '</button><label class="hint">Porte <input type="text" id="ct-porte" value="' + esc(porte) + '" style="width:170px"></label><span class="sp"></span><button class="btn" data-a="telecharger">' + (liste ? "Mettre à jour la liste hors ligne" : "Télécharger pour le hors ligne") + "</button></div>" +
        (liste ? '<p class="hint" style="margin:6px 0 0">Liste hors ligne : ' + liste.billets.length + " billets · règle « " + esc(liste.regle) + " »" + (liste.regle === "secours" ? " (aucun contrôle sans réseau : liste papier)" : "") + "</p>" : "") +
        (camera ? '<video class="scan" id="ct-video" playsinline muted style="margin-top:10px"></video>' : "") + "</div>" +
        '<div class="carte"><h3>Chercher par nom</h3><div class="saisie-gros"><input type="search" id="ct-nom" placeholder="Nom ou numéro (2 lettres minimum)"></div><div id="ct-trouves" style="margin-top:8px">' + (trouves ? tableau([["n", "Billet"], ["e", "État"], ["", ""]], trouves.map((b) => "<tr><td><b>" + esc(b.numero) + "</b><div class=\"hint\">" + esc(b.nom || "") + "</div></td><td>" + (b.etat !== "valide" ? puce("annulé", "dg") : puce(b.entrees_faites + "/" + b.entrees + " entrée(s)", b.entrees_faites >= b.entrees ? "al" : "ok")) + '</td><td class="n">' + (b.etat === "valide" ? '<button class="btn sm pri" data-a="manuel" data-n="' + esc(b.numero) + '">Valider à la main</button>' : "") + "</td></tr>"), "Personne ne correspond.") : "") + "</div></div>" +
        ((cfl && cfl.conflits.length) ? '<div class="carte"><h3>Entrées en double à arbitrer</h3>' + tableau([["b", "Billet"], ["p", "Passages"], ["", ""]], cfl.conflits.map((c) => "<tr><td><b>" + esc(c.numero) + "</b></td><td>" + esc(c.porte1) + " · " + esc(c.heure1) + "<br>" + esc(c.porte2) + " · " + esc(c.heure2) + '</td><td class="n" style="white-space:nowrap"><button class="btn sm" data-a="arbitrer" data-id="' + c.id + '" data-d="accepter">Accepter</button> <button class="btn sm dng" data-a="arbitrer" data-id="' + c.id + '" data-d="bloquer">Bloquer</button></td></tr>')) + "</div>" : "") +
        ((e.derniers || []).length ? "<h3>Derniers passages</h3>" + tableau([["h", "Quand"], ["b", "Billet"], ["r", "Résultat"]], e.derniers.map((d) => "<tr><td>" + esc(quand(d.le)) + "</td><td>" + esc(d.numero || "") + "</td><td>" + puce(d.titre || d.niveau, d.niveau === "ok" ? "ok" : d.niveau === "warn" ? "al" : "dg") + "</td></tr>")) : "");
    };
    const lire = (texte) => { const m = String(texte).trim().toUpperCase().match(/^CASS1\.([A-Z]+-\d+)\.([A-HJ-NP-Z2-9]{6})$/) || String(texte).trim().toUpperCase().match(/^([A-Z]+-\d+)-([A-HJ-NP-Z2-9]{6})$/); return m ? { numero: m[1], sig: m[2] } : null; };
    function controleLocal(texte) {
      const l = lire(texte);
      if (!l) return { niveau: "ko", titre: "Code illisible", detail: "Ce n’est pas un billet de cette billetterie." };
      const b = liste.billets.find((x) => x.numero === l.numero);
      if (!b || String(b.signature).toUpperCase() !== l.sig) return { niveau: "ko", titre: "Billet inconnu ou faux", detail: "Pas dans la liste téléchargée." };
      if (liste.regle === "secours") return { niveau: "warn", titre: "Contrôle hors ligne interdit", detail: "Règle « secours » : utilise la liste papier." };
      if (liste.regle === "portes" && b.porte && b.porte !== porte) return { niveau: "ko", titre: "Mauvaise porte", detail: "Ce billet entre par : " + b.porte };
      const fait = (local[b.numero] || 0) + b.entrees_faites;
      if (fait >= b.entrees) return { niveau: "ko", titre: "Déjà utilisé", detail: b.nom || b.numero };
      local[b.numero] = (local[b.numero] || 0) + 1; mem.ecrire("local." + eid, local);
      file.push({ numero: b.numero, porte: porte, heure_appareil: new Date().toISOString() }); mem.ecrire("entrees." + eid, file);
      return { niveau: "ok", titre: "Entrée validée (hors ligne)", detail: (b.nom || "—") + " · " + b.type + (b.entrees > 1 ? " · entrée " + (fait + 1) + " sur " + b.entrees : "") };
    }
    async function synchroniser() {
      if (!file.length) return true;
      try { const r = await agir("controle_synchroniser", { evenement_id: eid, entrees: file }); dire(r.appliquees + " entrée(s) envoyée(s)" + (r.conflits ? ", " + r.conflits + " en double à arbitrer" : "") + ".", r.conflits ? "err" : "ok"); file = []; local = {}; mem.ecrire("entrees." + eid, file); mem.ecrire("local." + eid, local); return true; } catch (e) { if (!hors(e)) dire(e.message || String(e), "err"); return false; }
    }
    async function valider(texte, manuel) {
      if (!String(texte).trim()) return;
      porte = (R.querySelector("#ct-porte") || {}).value || porte; mem.ecrire("porte", porte);
      if (navigator.onLine) {
        try { if (file.length) await synchroniser(); verdict = await agir("controler", { evenement_id: eid, texte: texte, porte: porte, manuel: !!manuel }); }
        catch (e) { if (hors(e) && liste) verdict = controleLocal(texte); else verdict = { niveau: "ko", titre: "Erreur", detail: e.message || String(e) }; }
      } else if (liste) verdict = controleLocal(texte);
      else verdict = { niveau: "warn", titre: "Pas de réseau", detail: "Télécharge la liste hors ligne avant l’ouverture des portes." };
      if (navigator.onLine) { const e2 = await S.lire("controle_etat", { evenement_id: eid }); if (e2) Object.assign(etat, e2); }
      dessiner();
      const q = R.querySelector("#ct-q"); if (q) q.focus();
      try { if (navigator.vibrate) navigator.vibrate(verdict.niveau === "ok" ? 60 : [120, 60, 120]); } catch (e) { /* pas de vibreur */ }
    }
    async function demarrerCamera() {
      if (!("BarcodeDetector" in window) || !navigator.mediaDevices) { dire("La caméra ne lit pas les QR codes sur cet appareil : saisis le code ou utilise une douchette.", "err"); return; }
      camera = { flux: await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }), fin: false }; dessiner();
      const v = R.querySelector("#ct-video"); v.srcObject = camera.flux; await v.play();
      const det = new window.BarcodeDetector({ formats: ["qr_code"] }); let dernier = "", quand0 = 0;
      const boucle = async () => { if (!camera || camera.fin) return; try { const r = await det.detect(v); if (r.length && (r[0].rawValue !== dernier || Date.now() - quand0 > 3000)) { dernier = r[0].rawValue; quand0 = Date.now(); await valider(dernier, false); const nv = R.querySelector("#ct-video"); if (nv && camera && !nv.srcObject) { nv.srcObject = camera.flux; nv.play(); } } } catch (e) { /* image sans code */ } setTimeout(boucle, 350); };
      boucle();
    }
    const arreterCamera = () => { if (camera) { camera.fin = true; camera.flux.getTracks().forEach((t) => t.stop()); camera = null; } };
    S.saisie = (ev) => {
      if (ev.target.id === "ct-nom") { clearTimeout(S.t); const q = ev.target.value; S.t = setTimeout(async () => { if (q.trim().length < 2) { trouves = null; } else { const r = await S.lire("controle_chercher", { evenement_id: eid, q: q }); trouves = (r && r.billets) || []; } const p = q.length; dessiner(); const n = R.querySelector("#ct-nom"); if (n) { n.value = q; n.focus(); n.setSelectionRange(p, p); } }, 350); }
    };
    R.onkeydown = (ev) => { if (ev.key === "Enter" && ev.target.id === "ct-q") { const v = ev.target.value; ev.target.value = ""; valider(v, false); } };       // une seule écoute, même si l'écran est redessiné
    S.change = (ev) => { if (ev.target.id === "ct-evt") { arreterCamera(); mem.ecrire("controle.evt", Number(ev.target.value)); S.rendre(); } };
    S.clic = async (k, a) => {
      if (k === "valider") { const q = R.querySelector("#ct-q"), v = q.value; q.value = ""; valider(v, false); }
      else if (k === "manuel") { if (await confirmer("Valider à la main ?", "<p>Le billet " + esc(a.dataset.n) + " est validé sans lecture du QR code. C’est consigné.</p>", "Valider")) valider(a.dataset.n, true); }
      else if (k === "camera") { if (camera) { arreterCamera(); dessiner(); } else { try { await demarrerCamera(); } catch (e) { camera = null; dire("Caméra refusée ou absente.", "err"); dessiner(); } } }
      else if (k === "telecharger") { const r = await S.lire("controle_liste", { evenement_id: eid }); if (r) { liste = r; mem.ecrire("liste." + eid, r); dire(r.billets.length + " billets téléchargés.", "ok"); dessiner(); } }
      else if (k === "arbitrer") { if (await S.geste("conflit_arbitrer", { id: Number(a.dataset.id), decision: a.dataset.d }, "Arbitré.")) S.rendre(); }
    };
    if (window.__blEnLigne) window.removeEventListener("online", window.__blEnLigne);
    window.__blEnLigne = () => { if (R.isConnected && file.length) synchroniser().then(() => S.rendre()); };
    window.addEventListener("online", window.__blEnLigne);
    dessiner();
  };

  // ═══ MON ESPACE ═══
  const portefeuille = (w, qui) => '<div class="tuiles"><div class="tuile"><b>' + eur(Math.max(0, w.disponible)) + "</b><span>retirable maintenant</span></div><div class=\"tuile\"><b>" + eur(w.en_attente) + "</b><span>en attente de date</span></div><div class=\"tuile\"><b>" + eur(w.retraits_en_cours) + "</b><span>retrait demandé</span></div><div class=\"tuile\"><b>" + eur(w.verse) + "</b><span>déjà versé</span></div></div>" +
    '<div class="row"><button class="btn pri" data-a="retrait" data-q="' + qui + '"' + (w.disponible > 0 ? "" : " disabled") + ">Demander un retrait</button><span class=\"hint\">Le versement est fait par virement par l’organisateur.</span></div>" +
    (w.retraits.length ? "<h3>Mes demandes</h3>" + tableau([["d", "Demande"], ["m", "Montant", "n"], ["e", "État"]], w.retraits.map((r) => "<tr><td>" + esc(quand(r.demande_le)) + '</td><td class="n">' + eur(r.montant) + "</td><td>" + puce({ demandee: "en attente", validee: "validée", payee: "versée", refusee: "refusée" }[r.etat] || r.etat, r.etat === "payee" ? "ok" : r.etat === "refusee" ? "dg" : "al") + (r.motif ? '<div class="hint">' + esc(r.motif) + "</div>" : "") + "</td></tr>")) : "") +
    (w.mouvements.length ? "<h3>Mon registre</h3>" + tableau([["d", "Date"], ["n", "Nature"], ["m", "Montant", "n"]], w.mouvements.slice(0, 15).map((m) => "<tr><td>" + esc(quand(m.cree_le)) + "</td><td>" + esc(m.note || m.nature) + '</td><td class="n">' + eur(m.montant) + "</td></tr>")) : "");
  async function demanderRetrait(S, cap, w) {
    const v = await B.formulaire("Demander un retrait", [{ n: "n", t: "note", l: "Tu peux retirer jusqu’à <b>" + esc(eur(w.disponible)) + "</b>." }, { n: "montant", l: "Montant (€)", t: "eur" }], { montant: w.disponible }, "Demander");
    return v && (await S.geste(cap, { montant: v.montant }, "Demande envoyée : l’organisateur la traite sous peu."));
  }
  const ventesTable = (l) => tableau([["d", "Date"], ["e", "Événement"], ["b", "Billets", "n"], ["t", "Total", "n"], ["c", "Ma commission", "n"]], l.map((v) => "<tr><td>" + esc(quand(v.date)) + "</td><td>" + esc(v.evenement) + (v.etat !== "payee" ? " " + puce(v.etat === "remboursee" ? "remboursée" : v.etat, "dg") : "") + "<div class=\"hint\">" + esc(v.acheteur || "") + '</div></td><td class="n">' + v.billets + '</td><td class="n">' + eur(v.total) + '</td><td class="n">' + eur(v.commission) + "</td></tr>"), "Pas encore de vente.");

  P.revendeur = async (S) => {
    const R = S.racine, m = await S.lire("mon_revendeur");
    if (!m) { R.innerHTML = S.entetes("Mon espace revendeur", "") + '<div class="carte vide">' + esc(S.erreur || "Indisponible.") + "</div>"; return; }
    const lien = location.origin + "/" + m.lien_de_vente;
    R.innerHTML = S.entetes(m.nom, "Mon espace revendeur", m.actif ? puce("actif", "ok") : puce("suspendu", "dg")) + (m.actif ? "" : '<div class="alerte dg"><span class="sp">Ton compte est suspendu' + (m.motif_suspension ? " : " + esc(m.motif_suspension) : "") + ". Tes ventes passées restent visibles.</span></div>") +
      '<div class="carte"><h3>Mon code de vente</h3><p class="sub" style="margin:0 0 8px">Donne-le à tes acheteurs : leurs billets te sont attribués.</p><div class="row"><b style="font:700 22px ui-monospace,Menlo,monospace">' + esc(m.code) + '</b><button class="btn sm" data-a="copier" data-v="' + esc(m.code) + '">Copier le code</button><button class="btn sm" data-a="copier" data-v="' + esc(lien) + '">Copier le lien</button></div></div>' +
      portefeuille(m.portefeuille, "revendeur") +
      "<h3>Mes événements</h3>" + tableau([["e", "Événement"], ["f", "Formule"], ["v", "Vendus", "n"], ["q", "Reste", "n"], ["c", "Commission", "n"]], m.affectations.map((a) => "<tr><td><b>" + esc(a.evenement) + '</b><div class="hint">' + esc(jour(a.date)) + "</div></td><td>" + esc(a.formule) + '</td><td class="n">' + a.vendus + '</td><td class="n">' + (a.restant == null ? "—" : a.restant) + '</td><td class="n">' + eur(a.commission) + "</td></tr>"), "Tu n’es affecté à aucun événement pour l’instant.") +
      "<h3>Mes ventes</h3>" + ventesTable(m.ventes);
    S.clic = async (k, a) => {
      if (k === "copier") { try { await navigator.clipboard.writeText(a.dataset.v); dire("Copié.", "ok"); } catch (e) { dire("Copie refusée par le navigateur.", "err"); } }
      else if (k === "retrait") { if (await demanderRetrait(S, "mon_retrait_revendeur", m.portefeuille)) S.rendre(); }
    };
  };

  P.artiste = async (S) => {
    const R = S.racine, m = await S.lire("mon_artiste");
    if (!m) { R.innerHTML = S.entetes("Mon espace artiste", "") + '<div class="carte vide">' + esc(S.erreur || "Indisponible.") + "</div>"; return; }
    R.innerHTML = S.entetes(m.scene, "Mon espace artiste" + (m.genre ? " · " + m.genre : "")) +
      "<h3>Mes passages</h3>" + (m.programme.length ? '<div class="grille" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px">' + m.programme.map((p) => '<div class="carte"><b>' + esc(p.evenement) + "</b><div class=\"hint\">" + esc(jour(p.date)) + "</div><div class=\"row\" style=\"margin-top:8px\"><span style=\"font:700 24px ui-monospace,Menlo,monospace\">" + esc(p.heure || "—") + "</span><span class=\"sp\"></span><span>" + p.duree + " min</span></div><div class=\"hint\">Passage " + p.ordre + " sur " + p.sur + " · portes " + esc(p.portes) + "</div></div>").join("") + "</div>" : '<div class="carte vide">Aucun passage programmé pour l’instant.</div>') +
      (m.formule ? '<div class="carte"><h3>Ma formule · ' + esc(m.formule.nom) + "</h3><dl class=\"kv\">" + (m.formule.forfait ? "<dt>Forfait / cachet</dt><dd>" + eur(m.formule.forfait) + "</dd>" : "") + (m.formule.commission ? "<dt>Commission par place</dt><dd>" + eur(m.formule.commission) + "</dd>" : "") + (m.formule.fixe ? "<dt>Fixe</dt><dd>" + eur(m.formule.fixe) + "</dd>" : "") + "</dl></div>" : "") +
      "<h3>Mon portefeuille</h3>" + portefeuille(m.portefeuille, "artiste") +
      (m.vente ? '<div class="carte"><h3>Mes ventes de billets</h3><p class="sub" style="margin:0 0 8px">Mon code : <b>' + esc(m.vente.code) + "</b></p>" + ventesTable(m.vente.ventes) + "</div>" : "");
    S.clic = async (k, a) => { if (k === "retrait") { if (await demanderRetrait(S, "mon_retrait_artiste", m.portefeuille)) S.rendre(); } };
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
