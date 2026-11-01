// ═════════════════════════════════════════════════════════════════════
// TITRE      : Dolibarr : l'écran de gestion
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #0a3add
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : l'écran de gestion du module dolibarr : à faire, factures, devis, tiers, banque, dons, adhérents, projets, ma clé, requête libre
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.dolibarr) ; toutes les listes se lisent par dolibarr.lire_libre (une page de 100 lignes), tous les gestes passent par les capacités du module, après une confirmation sur place ; tout texte dynamique est échappé
// ═════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=0a3add ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const K = CASS.kit, esc = K.esc, pill = K.pill;
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const eur = (n) => Number(n || 0).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
  const jour = (v) => { if (!v) return "—"; const d = /^\d+$/.test(String(v)) ? new Date(Number(v) * 1000 + 43200000) : new Date(v); return isNaN(d) ? esc(v) : d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }); };
  const iso = (v) => { if (!v) return ""; const d = /^\d+$/.test(String(v)) ? new Date(Number(v) * 1000 + 43200000) : new Date(v); return isNaN(d) ? "" : d.toISOString().slice(0, 10); };
  const retard = (f) => { const e = f.date_lim_reglement; if (!e) return 0; const d = /^\d+$/.test(String(e)) ? Number(e) * 1000 : new Date(e).getTime(); return Math.floor((Date.now() - d) / 864e5); };
  const AUJ = new Date().toISOString().slice(0, 10);
  const CSS = ".sh-scene:has(.kit.dlb){max-width:none;width:100%;flex:1 1 100%;min-width:0}.sh-scene:has(.kit.dlb)>.sh-titre{display:none}.kit.dlb{width:100%}" +
    ".dlb .barre2{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.dlb .t{width:100%;border-collapse:collapse;font-size:13px}.dlb .t th{text-align:left;font:600 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);padding:6px 8px;border-bottom:1px solid var(--line)}" +
    ".dlb .t td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}.dlb .t tr.clk{cursor:pointer}.dlb .t tr.clk:hover td{background:color-mix(in srgb,var(--accent) 7%,transparent)}.dlb .t .num{font-family:ui-monospace,Menlo,monospace;white-space:nowrap}" +
    ".dlb .defil{overflow-x:auto}.dlb .fld{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--txt-faint);font-weight:600}.dlb .in,.kit-m .in{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 11px;font:500 13px 'Inter',sans-serif;min-width:0;max-width:100%}" +
    ".kit-m .fld{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--txt-faint);font-weight:600}.kit-m .grille2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.kit-m [hidden]{display:none!important}.ib{display:inline-flex;align-items:center;gap:5px;outline:none;position:relative}.ib-i{display:inline-grid;place-items:center;width:15px;height:15px;border-radius:50%;border:1px solid var(--line-strong,var(--line));color:var(--txt-faint);font:700 10px 'Inter',sans-serif;font-style:normal;text-transform:none;letter-spacing:0;cursor:help;flex:none}.ib:hover .ib-i,.ib:focus .ib-i{color:var(--accent);border-color:var(--accent)}.ib-b{display:none;position:fixed;z-index:100000;background:var(--surface-solid,#fff);color:var(--txt);border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 34px -14px rgba(16,24,40,.38);padding:11px 13px;font:400 12px/1.5 'Inter',sans-serif;letter-spacing:0;text-transform:none;white-space:normal;text-align:left;cursor:default}.ib:hover .ib-b,.ib:focus .ib-b,.ib:focus-within .ib-b{display:block}.ib-b p{margin:0 0 7px}.ib-b p:last-child{margin:0}.ib-b code{font:11px ui-monospace,Menlo,monospace;background:color-mix(in srgb,var(--txt) 8%,transparent);padding:1px 4px;border-radius:4px}.dlb .ib-page{margin:-2px 0 10px;font-size:12px;color:var(--txt-faint)}.kit-m .in{box-sizing:border-box;max-width:100%}.kit-m select.in,.kit-m input.in{width:100%}.kit-m textarea.in{width:100%;resize:vertical}.dlb .code{background:var(--surface);border:1px dashed var(--line-strong,var(--line));border-radius:10px;padding:10px 12px;font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}";

  // ───────── les infobulles : ce que chaque champ, colonne et page veut dire, avec la règle de Dolibarr quand il y en a une. Du texte écrit ici, jamais une donnée : il peut porter du HTML simple.
  const AIDE = {
    champs: {
      "name": "<p>Raison sociale ou nom d'usage du tiers : une société, une association ou un particulier (saisis alors « Prénom Nom »).</p><p><b>Obligatoire</b> dans Dolibarr.</p>",
      "name_alias": "<p>Nom commercial ou sigle, affiché à côté du nom. Facultatif ; Dolibarr s'en sert aussi dans ses recherches.</p>",
      "client": "<p>La nature du tiers pour Dolibarr :</p><p><b>Client</b> : il a acheté ou achète. <b>Prospect</b> : contact commercial, pas encore client. <b>Prospect / Client</b> : les deux. <b>Ni l'un ni l'autre</b> : par exemple un fournisseur seul.</p><p>Un client reçoit un code client.</p>",
      "fournisseur": "<p><b>Oui</b> si tu achètes à ce tiers : il reçoit un code fournisseur et peut porter des factures d'achat. Un tiers peut être client <i>et</i> fournisseur.</p>",
      "code_client": "<p>Dolibarr le numérote lui-même (par exemple <code>CU2611-00131</code> : CU, l'année et le mois, un numéro).</p><p>Laisse <code>auto</code> ou vide : Cassandra envoie « auto », sans quoi Dolibarr refuse la création (<code>ErrorCustomerCodeRequired</code>).</p>",
      "code_fournisseur": "<p>Numéroté par Dolibarr (par exemple <code>SU2611-00049</code>). Laisse <code>auto</code> ou vide.</p>",
      "tiers.status": "<p><b>Ouvert</b> : le tiers apparaît dans les listes et peut servir sur une pièce.</p><p><b>Fermé</b> : il est gardé avec tout son historique, mais n'est plus proposé.</p>",
      "address": "<p>Adresse postale (rue, numéro, bâtiment). Elle s'imprime sur les devis et factures du tiers.</p>",
      "zip": "<p>Code postal. Avec la ville, il complète l'adresse imprimée sur les pièces.</p>",
      "country_id": "<p>Le pays <b>change les règles</b> : pour la France, le SIREN doit avoir 9 chiffres et le SIRET 14, la liste des départements et celle des formes juridiques sont celles de la France.</p><p>Liste lue dans ton Dolibarr.</p>",
      "state_id": "<p>Département (France) ou région/canton selon le pays. Liste lue dans Dolibarr pour le pays choisi.</p>",
      "phone": "<p>Téléphone fixe. Libre : Dolibarr ne le contrôle pas.</p>",
      "phone_mobile": "<p>Téléphone mobile. Libre.</p>",
      "url": "<p>Adresse du site, <b>avec</b> <code>http://</code> ou <code>https://</code>. Dolibarr refuse une adresse sans cela (<code>ErrorBadUrl</code>).</p>",
      "email": "<p>Adresse de courriel valide. Dolibarr refuse une adresse mal formée (<code>ErrorBadEMail</code>). Elle sert à envoyer les factures.</p>",
      "no_email": "<p><b>Oui</b> : ce tiers ne reçoit pas les envois de masse (mailings) de Dolibarr. Les courriels d'une facture ne sont pas concernés.</p>",
      "town": "<p>Ville. Avec le code postal, elle complète l'adresse imprimée sur les pièces.</p>",
      "fax": "<p>Numéro de fax. Libre : Dolibarr ne le contrôle pas.</p>",
      "twitter": "<p>Identifiant X (anciennement Twitter), sans l'adresse. Rangé avec les autres réseaux sociaux (<code>socialnetworks</code>).</p>",
      "facebook": "<p>Identifiant ou nom de page Facebook. Rangé avec les autres réseaux sociaux (<code>socialnetworks</code>).</p>",
      "linkedin": "<p>Identifiant ou nom de page LinkedIn. Rangé avec les autres réseaux sociaux (<code>socialnetworks</code>).</p>",
      "skype": "<p>Identifiant Skype. Dolibarr 24 le range avec les autres réseaux sociaux (<code>socialnetworks</code>).</p>",
      "idprof1": "<p><b>SIREN</b> : 9 chiffres, l'identifiant de l'entreprise ou de l'association (Insee). Les espaces sont tolérés.</p><p>Contrôlé pour un tiers français. Le SIRET, lui, va dans l'identifiant 2.</p>",
      "idprof2": "<p><b>SIRET</b> : 14 chiffres, le SIREN suivi de 5 chiffres qui désignent l'établissement.</p><p>Contrôlé pour un tiers français.</p>",
      "idprof3": "<p><b>Code NAF/APE</b> : l'activité principale (par exemple <code>90.01Z</code>, arts du spectacle vivant).</p>",
      "idprof4": "<p><b>RCS ou RM</b> : inscription au registre du commerce ou au répertoire des métiers. Vide pour une association.</p>",
      "idprof5": "<p><b>Numéro EORI</b> : opérateurs de douane de l'Union européenne. Utile seulement pour l'import et l'export.</p>",
      "idprof6": "<p><b>Numéro RNA</b> : le répertoire national des associations (la lettre W suivie de 9 chiffres).</p>",
      "tva_assuj": "<p><b>Oui</b> : ce tiers est assujetti à la TVA. <b>Non</b> : il ne l'est pas (par exemple une association non assujettie).</p><p>Dolibarr s'en sert pour choisir la TVA des pièces de ce tiers.</p>",
      "tva_intra": "<p>Numéro de TVA intracommunautaire (en France : <code>FR</code> + 11 caractères). Facultatif.</p>",
      "forme_juridique_code": "<p>Le type d'entité légale (SARL, SAS, association loi 1901 : code 92…). Liste lue dans Dolibarr pour le pays choisi.</p>",
      "typent_id": "<p>Le type de tiers (grande entreprise, PME, administration, association, particulier…). Sert aux statistiques et aux filtres.</p>",
      "effectif_id": "<p>La tranche d'effectifs du tiers. Facultatif.</p>",
      "capital": "<p>Capital social, en euros. Vide pour une association.</p>",
      "default_lang": "<p>La langue des documents et des courriels envoyés à ce tiers. Vide : celle de Dolibarr.</p>",
      "note_public": "<p>Note visible par tous les utilisateurs qui ouvrent la fiche ; Dolibarr peut la reprendre sur certaines pièces selon le modèle d'impression.</p>",
      "note_private": "<p>Note <b>interne</b> : réservée aux utilisateurs de Dolibarr, jamais imprimée.</p>",
      "contacts.civility_code": "<p>Madame, Monsieur, Docteur… Liste lue dans Dolibarr.</p>",
      "lastname": "<p>Nom de famille. <b>Obligatoire</b> dans Dolibarr.</p>",
      "firstname": "<p>Prénom. Facultatif.</p>",
      "contacts.socid": "<p>Le tiers (société, association) auquel ce contact est rattaché. Un contact Dolibarr est normalement rattaché à un tiers ; sans lui il reste un contact isolé.</p>",
      "poste": "<p>Fonction du contact dans son organisation (régie, présidente, comptable…).</p>",
      "contacts.statut": "<p><b>Actif</b> : proposé dans les listes. <b>Inactif</b> : gardé mais non proposé.</p>",
      "priv": "<p><b>Public (partagé)</b> : visible par tous les utilisateurs de Dolibarr. <b>Privé (personnel)</b> : visible seulement par l'utilisateur qui l'a créé.</p>",
      "phone_pro": "<p>Téléphone professionnel du contact.</p>",
      "phone_perso": "<p>Téléphone personnel du contact.</p>",
      "birthday": "<p>Date de naissance. Dolibarr la garde en secondes ; Cassandra la compare comme une date.</p>",
      "ref": "<p>Référence unique. Pour un <b>produit</b>, elle est obligatoire. Pour un <b>projet</b>, laisse <code>auto</code> : Dolibarr le numérote (par exemple <code>PJ2611-0036</code>).</p>",
      "label": "<p>Le libellé affiché sur les devis et factures. <b>Obligatoire</b>.</p>",
      "produits.type": "<p><b>Produit</b> : un bien. <b>Service</b> : une prestation (billetterie, cachet, location).</p>",
      "produits.status": "<p><b>En vente</b> : le produit peut figurer sur un devis ou une facture. <b>Hors vente</b> : il est gardé mais plus proposé.</p>",
      "status_buy": "<p><b>En achat</b> : le produit peut figurer sur une commande ou une facture fournisseur.</p>",
      "barcode": "<p>Code-barres. Facultatif ; unique dans Dolibarr s'il est rempli.</p>",
      "price_base_type": "<p>Le prix saisi est <b>hors taxe</b> (HT) ou <b>toutes taxes comprises</b> (TTC). Dolibarr calcule l'autre à partir du taux de TVA.</p>",
      "price": "<p>Prix de vente unitaire, dans la base choisie.</p>",
      "tva_tx": "<p>Taux de TVA appliqué par défaut à ce produit. Liste des taux lue dans Dolibarr pour la France.</p>",
      "accountancy_code_sell": "<p>Compte comptable des ventes de ce produit.</p><p>Attention : Dolibarr <b>tronque les zéros de fin</b> selon la longueur de compte réglée (<code>706000</code> devient <code>706</code>).</p>",
      "accountancy_code_buy": "<p>Compte comptable des achats de ce produit. Même règle de troncature que pour la vente.</p>",
      "weight": "<p>Poids, dans l'unité choisie. Facultatif.</p>",
      "projets.public": "<p><b>Contacts du projet</b> : visible des personnes qui y sont affectées. <b>Tout le monde</b> : visible de tous les utilisateurs.</p>",
      "projets.status": "<p><b>Brouillon</b> : pas encore ouvert ; il prendra sa référence à la validation. <b>Ouvert</b> : actif, on peut y rattacher des pièces et du temps.</p>",
      "date_start": "<p>Date de début. Dolibarr la garde en secondes ; Cassandra l'envoie comme une date (AAAA-MM-JJ).</p>",
      "date_end": "<p>Date de fin prévue.</p>",
      "budget_amount": "<p>Budget prévu du projet, en euros.</p>",
      "usage_opportunity": "<p><b>Oui</b> : le projet suit une opportunité commerciale (probabilité et montant). Utile pour prévoir un chiffre d'affaires.</p>",
      "opp_percent": "<p>Probabilité (en %) que l'opportunité se réalise.</p>",
      "opp_amount": "<p>Montant attendu si l'opportunité se réalise.</p>",
      "socid": "<p>Le tiers concerné. <b>Obligatoire</b> sur une facture ou un devis.</p>",
      "ref_client": "<p>La référence que <b>le client</b> donne à sa commande (bon de commande, numéro d'engagement). Elle s'imprime sur la pièce et aide au rapprochement.</p>",
      "date": "<p>Date de la pièce (facture, devis) ou du règlement. Sur une facture, elle ouvre le délai de paiement.</p>",
      "date_lim_reglement": "<p>Date limite de paiement. Vide : Dolibarr la calcule d'après les conditions de règlement.</p>",
      "cond_reglement_id": "<p>Les conditions de règlement (à réception, 30 jours fin de mois…). Elles fixent l'échéance quand elle n'est pas saisie. Liste lue dans Dolibarr.</p>",
      "mode_reglement_id": "<p>Le mode de règlement proposé au client (virement, chèque, carte…). Liste lue dans Dolibarr.</p>",
      "fk_account": "<p>Le compte bancaire à indiquer sur la facture pour être payé par virement.</p>",
      "duree_validite": "<p>Nombre de jours pendant lesquels le devis reste valable. La date de fin de validité est la date du devis plus cette durée.</p>",
      "lignes": "<p>Les lignes de la pièce. Choisir un <b>produit</b> reprend sa désignation, son prix et sa TVA ; tu peux les changer.</p><p>Une <b>remise</b> peut être une ligne à prix négatif, ou un pourcentage sur la ligne. Les montants sont <b>hors taxe</b> ; Dolibarr calcule la TVA et le total.</p>",
      "reglement.date": "<p>La date de valeur du règlement. Le solde du compte ne la compte qu'<b>à partir de cette date</b> : un règlement daté du futur n'apparaît pas encore dans le solde.</p>",
      "reglement.mode": "<p>Le mode de règlement (virement, chèque, espèces, carte, prélèvement). Liste lue dans Dolibarr.</p><p>Pour un <b>chèque</b>, Dolibarr exige l'émetteur.</p>",
      "reglement.banque": "<p>Le compte bancaire <b>crédité</b> par ce règlement.</p>",
      "montant": "<p>Le montant, en euros. Pour un règlement : au plus le reste dû ; un montant partiel laisse la facture ouverte, le solde la clôture.</p>",
      "numero": "<p>Le numéro du chèque, ou la référence de la transaction pour un virement ou une carte. Garde-le : il sert au rapprochement bancaire.</p>",
      "emetteur": "<p>Qui a signé le chèque. <b>Obligatoire pour un chèque</b> : Dolibarr refuse sinon (<code>Emetteur is mandatory when payment code is CHQ</code>).</p>",
      "banque_cheque": "<p>La banque sur laquelle le chèque est tiré. Facultatif.</p>",
      "note": "<p>Commentaire gardé sur le règlement, visible dans Dolibarr.</p>",
      "de": "<p>Le compte qui est <b>débité</b>.</p>",
      "vers": "<p>Le compte qui est <b>crédité</b>. Doit être différent du premier.</p>",
      "virement.date": "<p>Date du virement. Comme pour un règlement, le solde ne la compte qu'à partir de cette date.</p>",
      "libelle": "<p>Le libellé inscrit sur les deux lignes bancaires du virement.</p>",
      "don.date": "<p>Date du don.</p>",
      "don.public": "<p><b>Oui</b> : le donateur accepte d'être cité publiquement.</p>",
      "nom": "<p>Nom du donateur.</p><p>Pour le <b>reçu fiscal</b>, Dolibarr exige : un nom ou une société, <b>l'adresse, le code postal, la ville et le courriel</b>. Cassandra ne l'impose pas ici : sans eux, le reçu sera impossible à produire.</p>",
      "prenom": "<p>Prénom du donateur.</p>",
      "societe": "<p>Société ou association donatrice. Remplace le nom si le donateur est une personne morale.</p>",
      "don.address": "<p>Adresse du donateur, nécessaire au reçu fiscal.</p><p>Dolibarr l'enregistre mais son API ne la rend pas à la relecture : un superadministrateur la voit dans la liste, lue directement dans la base.</p>",
      "cotisation.debut": "<p>Début de la période couverte par la cotisation.</p>",
      "fin": "<p>Fin de la période couverte. Dolibarr en fait la <b>fin d'adhésion</b> du membre.</p>",
      "cotisation.libelle": "<p>Le libellé de la cotisation, tel qu'il apparaît chez Dolibarr (par exemple « Cotisation 2026 »).</p>",
      "cotisation.montant": "<p>Montant de la cotisation, en euros.</p>"
    },
    cols: {
      "Réf. client": "La référence que le client a donnée à sa commande.",
      "Date facture": "La date de la facture ; elle ouvre le délai de paiement.",
      "Date d'échéance": "La date limite de paiement. Une facture ouverte dont l'échéance est passée est « en retard ».",
      "Montant HT": "Hors taxe : avant TVA.",
      "Montant TVA": "La TVA de la pièce, calculée par Dolibarr ligne par ligne.",
      "Montant TTC": "Toutes taxes comprises : ce que le client doit au total.",
      "Reçu": "La somme déjà réglée sur la facture (tous les règlements comptés).",
      "Reste à payer": "Ce qui reste dû : le total TTC moins ce qui a été reçu. Vide pour une facture soldée ou en brouillon.",
      "Statut": "L'état de la pièce dans Dolibarr : brouillon (modifiable, sans numéro légal), validée (numérotée, figée), payée, abandonnée…",
      "Fin de validité": "Jusqu'à quand le devis reste valable : sa date plus la durée de validité.",
      "Prospect / Client": "La nature du tiers : client, prospect, ou les deux.",
      "Code client": "Le code attribué par Dolibarr à un client (CU + année et mois + numéro).",
      "Code fournisseur": "Le code attribué par Dolibarr à un fournisseur (SU + année et mois + numéro).",
      "Factures": "Ajout de Cassandra : le nombre de factures de ce tiers dans Dolibarr.",
      "Dû": "Ajout de Cassandra : ce que ce tiers doit encore sur ses factures ouvertes.",
      "Nature": "Produit (un bien) ou service (une prestation), ou pour un adhérent : personne physique ou morale.",
      "Prix de vente HT": "Le prix de vente unitaire hors taxe.",
      "État (vente)": "En vente : le produit peut figurer sur un devis ou une facture.",
      "État (achat)": "En achat : le produit peut figurer sur une commande ou une facture fournisseur.",
      "Type d'adhérent": "Le type de membre (par exemple « Artiste ») : il fixe la cotisation et la durée.",
      "Fin d'adhésion": "La date jusqu'à laquelle la cotisation couvre le membre. Une cotisation enregistrée la repousse.",
      "Donateur": "Le nom, le prénom ou la société du donateur.",
      "Adresse": "Lue directement dans la base de Dolibarr, car son API ne rend pas l'adresse d'un don. Visible des superadministrateurs seulement.",
      "Date du don": "La date à laquelle le don a été fait ou promis.",
      "Visibilité": "Qui voit le projet : les contacts du projet, ou tout le monde.",
      "Date de début": "Le début du projet.",
      "Date de fin": "La fin prévue du projet.",
      "Réf. fournisseur": "La référence que le fournisseur donne à sa facture.",
      "Poste": "La fonction du contact dans son organisation.",
      "Mois": "Le mois de la date de facture.",
      "Enregistrements": "Le nombre de lignes du journal inaltérable : chaque facture validée et chaque règlement y laissent une trace signée."
    },
    pages: {
      afaire: ["À faire", "<p>Ce qui attend un geste : factures en retard à relancer, brouillons à valider, devis signés à facturer, dons à valider.</p><p>Tout est lu dans Dolibarr à l'instant ; chaque bouton ouvre une fenêtre qui te montre ce qui va être écrit avant de le faire.</p>"],
      factures: ["Factures", "<p>Les factures clients de Dolibarr, les plus récentes d'abord. Les colonnes sont celles de la liste de Dolibarr.</p><p>Clique une facture pour la valider, l'encaisser, la relancer, créer un avoir ou voir son PDF. <b>Valider</b> donne le numéro légal et la fige : cela s'inscrit au journal inaltérable et ne se défait pas.</p>"],
      devis: ["Devis", "<p>Les propositions commerciales de Dolibarr. Un devis passe de brouillon à validé, puis à signé, puis se transforme en facture (en brouillon : rien n'est validé à ta place).</p>"],
      tiers: ["Tiers", "<p>Les sociétés, associations et particuliers de Dolibarr : clients, prospects et fournisseurs. La fiche reprend exactement celle de Dolibarr, avec ses règles.</p><p>Les colonnes « Factures » et « Dû » sont un ajout de Cassandra.</p>"],
      contacts: ["Contacts", "<p>Les personnes rattachées aux tiers dans Dolibarr. Les contacts de Cassandra sont dans « Contacts de Cassandra » : tu choisis lesquels envoyer ici.</p>"],
      produits: ["Produits", "<p>Les produits et services de Dolibarr : ceux que la billetterie utilise pour ses factures. Modifier un prix se défait.</p>"],
      fournisseurs: ["Fournisseurs", "<p>Les factures reçues de tes fournisseurs. « Payer » règle <b>tout le reste dû</b> sur un compte bancaire, à la date et avec le numéro que tu donnes.</p>"],
      banque: ["Banque", "<p>Les comptes bancaires de Dolibarr et leur solde. Un virement entre deux comptes crée deux écritures ; un contre-virement le défait.</p><p>Le rapprochement bancaire ligne à ligne reste dans Dolibarr : son API ne le permet pas.</p>"],
      adherents: ["Adhérents", "<p>Les membres de l'association dans Dolibarr. « Cotisation » enregistre une cotisation et repousse la fin d'adhésion.</p>"],
      dons: ["Dons", "<p>Les dons saisis dans Dolibarr : d'abord une promesse, puis validée (elle prend son numéro). Le reçu fiscal se produit dans Dolibarr, sur la fiche du don : son API ne le propose pas.</p>"],
      projets: ["Projets", "<p>Les projets de Dolibarr. Valider un projet lui donne sa référence ; le clore le termine.</p>"],
      cprojets: ["Projets de Cassandra", "<p>Les projets que tu tiens dans Cassandra. Ils restent chez Cassandra tant que tu ne les envoies pas ; envoyé, Dolibarr fait foi pour son titre, ses dates et sa description.</p>"],
      ccontacts: ["Contacts de Cassandra", "<p>Les contacts de ton carnet. Un contact envoyé à Dolibarr y est rattaché à un tiers que tu choisis : il ne devient jamais un tiers tout seul.</p>"],
      itare: ["Itare", "<p>Itare répond sur Dolibarr avec <b>ta clé</b> : il agit sous ton nom, avec tes droits, dans les limites que tu as réglées (« Mon accès »).</p>"],
      acces: ["Mon accès", "<p>La clé d'API de ton utilisateur Dolibarr, rangée dans ton coffre. Avec elle, ce que tu fais et ce que fait ton Itare passe sous ton nom. Sans elle, tu peux lire mais pas écrire (sauf réglage de l'administrateur).</p>"],
      capacites: ["Capacités", "<p>Ce que Cassandra sait faire dans Dolibarr, geste par geste, et le <b>palier</b> de chacun : « raconter » (on prépare, tu approuves) ou « auto ». C'est le choix de l'administrateur.</p>"],
      comptes: ["Comptes", "<p>Qui a une clé personnelle Dolibarr. Réservé aux administrateurs.</p>"],
      instance: ["Instance", "<p>L'état de ta connexion à Dolibarr : version, délai de réponse, nombre d'objets, modules actifs.</p><p>Les superadministrateurs voient en plus des cartes lues <b>directement dans la base</b> : le journal inaltérable, le chiffre d'affaires par mois et les champs personnalisés.</p>"],
      libre: ["Requête libre", "<p>Pour les gestes que l'écran n'a pas encore. <code>GET /chemin</code> lit ; <code>POST</code> ou <code>PUT</code> écrit, après une confirmation, avec relecture. Le chemin doit être dans l'API de Dolibarr ; <code>DELETE</code> n'existe pas ici.</p>"]
    },
    base: {
      carte: "<p>Lu <b>directement dans la base</b> de Dolibarr, en lecture seule, par un utilisateur SQL qui n'a que le droit de lire. Réservé aux <b>superadministrateurs</b>.</p><p>Aucune écriture ne passe par là : elles restent dans l'API de Dolibarr, qui applique ses règles et ses droits.</p>",
      journal: "<p>Le journal inaltérable enchaîne chaque facture validée et chaque règlement avec une signature : une ligne modifiée ou retirée est détectée. Ici : le nombre d'enregistrements, le dernier numéro et sa date.</p><p>Si ce nombre n'avance plus alors que tu valides des factures, le journal est cassé : à regarder tout de suite.</p>",
      ca: "<p>Le total des factures <b>validées ou payées</b>, mois par mois, sur les douze derniers mois (date de facture). Les brouillons et les abandonnées ne comptent pas. Les avoirs sont comptés avec leur signe.</p>",
      champs: "<p>Les champs ajoutés à ton Dolibarr (par les modules ou par toi), par type d'objet. Une étoile * : champ obligatoire.</p><p>Cassandra les lit pour pouvoir, plus tard, les proposer à l'identique dans ses formulaires.</p>"
    }
  };
  // L'infobulle : un « i » qui montre le texte au survol ou au clavier. La bulle se place en « fixed » (elle ne se laisse pas couper par une fenêtre qui défile) et se retourne si elle manque de place.
  const ib = (texte, aide, droite) => '<span class="ib" tabindex="0">' + (texte ? texte + " " : "") + '<span class="ib-i" aria-hidden="true">i</span><span class="ib-b" role="tooltip">' + aide + "</span></span>";
  if (!window.__dlbIb) {
    window.__dlbIb = true;
    const place = (e) => {
      const w = e.target && e.target.closest ? e.target.closest(".ib") : null; if (!w) return;
      const b = w.querySelector(".ib-b"); if (!b) return;
      const r = w.getBoundingClientRect(), L = Math.min(360, window.innerWidth - 24);
      b.style.width = L + "px"; b.style.left = Math.max(12, Math.min(r.left, window.innerWidth - L - 12)) + "px";
      b.style.top = "auto"; b.style.bottom = "auto";
      if (window.innerHeight - r.bottom > 180 || r.top < 200) { b.style.top = Math.min(r.bottom + 8, window.innerHeight - 60) + "px"; } else { b.style.bottom = (window.innerHeight - r.top + 8) + "px"; }
    };
    document.addEventListener("mouseover", place); document.addEventListener("focusin", place);
  }
  const COURANTE = { racine: null };      // la page qui a reçu le dernier clic : à elle les fenêtres qu'elle a ouvertes
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.dolibarr = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("dolibarr", corps); return; }
    K.injecter();
    const anc = document.getElementById("dlb-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "dlb-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "kit dlb"; corps.appendChild(racine);
    const PAGES = {
    d_afaire: "afaire",
    d_tiers: "tiers",
    d_contacts: "contacts",
    d_devis: "devis",
    d_factures: "factures",
    d_produits: "produits",
    d_fournisseurs: "fournisseurs",
    d_banque: "banque",
    d_adherents: "adherents",
    d_dons: "dons",
    d_projets: "projets",
    d_cprojets: "cprojets",
    d_ccontacts: "ccontacts",
    d_itare: "itare",
    d_acces: "acces",
    d_capacites: "capacites",
    d_comptes: "comptes",
    d_instance: "instance",
    d_libre: "libre" };
    const S = { v: {}, onglet: PAGES[String((ctx && ctx.ecran) || "").split(":")[1]] || "afaire", d: {}, q: {}, f: { factures: "ouvertes" }, err: "", occupe: false, acces: null, libre: "", libreRep: null };

    async function lire(chemin, params) { return (await agir("dolibarr.lire_libre", { chemin: chemin, parametres: params || "" })).reponse || []; }
    const liste = (r) => (Array.isArray(r) ? r : []);
    const PAGE = "limit=100&sortfield=t.rowid&sortorder=DESC";
    const CHARGEURS = {
      tiers: async () => liste(await lire("/thirdparties", PAGE + "&properties=id,name,name_alias,code_client,code_fournisseur,zip,town,country_code,phone,email,client,fournisseur,status")),
      contacts: async () => liste(await lire("/contacts", PAGE + "&properties=id,civility_code,lastname,firstname,socid,poste,phone_pro,phone_mobile,email,statut")),
      factures: async () => liste(await lire("/invoices", PAGE + "&properties=id,ref,ref_client,socid,date,date_lim_reglement,total_ht,total_tva,total_ttc,totalpaid,remaintopay,statut,paye,type")),
      devis: async () => liste(await lire("/proposals", PAGE + "&properties=id,ref,ref_client,socid,date,fin_validite,total_ht,total_ttc,statut")),
      projets: async () => liste(await lire("/projects", PAGE + "&properties=id,ref,title,socid,statut,public,date_start,date_end")),
      produits: async () => liste(await lire("/products", PAGE + "&properties=id,ref,label,type,price,tva_tx,status,status_buy,barcode")),
      dons: async () => {
        const l = liste(await lire("/donations", PAGE + "&properties=id,ref,lastname,firstname,societe,amount,date,statut"));
        S.adrdons = null;                                                   // sans lecture de la base (réglage absent, ou compte non superadministrateur) : pas de colonne
        if (l.length) { try { const r = await agir("dolibarr.base_requete", { nom: "don_adresses", parametres: { ids: l.map((d) => Number(d.id)) } }); S.adrdons = {}; (r.lignes || []).forEach((x) => { S.adrdons[String(x.id)] = x; }); } catch (e) { S.adrdons = null; } }
        return l;
      },
      adherents: async () => liste(await lire("/members", PAGE + "&properties=id,ref,firstname,lastname,login,morphy,typeid,email,statut,datefin")),
      cp: async () => liste((await agir("projets.lister")).projets),
      cc: async () => liste((await agir("contacts.lister", { limite: 200 })).contacts),
      liens: async () => liste(await agir("dolibarr.liens")),
      sup: async () => liste(await lire("/supplierinvoices", PAGE + "&properties=id,ref,ref_supplier,socid,date,date_echeance,total_ht,total_ttc,statut,paye")),
      inst: async () => {
        const [r, m, st] = await Promise.all([agir("dolibarr.resume"), agir("dolibarr.modules"), agir("dolibarr.statut")]);
        const o = { r: r || {}, m: m || [], st: st || {}, base: null };
        try {                                                               // la base : superadministrateurs seulement ; les autres ne voient simplement pas ces cartes
          const e = await agir("dolibarr.base_etat");
          if (e && e.actif) { const [j, c, ca] = await Promise.all([agir("dolibarr.base_requete", { nom: "journal_etat" }), agir("dolibarr.base_requete", { nom: "champs_perso" }), agir("dolibarr.base_requete", { nom: "ca_par_mois" })]); o.base = { etat: e, journal: (j.lignes || [])[0] || {}, champs: c.lignes || [], ca: ca.lignes || [] }; }
          else if (e) o.base = { etat: e };
        } catch (e) { o.base = null; }
        return o;
      },
      cat: async () => await agir("dolibarr.catalogue_api"),
      rgl: async () => { const r = await agir("reglages.lire", { module: "dolibarr" }); const o = {}; (r.reglages || []).forEach((x) => { o[x.cle] = x.valeur; }); return o; },
      cpts: async () => { const l = (await agir("comptes.lister")); const cs = liste(l.comptes || l); return await Promise.all(cs.map(async (c) => { const id = c.id || c.compte || c.login || c; let cle = null; try { const r = await agir("reglages.lire", { module: "dolibarr", pour_compte: id }); const x = (r.reglages || []).find((y) => y.cle === "dolibarr.cle_api"); cle = !!(x && (x.valeur || x.defini || x.pose)); } catch (e) { cle = null; } return { id: id, nom: c.nom || c.display_name || id, cle: cle }; })); },
      types: async () => liste(await lire("/members/types", "limit=100")),
      banques: async () => { const l = liste(await lire("/bankaccounts", "limit=100&properties=id,label,clos")); await Promise.all(l.map(async (b) => { try { b.solde = Number((await lire("/bankaccounts/" + b.id + "/balance")) || 0); } catch (e) { b.solde = null; } })); return l; },
    };
    const BESOIN = { afaire: ["factures", "devis", "dons", "tiers"], factures: ["factures", "tiers", "banques"], devis: ["devis", "tiers"], tiers: ["tiers", "factures"], contacts: ["contacts", "tiers"], banque: ["banques"], dons: ["dons"], adherents: ["adherents", "types"], projets: ["projets"], cprojets: ["cp", "liens", "projets"], ccontacts: ["cc", "liens", "tiers"], produits: ["produits"], fournisseurs: ["sup", "tiers", "banques"], instance: ["inst"], capacites: ["cat", "rgl"], comptes: ["cpts"] };
    async function charger(forcer) {
      S.err = ""; const vus = BESOIN[S.onglet] || [];
      await Promise.all(vus.filter((k) => forcer || !S.d[k]).map(async (k) => { try { S.d[k] = await CHARGEURS[k](); } catch (e) { S.err = e.message || String(e); S.d[k] = []; } }));
      if (S.onglet === "acces" && !S.acces) { try { S.acces = await agir("dolibarr.mon_acces"); } catch (e) { S.acces = { erreur: e.message || String(e) }; } }
      dessiner();
    }
    const nomTiers = (id) => { const t = (S.d.tiers || []).find((x) => String(x.id) === String(id)); return t ? t.name : "tiers " + id; };
    const filtrer = (l, k, f) => (l || []).filter((x) => !S.q[k] || JSON.stringify(x).toLowerCase().includes(S.q[k].toLowerCase()) || (f && f(x)));
    const barre = (k, droite) => '<div class="barre2"><input type="search" class="in" data-q="' + k + '" placeholder="Chercher…" value="' + esc(S.q[k] || "") + '" style="flex:1 1 220px"><span style="flex:1"></span>' + (droite || "") + "</div>";
    const seg = (k, opts) => '<div class="seg">' + opts.map((o) => '<button data-f="' + k + '|' + o[0] + '" class="' + ((S.f[k] || opts[0][0]) === o[0] ? "on" : "") + '">' + o[1] + "</button>").join("") + "</div>";
    const etatF = (f) => { const s = String(f.statut); if (s === "0") return pill("Brouillon"); if (s === "3") return pill("Abandonnée"); if (s === "2" || String(f.paye) === "1") return pill("Payée", "ok"); const r = retard(f); return r > 0 ? pill("En retard · " + r + " j", r > 365 ? "dg" : "al") : pill("À encaisser", "ac"); };
    const etiq = (o) => (o.venu ? pill("Venu de Dolibarr", "ac") : o.lien ? pill("Dolibarr · lié", "ok") + ' <span class="note">le ' + jour(o.lien.le) + "</span>" : pill("Cassandra seulement", ""));
    const ouverte = (f) => String(f.statut) === "1" && String(f.paye) !== "1" && Number(f.remaintopay) > 0.005;
    const table = (cols, rows) => '<div class="defil"><table class="t"><thead><tr>' + cols.map((c) => "<th>" + (AIDE.cols[c] ? ib(esc(c), "<p>" + AIDE.cols[c] + "</p>") : c) + "</th>").join("") + "</tr></thead><tbody>" + (rows.join("") || '<tr><td colspan="' + cols.length + '" class="note">Rien ne correspond.</td></tr>') + "</tbody></table></div>";
    const btn = (t, a, p, c) => '<button class="btn mini ' + (c || "") + '" data-a="' + a + '" data-p="' + esc(p == null ? "" : p) + '">' + t + "</button>";

    // ───────── les onglets
    // Les cartes que la lecture de la base ajoute à la page Instance (superadministrateurs).
    const baseCartes = (b) => {
      if (!b) return "";
      const e = b.etat || {};
      if (!e.actif) return '<div class="carte"><h3>' + ib('Base de données', AIDE.base.carte) + '</h3><div class="note">' + esc(e.raison || "La lecture de la base n'est pas réglée.") + "</div></div>";
      const j = b.journal || {}, parObjet = {};
      (b.champs || []).forEach((c) => { (parObjet[c.objet] = parObjet[c.objet] || []).push(c); });
      return '<div class="g2"><div class="carte"><h3>' + ib('Base de données', AIDE.base.carte) + '</h3><dl class="kv"><dt>Serveur</dt><dd>' + esc(e.version || "?") + "</dd><dt>Accès</dt><dd>" + (e.lecture_seule ? pill("lecture seule", "ok") : pill("droits en trop : " + esc((e.droits_en_trop || []).join(", ")), "al")) + "</dd><dt>Tables</dt><dd>" + ((e.tables_manquantes || []).length ? pill("manque : " + esc(e.tables_manquantes.join(", ")), "al") : pill("toutes là", "ok")) + "</dd></dl></div>" +
        '<div class="carte"><h3>' + ib('Journal inaltérable', AIDE.base.journal) + '</h3><dl class="kv"><dt>Enregistrements</dt><dd class="num">' + esc(j.enregistrements || "0") + "</dd><dt>Dernier</dt><dd class=\"num\">" + esc(j.dernier || "—") + "</dd><dt>Date</dt><dd>" + esc(j.derniere_date || "—") + "</dd></dl></div></div>" +
        '<div class="carte"><h3>' + ib('Chiffre d\'affaires par mois', AIDE.base.ca) + '</h3>' + table(["Mois", "Factures", "Montant HT", "TVA", "Montant TTC"], (b.ca || []).map((x) => "<tr><td>" + esc(x.mois) + '</td><td class="num">' + esc(x.factures) + '</td><td class="num">' + eur(x.ht) + '</td><td class="num">' + eur(x.tva) + '</td><td class="num">' + eur(x.ttc) + "</td></tr>")) + "</div>" +
        '<div class="carte"><h3>' + ib('Champs personnalisés de cette instance (' + (b.champs || []).length + ')', AIDE.base.champs) + '</h3>' + (Object.keys(parObjet).length ? Object.keys(parObjet).sort().map((o) => '<div style="margin:6px 0"><b>' + esc(o) + "</b> : " + parObjet[o].map((c) => pill(esc(c.libelle || c.nom) + (String(c.obligatoire) === "1" ? " *" : ""))).join(" ") + "</div>").join("") : '<div class="note">Aucun.</div>') + "</div>";
    };
    const VUES = {
      afaire() {
        const F = S.d.factures || [], ouv = F.filter(ouverte), ret = ouv.filter((f) => retard(f) > 0), rec = ret.filter((f) => retard(f) <= 365), vie = ret.filter((f) => retard(f) > 365);
        const bro = F.filter((f) => String(f.statut) === "0"), sig = (S.d.devis || []).filter((d) => String(d.statut) === "2"), dons = (S.d.dons || []).filter((d) => String(d.statut) === "0");
        const li = (t, d, b) => '<div class="li"><div class="sp"><b>' + t + '</b><div class="note">' + d + '</div></div><div style="display:flex;gap:6px;flex-wrap:wrap">' + b + "</div></div>";
        return '<div class="stats"><div class="stat"><b>' + eur(ouv.reduce((s, f) => s + Number(f.remaintopay || 0), 0)) + "</b><span>à encaisser · " + ouv.length + ' factures</span></div><div class="stat al"><b>' + ret.length + "</b><span>en retard</span></div><div class=\"stat\"><b>" + bro.length + "</b><span>brouillons</span></div><div class=\"stat\"><b>" + sig.length + "</b><span>devis signés à facturer</span></div></div>" +
          '<div class="carte"><h3>À traiter</h3><div class="liste">' +
          (rec.length ? li("Relancer " + rec.length + " factures en retard", eur(rec.reduce((s, f) => s + Number(f.remaintopay), 0)) + " dus. Chaque relance se relit avant d’être gardée.", btn("Voir les factures", "onglet", "factures")) : "") +
          (vie.length ? li(vie.length + " factures de plus d’un an", eur(vie.reduce((s, f) => s + Number(f.remaintopay), 0)) + " : à ne pas relancer par automatisme. Un avoir les solderait si l’expert-comptable décide la perte.", btn("Voir", "onglet", "factures")) : "") +
          bro.map((f) => li("Valider " + esc(f.ref) + " ?", esc(nomTiers(f.socid)) + " · " + eur(f.total_ttc), btn("Valider", "valider", f.id, "pri"))).join("") +
          sig.map((d) => li("Facturer le devis " + esc(d.ref), esc(nomTiers(d.socid)) + " · " + eur(d.total_ttc), btn("Préparer la facture", "facturer", d.id, "pri"))).join("") +
          dons.map((d) => li("Valider le don de " + eur(d.amount), jour(d.date) + " : promesse à valider, puis reçu fiscal", btn("Valider", "donvalider", d.id, "pri"))).join("") +
          ((rec.length || vie.length || bro.length || sig.length || dons.length) ? "" : '<div class="vide">Rien n’attend un geste.</div>') + "</div></div>";
      },
      factures() {
        const f = S.f.factures || "ouvertes", F = filtrer(S.d.factures, "factures", (x) => nomTiers(x.socid).toLowerCase().includes((S.q.factures || "~").toLowerCase())).filter((x) => f === "toutes" || (f === "ouvertes" && ouverte(x)) || (f === "retard" && ouverte(x) && retard(x) > 0) || (f === "brouillons" && String(x.statut) === "0") || (f === "payees" && String(x.paye) === "1"));
        return '<div class="carte">' + barre("factures", btn("+ Nouvelle facture", "nfacture", "", "pri")) + seg("factures", [["ouvertes", "Ouvertes"], ["retard", "En retard"], ["brouillons", "Brouillons"], ["payees", "Payées"], ["toutes", "Toutes"]]) +
          table(["Réf.", "Réf. client", "Date facture", "Date d'échéance", "Tiers", "Montant HT", "Montant TVA", "Montant TTC", "Reçu", "Reste à payer", "Statut"], F.map((x) => '<tr class="clk" data-a="fiche" data-p="' + x.id + '"><td class="num"><b>' + esc(x.ref) + '</b></td><td class="num">' + esc(x.ref_client || "") + "</td><td>" + jour(x.date) + "</td><td>" + (String(x.statut) === "1" ? jour(x.date_lim_reglement) : "—") + "</td><td>" + esc(nomTiers(x.socid)) + '</td><td class="num">' + eur(x.total_ht) + '</td><td class="num">' + eur(x.total_tva) + '</td><td class="num">' + eur(x.total_ttc) + '</td><td class="num">' + (Number(x.totalpaid) ? eur(x.totalpaid) : "—") + '</td><td class="num">' + (ouverte(x) ? eur(x.remaintopay) : "—") + "</td><td>" + etatF(x) + "</td></tr>")) +
          (S.d.factures && S.d.factures.length >= 100 ? '<div class="note">100 lignes affichées : les plus récentes.</div>' : "") + "</div>";
      },
      devis() {
        const L = ["Brouillon", "Ouvert", "Signé", "Refusé", "Facturé"], D = filtrer(S.d.devis, "devis");
        return '<div class="carte">' + barre("devis", btn("+ Nouveau devis", "ndevis", "", "pri")) + table(["Réf.", "Réf. client", "Tiers", "Date", "Fin de validité", "Montant HT", "Montant TTC", "Statut", ""], D.map((d) => {
          const s = String(d.statut); const b = s === "0" ? btn("Valider", "devis", d.id + "|valider") : s === "1" ? btn("Marquer signé", "devis", d.id + "|signer") + btn("Refusé", "devis", d.id + "|refuser") : s === "2" ? btn("Facturer", "facturer", d.id, "pri") : "";
          return "<tr class=\"clk\" data-a=\"fichedevis\" data-p=\"" + d.id + "\"><td class=\"num\"><b>" + esc(d.ref) + "</b></td><td class=\"num\">" + esc(d.ref_client || "") + "</td><td>" + esc(nomTiers(d.socid)) + "</td><td>" + jour(d.date) + "</td><td>" + jour(d.fin_validite) + '</td><td class="num">' + eur(d.total_ht) + '</td><td class="num">' + eur(d.total_ttc) + "</td><td>" + pill(L[Number(s)] || "Annulé", s === "2" ? "ok" : "") + "</td><td>" + b + "</td></tr>";
        })) + "</div>";
      },
      tiers() {
        const T = filtrer(S.d.tiers, "tiers");
        return '<div class="carte">' + barre("tiers", btn("+ Nouveau tiers", "ntiers", "", "pri")) + table(["Nom du tiers", "Alias", "Code client", "Code fournisseur", "Code postal", "Ville", "Pays", "Téléphone", "Courriel", "Prospect / Client", "Fournisseur", "État", "Factures", "Dû"], T.map((t) => { const f = (S.d.factures || []).filter((x) => String(x.socid) === String(t.id)), du = f.filter(ouverte).reduce((s, x) => s + Number(x.remaintopay), 0); return '<tr class="clk" data-a="tiers" data-p="' + t.id + '"><td><b>' + esc(t.name) + "</b></td><td>" + esc(t.name_alias || "") + '</td><td class="num">' + esc(t.code_client || "") + '</td><td class="num">' + esc(t.code_fournisseur || "") + "</td><td>" + esc(t.zip || "") + "</td><td>" + esc(t.town || "") + "</td><td>" + esc(t.country_code || "") + "</td><td>" + esc(t.phone || "") + "</td><td>" + esc(t.email || "") + "</td><td>" + pill((NATURE.find((n) => n[0] === String(t.client)) || [0, "—"])[1], String(t.client) !== "0" ? "ac" : "") + "</td><td>" + (String(t.fournisseur) === "1" ? pill("Oui") : "Non") + "</td><td>" + (String(t.status) === "0" ? pill("Fermé") : pill("Ouvert", "ok")) + '</td><td class="num">' + f.length + '</td><td class="num">' + (du ? eur(du) : "—") + "</td></tr>"; })) + "</div>";
      },
      contacts() {
        const C = filtrer(S.d.contacts, "contacts", (x) => nomTiers(x.socid).toLowerCase().includes((S.q.contacts || "~").toLowerCase()));
        return '<div class="carte">' + barre("contacts", btn("+ Nouveau contact", "ncontact", "", "pri")) + table(["Nom", "Prénom", "Tiers", "Poste", "Téléphone pro", "Mobile", "Courriel", "Statut"], C.map((c) => '<tr class="clk" data-a="contact" data-p="' + c.id + '"><td><b>' + esc(c.lastname || "") + "</b></td><td>" + esc(c.firstname || "") + "</td><td>" + (c.socid && String(c.socid) !== "0" ? esc(nomTiers(c.socid)) : "") + "</td><td>" + esc(c.poste || "") + "</td><td>" + esc(c.phone_pro || "") + "</td><td>" + esc(c.phone_mobile || "") + "</td><td>" + esc(c.email || "") + "</td><td>" + (String(c.statut) === "0" ? pill("Inactif") : pill("Actif", "ok")) + "</td></tr>")) + '<div class="note">Les contacts de Cassandra sont dans « Contacts de Cassandra » : tu choisis lesquels envoyer ici.</div></div>';
      },
      banque() {
        const B = (S.d.banques || []).filter((b) => String(b.clos) !== "1");
        return '<div class="stats">' + B.map((b) => '<div class="stat"><b>' + (b.solde == null ? "?" : eur(b.solde)) + "</b><span>" + esc(b.label) + '</span><div style="margin-top:6px">' + btn("Voir les écritures", "lignesb", b.id) + "</div></div>").join("") + '</div><div class="carte"><h3>Virement entre comptes</h3><div class="note">Le solde des deux comptes est relu après le virement ; un contre-virement le défait.</div><div>' + btn("Virer d’un compte à l’autre", "virement", "", "pri") + "</div></div>";
      },
      dons() {
        const D = S.d.dons || [];
        return '<div class="carte"><div class="barre2"><h3 style="flex:1">Dons</h3>' + btn("+ Nouveau don", "ndon", "", "pri") + "</div>" + table(["Réf.", "Donateur"].concat(S.adrdons ? ["Adresse", "Courriel"] : []).concat(["Date du don", "Montant", "Statut", ""]), D.map((d) => { const a = (S.adrdons || {})[String(d.id)] || {}; return "<tr><td class=\"num\">" + esc(d.ref || d.id) + "</td><td>" + esc((((d.firstname || "") + " " + (d.lastname || "")).trim() || d.societe || "—")) + "</td>" + (S.adrdons ? "<td>" + esc([a.adresse, ((a.code_postal || "") + " " + (a.ville || "")).trim()].filter(Boolean).join(", ") || "—") + "</td><td>" + esc(a.courriel || "") + "</td>" : "") + "<td>" + jour(d.date) + '</td><td class="num">' + eur(d.amount) + "</td><td>" + ({ "-1": pill("Annulé"), "0": pill("Promesse à valider", "al"), "1": pill("Promesse validée", "ok"), "2": pill("Don payé", "ok") }[String(d.statut)] || pill(String(d.statut))) + "</td><td>" + (String(d.statut) === "0" ? btn("Valider", "donvalider", d.id) : "—") + "</td></tr>"; })) + '<div class="note">Le reçu fiscal d’un don se produit dans Dolibarr (fiche du don, « Générer ») : son API ne le propose pas.</div></div>';
      },
      adherents() {
        const T = Object.fromEntries((S.d.types || []).map((t) => [String(t.id), t.label])), A = filtrer(S.d.adherents, "adherents");
        return '<div class="carte">' + barre("adherents", "") + table(["Réf.", "Prénom", "Nom", "Login", "Nature", "Type d'adhérent", "Courriel", "Fin d'adhésion", "Statut", ""], A.map((a) => '<tr><td class="num">' + esc(a.ref || a.id) + "</td><td>" + esc(a.firstname || "") + "</td><td><b>" + esc(a.lastname || a.name || "") + "</b></td><td>" + esc(a.login || "") + "</td><td>" + (a.morphy === "mor" ? "Personne morale" : a.morphy === "phy" ? "Personne physique" : "") + "</td><td>" + esc(T[String(a.typeid)] || a.typeid) + "</td><td>" + esc(a.email || "") + "</td><td>" + jour(a.datefin) + "</td><td>" + ({ "-2": pill("Exclu"), "-1": pill("Brouillon"), "0": pill("Résilié", "al"), "1": pill("Validé", "ok") }[String(a.statut)] || pill(String(a.statut))) + "</td><td>" + btn("Cotisation", "cotis", a.id) + "</td></tr>")) + "</div>";
      },
      projets() {
        const P = filtrer(S.d.projets, "projets"), L = ["Brouillon", "Ouvert", "Clos"];
        return '<div class="carte">' + barre("projets", btn("+ Nouveau projet", "nprojet", "", "pri")) + table(["Réf.", "Libellé", "Tiers", "Date de début", "Date de fin", "Visibilité", "Statut", ""], P.map((p) => "<tr><td class=\"num\">" + esc(p.ref) + "</td><td><b>" + esc(p.title) + "</b></td><td>" + (p.socid && String(p.socid) !== "0" ? esc(nomTiers(p.socid)) : "") + "</td><td>" + jour(p.date_start) + "</td><td>" + jour(p.date_end) + "</td><td>" + (String(p.public) === "1" ? "Tout le monde" : "Contacts du projet") + "</td><td>" + pill(L[Number(p.statut)] || p.statut, String(p.statut) === "1" ? "ok" : "") + "</td><td>" + (String(p.statut) === "0" ? btn("Valider", "projet", p.id + "|valider") : String(p.statut) === "1" ? btn("Clore", "projet", p.id + "|clore") : "") + "</td></tr>")) + "</div>";
      },
      cprojets() {
        const lie = (id) => (S.d.liens || []).find((l) => l.type === "projet" && String(l.id) === String(id)), f = S.f.cprojets || "tous";
        const liesDoli = new Set((S.d.liens || []).filter((l) => l.type === "projet").map((l) => String(l.id_doli)));
        const mien = (S.d.cp || []).map((p) => ({ cle: "p|" + p.id, id: p.id, titre: p.nom, d1: p.debut, d2: p.fin, lien: lie(p.id), venu: false }));
        const venus = (S.d.projets || []).filter((p) => String(p.statut) === "1" && !liesDoli.has(String(p.id))).slice(0, 8).map((p) => ({ cle: "v|" + p.id, id: p.id, titre: p.title, d1: p.date_start, d2: p.date_end, ref: p.ref, venu: true }));
        const L = mien.concat(venus).filter((o) => (f === "tous" || (f === "cass" && !o.lien && !o.venu) || (f === "lie" && o.lien) || (f === "venu" && o.venu)) && (!S.q.cprojets || o.titre.toLowerCase().includes(S.q.cprojets.toLowerCase())));
        return '<div class="carte">' + barre("cprojets", "") + seg("cprojets", [["tous", "Tous"], ["cass", "Cassandra seulement"], ["lie", "Dolibarr · lié"], ["venu", "Venu de Dolibarr"]]) +
          table(["Projet", "Dates", "Étiquette", ""], L.map((o) => '<tr class="clk" data-a="fichec" data-p="' + o.cle + '"><td><b>' + esc(o.titre) + '</b><div class="note">' + esc(o.venu ? o.ref : o.lien ? o.lien.ref : "") + "</div></td><td>" + (o.d1 ? jour(o.d1) : "—") + (o.d2 && o.d2 !== o.d1 ? " → " + jour(o.d2) : "") + "</td><td>" + etiq(o) + "</td><td>" + (!o.venu && !o.lien ? btn("Envoyer à Dolibarr", "envoyerp", o.id) : "") + "</td></tr>")) + '<div class="note">Un projet reste chez Cassandra tant que tu ne l’envoies pas. Envoyé, Dolibarr fait foi pour son titre, ses dates et sa description.</div></div>';
      },
      ccontacts() {
        const lie = (id) => (S.d.liens || []).find((l) => l.type === "contact" && String(l.id) === String(id)), f = S.f.ccontacts || "tous";
        const L = (S.d.cc || []).map((c) => ({ id: c.id, nom: c.display_name, orga: c.company, lien: lie(c.id) })).filter((o) => (f === "tous" || (f === "cass" && !o.lien) || (f === "lie" && o.lien)) && (!S.q.ccontacts || (o.nom + " " + o.orga).toLowerCase().includes(S.q.ccontacts.toLowerCase())));
        return '<div class="carte">' + barre("ccontacts", "") + seg("ccontacts", [["tous", "Tous"], ["cass", "Cassandra seulement"], ["lie", "Dolibarr · lié"]]) +
          table(["Contact", "Organisation", "Étiquette", ""], L.map((o) => '<tr class="clk" data-a="fichec" data-p="c|' + o.id + '"><td><b>' + esc(o.nom) + "</b></td><td>" + esc(o.orga || "—") + "</td><td>" + etiq(o) + (o.lien ? '<div class="note">rattaché au tiers ' + esc(nomTiers(o.lien.tiers)) + "</div>" : "") + "</td><td>" + (o.lien ? "" : btn("Envoyer à Dolibarr", "envoyerc", o.id)) + "</td></tr>")) + '<div class="note">Un contact Dolibarr est toujours rattaché à un tiers que tu choisis : il ne devient jamais un tiers tout seul.</div></div>';
      },
      produits() {
        const P = filtrer(S.d.produits, "produits");
        return '<div class="carte">' + barre("produits", btn("+ Nouveau produit", "nprod", "", "pri")) + table(["Réf.", "Libellé", "Nature", "Prix de vente HT", "TVA", "État (vente)", "État (achat)", ""], P.map((p) => '<tr><td class="num">' + esc(p.ref) + "</td><td><b>" + esc(p.label) + "</b></td><td>" + (String(p.type) === "0" ? "Produit" : "Service") + '</td><td class="num">' + eur(p.price) + '</td><td class="num">' + Number(p.tva_tx || 0) + " %</td><td>" + (String(p.status) === "1" ? pill("En vente", "ok") : pill("Hors vente")) + "</td><td>" + (String(p.status_buy) === "1" ? pill("En achat", "ok") : pill("Hors achat")) + "</td><td>" + btn("Modifier le prix", "prix", p.id) + "</td></tr>")) + '<div class="note">Ce sont les pass et services de la billetterie : elle s’y accroche sans rien recréer.</div></div>';
      },
      fournisseurs() {
        const F = filtrer(S.d.sup, "fournisseurs");
        return '<div class="carte">' + barre("fournisseurs", "") + table(["Réf.", "Réf. fournisseur", "Fournisseur", "Date", "Date d'échéance", "Montant HT", "Montant TTC", "Statut", ""], F.map((f) => '<tr><td class="num"><b>' + esc(f.ref) + '</b></td><td class="num">' + esc(f.ref_supplier || "") + "</td><td>" + esc(nomTiers(f.socid)) + "</td><td>" + jour(f.date) + "</td><td>" + jour(f.date_echeance) + '</td><td class="num">' + eur(f.total_ht) + '</td><td class="num">' + eur(f.total_ttc) + "</td><td>" + (String(f.paye) === "1" || String(f.statut) === "2" ? pill("Payée", "ok") : String(f.statut) === "0" ? pill("Brouillon") : pill("À payer", "al")) + "</td><td>" + (String(f.statut) === "1" && String(f.paye) !== "1" ? btn("Payer", "payersup", f.id, "pri") : "") + "</td></tr>")) + '<div class="note">Pour collecter les factures reçues par courriel, le module emailcollector de Dolibarr doit être actif.</div></div>';
      },
      instance() {
        const i = S.d.inst || { r: {}, m: [], st: {} }, c = i.r.comptes || {}, imp = i.r.impayees || {};
        return '<div class="g2"><div class="carte"><h3>Connexion</h3><dl class="kv"><dt>Version</dt><dd>Dolibarr ' + esc(i.st.version || i.r.version || "?") + "</dd><dt>Réponse</dt><dd>" + (i.st.latence_ms != null ? i.st.latence_ms + " ms" : "—") + "</dd><dt>État</dt><dd>" + pill(i.r.etat === "ok" ? "joignable" : esc(i.r.etat || "inconnu"), i.r.etat === "ok" ? "ok" : "al") + "</dd><dt>Impayées</dt><dd>" + (imp.n != null ? imp.n + " · " + eur(imp.total_ttc) : "—") + '</dd></dl></div><div class="carte"><h3>Données</h3><dl class="kv">' + Object.keys(c).map((k) => "<dt>" + esc(k) + '</dt><dd class="num">' + c[k] + "</dd>").join("") + "</dl></div></div>" +
          '<div class="carte"><h3>' + (i.m || []).length + ' modules actifs</h3><div style="display:flex;gap:6px;flex-wrap:wrap">' + (i.m || []).map((m) => pill(m)).join("") + "</div></div>" + baseCartes(i.base);
      },
      capacites() {
        const c = S.d.cat || { domaines: [], operations: 0 }, g = S.d.rgl || {}, T = c.domaines.reduce((a, d) => [a[0] + d.lire, a[1] + d.creer + d.modifier, a[2] + d.supprimer], [0, 0, 0]);
        return '<div class="stats"><div class="stat"><b>' + c.operations + "</b><span>opérations dans l’API (" + c.domaines.length + ' domaines)</span></div><div class="stat"><b>' + T[0] + '</b><span>pour lire</span></div><div class="stat"><b>' + T[1] + '</b><span>pour créer ou modifier</span></div><div class="stat"><b>' + T[2] + "</b><span>pour supprimer</span></div></div>" +
          '<div class="carte"><h3>Ce que mon Itare peut faire seul</h3><div class="note">Le palier de chaque geste (« raconter » ou « auto ») est choisi par l’administrateur. Tes deux réglages ci-dessous sont plus stricts : ils ne sont jamais plus larges que lui.</div>' +
          '<label class="fld"><span><input type="checkbox" id="g-off"' + (g["dolibarr.itare_ecrire"] === "desactive" ? " checked" : "") + "> Mon Itare n’écrit jamais dans Dolibarr (il lit seulement)</span></label>" + champ("g-seuil", "Seuil en euros : au-dessus, mon Itare ne règle, ne vire ni ne cotise (0 : pas de seuil)", Number(g["dolibarr.itare_seuil"] || 0), "number") +
          '<div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Enregistrer mes réglages", "savegarde", "", "pri") + btn("Régler les paliers (administrateur)", "paliers") + "</div></div>" +
          '<div class="carte"><h3>Le catalogue de l’API</h3>' + table(["Domaine", "Lire", "Créer", "Modifier", "Supprimer"], c.domaines.map((d) => "<tr><td><b>/" + esc(d.domaine) + '</b></td><td class="num">' + d.lire + '</td><td class="num">' + d.creer + '</td><td class="num">' + d.modifier + '</td><td class="num">' + d.supprimer + "</td></tr>")) + '<div class="note">Tout passe par la requête libre, et chaque geste a sa preuve et son retour arrière quand l’acte le permet.</div></div>';
      },
      comptes() {
        const C = S.d.cpts || [];
        return '<div class="carte"><h3>Comptes de Cassandra</h3><div class="note">L’administrateur voit qui a branché sa clé. Il ne voit jamais les clés.</div>' + table(["Compte", "Clé Dolibarr"], C.map((c) => "<tr><td><b>" + esc(c.nom) + '</b></td><td>' + (c.cle === null ? pill("illisible (réservé à l’administrateur)") : c.cle ? pill("clé renseignée", "ok") : pill("aucune clé : il lit, il n’écrit pas", "al")) + "</td></tr>")) + '<div class="note">Un compte sans clé lit mais n’écrit pas. Le réglage « mandat pour tous » (société) change cela, au choix de l’administrateur.</div></div>';
      },
      itare() {
        return '<div class="carte"><h3>Demander à Itare</h3><div class="note">Itare agit avec <b>ta clé</b> et dans la limite de tes réglages : chaque geste passe par les mêmes capacités, avec leur palier, leur preuve et leur retour. Exemples : « Qui me doit de l’argent ? », « Prépare les relances des factures récentes », « Facture 2 jours de son à MONARCH, 260 € la journée ».</div><div class="liste" id="dlb-conv">' + (S.itare || []).map((m) => '<div class="li"><div class="sp"><b>' + (m[0] === "u" ? "Toi" : "Itare") + "</b><div>" + esc(m[1]) + "</div></div></div>").join("") + '</div><div class="barre2"><input class="in" id="dlb-msg" style="flex:1 1 320px" placeholder="Dis-lui quoi faire dans Dolibarr…" autocomplete="off"><button class="btn pri" data-a="itareenvoi">Envoyer</button></div></div>';
      },
      acces() {
        const a = S.acces || {}, o = { compte: "ta clé propre", mandat: "la clé de mandat", fichier: "le fichier de clé" }[a.cle] || "";
        return '<div class="g2"><div class="carte"><h3>Ma clé d’API Dolibarr</h3><div class="note">Mon Itare et moi agissons dans Dolibarr sous le nom de son utilisateur, avec ses droits. La clé est chiffrée, jamais réaffichée ; personne d’autre ne la lit.</div>' +
          (a.erreur ? "<div class=\"alerte dg\">" + esc(a.erreur) + "</div>" : a.cle ? "<div>" + pill("Clé utilisée : " + o, a.cle === "compte" ? "ok" : "al") + " " + pill(a.peut_ecrire ? "peut écrire" : "lecture seule", a.peut_ecrire ? "ok" : "al") + "</div><div class=\"note\">Dolibarr te voit comme « " + esc(a.utilisateur) + " »" + (a.administrateur ? " (administrateur : tous les droits)" : "") + ", dans la société « " + esc(a.societe) + " ».</div>" : "") +
          '<label class="fld">Coller ma clé<input type="password" class="in" id="dlb-cle" autocomplete="off" placeholder="clé d’API"></label><div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Enregistrer dans mon coffre", "savecle", "", "pri") + btn("Retirer ma clé", "rmcle") + btn("Tester", "tester") + "</div></div>" +
          '<div class="carte"><h3>Ce que mon Itare peut faire seul</h3><div class="note">Chaque geste a un palier, réglé par l’administrateur : « raconter » (il prépare, tu approuves) ou « auto ». Aucun geste n’est interdit par le code.</div><div>' + btn("Régler les paliers", "paliers") + "</div></div></div>";
      },
      libre() {
        return '<div class="carte"><h3>Requête libre</h3><div class="note">Tout le catalogue de Dolibarr : par exemple <span class="mono">GET /thirdparties/12</span> ou <span class="mono">PUT /products/3 {"price": 12}</span>. Les secrets sont masqués ; une suppression passe par la corbeille du module.</div><div class="barre2"><input class="in mono" id="dlb-req" style="flex:1 1 320px" value="' + esc(S.libre || "GET /thirdparties?limit=5") + '"><button class="btn pri" data-a="libre">Lancer</button></div>' + (S.libreRep ? '<pre class="code">' + esc(typeof S.libreRep === "string" ? S.libreRep : JSON.stringify(S.libreRep, null, 1)) + "</pre>" : "") + "</div>";
      },
    };
    const ONGLETS = [["afaire", "À faire"], ["factures", "Factures"], ["devis", "Devis"], ["tiers", "Tiers"], ["contacts", "Contacts"], ["banque", "Banque"], ["dons", "Dons"], ["adherents", "Adhérents"], ["projets", "Projets"], ["cprojets", "Projets de Cassandra"], ["ccontacts", "Contacts de Cassandra"], ["produits", "Produits"], ["fournisseurs", "Fournisseurs"], ["itare", "Itare"], ["capacites", "Capacités"], ["comptes", "Comptes"], ["instance", "Instance"], ["acces", "Mon accès"], ["libre", "Requête libre"]];
    function dessiner() {
      const foc = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.q : null, pos = foc ? document.activeElement.selectionStart : 0;
      racine.innerHTML = K.titre((ONGLETS.find((o) => o[0] === S.onglet) || ["", "Dolibarr"])[1], "Dolibarr · chaque geste est relu, journalisé et défaisable.") + (AIDE.pages[S.onglet] ? '<div class="ib-page">' + ib("À quoi sert cette page ?", "<p><b>" + AIDE.pages[S.onglet][0] + "</b></p>" + AIDE.pages[S.onglet][1]) + "</div>" : "") +
        (S.err ? '<div class="alerte dg"><div class="sp">' + esc(S.err) + "</div></div>" : "") + VUES[S.onglet]();
      if (foc) { const n = racine.querySelector('[data-q="' + foc + '"]'); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }
    }

    // ───────── les gestes : une confirmation, puis la capacité
    const fait = async (cap, args, dit, recharge) => { try { await agir(cap, args); K.dire(dit); } catch (e) { K.dire(e.message || String(e), "err"); } if (recharge !== false) { S.d = {}; await charger(true); } };
    // Comme K.confirmer, mais rend aussi ce qui a été saisi : la fenêtre se retire avant que la promesse ne reprenne, on relève donc les champs au clic.
    const modale = (titre, corps, oui) => new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre);
      m.innerHTML = "<h2>" + esc(titre) + "</h2>" + corps + '<div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn pri" data-c="oui">' + esc(oui || "Envoyer à Dolibarr") + "</button></div>";
      const clore = (r) => { if (r) { S.v = {}; m.querySelectorAll("[id]").forEach((e) => { S.v[e.id] = e.type === "checkbox" ? e.checked : e.value; }); } v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(false)); m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) clore(b.dataset.c === "oui"); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(false); });
      document.body.appendChild(v); document.body.appendChild(m); const f = m.querySelector("input,textarea,select,[data-c=non]"); if (f) f.focus();
    });
    const champ = (id, lib, v, t, x) => '<label class="fld">' + lib + '<input class="in" id="' + id + '" type="' + (t || "text") + '" value="' + esc(v == null ? "" : v) + '" ' + (x || "") + "></label>";
    const sel = (id, lib, opts, v) => '<label class="fld">' + lib + '<select class="in" id="' + id + '">' + opts.map((o) => '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(v) ? " selected" : "") + ">" + esc(o[1]) + "</option>").join("") + "</select></label>";
    const val = (id) => { if (S.v && id in S.v) return S.v[id]; const e = document.getElementById(id); return e ? e.value : ""; };
    // ───────── les fiches de Dolibarr 24 : mêmes champs, mêmes libellés, même ordre, mêmes règles (société/card.php). Ce qu'on écrit se retrouve dans Dolibarr à l'identique.
    const NATURE = [["0", "Ni prospect, ni client"], ["1", "Client"], ["2", "Prospect"], ["3", "Prospect / Client"]];
    const LANGUES = [["", ""], ["fr_FR", "Français (France)"], ["en_US", "Anglais (États-Unis)"], ["en_GB", "Anglais (Royaume-Uni)"], ["es_ES", "Espagnol"], ["de_DE", "Allemand"], ["it_IT", "Italien"], ["pt_PT", "Portugais"], ["nl_NL", "Néerlandais"], ["ar_SA", "Arabe"]];
    const SCHEMAS = {
      tiers: { objet: "tiers", chemin: "/thirdparties", nom: "tiers", sections: [
        ["Tiers", [
          { k: "name", l: "Nom du tiers", req: 1 }, { k: "name_alias", l: "Alias" },
          { k: "client", l: "Nature du tiers", t: "select", o: NATURE, d: "1" }, { k: "fournisseur", l: "Fournisseur", t: "select", o: [["0", "Non"], ["1", "Oui"]], d: "0" },
          { k: "code_client", l: "Code client", ph: "auto", aide: "Laisser « auto » : Dolibarr le numérote." }, { k: "code_fournisseur", l: "Code fournisseur", ph: "auto", aide: "Laisser « auto » : Dolibarr le numérote." },
          { k: "status", l: "État", t: "select", o: [["1", "Ouvert"], ["0", "Fermé"]], d: "1" }]],
        ["Coordonnées", [
          { k: "address", l: "Adresse", t: "area", large: 1 }, { k: "zip", l: "Code postal" }, { k: "town", l: "Ville" },
          { k: "country_id", l: "Pays", t: "select", dic: "pays", d: "1" }, { k: "state_id", l: "Département / Canton", t: "select", dic: "departements" },
          { k: "phone", l: "Téléphone" }, { k: "phone_mobile", l: "Téléphone mobile" }, { k: "fax", l: "Fax" }, { k: "url", l: "Web", ph: "https://" }, { k: "email", l: "Courriel", ph: "nom@exemple.fr" },
          { k: "no_email", l: "Refuser les courriels de masse", t: "select", o: [["0", "Non"], ["1", "Oui"]], d: "0" }]],
        ["Réseaux sociaux", [{ k: "skype", l: "Skype" }, { k: "twitter", l: "X (Twitter)" }, { k: "facebook", l: "Facebook" }, { k: "linkedin", l: "LinkedIn" }]],
        ["Identifiants professionnels", [
          { k: "idprof1", l: "Id. prof. 1 (SIREN)", ph: "9 chiffres" }, { k: "idprof2", l: "Id. prof. 2 (SIRET)", ph: "14 chiffres" }, { k: "idprof3", l: "Id. prof. 3 (NAF-APE)" },
          { k: "idprof4", l: "Id. prof. 4 (RCS/RM)" }, { k: "idprof5", l: "Id. prof. 5 (numéro EORI)" }, { k: "idprof6", l: "Id. prof. 6 (numéro RNA)" }]],
        ["TVA", [{ k: "tva_assuj", l: "Assujetti à la TVA", t: "select", o: [["1", "Oui"], ["0", "Non"]], d: "1" }, { k: "tva_intra", l: "Numéro de TVA" }]],
        ["Société", [
          { k: "forme_juridique_code", l: "Type d'entité légale", t: "select", dic: "formes" }, { k: "typent_id", l: "Type de tiers", t: "select", dic: "typent" },
          { k: "effectif_id", l: "Effectifs", t: "select", dic: "effectifs" }, { k: "capital", l: "Capital", t: "number" },
          { k: "default_lang", l: "Langue par défaut", t: "select", o: LANGUES }]],
        ["Notes", [{ k: "note_public", l: "Note publique", t: "area", large: 1 }, { k: "note_private", l: "Note privée", t: "area", large: 1 }]]] }
    };
    const LIGNES = { k: "lignes", l: "Lignes", t: "lignes", req: 1, large: 1 };
    const DOC = (titre, extra) => [
      ["Pièce", [{ k: "socid", l: "Tiers", t: "select", dic: "tiers", req: 1 }, { k: "ref_client", l: "Réf. client" }, { k: "date", l: "Date", t: "date", d: AUJ, req: 1 }].concat(extra || []).concat([
        { k: "cond_reglement_id", l: "Conditions de règlement", t: "select", dic: "conditions" }, { k: "mode_reglement_id", l: "Mode de règlement", t: "select", dic: "modes" }])],
      ["Lignes", [LIGNES]],
      ["Notes", [{ k: "note_public", l: "Note publique", t: "area", large: 1 }, { k: "note_private", l: "Note privée", t: "area", large: 1 }]]];
    SCHEMAS.contacts = { objet: "contacts", nom: "contact", sections: [
      ["Contact", [
        { k: "civility_code", l: "Civilité", t: "select", dic: "civilites" }, { k: "lastname", l: "Nom", req: 1 }, { k: "firstname", l: "Prénom" }, { k: "socid", l: "Tiers", t: "select", dic: "tiers" },
        { k: "poste", l: "Poste / Fonction" }, { k: "statut", l: "État", t: "select", o: [["1", "Actif"], ["0", "Inactif"]], d: "1" }, { k: "priv", l: "Visibilité", t: "select", o: [["0", "Public (partagé)"], ["1", "Privé (personnel)"]], d: "0" }]],
      ["Coordonnées", [
        { k: "address", l: "Adresse", t: "area", large: 1 }, { k: "zip", l: "Code postal" }, { k: "town", l: "Ville" }, { k: "country_id", l: "Pays", t: "select", dic: "pays", d: "1" }, { k: "state_id", l: "Département / Canton", t: "select", dic: "departements" },
        { k: "phone_pro", l: "Téléphone professionnel" }, { k: "phone_perso", l: "Téléphone personnel" }, { k: "phone_mobile", l: "Téléphone mobile" }, { k: "fax", l: "Fax" }, { k: "email", l: "Courriel" },
        { k: "no_email", l: "Refuser les courriels de masse", t: "select", o: [["0", "Non"], ["1", "Oui"]], d: "0" }, { k: "birthday", l: "Date de naissance", t: "date" }, { k: "default_lang", l: "Langue par défaut", t: "select", o: LANGUES }]],
      ["Notes", [{ k: "note_public", l: "Note publique", t: "area", large: 1 }, { k: "note_private", l: "Note privée", t: "area", large: 1 }]]] };
    const REGL = (avecMontant) => ({ nom: "règlement", sections: [["Règlement", [
      { k: "date", l: "Date de règlement", t: "date", d: AUJ, req: 1 }, { k: "mode", l: "Mode de règlement", t: "select", dic: "modescode", d: "VIR", req: 1 }, { k: "banque", l: "Compte bancaire", t: "select", dic: "comptes", req: 1 }]
      .concat(avecMontant ? [{ k: "montant", l: "Montant", t: "number", req: 1 }] : []).concat([{ k: "numero", l: "N° de chèque ou de transaction" }]).concat(avecMontant ? [{ k: "emetteur", l: "Émetteur du chèque", si: ["mode", "CHQ"], req: 1 }, { k: "banque_cheque", l: "Banque du chèque", si: ["mode", "CHQ"] }] : []).concat([{ k: "note", l: "Commentaire", t: "area", large: 1 }])]] });
    SCHEMAS.reglement = REGL(true); SCHEMAS.reglementSup = REGL(false);
    SCHEMAS.virement = { nom: "virement", sections: [["Virement entre comptes", [
      { k: "de", l: "Compte à débiter", t: "select", dic: "comptes", req: 1 }, { k: "vers", l: "Compte à créditer", t: "select", dic: "comptes", req: 1 }, { k: "date", l: "Date", t: "date", d: AUJ, req: 1 },
      { k: "montant", l: "Montant", t: "number", req: 1 }, { k: "libelle", l: "Description", d: "Virement interne", large: 1 }]]] };
    SCHEMAS.don = { nom: "don", sections: [
      ["Don", [{ k: "date", l: "Date du don", t: "date", d: AUJ, req: 1 }, { k: "montant", l: "Montant", t: "number", d: "50", req: 1 }, { k: "public", l: "Don public", t: "select", o: [["0", "Non"], ["1", "Oui"]], d: "0" }]],
      ["Donateur", [{ k: "nom", l: "Nom" }, { k: "prenom", l: "Prénom" }, { k: "societe", l: "Société" }, { k: "email", l: "Courriel" }, { k: "address", l: "Adresse", t: "area", large: 1 }, { k: "zip", l: "Code postal" }, { k: "town", l: "Ville" }, { k: "country_id", l: "Pays", t: "select", dic: "pays", d: "1" }]],
      ["Notes", [{ k: "note_public", l: "Note publique", t: "area", large: 1 }, { k: "note_private", l: "Note privée", t: "area", large: 1 }]]] };
    SCHEMAS.cotisation = { nom: "cotisation", sections: [["Cotisation", [
      { k: "debut", l: "Date de début de cotisation", t: "date", d: AUJ, req: 1 }, { k: "fin", l: "Date de fin de cotisation", t: "date", d: String(new Date().getFullYear() + 1) + AUJ.slice(4) }, { k: "montant", l: "Montant", t: "number", d: "15", req: 1 }, { k: "libelle", l: "Libellé", d: "Cotisation", large: 1 }]]] };
    SCHEMAS.factures = { objet: "factures", nom: "facture", sections: DOC("Facture", [{ k: "date_lim_reglement", l: "Date d'échéance", t: "date" }, { k: "fk_account", l: "Compte bancaire", t: "select", dic: "comptes" }]) };
    SCHEMAS.devis = { objet: "devis", nom: "devis", sections: DOC("Devis", [{ k: "duree_validite", l: "Durée de validité (jours)", t: "number", d: "30" }]) };
    SCHEMAS.produits = { objet: "produits", nom: "produit", sections: [
      ["Produit / Service", [
        { k: "ref", l: "Réf.", req: 1 }, { k: "label", l: "Libellé", req: 1 }, { k: "type", l: "Nature", t: "select", o: [["0", "Produit"], ["1", "Service"]], d: "1" },
        { k: "status", l: "État (vente)", t: "select", o: [["1", "En vente"], ["0", "Hors vente"]], d: "1" }, { k: "status_buy", l: "État (achat)", t: "select", o: [["1", "En achat"], ["0", "Hors achat"]], d: "0" },
        { k: "barcode", l: "Code-barres" }, { k: "url", l: "URL publique", ph: "https://" }, { k: "description", l: "Description", t: "area", large: 1 }]],
      ["Prix de vente", [{ k: "price_base_type", l: "Base de prix", t: "select", o: [["HT", "Hors taxe"], ["TTC", "TTC"]], d: "HT" }, { k: "price", l: "Prix de vente", t: "number", d: "0" }, { k: "tva_tx", l: "Taux de TVA", t: "select", dic: "tva", d: "0" }]],
      ["Comptabilité", [{ k: "accountancy_code_sell", l: "Code comptable (vente)" }, { k: "accountancy_code_buy", l: "Code comptable (achat)" }]],
      ["Notes", [{ k: "note_private", l: "Note privée", t: "area", large: 1 }]]] };
    SCHEMAS.projets = { objet: "projets", nom: "projet", sections: [
      ["Projet", [
        { k: "ref", l: "Réf.", ph: "auto", aide: "Laisser « auto » : Dolibarr le numérote." }, { k: "title", l: "Libellé", req: 1 }, { k: "socid", l: "Tiers", t: "select", dic: "tiers" },
        { k: "public", l: "Visibilité", t: "select", o: [["0", "Contacts du projet"], ["1", "Tout le monde"]], d: "0" }, { k: "status", l: "État", t: "select", o: [["0", "Brouillon"], ["1", "Ouvert"]], d: "1" },
        { k: "date_start", l: "Date de début", t: "date" }, { k: "date_end", l: "Date de fin", t: "date" }, { k: "budget_amount", l: "Budget", t: "number" },
        { k: "usage_opportunity", l: "Suivre une opportunité", t: "select", o: [["0", "Non"], ["1", "Oui"]], d: "0" }, { k: "opp_percent", l: "Probabilité d'opportunité (%)", t: "number" }, { k: "opp_amount", l: "Montant de l'opportunité", t: "number" },
        { k: "description", l: "Description", t: "area", large: 1 }]],
      ["Notes", [{ k: "note_public", l: "Note publique", t: "area", large: 1 }, { k: "note_private", l: "Note privée", t: "area", large: 1 }]]] };
    // Les listes de Dolibarr (dictionnaires), lues une fois dans l'instance : [valeur, libellé].
    const DICO = { cache: {} };
    const dico = async (nom, pays) => {
      const cle = nom + "|" + (pays || ""); if (DICO.cache[cle]) return DICO.cache[cle];
      let l = [];
      try {
        if (nom === "pays") l = liste(await lire("/setup/dictionary/countries", "limit=500&sortfield=label&sortorder=ASC")).map((x) => [String(x.id), x.label]);
        else if (nom === "departements") l = liste(await lire("/setup/dictionary/states", "limit=500&country=" + encodeURIComponent(pays || "1"))).map((x) => [String(x.id), (x.code_departement ? x.code_departement + " " : "") + (x.name || x.nom || "")]);
        else if (nom === "formes") l = liste(await lire("/setup/dictionary/legal_form", "limit=500&country=" + encodeURIComponent(pays || "1"))).map((x) => [String(x.code), x.libelle]);
        else if (nom === "typent") l = liste(await lire("/setup/dictionary/thirdparty_types", "limit=100")).map((x) => [String(x.id), x.label]);
        else if (nom === "effectifs") l = liste(await lire("/setup/dictionary/staff", "limit=100")).map((x) => [String(x.id), x.libelle]);
        else if (nom === "tiers") l = (S.d.tiers && S.d.tiers.length ? S.d.tiers : liste(await lire("/thirdparties", "limit=500&sortfield=t.nom&sortorder=ASC&properties=id,name"))).map((x) => [String(x.id), x.name]);
        else if (nom === "conditions") l = liste(await lire("/setup/dictionary/payment_terms", "limit=100")).map((x) => [String(x.id), x.label]);
        else if (nom === "modes") l = liste(await lire("/setup/dictionary/payment_types", "limit=100")).map((x) => [String(x.id), x.label || x.libelle]);
        else if (nom === "comptes") l = (S.d.banques && S.d.banques.length ? S.d.banques : liste(await lire("/bankaccounts", "limit=100&properties=id,label,clos"))).filter((b) => String(b.clos) !== "1").map((b) => [String(b.id), b.label]);
        else if (nom === "tva") l = Array.from(new Set(liste(await lire("/setup/dictionary/vat", "limit=200&country=1")).map((x) => String(Number(x.taux))))).map((t) => [t, t + " %"]);
        else if (nom === "produits") l = liste(await lire("/products", "limit=200&sortfield=t.ref&sortorder=ASC&properties=id,ref,label,price,tva_tx")).map((x) => [String(x.id), x.ref + " — " + x.label, x]);
        else if (nom === "civilites") l = liste(await lire("/setup/dictionary/civilities", "limit=100")).map((x) => [String(x.code), x.label]);
        else if (nom === "modescode") l = liste(await lire("/setup/dictionary/payment_types", "limit=100")).filter((x) => ["VIR", "CHQ", "LIQ", "CB", "PRE"].includes(String(x.code).toUpperCase())).map((x) => [String(x.code).toUpperCase(), x.label || x.libelle]);
        else if (nom === "devises") l = liste(await lire("/setup/dictionary/currencies", "limit=500")).map((x) => [String(x.code_iso), x.code_iso + " — " + x.label]);
      } catch (e) { l = []; }
      l = nom === "tva" || nom === "modescode" ? l : [["", ""]].concat(l.filter((o) => o[0] !== ""));
      DICO.cache[cle] = l; return l;
    };
    const COURRIEL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
    // Les règles que la fiche de Dolibarr applique avant d'écrire (les mêmes que le module : modules/dolibarr/CN_module.py, _regles_dolibarr).
    const regles = (sch, v, creation) => {
      const e = [];
      sch.sections.forEach((s) => s[1].forEach((f) => { if (creation && f.req && f.t !== "lignes" && (!f.si || String(v[f.si[0]]) === f.si[1]) && !String(v[f.k] || "").trim()) e.push(f.l + " : obligatoire"); }));
      if (sch.sections.some((x) => x[1].some((f) => f.t === "lignes"))) { if (!(v.lines || []).length) e.push("Lignes : au moins une ligne"); else if ((v.lines || []).some((l) => !l.desc && !l.fk_product || !l.qty)) e.push("Lignes : une désignation (ou un produit) et une quantité"); }
      if (v.email && !COURRIEL.test(String(v.email).trim())) e.push("Courriel : adresse invalide");
      if (v.url && !/^https?:\/\/[^\s/]+\.[^\s]{2,}/.test(String(v.url).trim())) e.push("Web : une adresse avec http:// ou https://");
      if (sch.objet === "tiers" && String(v.country_id || "1") === "1") [["idprof1", 9, "SIREN"], ["idprof2", 14, "SIRET"]].forEach((x) => { const s = String(v[x[0]] || "").replace(/\s/g, ""); if (s && !(/^\d+$/.test(s) && s.length === x[1])) e.push(x[2] + " : " + x[1] + " chiffres pour un tiers français"); });
      return e;
    };
    const ligneHtml = (l, opts) => '<tr class="lg"><td><select class="in lg-p">' + (opts.produits || []).map((o) => '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(l.fk_product || "") ? " selected" : "") + ">" + esc(o[1]) + "</option>").join("") + "</select></td>" +
      '<td><input class="in lg-d" value="' + esc(l.desc || "") + '" placeholder="Désignation"></td><td><select class="in lg-t">' + (opts.tva || []).map((o) => '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(l.tva_tx == null ? "0" : Number(l.tva_tx)) ? " selected" : "") + ">" + esc(o[1]) + "</option>").join("") + "</select></td>" +
      '<td><input class="in lg-q" type="number" step="any" value="' + esc(l.qty == null ? "1" : l.qty) + '" style="width:70px"></td><td><input class="in lg-u" type="number" step="0.01" value="' + esc(l.subprice == null ? "0" : l.subprice) + '" style="width:92px"></td>' +
      '<td><input class="in lg-r" type="number" step="any" value="' + esc(l.remise_percent || "0") + '" style="width:64px"></td><td><button class="btn mini" data-lg="del" type="button">×</button></td></tr>';
    const aideChamp = (f, opts, lib) => { const a = AIDE.champs[((opts && opts.__id) ? opts.__id + "." : "") + f.k] || AIDE.champs[f.k]; return a ? ib(lib, a) : lib; };
    const champSchema = (f, v, opts) => {
      if (f.t === "lignes") return '<div class="fld" style="grid-column:1/-1">' + aideChamp(f, opts, esc(f.l) + (f.req ? " *" : "")) + '<div class="defil"><table class="t" id="f-lignes"><thead><tr><th>Produit / service</th><th>Désignation</th><th>TVA</th><th>Qté</th><th>Prix unitaire HT</th><th>Remise %</th><th></th></tr></thead><tbody>' + (v.lines && v.lines.length ? v.lines : [{}]).map((l) => ligneHtml(l, opts)).join("") + '</tbody></table></div><div><button class="btn mini" data-lg="add" type="button">+ Ajouter une ligne</button></div></div>';
      const id = "f-" + f.k, x = v[f.k] != null && v[f.k] !== "" ? v[f.k] : (f.d != null ? f.d : ""), lib = aideChamp(f, opts, esc(f.l) + (f.req ? " *" : ""));
      const style = (f.large ? ' style="grid-column:1/-1"' : "") + (f.si ? ' data-si="' + f.si[0] + "|" + f.si[1] + '"' : "");
      const aide = f.aide ? '<span class="note" style="font-weight:400">' + esc(f.aide) + "</span>" : "";
      if (f.t === "area") return '<label class="fld"' + style + ">" + lib + '<textarea class="in" id="' + id + '" rows="3">' + esc(x) + "</textarea></label>";
      if (f.t === "select") { const o = f.o || (opts && opts[f.dic]) || []; const dej = o.some((y) => String(y[0]) === String(x)); return '<label class="fld"' + style + ">" + lib + '<select class="in" id="' + id + '">' + (dej || x === "" ? "" : '<option value="' + esc(x) + '" selected>' + esc(x) + "</option>") + o.map((y) => '<option value="' + esc(y[0]) + '"' + (String(y[0]) === String(x) ? " selected" : "") + ">" + esc(y[1]) + "</option>").join("") + "</select></label>"; }
      return '<label class="fld"' + style + ">" + lib + '<input class="in" id="' + id + '" type="' + (f.t || "text") + '" value="' + esc(x) + '"' + (f.ph ? ' placeholder="' + esc(f.ph) + '"' : "") + (f.t === "number" ? ' step="any"' : "") + ">" + aide + "</label>";
    };
    // Le formulaire : il reste ouvert tant que la saisie n'est pas valide ou que Dolibarr la refuse, et dit pourquoi (le message de Dolibarr, tel quel).
    const formulaire = async (titre, sch, valeurs, enregistrer, oui) => {
      const v = Object.assign({}, valeurs || {}), pays0 = String(v.country_id || "1");
      const veut = {}; sch.sections.forEach((x) => x[1].forEach((f) => { if (f.dic) veut[f.dic] = 1; if (f.t === "lignes") { veut.produits = 1; veut.tva = 1; } }));
      const opts = { __id: sch.objet || ({ "règlement": "reglement" }[sch.nom] || sch.nom) }; await Promise.all(Object.keys(veut).map(async (n) => { opts[n] = await dico(n, ["departements", "formes"].includes(n) ? pays0 : ""); }));
      return new Promise((fin) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const bg = document.createElement("div"); bg.className = "kit-v"; bg.style.zIndex = 9999;
        const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre);
        m.style.cssText = "max-height:88vh;overflow:auto;width:min(860px,94vw)";
        m.innerHTML = "<h2>" + esc(titre) + "</h2>" + sch.sections.map((s) => '<h3 style="margin:14px 0 6px;font:600 12px Inter,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint)">' + esc(s[0]) + '</h3><div class="grille2">' + s[1].map((f) => champSchema(f, v, opts)).join("") + "</div>").join("") +
          '<div class="alerte dg" id="f-err" style="display:none;margin-top:12px"><div class="sp"></div></div><div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn pri" data-c="oui">' + esc(oui || "Enregistrer") + "</button></div>";
        const clore = (r) => { bg.remove(); m.remove(); fin(r); };
        const lignesLues = () => [...m.querySelectorAll("#f-lignes tbody tr.lg")].map((tr) => { const q = (c) => tr.querySelector(c).value; const l = { desc: q(".lg-d").trim(), qty: Number(q(".lg-q")) || 0, subprice: Number(q(".lg-u")) || 0, tva_tx: Number(q(".lg-t")) || 0 }; if (q(".lg-p")) l.fk_product = Number(q(".lg-p")); if (Number(q(".lg-r"))) l.remise_percent = Number(q(".lg-r")); return l; }).filter((l) => l.desc || l.fk_product);
        m.addEventListener("click", (e) => { const b = e.target.closest("[data-lg]"); if (!b) return; e.stopPropagation(); const tb = m.querySelector("#f-lignes tbody"); if (b.dataset.lg === "add") tb.insertAdjacentHTML("beforeend", ligneHtml({}, opts)); else if (tb.querySelectorAll("tr.lg").length > 1) b.closest("tr").remove(); });
        m.addEventListener("change", (e) => { if (!e.target.classList.contains("lg-p")) return; const tr = e.target.closest("tr"), p = (opts.produits || []).find((o) => String(o[0]) === e.target.value); if (p && p[2]) { tr.querySelector(".lg-d").value = p[2].label || ""; tr.querySelector(".lg-u").value = p[2].price ? Number(p[2].price).toFixed(2) : "0"; const t = String(Number(p[2].tva_tx || 0)), st = tr.querySelector(".lg-t"); if ([...st.options].some((o) => o.value === t)) st.value = t; } });
        const lit = () => { const o = {}; if (m.querySelector("#f-lignes")) o.lines = lignesLues(); sch.sections.forEach((s) => s[1].forEach((f) => { if (f.t === "lignes") return; const e = m.querySelector("#f-" + f.k); if (e && !e.closest("[hidden]") && (String(e.value) !== "" || (valeurs && valeurs.id != null && valeurs[f.k] != null && String(valeurs[f.k]) !== ""))) o[f.k] = e.value; })); return o; };
        const dire = (t) => { const b = m.querySelector("#f-err"); b.style.display = t ? "" : "none"; b.firstChild.textContent = t || ""; };
        const remplir = async (id, nom, pays) => { const e = m.querySelector("#f-" + id); if (!e) return; const cur = e.value, o = await dico(nom, pays); e.innerHTML = o.map((y) => '<option value="' + esc(y[0]) + '"' + (String(y[0]) === cur ? " selected" : "") + ">" + esc(y[1]) + "</option>").join(""); };
        const majSi = () => m.querySelectorAll("[data-si]").forEach((l) => { const [k, vv] = l.dataset.si.split("|"), c = m.querySelector("#f-" + k); l.hidden = !(c && c.value === vv); });
        m.addEventListener("change", majSi); majSi();
        const pays = m.querySelector("#f-country_id"); if (pays) pays.addEventListener("change", () => { remplir("state_id", "departements", pays.value); remplir("forme_juridique_code", "formes", pays.value); });
        bg.addEventListener("click", () => clore(false)); m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(false); });
        m.addEventListener("click", async (e) => {
          const b = e.target.closest("[data-c]"); if (!b) return;
          if (b.dataset.c === "non") return clore(false);
          const saisie = lit(), err = regles(sch, saisie, !valeurs || valeurs.id == null);
          if (err.length) { dire(err.join(" · ")); return; }
          b.disabled = true; dire("");
          try { await enregistrer(saisie); clore(true); } catch (x) { dire(x.message || String(x)); b.disabled = false; }
        });
        document.body.appendChild(bg); document.body.appendChild(m); const f = m.querySelector("input,textarea,select"); if (f) f.focus();
      });
    };
    const banqueOpts = () => (S.d.banques || []).filter((b) => String(b.clos) !== "1").map((b) => [b.id, b.label]);
    const extras = (c) => { const o = {}; Object.keys(c).forEach((k) => { if (!["socid", "lines"].includes(k)) o[k] = c[k]; }); return o; };
    const tiersOpts = () => (S.d.tiers || []).map((t) => [t.id, t.name]);
    const GESTES = {
      onglet: async (p) => {
        const ecran = Object.keys(PAGES).find((k) => PAGES[k] === p), lib = (ONGLETS.find((o) => o[0] === p) || [0, p])[1];
        if (ecran && typeof CASS.ouvrirEcran === "function") { CASS.ouvrirEcran("dolibarr:" + ecran, lib); return; }          // la vraie page : le menu, le fil d'Ariane et le titre suivent
        S.onglet = p; dessiner(); await charger();
      },
      valider: async (p) => { if (await modale("Valider la facture", '<p>Elle prend son numéro légal. Cela se défait tant qu’elle n’est ni payée ni comptabilisée.</p>', "Valider")) await fait("dolibarr.valider_facture", { id: Number(p) }, "Facture validée"); },
      fiche: async (p) => {
        const f = (S.d.factures || []).find((x) => String(x.id) === String(p)); if (!f) return;
        const corpsF = '<div class="note">' + esc(nomTiers(f.socid)) + " · " + jour(f.date) + " · " + eur(f.total_ttc) + (ouverte(f) ? " · reste " + eur(f.remaintopay) : "") + "</div><div>" + etatF(f) + "</div><div style=\"display:flex;gap:6px;flex-wrap:wrap\">" +
          (String(f.statut) === "0" ? btn("Valider", "valider", f.id, "pri") : "") + (ouverte(f) ? btn("Encaisser", "encaisser", f.id, "pri") + btn("Relancer", "relancer", f.id) : "") + (String(f.statut) !== "0" ? btn("Créer un avoir", "avoir", f.id) : "") + (String(f.statut) !== "0" ? btn("Voir le PDF", "pdf", "factures|" + f.id) : "") + "</div>";
        modale("Facture " + f.ref, corpsF, "Fermer");
      },
      encaisser: async (p) => { const f = (S.d.factures || []).find((x) => String(x.id) === String(p)); if (await formulaire("Règlement · " + f.ref, SCHEMAS.reglement, { montant: f.remaintopay }, async (c) => { await agir("dolibarr.encaisser", { id: Number(p), montant: c.montant, banque: Number(c.banque), mode: c.mode, date: c.date, numero: c.numero || "", note: c.note || "", emetteur: c.emetteur || "", banque_cheque: c.banque_cheque || "" }); }, "Enregistrer le règlement")) { K.dire("Règlement enregistré"); S.d = {}; await charger(true); } },
      relancer: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const f = (S.d.factures || []).find((x) => String(x.id) === String(p));
        const msg = "Bonjour,\n\nSauf erreur de notre part, la facture " + f.ref + " du " + jour(f.date) + ", d’un reste dû de " + eur(f.remaintopay) + ", est échue depuis " + retard(f) + " jours.\n\nPourriez-vous nous indiquer la date de règlement prévue ?\n\nBien cordialement,\nLa Maison Bohème";
        if (await modale("Relance · " + f.ref, '<p class="note">La relance est gardée dans l’agenda du tiers. Le courriel part par le module Mandats, qui seul résout l’adresse.</p><label class="fld">Message<textarea class="in" id="r-msg" rows="8">' + esc(msg) + "</textarea></label>", "Garder la relance")) await fait("dolibarr.relancer", { id: Number(p), message: val("r-msg") }, "Relance gardée");
      },
      avoir: async (p) => { document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove()); if (await modale("Créer un avoir", "<p>Un avoir en BROUILLON, relié à la facture, mêmes lignes en négatif. Rien n’est validé.</p>", "Créer le brouillon")) await fait("dolibarr.creer_avoir", { id: Number(p) }, "Avoir préparé"); },
      nfacture: async () => { if (await formulaire("Nouvelle facture (brouillon)", SCHEMAS.factures, { date: AUJ }, async (c) => { await agir("dolibarr.creer_brouillon", { objet: "factures", socid: Number(c.socid), lignes: c.lines, champs: extras(c) }); }, "Créer le brouillon")) { K.dire("Brouillon créé"); S.d = {}; await charger(true); } },
      ndevis: async () => { if (await formulaire("Nouveau devis (brouillon)", SCHEMAS.devis, { date: AUJ }, async (c) => { await agir("dolibarr.creer_brouillon", { objet: "devis", socid: Number(c.socid), lignes: c.lines, champs: extras(c) }); }, "Créer le brouillon")) { K.dire("Devis créé"); S.d = {}; await charger(true); } },
      devis: async (p) => { const [id, action] = p.split("|"); if (await modale("Devis : " + action, "<p>Le statut du devis change ; cela se défait (retour en brouillon).</p>", "Faire")) await fait("dolibarr.devis", { id: Number(id), action: action }, "Devis mis à jour"); },
      facturer: async (p) => { if (await modale("Facturer le devis", "<p>Une facture en brouillon est préparée avec les lignes du devis. Rien n’est validé.</p>", "Préparer la facture")) await fait("dolibarr.facturer_devis", { id: Number(p) }, "Facture préparée"); },
      ncontact: async () => { if (await formulaire("Nouveau contact", SCHEMAS.contacts, {}, async (champs) => { await agir("dolibarr.creer", { objet: "contacts", champs: champs }); }, "Créer")) { K.dire("Contact créé"); S.d = {}; await charger(true); } },
      contact: async (p) => { let c; try { c = await lire("/contacts/" + p); } catch (e) { K.dire(e.message || String(e), "err"); return; } if (!c || c.id == null) { K.dire("Contact introuvable", "err"); return; } if (await formulaire(((c.firstname || "") + " " + (c.lastname || "")).trim(), SCHEMAS.contacts, c, async (champs) => { await agir("dolibarr.modifier", { objet: "contacts", id: Number(p), champs: champs }); }, "Enregistrer")) { K.dire("Contact enregistré"); S.d = {}; await charger(true); } },
      ntiers: async () => { if (await formulaire("Nouveau tiers", SCHEMAS.tiers, {}, async (champs) => { await agir("dolibarr.creer", { objet: "tiers", champs: champs }); }, "Créer")) { K.dire("Tiers créé"); S.d = {}; await charger(true); } },
      fichedevis: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const d = (S.d.devis || []).find((x) => String(x.id) === String(p)); if (!d) return;
        let full = {}; try { full = (await agir("dolibarr.lire_libre", { chemin: "/proposals/" + p })).reponse || {}; } catch (e) { K.dire(e.message || String(e), "err"); }
        const L = ["Brouillon", "Ouvert", "Signé", "Refusé", "Facturé"], s = String(d.statut), nb = (n) => Number(n || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const lignes = (full.lines || []).map((l) => "<tr><td>" + esc(String(l.desc || l.description || l.product_label || "").replace(/<br\s*\/?>/gi, " ").replace(/\s+/g, " ").trim()) + '</td><td class="num">' + nb(l.qty) + '</td><td class="num">' + nb(l.subprice) + '</td><td class="num">' + nb(l.tva_tx) + ' %</td><td class="num">' + nb(l.total_ttc) + " €</td></tr>");
        const gestes = s === "0" ? btn("Valider", "devis", d.id + "|valider", "pri") : s === "1" ? btn("Marquer signé", "devis", d.id + "|signer", "pri") + btn("Refusé", "devis", d.id + "|refuser") : s === "2" ? btn("Facturer", "facturer", d.id, "pri") : "";
        await modale("Propale " + d.ref, '<div class="note">' + esc(nomTiers(d.socid)) + " · " + jour(d.date) + (full.fin_validite ? " · valable jusqu’au " + jour(full.fin_validite) : "") + "</div><div>" + pill(L[Number(s)] || "Annulé", s === "2" ? "ok" : "") + "</div>" +
          table(["Désignation", "Qté", "PU HT", "TVA", "Total"], lignes) + '<p class="num" style="text-align:right">Total HT ' + nb(full.total_ht || d.total_ttc) + " € · TVA " + nb(full.total_tva) + " € · <b>Total TTC " + nb(d.total_ttc) + " €</b></p>" +
          '<div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Voir le PDF", "pdf", "devis|" + d.id, "pri") + gestes + "</div>", "Fermer");
      },
      fichec: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [k, id] = p.split("|");
        if (k === "v") { const d = (S.d.projets || []).find((x) => String(x.id) === String(id)); return void modale(d.title, '<div>' + pill("Venu de Dolibarr", "ac") + ' <span class="mono">' + esc(d.ref) + '</span></div><p class="note">Ce projet est né dans Dolibarr : Cassandra le montre, il se modifie chez Dolibarr.</p>', "Fermer"); }
        const type = k === "p" ? "projet" : "contact", o = (k === "p" ? S.d.cp : S.d.cc || []).find((x) => String(x.id) === String(id)); if (!o) return;
        const lien = (S.d.liens || []).find((l) => l.type === type && String(l.id) === String(id)), nom = k === "p" ? o.nom : o.display_name;
        const corps = lien
          ? "<div>" + etiq({ lien: lien }) + ' <span class="mono">' + esc(lien.ref) + '</span></div><div class="alerte"><div class="sp"><b>Dolibarr fait foi</b> pour ' + (k === "p" ? "le titre, les dates et la description" : "le nom, le courriel, le téléphone et le tiers") + ". Modifier ici envoie la modification à Dolibarr. Restent dans Cassandra : " + (k === "p" ? "les notes, l’équipe, les jalons et les tâches." : "les notes.") + '</div></div><div style="display:flex;gap:6px;flex-wrap:wrap">' + btn("Modifier (part vers Dolibarr)", "modifl", type + "|" + id, "pri") + btn("Détacher", "detacher", type + "|" + id) + '</div><div class="note">« Détacher » rompt le lien et garde les deux copies : rien n’est supprimé, ni chez Dolibarr ni chez Cassandra.</div>'
          : "<div>" + etiq({}) + '</div><p class="note">Cette fiche n’existe que dans Cassandra. Rien ne part vers Dolibarr sans ton clic.</p><div>' + btn("Envoyer à Dolibarr…", k === "p" ? "envoyerp" : "envoyerc", id, "pri") + "</div>";
        await modale(nom, corps, "Fermer");
      },
      envoyerp: async (id) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const o = (S.d.cp || []).find((x) => String(x.id) === String(id));
        const ok = await modale("Envoyer le projet à Dolibarr", '<p class="note">Il y sera créé avec son titre « ' + esc(o.nom) + " », ses dates et sa description. Ses notes, son équipe, ses jalons et ses tâches restent dans Cassandra.</p>" + sel("e-t", "Tiers de rattachement (facultatif)", [["", "Aucun"]].concat(tiersOpts()), "") + '<label class="fld"><span><input type="checkbox" id="e-v"> Le valider tout de suite (il prend sa référence)</span></label>', "Envoyer");
        if (ok) await fait("dolibarr.envoyer_projet", { id: Number(id), tiers: val("e-t") === "" ? "" : Number(val("e-t")), valider: val("e-v") === true }, "Projet envoyé");
      },
      envoyerc: async (id) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const o = (S.d.cc || []).find((x) => String(x.id) === String(id));
        const ok = await modale("Envoyer le contact à Dolibarr", '<p class="note">Un contact Dolibarr est toujours rattaché à un tiers. Choisis-le, ou nomme celui à créer : le contact ne devient jamais un tiers.</p>' + sel("e-t", "Rattacher à un tiers existant", [["", "— en créer un —"]].concat(tiersOpts()), "") + champ("e-nt", "… ou créer ce tiers", o.company || ""), "Envoyer");
        if (ok) await fait("dolibarr.envoyer_contact", { id: Number(id), tiers: val("e-t") === "" ? "" : Number(val("e-t")), nouveau_tiers: val("e-t") === "" ? val("e-nt") : "" }, "Contact envoyé");
      },
      modifl: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [type, id] = p.split("|");
        const ok = await modale("Modifier chez Dolibarr", type === "projet" ? champ("m-a", "Titre", "") + champ("m-b", "Description", "") : champ("m-a", "Courriel", "") + champ("m-b", "Téléphone", ""), "Envoyer");
        if (!ok) return;
        const champs = type === "projet" ? { title: val("m-a"), description: val("m-b") } : { email: val("m-a"), phone_pro: val("m-b") };
        Object.keys(champs).forEach((k) => { if (champs[k] === "") delete champs[k]; });
        if (!Object.keys(champs).length) return K.dire("Rien à modifier", "err");
        await fait("dolibarr.modifier_lie", { type: type, id: Number(id), champs: champs }, "Modification envoyée à Dolibarr");
      },
      detacher: async (p) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const [type, id] = p.split("|");
        if (await modale("Détacher de Dolibarr", "<p>Le lien est rompu, les deux copies restent. L’étiquette redevient « Cassandra seulement ».</p>", "Détacher")) await fait("dolibarr.detacher", { type: type, id: Number(id) }, "Fiche détachée");
      },
      lignesb: async (id) => {
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const b = (S.d.banques || []).find((x) => String(x.id) === String(id)); let L;
        try { L = liste((await agir("dolibarr.lire_libre", { chemin: "/bankaccounts/" + id + "/lines", parametres: "limit=100&sortfield=rowid&sortorder=DESC" })).reponse); } catch (e) { return K.dire(e.message || String(e), "err"); }
        L.sort((x, y) => Number(y.dateo) - Number(x.dateo) || Number(y.id) - Number(x.id));
        L = L.slice(0, 300);
        const nonR = L.filter((l) => String(l.rappro) !== "1" && l.fk_type !== "SOLD").length;
        await modale("Écritures · " + (b ? b.label : "compte " + id), '<div class="note">' + L.length + " écritures · " + nonR + " non rapprochées. Un règlement enregistré depuis une facture crée sa propre ligne ici ; le rapprochement avec un relevé se fait dans Dolibarr.</div>" +
          table(["Date", "Libellé", "Mode", "Montant", "Rapprochée"], L.map((l) => "<tr><td>" + jour(l.dateo) + "</td><td>" + esc(l.label || "") + '</td><td class="num">' + esc(l.fk_type || "") + '</td><td class="num" style="color:' + (Number(l.amount) < 0 ? "var(--danger)" : "var(--ok)") + '">' + eur(l.amount) + "</td><td>" + (String(l.rappro) === "1" ? pill("oui" + (l.num_releve ? " · " + esc(l.num_releve) : ""), "ok") : l.fk_type === "SOLD" ? "—" : pill("non", "al")) + "</td></tr>")), "Fermer");
      },
      nprod: async () => {
        if (await formulaire("Nouveau produit ou service", SCHEMAS.produits, {}, async (champs) => { await agir("dolibarr.creer", { objet: "produits", champs: champs }); }, "Créer")) { K.dire("Produit créé"); S.d = {}; await charger(true); }
      },
      prix: async (id) => {
        const p = (S.d.produits || []).find((x) => String(x.id) === String(id));
        if (await modale("Prix de " + p.label, champ("n-p", "Nouveau prix HT", Number(p.price), "number", 'step="0.01"'), "Modifier")) await fait("dolibarr.modifier", { objet: "produits", id: Number(id), champs: { price: Number(val("n-p")), price_base_type: "HT" } }, "Prix modifié");
      },
      payersup: async (id) => { const f = (S.d.sup || []).find((x) => String(x.id) === String(id)); if (await formulaire("Règlement · " + f.ref + " (Dolibarr règle tout le reste dû : " + eur(f.total_ttc) + ")", SCHEMAS.reglementSup, {}, async (c) => { await agir("dolibarr.payer_fournisseur", { id: Number(id), banque: Number(c.banque), mode: c.mode, date: c.date, numero: c.numero || "", note: c.note || "" }); }, "Payer")) { K.dire("Facture payée"); S.d = {}; await charger(true); } },
      savegarde: async () => {
        const off = document.getElementById("g-off").checked, seuil = Number(document.getElementById("g-seuil").value) || 0;
        try { await agir("reglages.regler", { cle: "dolibarr.itare_ecrire", valeur: off ? "desactive" : "libre" }); await agir("reglages.regler", { cle: "dolibarr.itare_seuil", valeur: seuil }); K.dire("Réglages enregistrés"); S.d.rgl = null; await charger(true); } catch (e) { K.dire(e.message || String(e), "err"); }
      },
      itareenvoi: async () => {
        const e = document.getElementById("dlb-msg"), m = (e && e.value || "").trim(); if (!m) return;
        S.itare = (S.itare || []).concat([["u", m]]); dessiner();
        try { const r = await agir("agents.converser", { conversation_id: S.conv || 0, message: "[Dolibarr, avec ma clé] " + m, agent: "itare" }); S.conv = r.conversation_id || S.conv; const pannes = (r.actions || []).filter((a) => a && a.erreur).map((a) => a.erreur); S.itare.push(["i", String(r.reponse || r.message || r.texte || r.resume || (pannes.length ? "Je ne peux pas répondre : " + pannes.join(" ; ") : "(Itare a répondu sans texte)"))]); }
        catch (x) { S.itare.push(["i", "Je n’ai pas pu : " + (x.message || String(x))]); }
        dessiner();
      },
      pdf: async (p) => {
        const [objet, id] = p.split("|"); document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        let r; try { r = await agir("dolibarr.piece_pdf", { objet: objet, id: Number(id) }); }
        catch (e) {
          if (/pas de PDF/.test(e.message || "")) { if (await modale("Pas encore de PDF", "<p>Dolibarr n’a pas encore produit le PDF de cette pièce. Il peut le faire maintenant ; le geste se défait.</p>", "Produire le PDF")) { await fait("dolibarr.produire_pdf", { objet: objet, id: Number(id) }, "PDF produit", false); return GESTES.pdf(p); } return; }
          return K.dire(e.message || String(e), "err");
        }
        const oct = Uint8Array.from(atob(r.donnees_b64), (c) => c.charCodeAt(0)), url = URL.createObjectURL(new Blob([oct], { type: "application/pdf" }));
        // pas d'attribut sandbox : le lecteur PDF du navigateur a besoin de scripter son document (même choix que le visionneur de la GED)
        const fin = modale("PDF · " + r.nom, '<iframe id="dlb-pdf" title="' + esc(r.nom) + '" style="width:100%;height:70vh;border:0;border-radius:8px;background:#fff"></iframe><div class="note">' + esc(r.ref) + " · " + Math.round(r.taille / 1024) + " Ko · produit par Dolibarr</div>", "Fermer");
        const cadre = document.getElementById("dlb-pdf"); if (cadre) cadre.src = url; fin.then(() => URL.revokeObjectURL(url));
      },
      tiers: async (p) => { let t; try { t = await lire("/thirdparties/" + p); } catch (e) { K.dire(e.message || String(e), "err"); return; } if (!t || t.id == null) { K.dire("Tiers introuvable", "err"); return; } t = Object.assign({}, t, (t.socialnetworks && !Array.isArray(t.socialnetworks)) ? t.socialnetworks : {}); if (await formulaire(t.name, SCHEMAS.tiers, t, async (champs) => { await agir("dolibarr.modifier", { objet: "tiers", id: Number(p), champs: champs }); }, "Enregistrer")) { K.dire("Tiers enregistré"); S.d = {}; await charger(true); } },
      virement: async () => { if (banqueOpts().length < 2) return K.dire("Il faut deux comptes ouverts", "err"); if (await formulaire("Virement entre comptes", SCHEMAS.virement, {}, async (c) => { await agir("dolibarr.virement_interne", { de: Number(c.de), vers: Number(c.vers), montant: c.montant, date: c.date, libelle: c.libelle || "" }); }, "Virer")) { K.dire("Virement fait"); S.d = {}; await charger(true); } },
      ndon: async () => { if (await formulaire("Nouveau don", SCHEMAS.don, {}, async (c) => { const x = Object.assign({}, c), a = { montant: x.montant, date: x.date, nom: x.nom || "", prenom: x.prenom || "", societe: x.societe || "" }; ["montant", "date", "nom", "prenom", "societe"].forEach((k) => delete x[k]); await agir("dolibarr.don_creer", Object.assign(a, { champs: x })); }, "Saisir la promesse")) { K.dire("Promesse saisie"); S.d = {}; await charger(true); } },
      donvalider: async (p) => { if (await modale("Valider le don", "<p>Le don prend son numéro. Dolibarr ne le repasse pas en promesse par l’API.</p>", "Valider")) await fait("dolibarr.don_valider", { id: Number(p) }, "Don validé"); },
      cotis: async (p) => { if (await formulaire("Cotisation", SCHEMAS.cotisation, {}, async (c) => { await agir("dolibarr.cotisation", { membre: Number(p), montant: c.montant, debut: c.debut, fin: c.fin || "", libelle: c.libelle || "" }); }, "Enregistrer")) { K.dire("Cotisation enregistrée"); S.d = {}; await charger(true); } },
      nprojet: async () => { if (await formulaire("Nouveau projet", SCHEMAS.projets, {}, async (champs) => { await agir("dolibarr.creer", { objet: "projets", champs: champs }); }, "Créer")) { K.dire("Projet créé"); S.d = {}; await charger(true); } },
      projet: async (p) => { const [id, action] = p.split("|"); if (await modale("Projet : " + action, "<p>Le statut du projet change ; cela se défait.</p>", "Faire")) await fait("dolibarr.projet", { id: Number(id), action: action }, "Projet mis à jour"); },
      savecle: async () => { const v = val("dlb-cle").trim(); if (!v) return K.dire("Colle d’abord ta clé", "err"); try { await agir("reglages.regler_secret", { cle: "dolibarr.cle_api", valeur: v }); K.dire("Clé enregistrée dans ton coffre"); S.acces = null; await charger(); } catch (e) { K.dire(e.message || String(e), "err"); } },
      rmcle: async () => { if (await modale("Retirer ma clé", "<p>Ni toi ni ton Itare n’écrirez plus dans Dolibarr sous ton nom.</p>", "Retirer")) { try { await agir("reglages.reinitialiser", { cle: "dolibarr.cle_api" }); K.dire("Clé retirée"); S.acces = null; await charger(); } catch (e) { K.dire(e.message || String(e), "err"); } } },
      tester: async () => { S.acces = null; await charger(); },
      paliers: async () => {
        if (typeof CASS.console !== "function") return K.dire("La console des paliers n'est pas disponible ici", "err");
        document.querySelectorAll(".kit-m,.kit-v").forEach((e) => e.remove());
        const fin = modale("Paliers de Dolibarr", '<div id="dlb-console" style="min-height:120px">Lecture…</div><div class="note">Le palier de chaque geste est le choix de l’administrateur : « raconter » (on prépare, tu approuves) ou « auto ».</div>', "Fermer");
        const h = document.getElementById("dlb-console"); if (h) { h.textContent = ""; try { await CASS.console("dolibarr", h); } catch (e) { h.textContent = e.message || String(e); } }
        await fin;
      },
      libre: async () => {
        S.libre = val("dlb-req").trim(); const m = S.libre.match(/^(GET|POST|PUT)\s+(\/[^\s?]*)(\?\S*)?\s*(\{[\s\S]*\})?$/i); if (!m) return K.dire("Format : GET /chemin  ou  PUT /chemin {json}", "err");
        try {
          if (m[1].toUpperCase() === "GET") S.libreRep = (await agir("dolibarr.lire_libre", { chemin: m[2], parametres: (m[3] || "").slice(1) })).reponse;
          else if (await modale(m[1].toUpperCase() + " " + m[2], '<div class="code">' + esc(m[4] || "{}") + "</div><p class=\"note\">Relu après l’écriture ; défaisable quand l’acte le permet.</p>")) S.libreRep = await agir("dolibarr.ecrire_libre", { methode: m[1].toUpperCase(), chemin: m[2], corps: m[4] ? JSON.parse(m[4]) : {} });
        } catch (e) { S.libreRep = "Erreur : " + (e.message || String(e)); }
        dessiner();
      },
    };
    // le tiroir de fiche (K.confirmer) ne porte pas nos boutons : on délègue sur tout le document pour ses data-a
    // Chaque page montée garde son gestionnaire sur le document (le shell garde les pages cachées) : sans cette garde, UN clic déclenchait le geste dans TOUTES les pages montées,
    // donc plusieurs écritures. Seule répond la page qui a reçu le clic, ou qui a ouvert la fenêtre où il a eu lieu.
    const clic = (e) => {
      const b = e.target.closest("[data-a]"); if (!b || !GESTES[b.dataset.a]) return;
      if (!racine.isConnected) { document.removeEventListener("click", clic); return; }
      if (racine.contains(e.target)) { COURANTE.racine = racine; }
      else if (!(e.target.closest(".kit-m") && COURANTE.racine === racine)) return;
      e.preventDefault();
      if (e.target.closest(".kit-m")) document.querySelectorAll(".kit-m,.kit-v").forEach((x) => x.remove());      // un geste lancé depuis une fiche la remplace : sinon la fenêtre de confirmation s'empile sur une fiche qui devient périmée
      GESTES[b.dataset.a](b.dataset.p);
    };
    document.addEventListener("click", clic);
    racine.addEventListener("click", (e) => { const o = e.target.closest("[data-o]"); if (o) { GESTES.onglet(o.dataset.o); return; } const f = e.target.closest("[data-f]"); if (f) { const [k, v] = f.dataset.f.split("|"); S.f[k] = v; dessiner(); } });
    racine.addEventListener("input", (e) => { const k = e.target.dataset && e.target.dataset.q; if (k) { S.q[k] = e.target.value; dessiner(); } });
    racine.innerHTML = '<div class="vide">Lecture de Dolibarr…</div>';
    // Le shell garde les pages cachées : revenir sur une page déjà vue la montrait périmée. À chaque retour (8 s au moins après la dernière lecture), on relit.
    S.vu = Date.now();
    if ("IntersectionObserver" in window) new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting) && !S.occupe && Date.now() - S.vu > 8000) { S.vu = Date.now(); S.d = {}; charger(); } }).observe(racine);
    await charger();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de l'écran et ses gestes.
// EC : néant.
// LIEN : modules/dolibarr (le module et ses capacités), interface/CN_kit.js (les composants), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce fichier).
