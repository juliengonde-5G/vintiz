// Page Charte — affiche les 3 directions côte à côte
// Chaque direction = colonne montrant: hero logo, palette, typo, composants, exemple layout

const { useState } = React;

function ChartePage() {
  const dirs = Object.values(window.VINTIZ_DIRECTIONS);
  return (
    <div className="charte-root">
      <header className="charte-header">
        <div className="charte-header-inner">
          <div className="charte-eyebrow">Vintiz · Charte v3 · 3 directions</div>
          <h1 className="charte-title">
            Trois manières de devenir <em>Vintiz</em>.
          </h1>
          <p className="charte-lede">
            Le logo monogramme VZ et le lettrage VINTIZ restent. Tout le reste — palette élargie,
            typographie, ton, composants, traitement print — est remis à plat sur trois directions
            distinctes. Comparez côte à côte, choisissez l'une, ou mixez : la palette de l'une, la typo de l'autre.
          </p>
          <div className="charte-meta">
            <span>Cible primaire — femmes 35–55 actives, sensibles aux marques, mode responsable</span>
            <span className="dot"></span>
            <span>Cible secondaire — 18–30 acculturées Vinted</span>
          </div>
        </div>
      </header>

      <div className="charte-grid">
        {dirs.map(d => <DirectionColumn key={d.id} dir={d} />)}
      </div>

      <footer className="charte-footer">
        <div>Vintiz Vernon, Normandie · Logo VZ conservé · Charte v3 · 2026</div>
      </footer>
    </div>
  );
}

function DirectionColumn({ dir }) {
  return (
    <section className="dir-col" data-dir={dir.id}>
      <div className="dir-head">
        <div className="dir-num">0{Object.keys(window.VINTIZ_DIRECTIONS).indexOf(dir.id) + 1}</div>
        <div className="dir-name-wrap">
          <h2 className="dir-name">{dir.name}</h2>
          <div className="dir-tagline">{dir.tagline}</div>
        </div>
      </div>

      <p className="dir-desc">{dir.description}</p>

      <DirHero dir={dir} />
      <DirPalette dir={dir} />
      <DirTypo dir={dir} />
      <DirComponents dir={dir} />
      <DirSample dir={dir} />
      <DirTokens dir={dir} />
    </section>
  );
}

function DirHero({ dir }) {
  // Logo treatment varies by direction
  if (dir.id === 'atelier') {
    return (
      <div className="dir-hero atelier-hero">
        <div className="atelier-hero-rule">— Maison —</div>
        <img src={window.__resources && window.__resources.logoTeal || 'assets/logo-teal.png'} alt="VZ" className="hero-logo-img" style={{filter:'brightness(0)'}} />
        <div className="atelier-hero-letter">VINTIZ</div>
        <div className="atelier-hero-rule">Vernon · 2026 · seconde main d'auteur</div>
      </div>
    );
  }
  if (dir.id === 'sauge' || dir.id === 'saugeNeo') {
    return (
      <div className="dir-hero sauge-hero">
        <div className="sauge-hero-grid">
          <div className="sauge-hero-card">
            <img src={window.__resources && window.__resources.logoTeal || 'assets/logo-teal.png'} alt="VZ" className="hero-logo-img" />
          </div>
          <div className="sauge-hero-meta">
            <div className="sauge-hero-label">Established</div>
            <div className="sauge-hero-value">Vernon, 2026</div>
            <div className="sauge-hero-label" style={{marginTop:14}}>Capsule</div>
            <div className="sauge-hero-value">Pré-aimée</div>
          </div>
        </div>
      </div>
    );
  }
  // neo
  return (
    <div className="dir-hero neo-hero">
      <div className="neo-hero-mark">VINTIZ</div>
      <img src={window.__resources && window.__resources.logoTeal || 'assets/logo-teal.png'} alt="VZ" className="hero-logo-img neo-hero-mono" />
      <div className="neo-hero-row">
        <span>EST · 2026</span>
        <span>VRN · NMD</span>
        <span>2ND · LIFE</span>
      </div>
    </div>
  );
}

