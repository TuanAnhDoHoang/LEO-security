import { useState } from 'react'
import './App.css'
import Header from './components/Header'
import TabBar from './components/TabBar'
import TopologyTab from './components/TopologyTab'
import AttacksTab from './components/AttacksTab'
import SecurityTab from './components/SecurityTab'
import DemoSimulatorTab from './components/DemoSimulatorTab'
import ReferencesTab from './components/ReferencesTab'

type TabId = 'topology' | 'attacks' | 'security' | 'simulator' | 'references'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('simulator')

  return (
    <>
      <Header />
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="main-content">
        <TopologyTab active={activeTab === 'topology'} />
        <AttacksTab active={activeTab === 'attacks'} />
        <SecurityTab active={activeTab === 'security'} />
        <DemoSimulatorTab active={activeTab === 'simulator'} />
        <ReferencesTab active={activeTab === 'references'} />
      </div>
    </>
  )
}

export default App
