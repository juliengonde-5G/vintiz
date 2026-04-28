// App shell — onglets Charte / Frontend / Backend + tweaks panel
const { useState: useStateApp } = React;

const APP_DEFAULTS = /*EDITMODE-BEGIN*/{
  "tab": "charte",
  "showTweaks": false
}/*EDITMODE-END*/;

function App() {
  const [tab, setTab] = useStateApp(APP_DEFAULTS.tab || 'charte');
  const tabs = [
    { id: 'charte', label: '01 · Charte' },
    { id: 'frontend', label: '02 · Frontend' },
    { id: 'backend', label: '03 · Backend' },
  ];
  return (
    <div className="app-shell">
      <nav className="app-tabs">
        <span className="app-tabs-mark"><em>Vintiz</em> · charte v3</span>
        {tabs.map(t => (
          <button key={t.id} className={`app-tab ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
        <span className="app-tabs-spacer"></span>
        <span className="app-tabs-meta">3 directions · Atelier · Sauge · Néo</span>
      </nav>
      {tab === 'charte' && <window.ChartePage />}
      {tab === 'frontend' && <window.FrontendPage />}
      {tab === 'backend' && <window.BackendPage />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
