type TabId = 'topology' | 'attacks' | 'security' | 'simulator' | 'references'

interface TabBarProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
}

const TABS: { id: TabId; icon: string; label: string }[] = [
  { id: 'topology', icon: '🌐', label: 'Kiến Trúc LEO' },
  { id: 'attacks', icon: '⚠️', label: 'Vector Tấn Công' },
  { id: 'security', icon: '🔒', label: 'Cơ Chế Bảo Mật' },
  { id: 'simulator', icon: '▶', label: 'Mô Phỏng Demo' },
  { id: 'references', icon: '📚', label: 'Tài Liệu & Từ Khóa' },
]

export default function TabBar({ activeTab, onTabChange }: TabBarProps) {
  return (
    <div className="tabs">
      {TABS.map(tab => (
        <div
          key={tab.id}
          className={`tab ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.icon} {tab.label}
        </div>
      ))}
    </div>
  )
}
