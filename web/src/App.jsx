import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import PriceSimulator from './components/PriceSimulator';
import DomainStudio from './components/DomainStudio';
import CopilotView from './components/CopilotView';
import ValidationView from './components/ValidationView';
import ScorecardView from './components/ScorecardView';
import EcommerceStore from './pages/EcommerceStore.jsx';
import SalesDashboard from './pages/SalesDashboard.jsx';

export default function App() {
  const [activeTab, setActiveTab] = useState('simulator');
  const [domains, setDomains] = useState([]);
  const [activeDomain, setActiveDomain] = useState('ecommerce');
  const [activeDomainPack, setActiveDomainPack] = useState(null);

  // Fetch list of domains from backend API
  const fetchDomains = async () => {
    try {
      const res = await fetch('/v1/domains');
      if (res.ok) {
        const data = await res.json();
        setDomains(data);
        if (data.length > 0 && !activeDomain) {
          setActiveDomain(data[0].pack_id || data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch domains list:', e);
      // Fallback mock list for standalone preview
      setDomains([
        { pack_id: 'ecommerce', name: 'E-commerce', status: 'published' },
        { pack_id: 'hospitality', name: 'Hospitality', status: 'published' },
        { pack_id: 'banking', name: 'Banking', status: 'published' },
        { pack_id: 'ev_charging', name: 'EV Charging', status: 'published' },
      ]);
    }
  };

  // Fetch detailed domain pack data for active domain
  const fetchActiveDomainPack = async (domainId) => {
    if (!domainId) return;
    try {
      const res = await fetch(`/v1/domains/${domainId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveDomainPack(data.pack_data || data);
      }
    } catch (e) {
      console.error(`Failed to fetch pack for ${domainId}:`, e);
    }
  };

  useEffect(() => {
    fetchDomains();
  }, []);

  useEffect(() => {
    if (activeDomain) {
      fetchActiveDomainPack(activeDomain);
    }
  }, [activeDomain]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeDomain={activeDomain}
        setActiveDomain={setActiveDomain}
        domains={domains.length > 0 ? domains : [
          { pack_id: 'ecommerce', name: 'E-commerce', status: 'published' },
          { pack_id: 'hospitality', name: 'Hospitality', status: 'published' },
          { pack_id: 'banking', name: 'Banking', status: 'published' },
          { pack_id: 'ev_charging', name: 'EV Charging', status: 'published' },
        ]}
      />

      {activeTab === 'store' ? (
        <EcommerceStore onBackToDashboard={() => setActiveTab('dashboard')} />
      ) : activeTab === 'dashboard' ? (
        <SalesDashboard
          activeDomain={activeDomain}
          activeDomainPack={activeDomainPack}
          onNavigateTab={setActiveTab}
        />
      ) : (
        <>
          <main className="container">
            {activeTab === 'simulator' && (
              <PriceSimulator activeDomainPack={activeDomainPack} />
            )}
            {activeTab === 'studio' && (
              <DomainStudio
                activeDomainPack={activeDomainPack}
                onPackUpdated={() => fetchActiveDomainPack(activeDomain)}
              />
            )}
            {activeTab === 'copilot' && (
              <CopilotView
                onDomainGenerated={(newPackId) => {
                  fetchDomains();
                  setActiveDomain(newPackId);
                  setActiveTab('simulator');
                }}
              />
            )}
            {activeTab === 'validation' && (
              <ValidationView activeDomainPack={activeDomainPack} />
            )}
            {activeTab === 'scorecard' && (
              <ScorecardView />
            )}
          </main>

          <footer style={{ marginTop: 'auto', padding: '1.5rem', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.8rem', borderTop: '1px solid var(--border-color)' }}>
            Monetize360 — Universal Dynamic Pricing Engine &bull; Deterministic Engine v1.0.0 &bull; E-commerce, Hospitality, Banking & EV Charging
          </footer>
        </>
      )}
    </div>
  );
}
