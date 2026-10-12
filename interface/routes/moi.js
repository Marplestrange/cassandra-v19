/* Mon compte : /api/me/* (V18) -> capacités comptes.* du noyau. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  P("/api/me", "comptes.moi", {
    args: () => ({}),
    sortie: (m) => ({ ok: true, user: m.compte, role: m.admin ? "admin" : "utilisateur", is_admin: !!m.admin, sites: m.sites || [], fp_account: m.fp_account || "", sites_herites: [],
      display_name: m.display_name || "", role_label: m.role_label || "", contact_email: m.contact_email || "", phone: m.phone || "", lang: m.lang || "fr", photo: false }),
  });
  P("/api/me/profile", "comptes.modifier_moi", { args: (r) => ({ display_name: r.body.display_name, role_label: r.body.role_label, contact_email: r.body.contact_email, phone: r.body.phone, lang: r.body.lang }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/password", "comptes.changer_mon_mot_de_passe", { args: (r) => ({ actuel: r.body.current, nouveau: r.body.new }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions", "comptes.mes_sessions", { args: (r) => ({ courant: r.jeton }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions/revoke", "comptes.revoquer_session", { args: (r) => ({ court: r.body.id }), sortie: (x) => Object.assign({ ok: true }, x) });
  P("/api/me/sessions/revoke_others", "comptes.revoquer_autres_sessions", { args: (r) => ({ courant: r.jeton }), sortie: (x) => Object.assign({ ok: true }, x) });
})();