function DirPalette({ dir }) {
  const swatches = [
    { name: 'Fond', token: 'bg', value: dir.palette.bg, role: 'Background' },
    { name: 'Surface', token: 'surface', value: dir.palette.surface, role: 'Cartes' },
    { name: 'Encre', token: 'ink', value: dir.palette.ink, role: 'Texte' },
    { name: 'Teal', token: 'teal', value: dir.palette.teal, role: 'Signature · CTA' },
    { name: 'Accent', token: 'accent', value: dir.palette.accent, role: 'Souligner' },
    { name: 'Doux', token: 'tealSoft', value: dir.palette.tealSoft, role: 'Fidélité' },
    { name: 'Ligne', token: 'line', value: dir.palette.line, role: 'Séparateurs' },
    { name: 'Or', token: 'gold', value: dir.palette.gold, role: 'Détails fins' },
  ];
  return (
    <div className="dir-block">
      <div className="dir-block-label">Palette</div>
      <div className="dir-swatches">
        {swatches.map(s => (
          <div className="swatch" key={s.token}>
            <div className="swatch-chip" style={{background: s.value, border: ['surface','bg'].includes(s.token) ? '1px solid var(--line)' : 'none'}}></div>
            <div className="swatch-meta">
              <div className="swatch-name">{s.name}</div>
              <div className="swatch-hex">{s.value.toUpperCase()}</div>
              <div className="swatch-role">{s.role}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DirTypo({ dir }) {
  return (
    <div className="dir-block">
      <div className="dir-block-label">Typographie</div>
      <div className="typo-stack">
        <div className="typo-row">
          <div className="typo-meta">
            <div className="typo-meta-label">Display</div>
            <div className="typo-meta-name">{dir.type.display.split(',')[0].replace(/"/g,'')}</div>
            <div className="typo-meta-detail">Titres, hero, lettrage long</div>
          </div>
          <div className="typo-sample-display">Vintiz</div>
        </div>
        <div className="typo-row">
          <div className="typo-meta">
            <div className="typo-meta-label">Body</div>
            <div className="typo-meta-name">{dir.type.body.split(',')[0].replace(/"/g,'')}</div>
            <div className="typo-meta-detail">Texte courant, UI, labels</div>
          </div>
          <div className="typo-sample-body">
            La pièce trouvée se raconte d'elle-même : matière, coupe, époque. Ici on documente, on choisit.
          </div>
        </div>
        <div className="typo-row">
          <div className="typo-meta">
            <div className="typo-meta-label">Mono</div>
            <div className="typo-meta-name">{dir.type.mono.split(',')[0].replace(/"/g,'')}</div>
            <div className="typo-meta-detail">Tickets, codes, métadonnées</div>
          </div>
          <div className="typo-sample-mono">VZ-04829 · Petit Bateau · 36 · 18€</div>
        </div>
      </div>
    </div>
  );
}

function DirComponents({ dir }) {
  return (
    <div className="dir-block">
      <div className="dir-block-label">Composants</div>
      <div className="comp-stack">
        <div className="comp-row">
          <button className="btn-primary">Encaisser · 42€</button>
          <button className="btn-secondary">Voir détails</button>
        </div>
        <div className="comp-row">
          <span className="badge-loyalty">Gold · 1 240 pts</span>
          <span className="badge-tag">Pré-aimé</span>
          <span className="badge-zone">Tendance</span>
        </div>
        <div className="comp-card">
          <div className="comp-card-img"></div>
          <div className="comp-card-body">
            <div className="comp-card-brand">Petit Bateau</div>
            <div className="comp-card-title">Marinière marine, taille 36</div>
            <div className="comp-card-meta">
              <span className="comp-card-price">18€</span>
              <span className="comp-card-orig">— neuf 65€</span>
            </div>
          </div>
        </div>
        <div className="comp-input-wrap">
          <label className="comp-input-label">Email</label>
          <input className="comp-input" defaultValue="sophie@example.fr" />
        </div>
      </div>
    </div>
  );
}

function DirSample({ dir }) {
  return (
    <div className="dir-block">
      <div className="dir-block-label">Application — vignette</div>
      <div className="sample-frame">
        {dir.id === 'atelier' && <SampleAtelier />}
        {(dir.id === 'sauge' || dir.id === 'saugeNeo') && <SampleSauge />}
        {dir.id === 'neo' && <SampleNeo />}
      </div>
    </div>
  );
}

function SampleAtelier() {
  return (
    <div className="sample-atelier">
      <div className="sa-rule">— PIÈCE N° 482 —</div>
      <div className="sa-display"><em>La</em> marinière<br/>de <em>Petit Bateau</em></div>
      <div className="sa-body">Coton bio, taille 36. Petite trace côté gauche. Documentée dans le cahier du 14 mars.</div>
      <div className="sa-footer">
        <span>18€</span>
        <span>—</span>
        <span>réserver 48h</span>
      </div>
    </div>
  );
}
function SampleSauge() {
  return (
    <div className="sample-sauge">
      <div className="ss-tag">Capsule · Hiver pré-aimé</div>
      <div className="ss-display">Tout a déjà<br/>une histoire.</div>
      <div className="ss-row">
        <div className="ss-stat"><div className="ss-stat-num">482</div><div className="ss-stat-lbl">pièces</div></div>
        <div className="ss-stat"><div className="ss-stat-num">68%</div><div className="ss-stat-lbl">en boutique</div></div>
        <div className="ss-stat"><div className="ss-stat-num">241kg</div><div className="ss-stat-lbl">non-jetés</div></div>
      </div>
    </div>
  );
}
function SampleNeo() {
  return (
    <div className="sample-neo">
      <div className="sn-top">
        <span className="sn-pill">EN BOUTIQUE</span>
        <span className="sn-pill alt">VRN · 2026</span>
      </div>
      <div className="sn-display">SECOND<br/>HAND<br/><em>HAUT</em>.</div>
      <div className="sn-foot">
        <span>482 pièces</span>
        <span>↗ live</span>
      </div>
    </div>
  );
}

function DirTokens({ dir }) {
  const [open, setOpen] = useState(false);
  const tokens = {
    name: dir.name,
    palette: dir.palette,
    type: dir.type,
    radius: dir.radius,
    radiusLg: dir.radiusLg,
  };
  return (
    <div className="dir-block">
      <button className="tokens-toggle" onClick={() => setOpen(!open)}>
        {open ? '— Cacher tokens' : '+ Voir tokens JSON'}
      </button>
      {open && (
        <pre className="tokens-pre">{JSON.stringify(tokens, null, 2)}</pre>
      )}
    </div>
  );
}

window.ChartePage = ChartePage;
