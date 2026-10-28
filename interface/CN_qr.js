// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Un générateur de QR code (mode octets, correction M, versions 1 à 10), sans bibliothèque :
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f38c21
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Un générateur de QR code (mode octets, correction M, versions 1 à 10), sans bibliothèque : les billets doivent s'afficher partout, même sans réseau.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f38c21 ▼▼▼
// Un générateur de QR code (mode octets, correction M, versions 1 à 10), sans bibliothèque : les billets doivent s'afficher partout, même sans réseau.
// CASS.qr.matrice(texte, masque?) rend le tableau de modules ; CASS.qr.svg(texte, {taille, marge}) rend le dessin prêt à insérer.
(function () {
  "use strict";
  const CASS = window.CASS = window.CASS || {};
  const ECC = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26], NB = [0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5];     // codes de correction par bloc, nombre de blocs (niveau M)
  const modulesBruts = (v) => { let r = (16 * v + 128) * v + 64; if (v >= 2) { const n = Math.floor(v / 7) + 2; r -= (25 * n - 10) * n - 55; if (v >= 7) r -= 36; } return r; };
  const donnees = (v) => Math.floor(modulesBruts(v) / 8) - ECC[v] * NB[v];
  const EXP = new Array(512), LOG = new Array(256);
  (function () { let x = 1; for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11d; } for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255]; })();
  const mul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);
  function diviseur(deg) { const r = new Array(deg).fill(0); r[deg - 1] = 1; let racine = 1; for (let i = 0; i < deg; i++) { for (let j = 0; j < deg; j++) { r[j] = mul(r[j], racine); if (j + 1 < deg) r[j] ^= r[j + 1]; } racine = mul(racine, 2); } return r; }
  function reste(data, div) { const r = new Array(div.length).fill(0); data.forEach((b) => { const f = b ^ r.shift(); r.push(0); div.forEach((c, i) => { r[i] ^= mul(c, f); }); }); return r; }

  function octets(texte) { return Array.from(new TextEncoder().encode(String(texte))); }
  function mots(data, v) {
    const bits = [], pousse = (val, n) => { for (let i = n - 1; i >= 0; i--) bits.push((val >>> i) & 1); };
    pousse(4, 4); pousse(data.length, v >= 10 ? 16 : 8); data.forEach((b) => pousse(b, 8));
    const cap = donnees(v) * 8;
    pousse(0, Math.min(4, cap - bits.length)); pousse(0, (8 - bits.length % 8) % 8);
    for (let pad = 0xEC; bits.length < cap; pad ^= 0xEC ^ 0x11) pousse(pad, 8);
    const out = new Array(bits.length / 8).fill(0); bits.forEach((b, i) => { out[i >> 3] |= b << (7 - (i & 7)); });
    return out;
  }
  function entrelacer(data, v) {
    const nb = NB[v], lecc = ECC[v], brut = Math.floor(modulesBruts(v) / 8), courts = nb - brut % nb, longCourt = Math.floor(brut / nb), div = diviseur(lecc), blocs = [];
    for (let i = 0, k = 0; i < nb; i++) { const dat = data.slice(k, k + longCourt - lecc + (i < courts ? 0 : 1)); k += dat.length; const e = reste(dat, div); if (i < courts) dat.push(0); blocs.push(dat.concat(e)); }
    const out = [];
    for (let i = 0; i < blocs[0].length; i++) blocs.forEach((b, j) => { if (i !== longCourt - lecc || j >= courts) out.push(b[i]); });
    return out;
  }
  function matrice(texte, forceMasque) {
    const data = octets(texte); let v = 1;
    while (v <= 10 && data.length + (v >= 10 ? 3 : 2) > donnees(v)) v++;
    if (v > 10) throw new Error("Texte trop long pour un QR code");
    const taille = v * 4 + 17, mod = [], fn = [];
    for (let y = 0; y < taille; y++) { mod.push(new Array(taille).fill(false)); fn.push(new Array(taille).fill(false)); }
    const poser = (x, y, noir) => { mod[y][x] = noir; fn[y][x] = true; };
    for (let i = 0; i < taille; i++) { poser(6, i, i % 2 === 0); poser(i, 6, i % 2 === 0); }
    const repere = (cx, cy) => { for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) { const d = Math.max(Math.abs(dx), Math.abs(dy)), x = cx + dx, y = cy + dy; if (x >= 0 && x < taille && y >= 0 && y < taille) poser(x, y, d !== 2 && d !== 4); } };
    repere(3, 3); repere(taille - 4, 3); repere(3, taille - 4);
    const pos = []; if (v > 1) { const n = Math.floor(v / 7) + 2, pas = Math.ceil((v * 4 + 4) / (n * 2 - 2)) * 2; pos.push(6); for (let p = taille - 7; pos.length < n; p -= pas) pos.splice(1, 0, p); }
    pos.forEach((cy, i) => pos.forEach((cx, j) => { if ((i === 0 && j === 0) || (i === 0 && j === pos.length - 1) || (i === pos.length - 1 && j === 0)) return; for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) poser(cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1); }));
    const format = (masque) => {
      const d = (0 << 3) | masque; let r = d; for (let i = 0; i < 10; i++) r = (r << 1) ^ ((r >>> 9) * 0x537);
      const bits = ((d << 10) | r) ^ 0x5412, b = (i) => ((bits >>> i) & 1) !== 0;
      for (let i = 0; i <= 5; i++) poser(8, i, b(i)); poser(8, 7, b(6)); poser(8, 8, b(7)); poser(7, 8, b(8)); for (let i = 9; i < 15; i++) poser(14 - i, 8, b(i));
      for (let i = 0; i < 8; i++) poser(taille - 1 - i, 8, b(i)); for (let i = 8; i < 15; i++) poser(8, taille - 15 + i, b(i)); poser(8, taille - 8, true);
    };
    format(0);
    if (v >= 7) { let r = v; for (let i = 0; i < 12; i++) r = (r << 1) ^ ((r >>> 11) * 0x1F25); const bits = (v << 12) | r; for (let i = 0; i < 18; i++) { const b = ((bits >>> i) & 1) !== 0, a = taille - 11 + i % 3, c = Math.floor(i / 3); poser(a, c, b); poser(c, a, b); } }
    const tout = entrelacer(mots(data, v), v);
    for (let i = 0, droite = taille - 1; droite >= 1; droite -= 2) {
      if (droite === 6) droite = 5;
      for (let vert = 0; vert < taille; vert++) for (let j = 0; j < 2; j++) { const x = droite - j, haut = ((droite + 1) & 2) === 0, y = haut ? taille - 1 - vert : vert; if (!fn[y][x] && i < tout.length * 8) { mod[y][x] = ((tout[i >>> 3] >>> (7 - (i & 7))) & 1) !== 0; i++; } }
    }
    const COND = [(x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x) => x % 3 === 0, (x, y) => (x + y) % 3 === 0, (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => x * y % 2 + x * y % 3 === 0, (x, y) => (x * y % 2 + x * y % 3) % 2 === 0, (x, y) => ((x + y) % 2 + x * y % 3) % 2 === 0];
    const masquer = (m) => { for (let y = 0; y < taille; y++) for (let x = 0; x < taille; x++) if (!fn[y][x] && COND[m](x, y)) mod[y][x] = !mod[y][x]; };
    const penalite = () => {
      let p = 0;
      for (let y = 0; y < taille; y++) for (const lig of [mod[y], mod.map((r) => r[y])]) { let run = 1; for (let x = 1; x < taille; x++) { if (lig[x] === lig[x - 1]) { run++; if (run === 5) p += 3; else if (run > 5) p++; } else run = 1; } }
      for (let y = 0; y < taille - 1; y++) for (let x = 0; x < taille - 1; x++) { const c = mod[y][x]; if (c === mod[y][x + 1] && c === mod[y + 1][x] && c === mod[y + 1][x + 1]) p += 3; }
      const sch = [true, false, true, true, true, false, true], motif = (lig, i) => { for (let k = 0; k < 7; k++) if (lig[i + k] !== sch[k]) return false; return true; };
      for (let y = 0; y < taille; y++) for (const lig of [mod[y], mod.map((r) => r[y])]) for (let x = 0; x + 7 <= taille; x++) if (motif(lig, x)) { const av = x >= 4 && !lig.slice(x - 4, x).some(Boolean), ap = x + 11 <= taille && !lig.slice(x + 7, x + 11).some(Boolean); if (av || ap) p += 40; }
      let noirs = 0; mod.forEach((r) => r.forEach((c) => { if (c) noirs++; }));
      p += Math.floor(Math.abs(noirs * 20 - taille * taille * 10) / (taille * taille)) * 10;
      return p;
    };
    let meilleur = forceMasque, min = Infinity;
    if (meilleur == null) for (let m = 0; m < 8; m++) { masquer(m); format(m); const p = penalite(); if (p < min) { min = p; meilleur = m; } masquer(m); }
    masquer(meilleur); format(meilleur);
    return mod;
  }
  function svg(texte, o) {
    o = o || {}; const m = matrice(texte), marge = o.marge == null ? 4 : o.marge, n = m.length + 2 * marge; let d = "";
    m.forEach((r, y) => { let x = 0; while (x < r.length) { if (r[x]) { let l = 1; while (x + l < r.length && r[x + l]) l++; d += "M" + (x + marge) + " " + (y + marge) + "h" + l + "v1h-" + l + "z"; x += l; } else x++; } });
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + n + " " + n + '" width="' + (o.taille || 200) + '" height="' + (o.taille || 200) + '" shape-rendering="crispEdges" role="img" aria-label="QR code du billet"><rect width="100%" height="100%" fill="#fff"/><path d="' + d + '" fill="#000"/></svg>';
  }
  CASS.qr = { matrice: matrice, svg: svg };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
