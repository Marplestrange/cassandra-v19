/* Les canaux Telegram : /api/canaux/* -> capacités canaux.* du noyau.
   Différé : la connexion MTProto/Telethon, l'envoi et la réception. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/canaux/etat", "canaux.etat", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canaux/miroir", "canaux.miroir", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canaux/miroir/ecrire", "canaux.miroir_ecrire", { args: (r) => ({ actif: !!r.body.actif }), sortie: (x) => ok(x) });
})();
