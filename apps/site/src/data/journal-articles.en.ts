/**
 * English copy mirror of the Vintiz journal (`journal-articles.ts`).
 *
 * Same `slug`, `published_at`, `author` and `reading_minutes` as the French
 * source so shared URLs and hreflang line up — `title`, `excerpt`, `tags` and
 * the full Markdown `body` are translated to fluent English. Internal links in
 * the bodies are rewritten to their `/en/*` equivalents.
 */

export interface JournalArticleEn {
  slug: string;
  title: string;
  excerpt: string;
  published_at: string;
  author: string;
  reading_minutes: number;
  tags: readonly string[];
  body: string;
}

export const JOURNAL_ARTICLES_EN: JournalArticleEn[] = [
  {
    slug: "solidarite-textiles-le-tri-derriere-vintiz",
    title:
      "Solidarité Textiles: what happens before a piece reaches Vintiz",
    excerpt:
      "Before every dress, jacket and bag we offer, there is a sorting centre in Normandy, employees on work-reintegration programmes, and a real circular economy. Behind the scenes.",
    published_at: "2026-05-09T08:00:00Z",
    author: "Vintiz Team",
    reading_minutes: 6,
    tags: ["solidarité textiles", "social economy", "circular economy"],
    body: `## Why we talk about Solidarité Textiles from the very first piece

When a customer asks where our clothes come from, we always give the same answer: *"from a sorting centre in Normandy, where employees on work-reintegration programmes sorted them by hand before our team selected them"*. That centre is called Solidarité Textiles, and it has been our partner since day one.

This page is our way of telling the story of what happens upstream. Because "second-hand" often carries a vague image, and we want to be precise about what makes Vintiz consistent with its mission.

## Step 1 — Collection

Solidarité Textiles runs a network of collection bins spread across the Rouen Normandie metropolitan area. You've probably already walked past one: green metal containers on a street corner, outside a supermarket car park, near a recycling centre. Each one gathers several hundred kilos of textiles a month.

All those textiles travel in the same truck to the sorting centre. At this stage everything is mixed together: jumpers, shoes, baby clothes, jeans, sheets, damaged garments, brand-new garments still with their tags, luxury labels, discount brands. Sorting separates it all out.

## Step 2 — Sorting by hand

At the centre, employees on work-reintegration programmes (often people who have been out of work for a long time) sort each piece by hand. They look at: is it wearable? Is it washable? Is it a label a buyer might want? Is there a tear, a hole, a visible stain?

Depending on the flow, they split everything into several **categories**:

- **Reusable pieces, "premium" quality** — good label, good condition, standard size. This is what may interest us at Vintiz.
- **Reusable pieces, "standard" quality** — sellable in a classic second-hand shop or for export.
- **Pieces usable as raw material** — industrial wiping rags, thermal insulation.
- **Non-recoverable pieces** — recycled through an approved channel, never incinerated as long as another route remains possible.

This segmentation is the key. It's what lets Vintiz take only what matches our level of curation, without having to sort dozens of tonnes ourselves to find the gems.

## Step 3 — Our visit to the centre

Once or twice a week, our team visits the sorting centre. We go in with a precise mental checklist: which sizes are we short of in store? Which labels are turning over quickly this season? Which price range suits our Vernon-Giverny clientele?

We come back with pieces that we bring into the store for a second layer of checks:

- **Washing / dry-cleaning** systematically before they hit the rack.
- **Authentication** whenever the label warrants it (bags, leather pieces, iconic brands).
- **Setting a fair price** — neither too high nor too low, calibrated against the Vinted / Vestiaire market at the moment it goes on the rack.
- **Labelling** with a unique barcode, photography and a complete product sheet.

A piece that fails any of these filters goes back into the standard channel at Solidarité Textiles. That's often 30 to 40% of the initial volume. Not a loss — just a re-routing toward the right market.

## Step 4 — What it produces, concretely

This short chain produces three things that matter to us:

1. **Supported local jobs** — every piece bought from us helps fund the economic model of Solidarité Textiles, and therefore the reintegration programmes they run.
2. **Full traceability** — we know precisely where each piece comes from, what it went through upstream, and when it joined our racks. That's rare in second-hand, and it's a commitment we keep.
3. **A circular economy that doesn't pretend** — no greenwashing, no daydreaming about "sustainable fashion". Just this: a textile that could have ended up in landfill, living again in a wardrobe 50 km from where it started, and funding reintegration jobs 30 km from the store.

## And the impact report?

From 2027, we'll publish a public impact report every year, detailing:

- the **kilos** given a second life through Vintiz over the year
- the **reuse rate** (pieces sold / pieces recovered)
- the **revenue paid back** to Solidarité Textiles
- the **progress of the reintegration pathways** indirectly supported by this chain

It's our way of keeping the promise beyond the talk. Transparency on this subject is the least we can do when reselling premium second-hand in France in 2026.

## In the meantime

If you want to see what we get out of it for yourself, two ways in:

- [Our "Made in France iconic" selection](/en/produits) — the French labels curated specifically for our store.
- [Our About page](/en/a-propos) — for the overall project, without the sorting details.

And if you stop by the store at 6 rue Saint-Jacques, ask us to tell you about a particular piece. There's often a story — a journey, a label, a customer who loved it then let it go. That's what makes the difference with a rack at Zara.
`,
  },
  {
    slug: "comment-authentifier-sac-polene",
    title: "How to authenticate a second-hand Polène bag",
    excerpt:
      "Full-grain leather, hand-finished details, a discreet serial code: here are the 6 checks our Vintiz team runs on every Polène N°1, N°9 or Numéro Dix before authenticating it.",
    published_at: "2026-05-08T08:00:00Z",
    author: "Vintiz Team",
    reading_minutes: 5,
    tags: ["authentication", "iconic brands", "Polène"],
    body: `## Why Polène worries second-hand buyers

Polène exploded on Instagram between 2020 and 2024. The N°1, the N°9 and the Numéro Dix became almost cult references — and with them came the copies. On Vinted or eBay you see them every day, sometimes at prices "too good to be true".

When a customer brings us a Polène she has doubts about, or when one turns up in our deliveries from Solidarité Textiles, here are the 6 checks our team runs systematically before authenticating it and offering it in store.

## 1. The leather: full-grain, never split

Polène works only with full-grain leather — Italian or French. To the touch it is supple without being soft, dense without being stiff. Almost all copies use *split leather* or coated PU: it shines too much, it "plasticises" under a fingernail, and the smell gives it away (chemical vs. animal).

## 2. The stitching finish

On a genuine Polène, the stitching is perfectly even — around 6 stitches per centimetre, tone on tone. No loose thread, no broken corners. On copies you often see skipped stitches near the corners, or stitches that are too widely spaced on a straight run.

## 3. The magnetic closure

This is a detail that is almost never copied well. The magnetic closure of a Polène N°1 or N°9 has a **precise resistance**: it closes firmly without being brutal, and the snap is muffled. Copies either have a magnet that's too weak (the bag opens on its own) or too strong (impossible to open one-handed).

## 4. The internal marking

Inside, on the suede lining (never fabric), you'll find a discreet "POLÈNE PARIS" marking, embossed. Not stamped, not painted: heat-embossed. The grain of the suede isn't shiny; it has a slight nap.

## 5. The serial code

Every Polène since 2019 carries a numeric serial code printed on a satin interior label (often at the bottom of the main compartment or sewn into a side seam). The code follows the format PXXX-XXXX-XX (3 letters + 4 digits + 2 characters). No code, or a misaligned code, is a red flag.

## 6. The original packaging (if present)

Polène packs its bags in an unbleached organic-cotton dustbag with the logo embroidered (never printed), a rigid authenticity card, and — depending on the model — a named shoulder strap in a clean pouch. If the bag arrives with nothing, that's not disqualifying (we resell Polène bags without a dustbag at Vintiz). But if the dustbag is *printed* instead of embroidered, it's a copy.

## And at Vintiz?

Every Polène we offer in store passes these 6 checks. If a single red flag appears, the piece goes to textile recycling at Solidarité Textiles, never onto the rack. That's our "premium curation" commitment — and it's what lets us offer you a camel Polène N°1 mini at €220 with the guarantee that it's genuine.

To see the Polène bags available this week: [our Polène selection](/en/produits/marque/polene).
`,
  },
  {
    slug: "marques-francaises-iconiques-seconde-main-vernon",
    title:
      "Sandro, Maje, Sézane, Polène: why these labels sell so well second-hand",
    excerpt:
      "In Vernon, certain iconic French labels sell within days of arriving. Decoding what makes them sought after in premium second-hand — and what we look at before putting them on the rack.",
    published_at: "2026-05-01T08:00:00Z",
    author: "Vintiz Team",
    reading_minutes: 7,
    tags: ["iconic brands", "trends", "made in france"],
    body: `## The Vintiz sweet spot: €50–300, five pivot labels

When we shaped the Vintiz concept in Vernon, we made a deliberate choice: not to do "every second-hand label". Instead, five to ten iconic French labels that have a reason to turn over quickly in premium second-hand. Here's the reasoning, label by label.

## Sandro and Maje: the everyday French cut

Sandro and Maje are the labels Parisian women buy new when they want something "well cut without going all the way to Isabel Marant". €200–400 for a blazer or a dress new, but with a fabric and a cut far above Zara or Mango.

Second-hand, these pieces resell at €80–150 — and it's a market that isn't slowing down. The reason: their collections change quickly, but the cuts stay timeless. A 2022 Sandro dress is still wearable in 2026 if it's in good condition. And the customer who buys a Sandro dress at €95 at Vintiz knows exactly what she's buying.

## Sézane: the emotional collection

Sézane plays in another league: direct-to-consumer, limited drops, an active Instagram community. The consequence in premium second-hand: the signature pieces (the Pascale dress, the Aragon jumper, the Ludo shirt) hold their value surprisingly long.

A well-curated Sézane piece sells in under a week at Vintiz. Our advice: if you spot a Sézane in your size in good condition, don't dawdle — come and try it in store.

## Polène: the iconic French leather

We've already devoted [a full article to authenticating a second-hand Polène](/en/journal/comment-authentifier-sac-polene). The summary: Polène has become *the* accessible French leather-goods label (€300–500 new, €180–280 second-hand). In premium curation, it's one of the labels that best justifies the Vintiz approach: hard to authenticate online, an emotional purchase, a price that holds.

## IRO and Isabel Marant Étoile: the "slightly edgy"

IRO and Isabel Marant Étoile embody the French silhouette with a rock edge — the IRO lambskin biker jacket, the embroidered Étoile dress, the subtly logo'd tee. New, these pieces are expensive (€400–700). Second-hand, they turn over mostly on the models we'd call *signature* — that is, recognisable at a glance by someone who knows the label.

Our advice: an IRO biker jacket can't be compared to a copy in thick leather. The cut is fitted, the zips take on a patina, and the drape is unique.

## The hidden gems: The Kooples, Vanessa Bruno, A.P.C.

Alongside the "stars", we keep a particular eye on the **second-tier** labels: The Kooples (timeless black tailoring), Vanessa Bruno (totes and linen/cotton pieces), A.P.C. (jeans, white shirts). These labels don't create hype, but they're highly sought after by a customer who knows what she wants. A Vanessa Bruno linen blazer at €120 at Vintiz has its own devoted buyer.

## What we look at before putting a piece on the rack

For every piece from one of these labels that arrives at Solidarité Textiles, our team checks:

- **Overall condition**: stains, tears, pilling. A worn Sézane won't go on the rack — it'll go to textile recycling.
- **The label itself**: inner tag, serial code, discreet marking. We only rack what's genuine.
- **The market**: we occasionally check Vinted and Vestiaire Collective to set the right price — neither too high (it sits on the rack for two months) nor too low (it sells in a few days but we could have done better).
- **Vintiz consistency**: if the piece doesn't fit our tone (too logo-heavy, too out-of-season), it goes to second-hand outside our curation, with our partners.

## Seeing them in store in Vernon

All these labels are regularly on the racks at 6 rue Saint-Jacques. To see what's available this week, two ways in:

- [Our "Made in France iconic" selection](/en/produits) — the tourist-friendly window with the labels that also appeal to Giverny's international visitors.
- [All pieces by label](/en/produits) — the full inventory, updated in real time.

And of course, you can always [activate the AI Personal Shopper](/en/personal-shopper) so it alerts you the moment a piece in your style arrives in store.
`,
  },
];

export function findArticleEn(slug: string): JournalArticleEn | undefined {
  return JOURNAL_ARTICLES_EN.find((a) => a.slug === slug);
}

export function recentArticlesEn(limit = 10): JournalArticleEn[] {
  return [...JOURNAL_ARTICLES_EN]
    .sort((a, b) => b.published_at.localeCompare(a.published_at))
    .slice(0, limit);
}
