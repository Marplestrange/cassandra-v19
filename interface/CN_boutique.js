// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : stockage refusé : on continue
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #0f596c
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : stockage refusé : on continue
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=0f596c ▼▼▼
// La boutique publique : la programmation, la page d'un événement, la commande, le suivi d'une commande avec ses billets, la liste d'attente, le reçu de don.
// Page statique et SANS session : tout passe par les capacités publiques billetterie.public_* (limitées par origine, protégées par jeton de suivi). La route est dans le fragment (#/e/..., #/c/..., #/a/...).
(function () {
  "use strict";
  const app = document.getElementById("app");
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const eur = (c) => (Number(c || 0) / 100).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  const cts = (v) => Math.round(parseFloat(String(v || "").replace(",", ".").replace(/\s/g, "") || "0") * 100) || 0;
  const jourLong = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "Date à venir");
  const jourCourt = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }) : "Bientôt");
  const memoire = { lire(k, d) { try { const v = sessionStorage.getItem("bl_" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, ecrire(k, v) { try { sessionStorage.setItem("bl_" + k, JSON.stringify(v)); } catch (e) { /* stockage refusé : on continue */ } } };
  const API = (window.BOUTIQUE_API || "/api/public/billetterie.");
  const compteLocal = { lire() { try { return JSON.parse(localStorage.getItem("bl_compte") || "null"); } catch (e) { return null; } }, ecrire(v) { try { if (v) localStorage.setItem("bl_compte", JSON.stringify(v)); else localStorage.removeItem("bl_compte"); } catch (e) { /* stockage refusé */ } } };
  const majLien = () => { const c = compteLocal.lire(), l = document.getElementById("lien-compte"); if (l) l.textContent = c ? "Mon espace" : "Mon compte"; };

  async function api(cap, args) {
    const r = await fetch(API + cap, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ args: args || {} }) });
    let d = {};
    try { d = await r.json(); } catch (e) { /* réponse vide */ }
    if (!r.ok || d.statut !== "faite") throw new Error(d.erreur || d.raison || (r.status === 429 ? "Trop de demandes : réessayez dans un moment." : "Un problème est survenu. Réessayez dans un instant."));
    return d.resultat;
  }
  { const q = new URLSearchParams(location.search).get("r"); if (q) memoire.ecrire("revendeur", q.toUpperCase().slice(0, 40)); }       // le lien d'un revendeur : ?r=CODE

  const ETATS = { ouvert: ["Billets en vente", "ok"], "dernières places": ["Dernières places", "alerte"], complet: ["Complet", "danger"], "annulé": ["Annulé", "danger"], "reporté": ["Reporté", "alerte"], "terminé": ["Terminé", ""], "bientôt": ["Bientôt en vente", ""] };
  const puce = (e) => { const x = ETATS[e] || [e, ""]; return '<span class="puce ' + x[1] + '">' + esc(x[0]) + "</span>"; };
  const erreur = (m) => '<p class="erreur" role="alert">' + esc(m) + "</p>";
  const titrePage = (t) => { document.title = t + " · " + (window.__orga || "Billetterie"); };

  // ── la programmation ─────────────────────────────────────────────────────
  async function calendrier() {
    const c = await api("public_calendrier");
    window.__orga = c.organisateur || "Billetterie";
    document.getElementById("marque").textContent = window.__orga;
    titrePage("Programmation");
    const l = c.evenements.filter((e) => e.etat !== "terminé");
    app.innerHTML = "<div><h1>Programmation</h1><p class=\"doux\">" + esc(window.__orga) + "</p></div>" +
      (l.length ? '<div class="grille">' + l.map((e) => '<a class="carte evt" href="#/e/' + esc(e.ref) + '"><div class="ligne"><span class="titre ext">' + esc(e.nom) + "</span>" + puce(e.etat) + "</div><div>" + esc(jourLong(e.date)) + (e.lieu ? " · " + esc(e.lieu) : "") + "</div>" + (e.accroche ? '<div class="doux">' + esc(e.accroche) + "</div>" : "") + (e.a_partir_de != null && e.etat !== "annulé" ? '<div class="pale">À partir de ' + esc(eur(e.a_partir_de)) + "</div>" : "") + "</a>").join("") + "</div>" : '<div class="carte vide">Aucun événement annoncé pour le moment. Revenez bientôt.</div>');
  }

  // ── la page d'un événement ───────────────────────────────────────────────
  async function evenement(ref) {
    const p = await api("public_evenement", { ref: ref });
    const e = p.evenement, panier = {};
    window.__orga = (p.organisateur || {}).nom || window.__orga;
    titrePage(e.nom);
    const vendable = e.etat === "ouvert" || e.etat === "dernières places";
    const epuises = p.billets.length && p.billets.every((b) => b.etat === "épuisé") || e.etat === "complet";
    const revendeur = memoire.lire("revendeur", "");
    let moi = null;
    const cl = compteLocal.lire();
    if (cl) { try { moi = await api("public_compte_moi", { session: cl.session }); } catch (x) { compteLocal.ecrire(null); majLien(); } }
    const session = moi ? cl.session : "";
    const infos = [["Date", jourLong(e.date)], ["Lieu", p.salle ? p.salle.nom + (p.salle.adresse ? " — " + p.salle.adresse : "") : ""], ["Horaires", "Portes " + e.portes + " · début " + e.debut + (e.fin ? " · fin " + e.fin : "")], ["Public", e.age], ["Accès PMR", p.salle ? (p.salle.pmr ? "Oui" : "Non précisé") : ""]].filter((x) => x[1]);
    app.innerHTML = '<p class="ariane"><a href="#/">← Programmation</a></p><div><h1>' + esc(e.nom) + '</h1><p class="doux">' + esc(e.accroche) + '</p><p style="margin-top:8px">' + puce(e.etat) + "</p></div>" +
      (e.etat === "annulé" ? '<div class="info danger"><b>Cet événement est annulé.</b> Les billets déjà achetés sont remboursés ; vous avez reçu un courriel.</div>' : "") +
      '<div class="carte"><div class="prog">' + infos.map((x) => '<span class="pale">' + esc(x[0]) + "</span><span>" + esc(x[1]) + "</span><span></span>").join("") + "</div>" + (e.description ? '<p style="margin-top:12px">' + esc(e.description).replace(/\n/g, "<br>") + "</p>" : "") + "</div>" +
      (p.programme.length ? '<div class="carte"><h2>Au programme</h2><div class="prog">' + p.programme.map((x) => "<b>" + esc(x.heure || "") + "</b><span><b>" + esc(x.scene) + '</b> <span class="pale">' + esc(x.genre || "") + "</span></span><span class=\"pale\">" + x.duree + " min</span>").join("") + "</div></div>" : "") +
      '<div class="carte" id="achat"></div>';
    const zone = document.getElementById("achat");

    if (!vendable && !epuises) { zone.innerHTML = e.etat === "annulé" ? "" : '<p class="doux">' + (e.etat === "terminé" ? "Cet événement est terminé." : e.etat === "reporté" ? "Cet événement est reporté : la nouvelle date sera annoncée." : "La vente n’est pas encore ouverte.") + "</p>"; return; }
    if (epuises && p.liste_attente) { listeAttente(zone, p); return; }
    if (epuises) { zone.innerHTML = '<p class="doux">Complet. La liste d’attente n’est pas ouverte pour cet événement.</p>'; return; }

    zone.innerHTML = "<h2>Billets</h2>" + p.billets.map((b) => '<div class="billet"><div class="ext"><b>' + esc(b.nom) + "</b><div class=\"pale\">" + esc(b.description || "") + (b.entrees > 1 ? " · " + b.entrees + " entrées" : "") + (b.plus_que ? " · plus que " + b.plus_que : "") + "</div><div>" + esc(eur(b.prix)) + "</div></div>" +
      (b.etat === "ok" ? '<div class="qte"><button type="button" data-moins="' + esc(b.ref) + '" aria-label="Retirer un billet ' + esc(b.nom) + '">−</button><output id="q-' + esc(b.ref) + '">0</output><button type="button" data-plus="' + esc(b.ref) + '" aria-label="Ajouter un billet ' + esc(b.nom) + '">+</button></div>' : '<span class="puce">' + esc({ "épuisé": "Épuisé", "bientôt": "Bientôt", clos: "Vente terminée" }[b.etat] || b.etat) + "</span>") + "</div>").join("") +
      '<form id="commande" novalidate style="display:grid;gap:14px;margin-top:14px"><p class="pale">' + (moi ? "Connecté : <b>" + esc(moi.mail) + '</b> · <a href="#/compte">mon espace</a>' : 'Déjà client ? <a href="#/compte">Connectez-vous</a> : plus de frais d’achat sans compte, et vos billets sont gardés dans votre espace.') + '</p><div class="champs"><label>Nom et prénom<input type="text" name="nom" autocomplete="name" required value="' + esc(moi ? moi.nom : "") + '"></label><label>Courriel (vos billets y sont envoyés)<input type="email" name="mail" autocomplete="email" inputmode="email" required value="' + esc(moi ? moi.mail : "") + '"' + (moi ? " readonly" : "") + '></label></div>' +
      '<div class="champs"><label>Code promo<input type="text" name="code_promo" autocomplete="off" autocapitalize="characters"></label>' + (p.achat.don_possible ? '<label>Don à l’association (facultatif)<input type="text" name="don" inputmode="decimal" placeholder="0,00 €"></label>' : "") + "</div>" +
      (revendeur ? '<p class="pale">Code revendeur appliqué : <b>' + esc(revendeur) + "</b></p>" : "") +
      '<div id="devis" class="info" style="display:none"></div>' +
      (moi ? "" : (p.achat.compte_obligatoire ? '<div class="info alerte">Cet événement demande un compte client. <a href="#/compte">Se connecter ou créer un compte</a> (un lien vous est envoyé par courriel, sans mot de passe).</div>' : (p.achat.frais_sans_compte ? '<p class="pale">Achat sans compte : ' + esc(eur(p.achat.frais_sans_compte)) + " de frais.</p>" : ""))) +
      '<fieldset style="border:0;padding:0;margin:0;display:grid;gap:8px"><legend class="doux" style="padding:0;margin-bottom:6px">Paiement</legend>' + (p.paiements.length ? p.paiements.map((m, i) => '<label class="coche" style="color:var(--txt)"><input type="radio" name="moyen" value="' + esc(m.id) + '"' + (i === 0 ? " checked" : "") + "><span><b>" + esc(m.libelle) + "</b>" + (m.detail ? '<br><span class="pale">' + esc(m.detail) + "</span>" : "") + "</span></label>").join("") : '<p class="erreur">Le paiement en ligne n’est pas encore ouvert. Contactez l’organisateur.</p>') + "</fieldset>" +
      '<label class="coche"><input type="checkbox" name="consentement"><span>Je souhaite recevoir les nouvelles de l’organisateur (facultatif).</span></label>' +
      '<div id="msg"></div><div class="ligne"><span class="total" id="total">0,00 €</span><span class="ext"></span><button class="principal" type="submit" id="valider" disabled>Réserver et payer</button></div>' +
      '<p class="pale">Vos places sont retenues pendant quelques minutes le temps du paiement. Vos données ne servent qu’à vous envoyer vos billets.</p></form>';

    const form = document.getElementById("commande");
    const lignes = () => Object.keys(panier).filter((k) => panier[k] > 0).map((k) => ({ type: k, quantite: panier[k] }));
    const nb = () => Object.keys(panier).reduce((n, k) => n + panier[k], 0);
    let minuteur = 0;
    async function devis() {
      const d = document.getElementById("devis"), msg = document.getElementById("msg"), tot = document.getElementById("total");
      msg.innerHTML = "";
      if (!nb()) { d.style.display = "none"; tot.textContent = eur(0); document.getElementById("valider").disabled = true; return; }
      try {
        const f = new FormData(form), r = await api("public_panier", { evenement: e.ref, lignes: lignes(), code_promo: (f.get("code_promo") || "").trim(), don: cts(f.get("don")), session: session });
        d.style.display = "block";
        d.innerHTML = r.lignes.map((l) => esc(l.quantite + " × " + l.nom + " — " + eur(l.prix * l.quantite))).join("<br>") + (r.remise ? "<br>Remise " + esc(r.promo) + " : −" + esc(eur(r.remise)) : "") + (r.don ? "<br>Don : " + esc(eur(r.don)) : "") + (r.frais ? "<br>Frais d’achat sans compte : " + esc(eur(r.frais)) : "");
        tot.textContent = eur(r.total);
        document.getElementById("valider").disabled = !p.paiements.length;
      } catch (x) { d.style.display = "none"; msg.innerHTML = erreur(x.message); document.getElementById("valider").disabled = true; }
    }
    const differer = () => { clearTimeout(minuteur); minuteur = setTimeout(devis, 300); };
    zone.addEventListener("click", (ev) => {
      const pl = ev.target.closest("[data-plus]"), mo = ev.target.closest("[data-moins]"), r = (pl || mo || {}).dataset;
      if (!r) return;
      const k = pl ? r.plus : r.moins;
      panier[k] = Math.max(0, Math.min(20, (panier[k] || 0) + (pl ? 1 : -1)));
      document.getElementById("q-" + k).textContent = panier[k];
      differer();
    });
    form.addEventListener("input", (ev) => { if (ev.target.name === "code_promo" || ev.target.name === "don") differer(); });
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = new FormData(form), msg = document.getElementById("msg"), bouton = document.getElementById("valider");
      if (!(f.get("nom") || "").trim() || !(f.get("mail") || "").trim()) { msg.innerHTML = erreur("Indiquez votre nom et votre courriel."); return; }
      bouton.disabled = true; bouton.textContent = "Un instant…";
      try {
        const r = await api("public_commander", { evenement: e.ref, lignes: lignes(), nom: f.get("nom").trim(), mail: f.get("mail").trim(), moyen: f.get("moyen"), code_promo: (f.get("code_promo") || "").trim(), don: cts(f.get("don")),
          session: session, code_revendeur: revendeur, consentement: !!f.get("consentement") });
        memoire.ecrire("derniere", { commande: r.commande, suivi: r.suivi });
        if (r.paiement && r.paiement.type === "stripe") { window.location.href = r.paiement.url; return; }
        location.hash = "#/c/" + r.commande + "?s=" + encodeURIComponent(r.suivi);
      } catch (x) { msg.innerHTML = erreur(x.message); bouton.disabled = false; bouton.textContent = "Réserver et payer"; if (/session/.test(x.message)) { compteLocal.ecrire(null); majLien(); } else devis(); }
    });
  }

  // ── la liste d'attente ───────────────────────────────────────────────────
  function listeAttente(zone, p) {
    zone.innerHTML = '<h2>Complet</h2><p class="doux">Il n’y a plus de place. Inscrivez-vous : si une place se libère, elle vous est réservée dans l’ordre d’inscription, et vous êtes prévenu par courriel.</p>' +
      '<form id="attente" novalidate style="display:grid;gap:12px;margin-top:12px"><div class="champs"><label>Nom et prénom<input type="text" name="nom" autocomplete="name" required></label><label>Courriel<input type="email" name="mail" autocomplete="email" required></label><label>Billet<select name="type"><option value="">Le premier disponible</option>' + p.billets.map((b) => '<option value="' + esc(b.ref) + '">' + esc(b.nom + " · " + eur(b.prix)) + "</option>").join("") + '</select></label><label>Nombre de places<select name="quantite">' + [1, 2, 3, 4, 5, 6].map((n) => "<option>" + n + "</option>").join("") + "</select></label></div><div id=\"msg\"></div><button class=\"principal\" type=\"submit\">Me mettre sur la liste d’attente</button></form>";
    document.getElementById("attente").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = new FormData(ev.target), msg = document.getElementById("msg");
      try {
        const r = await api("public_attente_inscrire", { evenement: p.evenement.ref, type: f.get("type") || "", quantite: Number(f.get("quantite")), nom: (f.get("nom") || "").trim(), mail: (f.get("mail") || "").trim() });
        location.hash = "#/a/" + encodeURIComponent(r.suivi);
      } catch (x) { msg.innerHTML = erreur(x.message); }
    });
  }
  async function attente(jeton) {
    const a = await api("public_attente_suivre", { suivi: jeton });
    titrePage("Liste d’attente");
    const e = a.evenement;
    app.innerHTML = '<p class="ariane"><a href="#/e/' + esc(e.ref) + '">← ' + esc(e.nom) + "</a></p><h1>Liste d’attente</h1>" +
      '<div class="carte">' + ({ attente: "<p>Vous êtes <b>n° " + (a.rang || "?") + "</b> sur la liste d’attente pour " + a.places + " place(s). Vous serez prévenu par courriel dès qu’une place se libère.</p>",
        offerte: "<p><b>Des places vous sont réservées !</b></p><p class=\"doux\">Payez avant " + esc(a.offre ? new Date(a.offre.jusqua * 1000).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" }) : "") + ", sinon elles seront proposées à la personne suivante.</p><p style=\"margin-top:12px\"><a class=\"bouton principal\" href=\"#/c/" + esc(a.offre ? a.offre.commande : "") + "?s=" + encodeURIComponent(a.offre ? a.offre.suivi : "") + "\">Payer mes places</a></p>",
        convertie: "<p>Vous avez acheté vos places : merci !</p>", expiree: "<p>L’offre a expiré. Vous pouvez vous réinscrire si des places sont encore possibles.</p>", retiree: "<p>Vous n’êtes plus sur la liste d’attente.</p>" }[a.etat] || "") + "</div>" +
      ((a.etat === "attente" || a.etat === "offerte") ? '<p><button type="button" id="retirer">' + (a.etat === "offerte" ? "Je ne veux plus ces places" : "Me retirer de la liste") + "</button></p>" : "");
    const b = document.getElementById("retirer");
    if (b) b.addEventListener("click", async () => { if (confirm("Confirmer ?")) { try { await api("public_attente_retirer", { suivi: jeton }); } catch (x) { alert(x.message); } attente(jeton); } });
  }

  // ── le suivi d'une commande ──────────────────────────────────────────────
  const ics = (c) => {
    const e = c.evenement, d = (e.date || "").replace(/-/g, ""), h = (e.debut || "20:00").replace(":", "") + "00";
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Billetterie//FR\r\nBEGIN:VEVENT\r\nUID:" + c.commande + "@billetterie\r\nDTSTAMP:" + new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z\r\nDTSTART:" + d + "T" + h + "\r\nSUMMARY:" + e.nom + "\r\nLOCATION:" + [e.lieu, e.adresse].filter(Boolean).join(", ") + "\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n";
  };
  let suiviTimer = 0;
  async function commande(ref, suivi) {
    clearTimeout(suiviTimer);
    const c = await api("public_suivre", { commande: ref, suivi: suivi });
    const e = c.evenement, ENT = { retenue: "Réservée : en attente de paiement", en_attente: "En attente de votre virement", payee: "Payée", remboursee: "Remboursée", annulee: "Annulée", expiree: "Réservation expirée" };
    titrePage("Commande " + c.commande);
    let corps = "";
    if (c.etat === "payee") {
      corps = '<div class="info"><b>Merci ! Votre commande est payée.</b> Voici vos billets : présentez le QR code à l’entrée (sur téléphone ou imprimé). Ils vous ont aussi été envoyés par courriel.</div><div class="tickets" id="billets">' +
        c.billets.map((b) => '<div class="ticket"><div>' + window.CASS.qr.svg(b.qr, { taille: 200 }) + '</div><span class="num">' + esc(b.numero) + "</span>" + (b.nom ? "<span>" + esc(b.nom) + "</span>" : "") + '<span class="code">Code de contrôle : ' + esc(b.code_controle) + "</span>" + (b.etat !== "valide" ? '<span class="puce danger">Annulé</span>' : "") + "</div>").join("") + "</div>" +
        '<div class="ligne noprint"><button type="button" id="imprimer">Imprimer mes billets</button><button type="button" id="agenda">Ajouter à mon agenda</button></div>';
      if (c.recu_fiscal && c.recu_fiscal.possible) corps += '<div class="carte noprint" id="recu"><h2>Reçu fiscal de votre don</h2>' + (c.recu_fiscal.numero ? '<div id="recuvue"></div>' : '<p class="doux">Votre don de ' + esc(eur(c.don)) + ' ouvre droit à un reçu fiscal. Indiquez votre adresse postale pour l’obtenir.</p><form id="recuform" style="display:grid;gap:10px;margin-top:10px"><label>Nom du donateur<input type="text" name="nom" value="' + esc(c.nom || "") + '" required></label><label>Adresse postale complète<textarea name="adresse" required></textarea></label><div id="msg"></div><button type="submit">Obtenir mon reçu</button></form>') + "</div>";
    } else if (c.etat === "retenue" || c.etat === "en_attente") {
      const reste = Math.max(0, Math.round((c.expire_le * 1000 - Date.now()) / 60000));
      corps = '<div class="info alerte"><b>' + esc(ENT[c.etat]) + ".</b> Vos places sont retenues encore ~" + reste + " min" + (c.etat === "en_attente" ? " (3 jours pour un virement)" : "") + ".</div>" +
        (c.paiement && c.paiement.type === "virement" ? '<div class="carte"><h2>Virement bancaire</h2><div class="prog"><span class="pale">IBAN</span><b style="word-break:break-all">' + esc(c.paiement.iban) + '</b><span></span><span class="pale">Montant</span><b>' + esc(eur(c.paiement.montant)) + '</b><span></span><span class="pale">Référence</span><b>' + esc(c.paiement.reference) + "</b><span></span></div><p class=\"pale\" style=\"margin-top:8px\">Indiquez la référence en libellé : vos billets sont émis dès la réception.</p></div>" : "") +
        '<div class="carte noprint" id="payer"><h2>Payer maintenant</h2><div id="moyens" class="ligne"><span class="doux">Chargement…</span></div><div id="msg"></div></div>';
    } else corps = '<div class="info danger">' + esc(ENT[c.etat] || c.etat) + (c.etat === "remboursee" ? " : le remboursement vous a été annoncé par courriel." : ".") + "</div>";
    app.innerHTML = '<p class="ariane noprint"><a href="#/e/' + esc(e.ref) + '">← ' + esc(e.nom) + "</a></p><div><h1>Commande " + esc(c.commande) + "</h1><p class=\"doux\">" + esc(e.nom) + " — " + esc(jourLong(e.date)) + (e.lieu ? " — " + esc(e.lieu) : "") + "</p></div>" + corps;
    const imp = document.getElementById("imprimer"); if (imp) imp.addEventListener("click", () => window.print());
    const ag = document.getElementById("agenda"); if (ag) ag.addEventListener("click", () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([ics(c)], { type: "text/calendar" })); a.download = "evenement.ics"; document.body.appendChild(a); a.click(); a.remove(); });
    const rf = document.getElementById("recuform");
    if (rf) rf.addEventListener("submit", async (ev) => { ev.preventDefault(); const f = new FormData(rf); try { await api("public_recu_demander", { commande: ref, suivi: suivi, adresse: (f.get("adresse") || "").trim(), nom: (f.get("nom") || "").trim() }); commande(ref, suivi); } catch (x) { document.getElementById("msg").innerHTML = erreur(x.message); } });
    if (document.getElementById("recuvue")) { try { const r = await api("public_recu", { commande: ref, suivi: suivi }); document.getElementById("recuvue").innerHTML = '<p>Reçu <b>' + esc(r.numero) + "</b> — " + esc(eur(r.montant)) + ' — <button type="button" id="imprecu">Imprimer</button></p><div class="pale" style="margin-top:6px">' + esc(r.contenu.organisme.nom) + " — " + esc(r.contenu.organisme.adresse) + "<br>Donateur : " + esc(r.contenu.donateur.nom) + ", " + esc(r.contenu.donateur.adresse) + "<br>" + esc(r.contenu.mention) + "</div>"; document.getElementById("imprecu").addEventListener("click", () => window.print()); } catch (x) { /* pas de reçu */ } }
    if (c.etat === "retenue" || c.etat === "en_attente") {
      try {
        const ev = await api("public_evenement", { ref: e.ref }), z = document.getElementById("moyens");
        z.innerHTML = ev.paiements.map((m) => '<button type="button" class="principal" data-moyen="' + esc(m.id) + '">' + esc(m.libelle) + "</button>").join("") || '<span class="erreur">Aucun moyen de paiement n’est ouvert.</span>';
        z.addEventListener("click", async (x) => { const b = x.target.closest("[data-moyen]"); if (!b) return; b.disabled = true; try { const r = await api("public_payer", { commande: ref, suivi: suivi, moyen: b.dataset.moyen }); if (r.paiement.type === "stripe") window.location.href = r.paiement.url; else commande(ref, suivi); } catch (err) { document.getElementById("msg").innerHTML = erreur(err.message); b.disabled = false; } });
      } catch (x) { /* l'événement n'est plus public : le paiement reste possible par virement déjà affiché */ }
      if (c.expire_le * 1000 > Date.now()) suiviTimer = setTimeout(() => { if (/^#\/c\//.test(location.hash)) commande(ref, suivi); }, 6000);       // au retour du prestataire, la confirmation arrive par son webhook : on relit
    }
  }

  // ── mon espace ───────────────────────────────────────────────────────────
  async function compte(t) {
    titrePage("Mon espace");
    if (t) {                                                        // le lien reçu par courriel : on l'échange contre une session, puis on le retire de l'adresse
      try { const r = await api("public_compte_ouvrir", { jeton: t }); compteLocal.ecrire({ session: r.session, mail: r.mail }); majLien(); history.replaceState(null, "", location.pathname + location.search + "#/compte"); }
      catch (x) { app.innerHTML = '<div class="carte"><h2>Lien non valable</h2>' + erreur(x.message) + '<p style="margin-top:10px"><a href="#/compte">Demander un nouveau lien</a></p></div>'; return; }
    }
    const cl = compteLocal.lire();
    if (!cl) {
      app.innerHTML = '<div><h1>Mon espace</h1><p class="doux">Retrouvez vos billets, achetez sans frais d’achat sans compte. Pas de mot de passe : nous vous envoyons un lien par courriel.</p></div><form id="lien" class="carte" novalidate style="display:grid;gap:12px"><label>Votre courriel<input type="email" name="mail" autocomplete="email" inputmode="email" required></label><div id="msg"></div><button class="principal" type="submit">Recevoir mon lien de connexion</button></form>';
      document.getElementById("lien").addEventListener("submit", async (ev) => {
        ev.preventDefault(); const f = new FormData(ev.target), msg = document.getElementById("msg");
        try { await api("public_compte_lien", { mail: (f.get("mail") || "").trim() }); ev.target.innerHTML = '<div class="info"><b>C’est envoyé.</b> Si cette adresse est correcte, vous allez recevoir un lien de connexion (valable 15 minutes, un seul usage). Pensez à regarder vos courriers indésirables.</div>'; } catch (x) { msg.innerHTML = erreur(x.message); }
      });
      return;
    }
    let m;
    try { m = await api("public_compte_moi", { session: cl.session }); } catch (x) { compteLocal.ecrire(null); majLien(); return compte(); }
    const ETAT = { retenue: "À payer", en_attente: "Virement attendu", payee: "Payée", remboursee: "Remboursée", annulee: "Annulée", expiree: "Expirée" };
    app.innerHTML = '<div><h1>Mon espace</h1><p class="doux">' + esc(m.mail) + "</p></div>" +
      (m.suppression_le ? '<div class="info danger"><b>Suppression de votre compte programmée</b> le ' + esc(new Date(m.suppression_le * 1000).toLocaleDateString("fr-FR", { dateStyle: "long" })) + '. Vos données personnelles seront alors effacées. <button type="button" id="annuler-sup">Annuler la suppression</button></div>' : "") +
      '<div class="carte"><h2>Mes commandes</h2>' + (m.commandes.length ? m.commandes.map((c) => '<a class="billet" style="text-decoration:none;color:inherit" href="#/c/' + esc(c.commande) + "?s=" + encodeURIComponent(c.suivi) + '"><div class="ext"><b>' + esc(c.evenement) + '</b><div class="pale">' + esc(jourLong(c.date)) + " · " + esc(c.commande) + '</div></div><div style="text-align:right"><div>' + esc(eur(c.total)) + '</div><span class="puce ' + (c.etat === "payee" ? "ok" : c.etat === "retenue" || c.etat === "en_attente" ? "alerte" : "") + '">' + esc(ETAT[c.etat] || c.etat) + "</span></div></a>").join("") : '<p class="doux">Aucune commande pour le moment.</p>') + "</div>" +
      (m.attente.length ? '<div class="carte"><h2>Liste d’attente</h2>' + m.attente.map((a) => '<a class="billet" style="text-decoration:none;color:inherit" href="#/a/' + encodeURIComponent(a.suivi) + '"><div class="ext"><b>' + esc(a.evenement) + '</b><div class="pale">' + a.quantite + ' place(s)</div></div><span class="puce ' + (a.etat === "offerte" ? "alerte" : "") + '">' + (a.etat === "offerte" ? "Places réservées !" : "En attente") + "</span></a>").join("") + "</div>" : "") +
      '<form id="profil" class="carte" novalidate style="display:grid;gap:12px"><h2>Mes coordonnées</h2><div class="champs"><label>Nom et prénom<input type="text" name="nom" autocomplete="name" value="' + esc(m.nom) + '"></label><label>Téléphone<input type="text" name="tel" autocomplete="tel" value="' + esc(m.tel) + '"></label></div><label class="coche"><input type="checkbox" name="consentement"' + (m.consentement ? " checked" : "") + '><span>Je souhaite recevoir les nouvelles de l’organisateur.</span></label><div id="msg"></div><button type="submit">Enregistrer</button></form>' +
      '<div class="carte"><h2>Mes données</h2><p class="doux">Vous pouvez télécharger toutes les données que nous avons sur vous, ou demander leur suppression : elle est effective après quelques jours, et vous pouvez changer d’avis d’ici là. Les montants des commandes et les reçus fiscaux sont conservés (obligations comptables et fiscales), sans votre nom.</p><div class="ligne" style="margin-top:10px"><button type="button" id="exporter">Télécharger mes données</button>' + (m.suppression_le ? "" : '<button type="button" id="supprimer">Supprimer mon compte…</button>') + '<button type="button" id="quitter">Me déconnecter</button></div></div>';
    document.getElementById("profil").addEventListener("submit", async (ev) => { ev.preventDefault(); const f = new FormData(ev.target); try { await api("public_compte_modifier", { session: cl.session, nom: (f.get("nom") || "").trim(), tel: (f.get("tel") || "").trim(), consentement: !!f.get("consentement") }); document.getElementById("msg").innerHTML = '<p class="doux">Enregistré.</p>'; } catch (x) { document.getElementById("msg").innerHTML = erreur(x.message); } });
    document.getElementById("exporter").addEventListener("click", async () => { try { const d = await api("public_compte_exporter", { session: cl.session }); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); a.download = "mes-donnees.json"; document.body.appendChild(a); a.click(); a.remove(); } catch (x) { alert(x.message); } });
    document.getElementById("quitter").addEventListener("click", async () => { try { await api("public_compte_fermer", { session: cl.session }); } catch (x) { /* déjà fermée */ } compteLocal.ecrire(null); majLien(); compte(); });
    const sup = document.getElementById("supprimer"); if (sup) sup.addEventListener("click", async () => { if (confirm("Demander la suppression de votre compte et de vos données personnelles ?")) { try { await api("public_compte_supprimer", { session: cl.session }); compte(); } catch (x) { alert(x.message); } } });
    const an = document.getElementById("annuler-sup"); if (an) an.addEventListener("click", async () => { try { await api("public_compte_annuler_suppression", { session: cl.session }); compte(); } catch (x) { alert(x.message); } });
  }

  // ── la route ─────────────────────────────────────────────────────────────
  async function router() {
    clearTimeout(suiviTimer);
    const h = location.hash.replace(/^#/, "") || "/", [chemin, requete] = h.split("?"), q = new URLSearchParams(requete || ""), m = chemin.split("/").filter(Boolean);
    window.scrollTo(0, 0);
    try {
      if (!m.length) await calendrier();
      else if (m[0] === "e" && m[1]) await evenement(decodeURIComponent(m[1]));
      else if (m[0] === "c" && m[1]) await commande(decodeURIComponent(m[1]), q.get("s") || "");
      else if (m[0] === "a" && m[1]) await attente(decodeURIComponent(m[1]));
      else if (m[0] === "compte") await compte(q.get("t") || "");
      else await calendrier();
    } catch (x) { app.innerHTML = '<div class="carte"><h2>Oups</h2>' + erreur(x.message) + '<p style="margin-top:10px"><a href="#/">Retour à la programmation</a></p></div>'; }
    document.getElementById("pied").textContent = window.__orga ? window.__orga + " · billetterie" : "";
  }
  window.addEventListener("hashchange", router);
  majLien();
  router();
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
