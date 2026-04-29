// Page Backend — Cahier de Travail + Compagnon IA
// Backend = charte distincte (Linear/Stripe) + dark mode

const { useState: useStateB } = React;

function BackendPage() {
  const dirs = Object.values(window.VINTIZ_DIRECTIONS);
  const [theme, setTheme] = useStateB('light');
  React.useEffect(() => {
    const update = () => {
      document.querySelectorAll('.tablet-frame').forEach(el => {
        const w = el.clientWidth;
        el.style.setProperty('--tablet-scale', (w / 1024).toFixed(3));
      });
    };
    update();
    window.addEventListener('resize', update);
    const t = setTimeout(update, 100);
    return () => { window.removeEventListener('resize', update); clearTimeout(t); };
  }, [theme]);
  return (
    <div className="backend-root">
      <header className="page-section-header">
        <div className="page-section-eyebrow">03 · Backend — outil pro tactile</div>
        <h2 className="page-section-title">Caisse + ERP, optimisé tablette</h2>
        <p className="page-section-lede">
          Charte distincte cousine de la front : neutres dominants, accent teal pour les actions,
          densité raisonnée. Pour Hélène (manager) et Margaux (vendeuse) toute la journée.
        </p>
        <div className="theme-switch">
          <button className={theme==='light'?'active':''} onClick={()=>setTheme('light')}>Clair</button>
          <button className={theme==='dark'?'active':''} onClick={()=>setTheme('dark')}>Sombre</button>
        </div>
      </header>

      <div className="backend-grid">
        {dirs.map(d => (
          <div className="backend-col" key={d.id} data-dir={d.id} data-theme={theme}>
            <div className="backend-col-head">
              <span className="backend-col-num">0{Object.keys(window.VINTIZ_DIRECTIONS).indexOf(d.id) + 1}</span>
              <span className="backend-col-name">{d.name}</span>
              <span className="backend-col-tag">backend · {theme}</span>
            </div>

            <div className="tablet-wrap">
              <div className="tablet-label">Cahier de Travail — /dashboard/cahier-du-jour</div>
              <div className="tablet-frame">
                {d.id === 'atelier' && <CahierAtelier theme={theme} />}
                {(d.id === 'sauge' || d.id === 'saugeNeo') && <CahierSauge theme={theme} dir={d.id} />}
                {d.id === 'neo' && <CahierNeo theme={theme} />}
              </div>
            </div>

            <div className="tablet-wrap">
              <div className="tablet-label">Compagnon IA — /ia</div>
              <div className="tablet-frame">
                {d.id === 'atelier' && <IaAtelier theme={theme} />}
                {(d.id === 'sauge' || d.id === 'saugeNeo') && <IaSauge theme={theme} dir={d.id} />}
                {d.id === 'neo' && <IaNeo theme={theme} />}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────── Cahier (3 directions) ─────────── */

function CahierShell({ children, theme, dir }) {
  return (
    <div className={`bk-screen bk-${dir}`} data-theme={theme}>
      {children}
    </div>
  );
}

function BkSidebar({ dir, theme, active }) {
  const items = [
    { id: 'dash', label: 'Tableau de bord', icon: '◇' },
    { id: 'cahier', label: 'Cahier du jour', icon: '◈' },
    { id: 'pos', label: 'Caisse', icon: '◉' },
    { id: 'inv', label: 'Inventaire', icon: '☷' },
    { id: 'cli', label: 'Clientes', icon: '◌' },
    { id: 'ia', label: 'Compagnon IA', icon: '✦' },
    { id: 'rep', label: 'Rapports', icon: '◐' },
    { id: 'set', label: 'Réglages', icon: '⌗' },
  ];
  return (
    <aside className="bk-side">
      <div className="bk-side-mark">VINTIZ</div>
      <div className="bk-side-sub">Vernon</div>
      <nav className="bk-side-nav">
        {items.map(it => (
          <div key={it.id} className={`bk-side-item ${active===it.id?'active':''}`}>
            <span className="bk-side-icon">{it.icon}</span>
            <span className="bk-side-label">{it.label}</span>
          </div>
        ))}
      </nav>
      <div className="bk-side-foot">
        <div className="bk-side-user">HM</div>
        <div className="bk-side-user-meta">
          <div>Hélène Marais</div>
          <div className="bk-side-user-role">Manager</div>
        </div>
      </div>
    </aside>
  );
}

function CahierAtelier({ theme }) {
  return (
    <CahierShell theme={theme} dir="atelier">
      <BkSidebar dir="atelier" theme={theme} active="cahier" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread">Cahier du jour <span className="bk-bread-sep">/</span> Mardi 28 avril</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">12°C · couvert</span>
            <button className="bk-btn-mute">Imprimer</button>
            <button className="bk-btn-primary">Signer journée</button>
          </div>
        </div>
        <div className="bk-cahier-hero">
          <div className="bk-cahier-eyebrow">— Objectif du jour —</div>
          <div className="bk-cahier-amount">1 240<span> € · reste 482 €</span></div>
          <div className="bk-cahier-prog"><div style={{width:'61%'}}></div></div>
          <div className="bk-cahier-meta"><span>61% atteint</span><span>·</span><span>+8% vs N-1</span></div>
        </div>
        <div className="bk-grid-3">
          <BkKpi label="Tickets" value="14" delta="+3" />
          <BkKpi label="Panier" value="54€" delta="+12%" />
          <BkKpi label="Cumul mois" value="18 240€" delta="74%" />
        </div>
        <div className="bk-section">
          <div className="bk-section-title"><em>Message</em> du jour</div>
          <div className="bk-msg">Live Insta à 18h sur la sélection vintage cachemire. Margaux prépare 6 pièces.</div>
        </div>
        <div className="bk-section">
          <div className="bk-section-title"><em>Opération</em> en cours</div>
          <div className="bk-op">−20% sur les robes Sandro · jusqu'au 30 avril</div>
        </div>
      </main>
    </CahierShell>
  );
}

function CahierSauge({ theme }) {
  return (
    <CahierShell theme={theme} dir="sauge">
      <BkSidebar dir="sauge" theme={theme} active="cahier" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread">Cahier du jour · mardi 28 avril</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">12°C · couvert</span>
            <button className="bk-btn-mute">Exporter</button>
            <button className="bk-btn-primary">Signer la journée</button>
          </div>
        </div>
        <div className="bk-cahier-hero">
          <div className="bk-cahier-eyebrow">Objectif</div>
          <div className="bk-cahier-amount">1 240 €<span> · reste 482 €</span></div>
          <div className="bk-cahier-prog"><div style={{width:'61%'}}></div></div>
          <div className="bk-cahier-meta"><span>61% atteint</span><span>+8% vs N-1</span></div>
        </div>
        <div className="bk-grid-3">
          <BkKpi label="Tickets" value="14" delta="+3" />
          <BkKpi label="Panier moyen" value="54 €" delta="+12%" />
          <BkKpi label="Cumul mois" value="18 240 €" delta="74%" />
        </div>
        <div className="bk-section">
          <div className="bk-section-title">Message du jour</div>
          <div className="bk-msg">Live Insta à 18h sur la sélection vintage cachemire. Margaux prépare 6 pièces.</div>
        </div>
        <div className="bk-section">
          <div className="bk-section-title">Opération en cours</div>
          <div className="bk-op">−20% sur les robes Sandro — jusqu'au 30 avril</div>
        </div>
      </main>
    </CahierShell>
  );
}

function CahierNeo({ theme }) {
  return (
    <CahierShell theme={theme} dir="neo">
      <BkSidebar dir="neo" theme={theme} active="cahier" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread">CAHIER · MAR 28·04</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">12° · COUVERT</span>
            <button className="bk-btn-mute">EXPORT</button>
            <button className="bk-btn-primary">SIGNER ↗</button>
          </div>
        </div>
        <div className="bk-cahier-hero">
          <div className="bk-cahier-eyebrow">OBJECTIF JOUR</div>
          <div className="bk-cahier-amount">1 240€<span> / reste 482€</span></div>
          <div className="bk-cahier-prog"><div style={{width:'61%'}}></div></div>
          <div className="bk-cahier-meta"><span>61%</span><span>+8% N-1</span></div>
        </div>
        <div className="bk-grid-3">
          <BkKpi label="TICKETS" value="14" delta="+3" />
          <BkKpi label="PANIER" value="54€" delta="+12%" />
          <BkKpi label="MOIS" value="18 240€" delta="74%" />
        </div>
        <div className="bk-section">
          <div className="bk-section-title">MESSAGE</div>
          <div className="bk-msg">Live Insta 18h · sélection cachemire · Margaux prépare 6 pièces.</div>
        </div>
        <div className="bk-section">
          <div className="bk-section-title">OPÉRATION</div>
          <div className="bk-op">−20% ROBES SANDRO · JUSQU'AU 30·04</div>
        </div>
      </main>
    </CahierShell>
  );
}

function BkKpi({ label, value, delta }) {
  return (
    <div className="bk-kpi">
      <div className="bk-kpi-label">{label}</div>
      <div className="bk-kpi-value">{value}</div>
      <div className="bk-kpi-delta">{delta}</div>
    </div>
  );
}

/* ─────────── Compagnon IA (3 directions) ─────────── */

function IaTools() {
  return [
    { id: 'mapping', title: 'Mapping boutique', desc: 'Heatmap d\'occupation des 11 zones. L\'IA propose des réagencements.', glyph: '◇' },
    { id: 'check', title: 'Checklist semaine', desc: '5–8 actions concrètes générées chaque lundi.', glyph: '◈' },
    { id: 'tendances', title: 'Tendances mode', desc: 'Snapshot Vinted / Pinterest / Insta saison en cours.', glyph: '✧' },
    { id: 'personas', title: 'Personas marketing', desc: 'Rapport mensuel : performance + opportunités.', glyph: '◌' },
    { id: 'photo', title: 'Analyse photo', desc: 'Pré-remplit la fiche produit à partir d\'une image.', glyph: '◐' },
  ];
}

function IaShell({ children, theme, dir }) {
  return (
    <div className={`bk-screen bk-${dir}`} data-theme={theme}>
      {children}
    </div>
  );
}

function IaAtelier({ theme }) {
  const tools = IaTools();
  return (
    <IaShell theme={theme} dir="atelier">
      <BkSidebar dir="atelier" theme={theme} active="ia" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread"><em>Compagnon</em> IA</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">5 outils</span>
          </div>
        </div>
        <div className="bk-ia-intro">
          <div className="bk-ia-eyebrow">— Atelier —</div>
          <div className="bk-ia-title"><em>Cinq</em> outils pour penser la semaine.</div>
        </div>
        <div className="bk-ia-grid">
          {tools.map(t => (
            <div className="bk-ia-card" key={t.id}>
              <div className="bk-ia-glyph">{t.glyph}</div>
              <div className="bk-ia-card-title">{t.title}</div>
              <div className="bk-ia-card-desc">{t.desc}</div>
              <button className="bk-ia-card-cta">Ouvrir →</button>
            </div>
          ))}
        </div>
      </main>
    </IaShell>
  );
}

function IaSauge({ theme }) {
  const tools = IaTools();
  return (
    <IaShell theme={theme} dir="sauge">
      <BkSidebar dir="sauge" theme={theme} active="ia" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread">Compagnon IA</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">5 outils · à jour</span>
            <button className="bk-btn-mute">Historique</button>
          </div>
        </div>
        <div className="bk-ia-intro">
          <div className="bk-ia-eyebrow">Recommandation du jour</div>
          <div className="bk-ia-title">Déplacer 4 pièces de Petits Prix vers Tendance.</div>
          <div className="bk-ia-sub">Score moyen +0.4 · vélocité estimée +12% sur 7 jours.</div>
          <div className="bk-ia-actions">
            <button className="bk-btn-primary">Voir le détail</button>
            <button className="bk-btn-mute">Plus tard</button>
          </div>
        </div>
        <div className="bk-ia-grid">
          {tools.map(t => (
            <div className="bk-ia-card" key={t.id}>
              <div className="bk-ia-glyph">{t.glyph}</div>
              <div className="bk-ia-card-title">{t.title}</div>
              <div className="bk-ia-card-desc">{t.desc}</div>
              <button className="bk-ia-card-cta">Ouvrir</button>
            </div>
          ))}
        </div>
      </main>
    </IaShell>
  );
}

function IaNeo({ theme }) {
  const tools = IaTools();
  return (
    <IaShell theme={theme} dir="neo">
      <BkSidebar dir="neo" theme={theme} active="ia" />
      <main className="bk-main">
        <div className="bk-topbar">
          <div className="bk-bread">COMPAGNON IA</div>
          <div className="bk-topbar-actions">
            <span className="bk-pill-mute">5 / 5 OK</span>
            <button className="bk-btn-mute">LOG</button>
          </div>
        </div>
        <div className="bk-ia-intro">
          <div className="bk-ia-eyebrow">RECO #482 · 28·04</div>
          <div className="bk-ia-title">DÉPLACER 4 PIÈCES → TENDANCE.</div>
          <div className="bk-ia-sub">SCORE +0.4 · VÉLOCITÉ +12% · 7J</div>
          <div className="bk-ia-actions">
            <button className="bk-btn-primary">DÉTAIL ↗</button>
            <button className="bk-btn-mute">SKIP</button>
          </div>
        </div>
        <div className="bk-ia-grid">
          {tools.map(t => (
            <div className="bk-ia-card" key={t.id}>
              <div className="bk-ia-glyph">{t.glyph}</div>
              <div className="bk-ia-card-title">{t.title.toUpperCase()}</div>
              <div className="bk-ia-card-desc">{t.desc}</div>
              <button className="bk-ia-card-cta">OUVRIR ↗</button>
            </div>
          ))}
        </div>
      </main>
    </IaShell>
  );
}

window.BackendPage = BackendPage;
