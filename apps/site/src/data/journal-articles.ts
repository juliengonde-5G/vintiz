/**
 * Articles de blog éditoriaux Vintiz (audit M10 / S17).
 *
 * Approche longue traîne : un article par mois, mots-clés ciblés
 * « friperie premium Vernon », « comment authentifier un sac
 * Polène », « marques iconiques françaises seconde main »…
 *
 * Quand un PR ajoute un article pour le mois suivant, le site le sert
 * automatiquement à la date prévue (no-DB, MD/MDX en dur).
 */

export interface JournalArticle {
  /** Slug URL : ex. "comment-authentifier-sac-polene". */
  slug: string;
  /** Titre éditorial — H1 + meta title. */
  title: string;
  /** Sous-titre / accroche → meta description (150-160 char idéal). */
  excerpt: string;
  /** Date de publication (ISO 8601). */
  published_at: string;
  /** Auteur·rice. */
  author: string;
  /** Lecture estimée (min). */
  reading_minutes: number;
  /** Tags de catégorisation. */
  tags: readonly string[];
  /** Corps en Markdown léger — paragraphes + sous-titres. */
  body: string;
}

export const JOURNAL_ARTICLES: JournalArticle[] = [
  {
    slug: "solidarite-textiles-le-tri-derriere-vintiz",
    title:
      "Solidarité Textiles : ce qui se passe avant qu'une pièce arrive chez Vintiz",
    excerpt:
      "Avant chaque robe, chaque veste, chaque sac que nous proposons, il y a un centre de tri en Normandie, des salariés en parcours d'insertion, et une économie circulaire concrète. Coulisses.",
    published_at: "2026-05-09T08:00:00Z",
    author: "Équipe Vintiz",
    reading_minutes: 6,
    tags: ["solidarité textiles", "ESS", "économie circulaire"],
    body: `## Pourquoi nous parlons de Solidarité Textiles dès la première pièce

Quand une cliente nous demande d'où viennent nos vêtements, nous lui répondons toujours la même chose : *« d'un centre de tri en Normandie, où des salariés en parcours d'insertion les ont triés à la main avant que notre équipe les sélectionne »*. Ce centre s'appelle Solidarité Textiles, et c'est notre partenaire depuis le premier jour.

Cette page est notre manière de raconter ce qui se passe en amont. Parce que la « seconde main » a souvent un imaginaire flou, et qu'on a envie d'être précis sur ce qui rend Vintiz cohérent avec son projet.

## Étape 1 — La collecte

Solidarité Textiles gère un réseau de bornes de collecte réparties sur la Métropole Rouen Normandie. Vous en avez sûrement déjà croisé : des conteneurs métalliques verts au coin d'une rue, devant un parking de supermarché, près d'une déchèterie. Chacun récupère plusieurs centaines de kilos de textiles par mois.

Tous ces textiles partent dans le même camion vers le centre de tri. À ce stade, c'est tout en vrac : pulls, chaussures, vêtements de bébé, jeans, draps, vêtements abîmés, vêtements neufs encore avec étiquette, marques de luxe, marques discount. Le tri sépare tout cela.

## Étape 2 — Le tri à la main

Au centre, des salariés en parcours d'insertion (souvent éloignés de l'emploi depuis longtemps) trient manuellement chaque pièce. Ils regardent : est-ce que c'est portable ? Est-ce que c'est lavable ? Est-ce que c'est une marque qui peut intéresser un acheteur ? Est-ce qu'il y a une déchirure, un trou, une tache visible ?

Selon les flux, ils répartissent en plusieurs **catégories** :

- **Pièces réutilisables, qualité « premium »** — bonne marque, bon état, taille standard. C'est ce qui peut nous intéresser chez Vintiz.
- **Pièces réutilisables, qualité « standard »** — vendables en friperie classique ou export.
- **Pièces utilisables comme matière première** — chiffons d'essuyage industriel, isolants thermiques.
- **Pièces non valorisables** — recyclées en filière agréée, jamais incinérées tant qu'une voie reste possible.

Cette segmentation est la clé. C'est ce qui permet à Vintiz de ne récupérer que ce qui correspond à notre niveau de curation, sans avoir à trier nous-mêmes des dizaines de tonnes pour trouver les pépites.

## Étape 3 — Notre passage chez Vintiz

Une à deux fois par semaine, notre équipe passe au centre de tri. On y va avec une grille mentale précise : quelles tailles nous manquent en boutique ? Quelles marques tournent vite cette saison ? Quelle gamme de prix correspond à notre clientèle Vernon-Giverny ?

On repart avec des pièces qu'on rapporte en boutique pour la deuxième couche de contrôle :

- **Lavage / pressing** systématique avant mise en rayon.
- **Authentification** quand la marque le justifie (sacs, pièces de cuir, marques iconiques).
- **Fixation du prix juste** — ni trop cher ni trop bas, calé sur le marché Vinted / Vestiaire au moment de la mise en rayon.
- **Étiquetage** avec un code-barres unique, photographie, fiche produit complète.

Une pièce qui ne passe pas l'un de ces filtres repart en filière standard chez Solidarité Textiles. C'est souvent 30 à 40 % du volume initial. Pas une perte — juste une recanalisation vers le bon marché.

## Étape 4 — Ce que ça produit, concrètement

Cette chaîne courte produit trois choses qui nous tiennent à cœur :

1. **Des emplois locaux soutenus** — chaque pièce achetée chez nous contribue à financer le modèle économique de Solidarité Textiles, et donc les parcours d'insertion qu'ils portent.
2. **Une traçabilité totale** — on sait précisément d'où vient chaque pièce, ce qu'elle a vécu en amont, à quel moment elle a rejoint nos rayons. C'est rare en seconde main et c'est un engagement qu'on tient.
3. **Une économie circulaire qui ne fait pas semblant** — pas de greenwashing, pas de rêverie sur « la mode durable ». Juste : un textile qui aurait pu finir en décharge, qui revit dans un dressing à 50 km de son origine, et qui finance des emplois en parcours d'insertion à 30 km de la boutique.

## Et le rapport d'impact ?

À partir de 2027, nous publierons chaque année un rapport d'impact public qui détaillera :

- les **kilos** revalorisés via Vintiz dans l'année
- le **taux de réemploi** (pièces vendues / pièces récupérées)
- le **CA reversé** à Solidarité Textiles
- l'**évolution des parcours d'insertion** soutenus indirectement par cette filière

C'est notre manière de tenir la promesse au-delà du discours. La transparence sur ce sujet, c'est la moindre des choses quand on revend du second-hand premium en France en 2026.

## En attendant

Si vous voulez voir concrètement ce qu'on en tire, deux entrées :

- [Notre sélection « Made in France iconic »](/produits/made-in-france) — les marques françaises curées spécifiquement pour notre boutique.
- [Notre page À propos](/a-propos) — pour le projet d'ensemble, sans le détail du tri.

Et si vous passez en boutique au 6 rue Saint-Jacques, demandez-nous de vous raconter une pièce en particulier. Souvent, il y a une histoire — un parcours, une marque, une cliente qui l'a aimée puis cédée. C'est ce qui fait la différence avec un rayon Zara.
`,
  },
  {
    slug: "comment-authentifier-sac-polene",
    title: "Comment authentifier un sac Polène d'occasion",
    excerpt:
      "Cuir pleine fleur, finitions à la main, code de série discret : voici les 6 points de contrôle que notre équipe Vintiz vérifie sur chaque Polène N°1, N°9 ou Numéro Dix avant de l'authentifier.",
    published_at: "2026-05-08T08:00:00Z",
    author: "Équipe Vintiz",
    reading_minutes: 5,
    tags: ["authentification", "marques iconiques", "Polène"],
    body: `## Pourquoi Polène inquiète les acheteuses d'occasion

Polène a explosé sur Instagram entre 2020 et 2024. Le N°1, le N°9, le Numéro Dix sont devenus des références presque cultes — et avec elles, les copies. Sur Vinted ou eBay, on en croise tous les jours, parfois à des prix « trop beaux pour être vrais ».

Quand une cliente nous apporte un Polène dans le doute, ou qu'on en récupère un dans nos arrivages chez Solidarité Textiles, voici les 6 points de contrôle que notre équipe vérifie systématiquement avant de l'authentifier et de le proposer en boutique.

## 1. Le cuir : pleine fleur, jamais split

Polène ne travaille que du cuir pleine fleur — italien ou français. Au toucher, c'est souple sans être mou, dense sans être rigide. Les copies utilisent presque toutes du *split leather* (cuir refendu) ou du PU enduit : ça brille trop, ça « plastifie » sous l'ongle, et l'odeur trahit (chimique vs animale).

## 2. Les finitions de couture

Sur un Polène authentique, les coutures sont parfaitement régulières — environ 6 points par centimètre, ton sur ton. Aucun fil qui dépasse, aucune cassure d'angle. Sur les copies, on voit souvent des points sautés près des angles, ou des points trop espacés en ligne droite.

## 3. La fermeture aimantée

C'est un détail qui ne se copie quasiment jamais bien. La fermeture aimantée d'un Polène N°1 ou N°9 a une **résistance précise** : ferme sans être brutale, le claquement est sourd. Les copies ont soit un aimant trop faible (le sac s'ouvre tout seul), soit trop fort (impossible à ouvrir d'une main).

## 4. Le marquage interne

À l'intérieur, sur la doublure suède (jamais en tissu), on trouve un petit marquage discret « POLÈNE PARIS » embossé. Pas tamponné, pas peint : embossé à chaud. Le grain du suède n'est pas brillant, il a une légère pelucheuse.

## 5. Le code de série

Tous les Polène depuis 2019 portent un code de série numérique imprimé sur une étiquette satinée intérieure (souvent au fond du compartiment principal ou cousue dans une couture latérale). Le code suit le format PXXX-XXXX-XX (3 lettres + 4 chiffres + 2 caractères). Aucun code ou un code mal aligné = drapeau rouge.

## 6. Le packaging d'origine (si présent)

Polène emballe ses sacs dans un dustbag en coton bio non blanchi avec le logo brodé (jamais imprimé), une carte d'authenticité rigide, et — selon le modèle — une bandoulière nominale dans un sachet propre. Si le sac arrive sans rien, ça n'est pas disqualifiant (on revend des Polène sans dustbag chez Vintiz). Mais si le dustbag est *imprimé* au lieu d'être brodé, c'est une copie.

## Et chez Vintiz ?

Tous les Polène que nous proposons en boutique passent ces 6 contrôles. Si un seul flag rouge apparaît, la pièce part en recyclage textile chez Solidarité Textiles, jamais en rayon. C'est notre engagement « curation premium » — et c'est ce qui nous permet de vous proposer un Polène N°1 mini camel à 220 € avec la garantie d'être authentique.

Pour voir les Polène disponibles cette semaine : [notre sélection Polène](/produits/marque/polene).
`,
  },
  {
    slug: "marques-francaises-iconiques-seconde-main-vernon",
    title:
      "Sandro, Maje, Sézane, Polène : pourquoi ces marques tournent si bien en seconde main",
    excerpt:
      "À Vernon, certaines marques françaises iconiques se vendent en quelques jours quand elles arrivent. Décodage de ce qui les rend recherchées en seconde main premium — et de ce qu'on regarde avant de les mettre en rayon.",
    published_at: "2026-05-01T08:00:00Z",
    author: "Équipe Vintiz",
    reading_minutes: 7,
    tags: ["marques iconiques", "tendances", "made in france"],
    body: `## Le sweet spot Vintiz : 50-300 €, cinq marques pivots

Quand on a curé le concept de Vintiz à Vernon, on a fait un choix volontaire : ne pas faire « toutes les marques d'occasion ». Plutôt cinq à dix marques françaises iconiques qui ont une raison de tourner vite en seconde main premium. Voici le raisonnement, marque par marque.

## Sandro et Maje : la coupe française du quotidien

Sandro et Maje, ce sont les marques que les Parisiennes achètent neuves quand elles veulent du « bien coupé sans aller chez Isabel Marant ». 200-400 € le blazer ou la robe en neuf, mais avec une qualité de tissu et de coupe largement supérieure à Zara ou Mango.

En seconde main, ces pièces se revendent à 80-150 € — et c'est un marché qui ne ralentit pas. La raison : leurs collections changent vite, mais les coupes restent intemporelles. Une robe Sandro de 2022 reste portable en 2026 si elle est en bon état. Et la cliente qui achète une robe Sandro à 95 € chez Vintiz sait exactement ce qu'elle achète.

## Sézane : la collection émotionnelle

Sézane joue dans une autre catégorie : direct-to-consumer, drop limité, communauté Instagram active. Conséquence en seconde main premium : les pièces emblématiques (la robe Pascale, le pull Aragon, la chemise Ludo) gardent leur valeur étonnamment longtemps.

Une pièce Sézane bien curée part en moins d'une semaine chez Vintiz. Notre conseil : si vous voyez une Sézane dans votre taille en bon état, ne traînez pas pour la réserver.

## Polène : l'iconique cuir français

On a déjà dédié [un article complet à l'authentification d'un Polène d'occasion](/journal/comment-authentifier-sac-polene). Le résumé : Polène est devenue *la* marque de maroquinerie française accessible (300-500 € en neuf, 180-280 € en seconde main). En curation premium, c'est l'une des marques qui justifie le mieux la démarche Vintiz : difficile à authentifier en ligne, achat émotionnel, prix qui se tient.

## IRO et Isabel Marant Étoile : le « slightly edgy »

IRO et Isabel Marant Étoile incarnent la silhouette française avec une touche rock — le perfecto IRO en cuir d'agneau, la robe Étoile à broderies, le t-shirt à logo discret. Neuves, ces pièces sont chères (400-700 €). En seconde main, elles tournent surtout sur les modèles qu'on dit *signature* — c'est-à-dire reconnaissables au coup d'œil par quelqu'un qui connaît la marque.

Notre conseil : un perfecto IRO, ça ne se compare pas avec une copie en cuir épais. La coupe est ajustée, les zips patinent, et l'aplomb est unique.

## Les pépites confidentielles : The Kooples, Vanessa Bruno, A.P.C.

À côté des « stars », on garde une attention particulière pour les marques de **deuxième cercle** : The Kooples (tailoring noir intemporel), Vanessa Bruno (cabas et pièces lin/coton), A.P.C. (jeans, chemises blanches). Ces marques ne créent pas de hype, mais elles sont très recherchées par une cliente qui sait ce qu'elle veut. Un blazer Vanessa Bruno en lin à 120 € chez Vintiz, ça a sa cliente attitrée.

## Ce qu'on regarde avant de mettre en rayon

Pour chaque pièce d'une de ces marques arrivée chez Solidarité Textiles, notre équipe vérifie :

- **L'état général** : taches, déchirures, boulochage. Une Sézane usée ne sera pas mise en rayon, elle partira en recyclage textile.
- **La marque elle-même** : étiquette intérieure, code de série, marquage discret. On ne met en rayon qu'authentique.
- **Le marché** : on consulte ponctuellement Vinted et Vestiaire Collective pour caler le prix juste — ni trop cher (ça reste deux mois en rayon), ni trop bas (ça part en quelques jours mais on aurait pu mieux faire).
- **La cohérence Vintiz** : si la pièce ne correspond pas à notre ton (trop logotypé, trop saisonnier passé), elle file en seconde main hors curation chez nos partenaires.

## Les voir en boutique à Vernon

Toutes ces marques sont régulièrement présentes au 6 rue Saint-Jacques. Pour voir ce qui est disponible cette semaine, deux entrées :

- [Notre sélection « Made in France iconic »](/produits/made-in-france) — la vitrine touriste-friendly avec les marques qui plaisent aussi aux visiteurs internationaux de Giverny.
- [Toutes les pièces par marque](/produits) — l'inventaire complet, mis à jour en temps réel.

Et bien sûr, vous pouvez toujours [activer le Personal Shopper IA](/personal-shopper) pour qu'il vous prévienne dès qu'une pièce dans votre style arrive en boutique.
`,
  },
];

export function findArticle(slug: string): JournalArticle | undefined {
  return JOURNAL_ARTICLES.find((a) => a.slug === slug);
}

export function recentArticles(limit = 10): JournalArticle[] {
  return [...JOURNAL_ARTICLES]
    .sort((a, b) => b.published_at.localeCompare(a.published_at))
    .slice(0, limit);
}
