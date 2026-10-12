/* Pont V18 -> noyau V19.

L'interface V18 parle à ~615 routes (/api/...). Le noyau V19 n'en a qu'une porte : POST /api/agir/<module>.<capacité>.
Ce fichier enveloppe window.fetch AVANT app.js : une requête /api/ de l'interface est traduite en appel de capacité, la réponse est remise
dans la forme que l'interface attend. Rien d'autre ne change dans app.js tant qu'un écran n'est pas réécrit.

Chaque module apporte sa table dans interface/routes/<module>.js :

    CASS.route("GET", "/api/taches", "taches.lister", { args: (r) => ({ ...r.query }), sortie: (res) => ({ taches: res }) });
    CASS.route("POST", "/api/taches/:id/fait", "taches.terminer", { args: (r) => ({ id: +r.params.id }) });

Une route que personne n'a branchée répond 501 {error:"pas encore porté: ..."} : l'écran l'affiche, il ne casse pas.
*/
(function () {
  "use strict";
  const natif = window.fetch.bind(window);
  const routes = [];
  const CASS = (window.CASS = { routes, journal: [] });

  // "/api/taches/:id/fait" -> expression régulière + noms des paramètres
  function motif(chemin) {
    const noms = [];
    const re = chemin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/:([a-z_][a-z0-9_]*)/gi, (_, n) => { noms.push(n); return "([^/]+)"; });
    return { re: new RegExp("^" + re + "$"), noms };
  }
  CASS.route = function (methode, chemin, capacite, opt) {
    const m = motif(chemin);
    routes.push({ methode: methode.toUpperCase(), chemin, re: m.re, noms: m.noms, capacite, opt: opt || {} });
  };

  function reponse(statut, corps, entetes) {
    return new Response(JSON.stringify(corps), { status: statut, headers: Object.assign({ "Content-Type": "application/json; charset=utf-8" }, entetes || {}) });
  }
  function jeton() { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } }
  function entetesV19(init) {
    const e = {};
    const src = (init && init.headers) || {};
    const lire = (k) => (typeof src.get === "function" ? src.get(k) : src[k]);
    const t = lire("X-Session-Token") || jeton();
    if (t) e["Authorization"] = "Bearer " + t;
    e["Content-Type"] = "application/json";
    e["X-Cassandra"] = "1";
    return e;
  }
  async function v19(methode, chemin, corps, init) {
    const opt = { method: methode, headers: entetesV19(init), credentials: "same-origin" };
    if (methode !== "GET") opt.body = JSON.stringify(corps || {});
    return natif(chemin, opt);
  }

  // Un résultat de capacité devient la réponse que l'écran V18 lit.
  function traduire(res, statutHttp, opt) {
    const st = res && res.statut;
    if (st === "refuse") return reponse(403, { error: (res && (res.raison || res.erreur)) || "refusé", reason: (res && res.raison) || "", success: false });
    if (st === "echec" || st === "annulee") return reponse(500, { error: (res && (res.erreur || res.raison)) || "échec", success: false });
    let sortie = res && res.resultat !== undefined ? res.resultat : res;
    if (st === "racontee") sortie = { raconte: true, resultat: sortie };
    if (opt && opt.sortie) sortie = opt.sortie(sortie, res);
    return reponse(200, sortie);
  }

  function trouver(methode, chemin) {
    for (const r of routes) {
      if (r.methode !== methode) continue;
      const m = r.re.exec(chemin);
      if (m) { const params = {}; r.noms.forEach((n, i) => (params[n] = decodeURIComponent(m[i + 1]))); return { r, params }; }
    }
    return null;
  }

  async function login(corps) {
    const r = await v19("POST", "/api/connexion", { compte: corps.username, mot_de_passe: corps.password });
    const d = await r.json().catch(() => ({}));
    if (r.status === 200 && d.ok) {
      let admin = false;
      try { const mo = await (await v19("GET", "/api/moi", null, { headers: { "X-Session-Token": d.jeton } })).json(); admin = !!mo.admin; } catch (e) {}
      return reponse(200, { success: true, session: d.jeton, username: d.compte, is_admin: admin, role: admin ? "admin" : "utilisateur" });
    }
    if (r.status === 429) return reponse(429, { success: false, error: d.erreur || "trop d'essais", attente: d.attente_s || 0, attente_s: d.attente_s || 0 });
    if (d.second_facteur) return reponse(401, { success: false, error: "Second facteur requis : pas encore branché dans cette interface", second_facteur: true });
    return reponse(401, { success: false, error: d.erreur || "Identifiants invalides" });
  }

  window.fetch = async function (entree, init) {
    const url = typeof entree === "string" ? entree : entree && entree.url;
    if (!url || url.indexOf("/api/") !== 0) return natif(entree, init);
    const u = new URL(url, location.origin);
    const chemin = u.pathname;
    const methode = ((init && init.method) || "GET").toUpperCase();
    let corps = {};
    if (init && typeof init.body === "string") { try { corps = JSON.parse(init.body); } catch (e) { corps = {}; } }
    const query = {};
    u.searchParams.forEach((v, k) => { if (k !== "_") query[k] = v; });

    if (chemin === "/api/login" && methode === "POST") return login(corps);
    if (chemin === "/api/verify") {
      const r = await v19("GET", "/api/moi", null, init);
      if (r.status !== 200) return reponse(200, { valid: false });
      const d = await r.json();
      return reponse(200, { valid: true, username: d.compte, is_admin: !!d.admin, role: d.admin ? "admin" : "utilisateur" });
    }
    if (chemin === "/api/logout") { await v19("POST", "/api/deconnexion", {}, init); return reponse(200, { success: true }); }

    const t = trouver(methode, chemin);
    if (!t) {
      CASS.journal.push(methode + " " + chemin);
      return reponse(501, { error: "pas encore porté : " + methode + " " + chemin, success: false, ok: false });
    }
    const req = { params: t.params, query, body: corps, methode, url: chemin, jeton: ((init && init.headers && init.headers["X-Session-Token"]) || jeton()) };
    const args = t.r.opt.args ? t.r.opt.args(req) : Object.assign({}, query, corps, t.params);
    const cap = typeof t.r.capacite === "function" ? t.r.capacite(req) : t.r.capacite;
    const ecrit = methode !== "GET";
    let r;
    if (ecrit) r = await v19("POST", "/api/agir/" + cap, { args }, init);
    else r = await v19("GET", "/api/agir/" + cap + "?" + new URLSearchParams(Object.entries(args).map(([k, v]) => [k, typeof v === "object" ? JSON.stringify(v) : String(v)])).toString(), null, init);
    if (r.status === 401) return reponse(401, { error: "401" });
    let res;
    try { res = await r.json(); } catch (e) { return reponse(502, { error: "réponse illisible du noyau" }); }
    if (r.status === 404 || r.status === 405 || r.status === 400) return reponse(r.status, { error: res.erreur || "refusé", success: false });
    return traduire(res, r.status, t.r.opt);
  };
})();
