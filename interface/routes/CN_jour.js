/* Aujourd'hui : /api/bureau/jour (V18) -> jour.aujourdhui, qui assemble les signaux déclarés par les modules. */
(function () {
  CASS.route("POST", "/api/bureau/jour", "jour.aujourdhui", { args: () => ({}), sortie: (x) => Object.assign({ ok: true }, x) });
})();
