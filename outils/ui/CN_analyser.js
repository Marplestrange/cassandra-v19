// Analyse du JS de l'interface V18 : les instructions de premier niveau, leurs noms, leur taille, ce qu'elles lisent au chargement.
// usage : node CN_analyser.js ../../docs/v18/CN_interface_v18.js > CN_rapport.json
const fs = require("fs");
const acorn = require("acorn");
const src = fs.readFileSync(process.argv[2], "utf8");
const ast = acorn.parse(src, { ecmaVersion: "latest", sourceType: "script", locations: false });

function nomsDeclares(n) {
  if (n.type === "FunctionDeclaration" || n.type === "ClassDeclaration") return [n.id.name];
  if (n.type === "VariableDeclaration") {
    const out = [];
    const motif = (p) => {
      if (p.type === "Identifier") out.push(p.name);
      else if (p.type === "ObjectPattern") p.properties.forEach((q) => motif(q.value || q.argument));
      else if (p.type === "ArrayPattern") p.elements.forEach((q) => q && motif(q));
      else if (p.type === "AssignmentPattern") motif(p.left);
      else if (p.type === "RestElement") motif(p.argument);
    };
    n.declarations.forEach((d) => motif(d.id));
    return out;
  }
  return [];
}

// identifiants lus (toutes profondeurs) et identifiants lus AU CHARGEMENT (hors corps de fonctions imbriquées)
function lus(node, auChargement) {
  const out = new Set();
  const visiter = (n, dansFonction) => {
    if (!n || typeof n.type !== "string") return;
    if (n.type === "Identifier") { if (!(auChargement && dansFonction)) out.add(n.name); return; }
    const fonction = n.type === "FunctionDeclaration" || n.type === "FunctionExpression" || n.type === "ArrowFunctionExpression";
    for (const k of Object.keys(n)) {
      if (k === "type" || k === "start" || k === "end") continue;
      const v = n[k];
      if (Array.isArray(v)) v.forEach((x) => visiter(x, dansFonction || fonction));
      else if (v && typeof v.type === "string") {
        if ((n.type === "MemberExpression" && k === "property" && !n.computed)) continue;
        if (n.type === "Property" && k === "key" && !n.computed) continue;
        visiter(v, dansFonction || fonction);
      }
    }
  };
  visiter(node, false);
  return out;
}

const rapport = ast.body.map((n, i) => ({
  i, type: n.type, debut: n.start, fin: n.end, taille: n.end - n.start,
  noms: nomsDeclares(n),
  lit_au_chargement: n.type === "FunctionDeclaration" ? [] : [...lus(n, true)],
}));
fs.writeFileSync(process.argv[3] || "CN_rapport.json", JSON.stringify(rapport));
const types = {};
rapport.forEach((r) => (types[r.type] = (types[r.type] || 0) + 1));
console.log(JSON.stringify(types));
console.log("instructions", rapport.length);
