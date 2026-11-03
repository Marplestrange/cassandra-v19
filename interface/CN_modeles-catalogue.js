// ═════════════════════════════════════════════════════════════════
// TITRE      : Modèles : le catalogue
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #4b0855
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : les fiches des modèles que la page « Modèles & clés » propose : les modèles qu'Ollama installe sur la machine, et ceux des fournisseurs en ligne. Des données, pas du code.
// MÉTHODE    : un tableau par famille ; les tailles sont celles d'Ollama pour la quantification par défaut (Q4), arrondies ; les prix sont des ordres de grandeur à vérifier chez le fournisseur ; « fr » est une appréciation de 1 à 3, pas une mesure.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=4b0855 ▼▼▼
(function () {
  "use strict";
  // L'EXIGENCE DES AGENTS : un agent appelle des outils. Un modèle sans appel d'outils (« outils: false ») sait converser, pas agir : Cassandra ne peut pas s'en servir.
  const L = (nom, fam, edit, go, params, ctx, licence, o) => Object.assign({ nom: nom, famille: fam, editeur: edit, go: go, params: params, ctx: ctx, licence: licence, outils: false, vision: false, raisonne: false, code: false, embed: false, fr: 2, forces: [], limites: [], usage: "" }, o);

  const LOCAL = [
    // ── Qwen (Alibaba) : le meilleur rapport taille / outils / français pour les petites machines
    L("qwen2.5:0.5b", "Qwen 2.5", "Alibaba", 0.4, "0,5 Md", 32, "Apache 2.0", { outils: true, fr: 1, desc: "Minuscule : il tient n'importe où, mais il raisonne peu.", forces: ["Démarre en une seconde", "Tient sur une machine de 2 Go"], limites: ["Se trompe vite sur une consigne longue", "Trop faible pour piloter des outils de façon fiable"], usage: "Un essai de plomberie, jamais un agent." }),
    L("qwen2.5:1.5b", "Qwen 2.5", "Alibaba", 1.0, "1,5 Md", 32, "Apache 2.0", { outils: true, fr: 1, desc: "Léger, correct sur des tâches courtes et cadrées.", forces: ["Rapide même sans carte graphique"], limites: ["Perd le fil au-delà de quelques échanges"], usage: "Classer, résumer court, reformuler." }),
    L("qwen2.5:3b", "Qwen 2.5", "Alibaba", 1.9, "3 Md", 32, "Qwen Research (usage non commercial)", { outils: true, fr: 2, desc: "Le choix par défaut de Cassandra : il appelle des outils et parle français.", forces: ["Appelle des outils", "Français correct", "Tient sur 4 Go de mémoire"], limites: ["Réponses parfois creuses", "Licence de recherche : à vérifier pour un usage commercial"], usage: "Conversation et petites actions sur une machine modeste." }),
    L("qwen2.5:7b", "Qwen 2.5", "Alibaba", 4.7, "7 Md", 128, "Apache 2.0", { outils: true, fr: 3, desc: "Nettement plus fiable que le 3b : le premier palier où un agent tient la route.", forces: ["Appelle bien les outils", "Bon français", "Licence libre"], limites: ["Lent sans carte graphique", "Demande 8 Go de mémoire"], usage: "Cassandra sur une machine de 8 Go ou plus." }),
    L("qwen2.5:14b", "Qwen 2.5", "Alibaba", 9.0, "14 Md", 128, "Apache 2.0", { outils: true, fr: 3, desc: "Très bon généraliste local, à condition d'avoir la mémoire.", forces: ["Raisonne bien", "Suit des consignes longues"], limites: ["Très lent sur processeur", "16 Go de mémoire au moins"], usage: "Un serveur avec carte graphique ou beaucoup de mémoire." }),
    L("qwen2.5:32b", "Qwen 2.5", "Alibaba", 20, "32 Md", 128, "Apache 2.0", { outils: true, fr: 3, desc: "Proche des modèles en ligne pour beaucoup de tâches.", forces: ["Qualité élevée", "Outils fiables"], limites: ["32 Go de mémoire", "Inutilisable sans carte graphique"], usage: "Une station dédiée." }),
    L("qwen2.5-coder:7b", "Qwen 2.5 Coder", "Alibaba", 4.7, "7 Md", 128, "Apache 2.0", { outils: true, code: true, fr: 2, desc: "Spécialisé en code : lecture de scripts, de configurations, de journaux.", forces: ["Comprend le code et les fichiers de configuration"], limites: ["Moins à l'aise en conversation générale"], usage: "Aide à la maintenance : nginx, systemd, scripts." }),
    // ── Qwen 3 : raisonnement optionnel
    L("qwen3:1.7b", "Qwen 3", "Alibaba", 1.4, "1,7 Md", 32, "Apache 2.0", { outils: true, raisonne: true, fr: 2, desc: "Petit modèle qui peut réfléchir avant de répondre.", forces: ["Appelle des outils", "Léger"], limites: ["Réfléchit à voix haute : lent à la première réponse"], usage: "Petites machines qui veulent un peu de raisonnement." }),
    L("qwen3:4b", "Qwen 3", "Alibaba", 2.5, "4 Md", 32, "Apache 2.0", { outils: true, raisonne: true, fr: 2, desc: "Plus fin que qwen2.5:3b, mais il réfléchit longuement avant de répondre.", forces: ["Raisonne", "Appelle des outils"], limites: ["Sur processeur, la réflexion dépasse vite le délai d'un tour d'agent", "Réponses vides possibles si le budget de jetons est court"], usage: "Si tu acceptes d'attendre. Préfère la variante « instruct » pour un agent." }),
    L("qwen3:4b-instruct", "Qwen 3", "Alibaba", 2.5, "4 Md", 32, "Apache 2.0", { outils: true, fr: 3, desc: "La variante qui répond sans réfléchir à voix haute : celle qu'il faut pour un agent.", forces: ["Appelle des outils", "Répond directement", "Bon français"], limites: ["Pas de mode raisonnement"], usage: "Le meilleur choix local sur une machine de 8 Go." }),
    L("qwen3:8b", "Qwen 3", "Alibaba", 5.2, "8 Md", 32, "Apache 2.0", { outils: true, raisonne: true, fr: 3, desc: "Solide, avec un mode raisonnement.", forces: ["Outils fiables", "Raisonne"], limites: ["Lent sur processeur", "10 Go de mémoire confortables"], usage: "Machine de 16 Go." }),
    L("qwen3:14b", "Qwen 3", "Alibaba", 9.3, "14 Md", 32, "Apache 2.0", { outils: true, raisonne: true, fr: 3, desc: "Très bon niveau pour un modèle local.", forces: ["Qualité proche des modèles en ligne"], limites: ["16 Go de mémoire au moins", "Carte graphique conseillée"], usage: "Serveur avec carte graphique." }),
    // ── Llama (Meta)
    L("llama3.2:1b", "Llama 3.2", "Meta", 1.3, "1 Md", 128, "Licence Llama", { outils: true, fr: 1, desc: "Très petit, grand contexte.", forces: ["Ultra léger", "Long contexte"], limites: ["Faible en raisonnement et en français"], usage: "Tâches très simples." }),
    L("llama3.2:3b", "Llama 3.2", "Meta", 2.0, "3 Md", 128, "Licence Llama", { outils: true, fr: 2, desc: "Polyvalent et rapide, français pris en charge.", forces: ["Appelle des outils", "Long contexte (128 k)"], limites: ["Un peu moins précis que qwen2.5:3b sur les outils"], usage: "Alternative légère à Qwen." }),
    L("llama3.1:8b", "Llama 3.1", "Meta", 4.9, "8 Md", 128, "Licence Llama", { outils: true, fr: 2, desc: "Référence des modèles de 8 milliards de paramètres.", forces: ["Outils", "Long contexte", "Très répandu"], limites: ["Français honnête, sans plus", "Licence Llama (conditions d'usage)"], usage: "Généraliste sur 8 à 16 Go." }),
    L("llama3.3:70b", "Llama 3.3", "Meta", 43, "70 Md", 128, "Licence Llama", { outils: true, fr: 3, desc: "Niveau d'un grand modèle en ligne, mais il faut une vraie machine.", forces: ["Qualité élevée"], limites: ["48 Go de mémoire (carte graphique)", "Hors de portée d'un serveur ordinaire"], usage: "Station de calcul." }),
    // ── Mistral (France)
    L("mistral:7b", "Mistral 7B", "Mistral AI", 4.1, "7 Md", 32, "Apache 2.0", { outils: true, fr: 3, desc: "Le modèle français : à l'aise dans la langue.", forces: ["Très bon français", "Appelle des outils", "Licence libre"], limites: ["Dépassé en raisonnement par les modèles plus récents"], usage: "Conversation et rédaction en français." }),
    L("mistral-nemo:12b", "Mistral Nemo", "Mistral AI · NVIDIA", 7.1, "12 Md", 128, "Apache 2.0", { outils: true, fr: 3, desc: "Plus gros et très bon en français, avec un long contexte.", forces: ["Français excellent", "Long contexte", "Outils"], limites: ["12 Go de mémoire", "Lent sur processeur"], usage: "Rédaction, courrier, synthèse en français." }),
    L("mistral-small:24b", "Mistral Small", "Mistral AI", 14, "24 Md", 32, "Apache 2.0", { outils: true, fr: 3, desc: "Haut niveau, orienté usage professionnel.", forces: ["Qualité élevée", "Outils fiables"], limites: ["24 Go de mémoire", "Carte graphique conseillée"], usage: "Serveur dédié." }),
    // ── Gemma (Google)
    L("gemma2:2b", "Gemma 2", "Google", 1.6, "2 Md", 8, "Conditions Gemma", { fr: 2, desc: "Très léger, bon pour sa taille. Il n'appelle pas d'outils.", forces: ["Rapide", "Réponses propres"], limites: ["PAS d'appel d'outils : inutilisable par un agent", "Contexte court (8 k)"], usage: "Résumés, reformulations, sans action." }),
    L("gemma2:9b", "Gemma 2", "Google", 5.4, "9 Md", 8, "Conditions Gemma", { fr: 3, desc: "Excellent en conversation, mais sans outils.", forces: ["Très bonne qualité de texte"], limites: ["PAS d'appel d'outils", "Contexte court (8 k)"], usage: "Rédaction, pas d'action." }),
    L("gemma3:4b", "Gemma 3", "Google", 3.3, "4 Md", 128, "Conditions Gemma", { vision: true, fr: 3, desc: "Lit les images et parle bien français, avec un long contexte.", forces: ["Lit les images", "Long contexte", "Bon français"], limites: ["Pas d'appel d'outils natif : à éviter pour un agent"], usage: "Lecture de pièces jointes et de scans, hors agent." }),
    L("gemma3:12b", "Gemma 3", "Google", 8.1, "12 Md", 128, "Conditions Gemma", { vision: true, fr: 3, desc: "Très bon modèle généraliste avec vision.", forces: ["Vision", "Qualité élevée"], limites: ["Pas d'appel d'outils natif", "12 Go de mémoire"], usage: "Lecture de documents illustrés." }),
    // ── Microsoft
    L("phi3.5", "Phi 3.5", "Microsoft", 2.2, "3,8 Md", 128, "MIT", { fr: 1, desc: "Petit et bon en raisonnement court, mais surtout en anglais.", forces: ["Compact", "Long contexte"], limites: ["PAS d'appel d'outils", "Français faible"], usage: "Questions courtes en anglais." }),
    L("phi4-mini", "Phi 4 mini", "Microsoft", 2.5, "3,8 Md", 128, "MIT", { outils: true, fr: 2, desc: "Petit modèle récent qui appelle des outils.", forces: ["Outils", "Raisonnement correct pour sa taille"], limites: ["Français moyen"], usage: "Alternative à qwen2.5:3b." }),
    L("phi4:14b", "Phi 4", "Microsoft", 9.1, "14 Md", 16, "MIT", { fr: 2, desc: "Très bon en raisonnement, sans appel d'outils.", forces: ["Raisonne bien"], limites: ["PAS d'appel d'outils", "Contexte court (16 k)", "16 Go de mémoire"], usage: "Analyse, pas d'action." }),
    // ── Raisonnement
    L("deepseek-r1:7b", "DeepSeek R1", "DeepSeek", 4.7, "7 Md", 128, "MIT", { raisonne: true, fr: 1, desc: "Pense longuement avant de répondre : bon en logique, lent, bavard.", forces: ["Raisonnement pas à pas"], limites: ["PAS d'appel d'outils", "Réflexion très longue sur processeur", "Français faible"], usage: "Problèmes de logique, pas un agent." }),
    L("deepseek-r1:14b", "DeepSeek R1", "DeepSeek", 9.0, "14 Md", 128, "MIT", { raisonne: true, fr: 2, desc: "La version qui raisonne sérieusement, pour qui a la mémoire.", forces: ["Raisonnement"], limites: ["PAS d'appel d'outils", "16 Go de mémoire", "Très lent sans carte graphique"], usage: "Analyse approfondie." }),
    // ── Images
    L("llava:7b", "LLaVA", "Communauté", 4.7, "7 Md", null, "Apache 2.0", { vision: true, fr: 1, desc: "Décrit et lit des images.", forces: ["Lit les images"], limites: ["Pas d'outils", "Français faible", "Qualité de lecture limitée"], usage: "Décrire une photo ou un scan." }),
    L("llama3.2-vision:11b", "Llama 3.2 Vision", "Meta", 7.8, "11 Md", 128, "Licence Llama", { vision: true, fr: 2, desc: "Lit les images avec une bonne précision.", forces: ["Vision de bon niveau"], limites: ["Pas d'appel d'outils", "12 Go de mémoire"], usage: "Lecture de documents scannés, factures." }),
    // ── Recherche par le sens (pas de conversation)
    L("nomic-embed-text", "Nomic Embed", "Nomic AI", 0.3, "137 M", 8, "Apache 2.0", { embed: true, fr: 2, desc: "Transforme du texte en vecteurs pour la recherche par le sens. Il ne converse pas.", forces: ["Minuscule", "Rapide"], limites: ["Ne sert pas à dialoguer", "Cassandra utilise déjà son propre moteur de sens (e5)"], usage: "Seulement si un outil externe en a besoin." }),
    L("bge-m3", "BGE M3", "BAAI", 1.2, "567 M", 8, "MIT", { embed: true, fr: 3, desc: "Recherche par le sens multilingue, très bon en français.", forces: ["Multilingue", "Long contexte"], limites: ["Ne converse pas"], usage: "Alternative à e5 pour la recherche." }),
  ];

  // [fournisseur, modèle, contexte (k), prix ordre de grandeur, outils, vision, raisonne, fr, description, forces, limites]
  const E = (fournisseur, nom, ctx, prix, o) => Object.assign({ fournisseur: fournisseur, nom: nom, ctx: ctx, prix: prix, outils: true, vision: false, raisonne: false, fr: 3, desc: "", forces: [], limites: [], usage: "" }, o);
  const ONLINE = [
    E("deepseek", "deepseek-chat", 64, "€", { desc: "Très bon rapport qualité prix, bon en français et en code.", forces: ["Très bon marché", "Outils", "Bon niveau général"], limites: ["Serveurs en Chine : les données partent hors d'Europe", "Débit variable aux heures chargées"], usage: "Cassandra au quotidien, à bas coût." }),
    E("deepseek", "deepseek-reasoner", 64, "€", { raisonne: true, outils: false, desc: "Raisonne longuement avant de répondre.", forces: ["Raisonnement fort"], limites: ["Appels d'outils non fiables : à éviter pour un agent", "Plus lent"], usage: "Analyse approfondie, hors agent." }),
    E("openai", "gpt-4o-mini", 128, "€", { vision: true, desc: "Rapide et économique, lit les images.", forces: ["Outils fiables", "Vision", "Rapide"], limites: ["Moins précis que les grands modèles"], usage: "Itare, tâches courantes." }),
    E("openai", "gpt-4.1-mini", 1000, "€", { vision: true, desc: "Contexte immense à petit prix.", forces: ["1 M de jetons de contexte", "Outils"], limites: ["Un long contexte coûte cher en entrée"], usage: "Lire de gros documents." }),
    E("openai", "gpt-4.1", 1000, "€€€", { vision: true, desc: "Le grand modèle d'OpenAI pour l'action et le code.", forces: ["Suit très bien les consignes", "Outils excellents"], limites: ["Plus cher"], usage: "Cassandra sur des opérations délicates." }),
    E("openai", "gpt-4o", 128, "€€€", { vision: true, desc: "Généraliste de haut niveau, avec vision.", forces: ["Qualité élevée", "Vision"], limites: ["Plus cher"], usage: "Usage général exigeant." }),
    E("google", "gemini-2.5-flash", 1000, "€", { vision: true, raisonne: true, desc: "Rapide, contexte d'un million de jetons, bon marché.", forces: ["Contexte immense", "Vision", "Raisonne"], limites: ["Quotas stricts sur l'offre gratuite"], usage: "Équilibre vitesse, prix, qualité." }),
    E("google", "gemini-2.5-pro", 1000, "€€€", { vision: true, raisonne: true, desc: "Le plus capable de Google, pour les cas difficiles.", forces: ["Raisonnement", "Long contexte"], limites: ["Plus cher et plus lent"], usage: "Analyses lourdes." }),
    E("google", "gemini-2.0-flash", 1000, "€", { vision: true, desc: "Rapide et très économique.", forces: ["Très rapide", "Vision"], limites: ["Moins profond que la série 2.5"], usage: "Tâches courtes." }),
    E("groq", "llama-3.3-70b-versatile", 128, "€", { desc: "Un grand modèle ouvert servi à très grande vitesse.", forces: ["Vitesse impressionnante", "Outils", "Bon marché"], limites: ["Quotas par minute serrés"], usage: "Réponses vives, conversation." }),
    E("groq", "llama-3.1-8b-instant", 128, "€", { fr: 2, desc: "Petit modèle, quasi instantané.", forces: ["Instantané", "Économique"], limites: ["Qualité limitée"], usage: "Tâches simples et rapides." }),
    E("openrouter", "google/gemini-2.5-flash", 1000, "€", { vision: true, raisonne: true, desc: "Gemini 2.5 Flash via OpenRouter : une seule facture pour plusieurs fournisseurs.", forces: ["Un compte, de nombreux modèles"], limites: ["Une couche de plus entre toi et le fournisseur"], usage: "Pour essayer plusieurs modèles sans multiplier les clés." }),
    E("openrouter", "anthropic/claude-sonnet-4.5", 200, "€€€", { vision: true, desc: "Un des meilleurs modèles pour agir avec des outils et rédiger.", forces: ["Outils excellents", "Écriture soignée", "Français très bon"], limites: ["Plus cher"], usage: "Cassandra pour les actions importantes." }),
    E("openrouter", "openai/gpt-4o-mini", 128, "€", { vision: true, desc: "GPT-4o mini via OpenRouter.", forces: ["Économique", "Outils"], limites: ["Moins précis que les grands modèles"], usage: "Tâches courantes." }),
    E("openrouter", "meta-llama/llama-3.3-70b-instruct", 128, "€", { desc: "Llama 3.3 70B via OpenRouter.", forces: ["Grand modèle ouvert", "Outils"], limites: ["Qualité variable selon l'hébergeur choisi"], usage: "Alternative ouverte." }),
    E("openrouter", "deepseek/deepseek-chat", 64, "€", { desc: "DeepSeek via OpenRouter, hébergeurs au choix.", forces: ["Très bon marché"], limites: ["Selon l'hébergeur, les données quittent l'Europe"], usage: "À bas coût." }),
  ];

  window.CASS_CATALOGUE_MODELES = { local: LOCAL, enligne: ONLINE };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le catalogue des modèles locaux et en ligne.
// EC : néant.
// LIEN : interface/CN_modeles-ecran.js (qui l'affiche), outils/ui/CN_assembler.py (qui le charge avant l'écran).
