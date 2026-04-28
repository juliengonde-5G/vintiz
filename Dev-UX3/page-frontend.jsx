// Page Frontend — landing publique + espace client mobile
// Affiche les 3 directions empilées, chacune montrant un mockup mobile (375px)

const { useState: useStateF } = React;

function FrontendPage() {
  const dirs = Object.values(window.VINTIZ_DIRECTIONS);
  return (
    <div className="frontend-root">
      <header className="page-section-header">
        <div className="page-section-eyebrow">02 · Frontend public</div>
        <h2 className="page-section-title">Landing + espace client, mobile-first</h2>
        <p className="page-section-lede">
          Sophie regarde Vintiz dans le métro. Trois traitements pour la même page d'accueil
          et le même dashboard fidélité, à 375 px.
        </p>
      </header>

      <div className="frontend-grid">
        {dirs.map(d => (
          <div className="frontend-col" key={d.id} data-dir={d.id}>
            <div className="frontend-col-head">
              <span className="frontend-col-num">0{Object.keys(window.VINTIZ_DIRECTIONS).indexOf(d.id) + 1}</span>
              <span className="frontend-col-name">{d.name}</span>
            </div>

            <div className="phone-pair">
              <PhoneFrame label="Landing — vintiz.fr">
                {d.id === 'atelier' && <LandingAtelier />}
                {d.id === 'sauge' && <LandingSauge />}
                {d.id === 'neo' && <LandingNeo />}
              </PhoneFrame>
              <PhoneFrame label="Espace client — /account">
                {d.id === 'atelier' && <AccountAtelier />}
                {d.id === 'sauge' && <AccountSauge />}
                {d.id === 'neo' && <AccountNeo />}
              </PhoneFrame>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PhoneFrame({ children, label }) {
  return (
    <div className="phone-wrap">
      <div className="phone-label">{label}</div>
      <div className="phone-frame">
        <div className="phone-notch"></div>
        <div className="phone-screen">{children}</div>
      </div>
    </div>
  );
}

/* ─────────── Atelier ─────────── */

function LandingAtelier() {
  return (
    <div className="screen at-screen">
      <div className="at-nav">
        <span className="at-nav-menu">≡</span>
        <span className="at-nav-mark">VINTIZ</span>
        <span className="at-nav-account">·</span>
      </div>
      <div className="at-hero">
        <div className="at-hero-rule">— Maison fondée à Vernon —</div>
        <h1 className="at-hero-title"><em>Le</em> dressing<br/>retrouvé.</h1>
        <p className="at-hero-lede">Sélection de pièces de seconde main choisies, documentées et photographiées avec le soin d'une première main.</p>
      </div>
      <div className="at-rule"></div>
      <div className="at-piece">
        <div className="at-piece-img" style={{background:'linear-gradient(135deg, #d8c8b2 0%, #b9a486 100%)'}}>
          <div className="at-piece-num">N° 482</div>
        </div>
        <div className="at-piece-meta">
          <div className="at-piece-brand">Petit Bateau</div>
          <div className="at-piece-title"><em>Marinière</em>, taille 36</div>
          <div className="at-piece-foot"><span>18€</span><span className="at-link">Réserver →</span></div>
        </div>
      </div>
      <div className="at-piece">
        <div className="at-piece-img" style={{background:'linear-gradient(135deg, #c4b29c 0%, #9f8a72 100%)'}}>
          <div className="at-piece-num">N° 481</div>
        </div>
        <div className="at-piece-meta">
          <div className="at-piece-brand">Sandro</div>
          <div className="at-piece-title"><em>Robe</em> en lin écru</div>
          <div className="at-piece-foot"><span>78€</span><span className="at-link">Réserver →</span></div>
        </div>
      </div>
      <div className="at-foot">
        <div className="at-foot-rule">— Reverse à Solidarité Textiles —</div>
        <div className="at-foot-meta">Vernon · ouvert mardi-samedi</div>
      </div>
    </div>
  );
}

function AccountAtelier() {
  return (
    <div className="screen at-screen at-account">
      <div className="at-nav">
        <span className="at-nav-menu">←</span>
        <span className="at-nav-mark">VINTIZ</span>
        <span className="at-nav-account">·</span>
      </div>
      <div className="at-hero" style={{paddingTop: 12}}>
        <div className="at-hero-rule">— Carte fidélité —</div>
        <h1 className="at-hero-title" style={{fontSize:36}}>Sophie M.</h1>
        <div className="at-account-num">Membre n° V482931</div>
      </div>
      <div className="at-card-fid">
        <div className="at-card-fid-tier">Gold</div>
        <div className="at-card-fid-pts">1 240 <span>points</span></div>
        <div className="at-card-fid-rule"></div>
        <div className="at-card-fid-foot">Prochain palier · 1 500 pts</div>
      </div>
      <div className="at-rule"></div>
      <div className="at-section-label">— Dernières visites —</div>
      <div className="at-history">
        <div className="at-hist-row"><span className="at-hist-date">14 mars</span><span className="at-hist-it">Marinière P. Bateau</span><span className="at-hist-pr">18€</span></div>
        <div className="at-hist-row"><span className="at-hist-date">28 fév.</span><span className="at-hist-it">Robe lin Sandro</span><span className="at-hist-pr">78€</span></div>
        <div className="at-hist-row"><span className="at-hist-date">06 fév.</span><span className="at-hist-it">Pull cachemire</span><span className="at-hist-pr">42€</span></div>
      </div>
    </div>
  );
}

/* ─────────── Sauge ─────────── */

function LandingSauge() {
  return (
    <div className="screen sg-screen">
      <div className="sg-nav">
        <span className="sg-nav-mark">Vintiz</span>
        <span className="sg-nav-cta">Boutique</span>
      </div>
      <div className="sg-hero">
        <div className="sg-hero-tag">Capsule · Printemps pré-aimé</div>
        <h1 className="sg-hero-title">Tout a déjà<br/>une histoire.</h1>
        <p className="sg-hero-lede">482 pièces sélectionnées à Vernon. Documentées une à une. À porter de nouveau.</p>
        <button className="sg-cta">Voir la sélection</button>
      </div>
      <div className="sg-stats">
        <div className="sg-stat"><div className="sg-stat-n">482</div><div className="sg-stat-l">pièces actives</div></div>
        <div className="sg-stat"><div className="sg-stat-n">68%</div><div className="sg-stat-l">premium</div></div>
        <div className="sg-stat"><div className="sg-stat-n">241<span>kg</span></div><div className="sg-stat-l">non-jetés</div></div>
      </div>
      <div className="sg-grid">
        <div className="sg-tile">
          <div className="sg-tile-img" style={{background:'linear-gradient(140deg,#cdd6c8,#8aa092)'}}></div>
          <div className="sg-tile-brand">Petit Bateau</div>
          <div className="sg-tile-meta"><span>Marinière 36</span><span>18€</span></div>
        </div>
        <div className="sg-tile">
          <div className="sg-tile-img" style={{background:'linear-gradient(140deg,#e8d4c2,#c2937a)'}}></div>
          <div className="sg-tile-brand">Sandro</div>
          <div className="sg-tile-meta"><span>Robe lin</span><span>78€</span></div>
        </div>
      </div>
      <div className="sg-foot">Vintiz · Vernon · reverse à Solidarité Textiles</div>
    </div>
  );
}

function AccountSauge() {
  return (
    <div className="screen sg-screen sg-account">
      <div className="sg-nav">
        <span className="sg-nav-mark">Bonjour Sophie</span>
        <span className="sg-nav-cta">Déco.</span>
      </div>
      <div className="sg-card-fid">
        <div className="sg-card-row">
          <div className="sg-card-tier">Gold</div>
          <div className="sg-card-num">V482931</div>
        </div>
        <div className="sg-card-pts">1 240<span> pts</span></div>
        <div className="sg-progress"><div className="sg-progress-bar" style={{width:'82%'}}></div></div>
        <div className="sg-card-foot">260 pts pour le palier suivant</div>
      </div>
      <div className="sg-tabs">
        <span className="sg-tab active">Aperçu</span>
        <span className="sg-tab">Offres</span>
        <span className="sg-tab">Historique</span>
        <span className="sg-tab">RGPD</span>
      </div>
      <div className="sg-offer">
        <div className="sg-offer-tag">Anniversaire</div>
        <div className="sg-offer-title">−10€ valable jusqu'au 30 avril</div>
        <div className="sg-offer-code">ANNIV-AB12CD</div>
      </div>
      <div className="sg-section">Dernières pièces achetées</div>
      <div className="sg-hist">
        <div className="sg-hist-row"><span>14 mars</span><span>Marinière P. Bateau</span><span>18€</span></div>
        <div className="sg-hist-row"><span>28 fév.</span><span>Robe lin Sandro</span><span>78€</span></div>
        <div className="sg-hist-row"><span>06 fév.</span><span>Pull cachemire</span><span>42€</span></div>
      </div>
    </div>
  );
}

/* ─────────── Néo ─────────── */

function LandingNeo() {
  return (
    <div className="screen nx-screen">
      <div className="nx-nav">
        <span className="nx-nav-mark">VINTIZ</span>
        <span className="nx-nav-dot"></span>
        <span className="nx-nav-cta">SHOP</span>
      </div>
      <div className="nx-hero">
        <div className="nx-hero-meta"><span>VRN · 2026</span><span>482 PIÈCES</span></div>
        <h1 className="nx-hero-title">SECOND<br/>HAND<br/><em>HAUT.</em></h1>
        <div className="nx-hero-sub">Boutique physique à Vernon. Sélection live mise à jour chaque vendredi.</div>
        <button className="nx-cta">Voir la sélection ↗</button>
      </div>
      <div className="nx-grid">
        <div className="nx-tile">
          <div className="nx-tile-img" style={{background:'linear-gradient(140deg,#a8c4ba,#0b7a6a)'}}></div>
          <div className="nx-tile-meta"><span>P. BATEAU · 36</span><span>18€</span></div>
        </div>
        <div className="nx-tile featured">
          <div className="nx-tile-img" style={{background:'linear-gradient(140deg,#ffd5e5,#e84e8b)'}}>
            <span className="nx-tile-flag">NOUVEAU</span>
          </div>
          <div className="nx-tile-meta"><span>SANDRO</span><span>78€</span></div>
        </div>
        <div className="nx-tile">
          <div className="nx-tile-img" style={{background:'linear-gradient(140deg,#ddd9c8,#8e7b57)'}}></div>
          <div className="nx-tile-meta"><span>ZADIG · 38</span><span>92€</span></div>
        </div>
        <div className="nx-tile">
          <div className="nx-tile-img" style={{background:'linear-gradient(140deg,#cde5df,#0b7a6a)'}}></div>
          <div className="nx-tile-meta"><span>SÉZANE</span><span>54€</span></div>
        </div>
      </div>
      <div className="nx-foot">
        <span>VINTIZ · VERNON · NMD</span>
        <span>2026</span>
      </div>
    </div>
  );
}

function AccountNeo() {
  return (
    <div className="screen nx-screen nx-account">
      <div className="nx-nav">
        <span className="nx-nav-mark">VINTIZ</span>
        <span className="nx-nav-cta">SOPHIE M.</span>
      </div>
      <div className="nx-card">
        <div className="nx-card-tier">GOLD MEMBER</div>
        <div className="nx-card-pts">1 240<span>PTS</span></div>
        <div className="nx-card-num">V — 482931</div>
        <div className="nx-card-bar"><div className="nx-card-bar-fill" style={{width:'82%'}}></div></div>
      </div>
      <div className="nx-tabs">
        <span className="nx-tab active">APERÇU</span>
        <span className="nx-tab">OFFRES</span>
        <span className="nx-tab">HISTO.</span>
      </div>
      <div className="nx-offer">
        <div className="nx-offer-flag">ANNIV</div>
        <div className="nx-offer-body">
          <div className="nx-offer-title">−10€ jusqu'au 30 avril</div>
          <div className="nx-offer-code">ANNIV-AB12CD</div>
        </div>
      </div>
      <div className="nx-section">DERNIÈRES VISITES</div>
      <div className="nx-hist">
        <div className="nx-hist-row"><span>14·03</span><span>P. BATEAU MARINIÈRE</span><span>18€</span></div>
        <div className="nx-hist-row"><span>28·02</span><span>SANDRO ROBE</span><span>78€</span></div>
        <div className="nx-hist-row"><span>06·02</span><span>CACHEMIRE NOIR</span><span>42€</span></div>
      </div>
    </div>
  );
}

window.FrontendPage = FrontendPage;
