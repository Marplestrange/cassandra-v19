// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Les canaux Telegram : /api/canaux/* -> capacités canaux
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #6beeaa
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les canaux Telegram : /api/canaux/* -> capacités canaux.* du noyau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=6beeaa ▼▼▼
/* Les canaux Telegram : /api/canaux/* -> capacités canaux.* du noyau.
   Différé : la connexion MTProto/Telethon, l'envoi et la réception. */
(function () {
  const P = (c, cap, o) => CASS.route("POST", c, cap, o);
  const ok = (x) => Object.assign({ ok: true }, x);

  P("/api/canaux/etat", "canaux.etat", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canaux/miroir", "canaux.miroir", { args: () => ({}), sortie: (x) => ok(x) });
  P("/api/canaux/miroir/ecrire", "canaux.miroir_ecrire", { args: (r) => ({ actif: !!r.body.actif }), sortie: (x) => ok(x) });
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
