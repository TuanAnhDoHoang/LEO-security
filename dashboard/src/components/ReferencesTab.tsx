interface ReferencesTabProps { active: boolean }

export default function ReferencesTab({ active }: ReferencesTabProps) {
  const keywords = ['LEO cybersecurity', 'ENISA satellite assessment', 'GNS3 satellite simulation', 'NS-3 LEO network', 'satellite jamming attack', 'SATCOM encryption', 'DVB-S2 vulnerability', 'post-quantum satellite', 'Starlink security', 'low earth orbit threat model', 'satellite intrusion detection', 'TT&C security', 'ISL link encryption', 'GNSS spoofing']

  const refs = [
    { type: '🏛 ENISA Report', title: 'ENISA Cybersecurity of Space — Good Practices', meta: 'ENISA, 2023' },
    { type: '📖 IEEE Paper', title: 'Security Threats and Countermeasures in LEO Networks', meta: 'IEEE Communications Surveys' },
    { type: '📖 Journal', title: 'Cybersecurity Challenges for LEO Satellite Constellations', meta: 'Int. J. Cybersecurity, 2023' },
    { type: '🔧 Tool', title: 'NS-3 Satellite Module (SNS3)', meta: 'DVB-RCS2, DVB-S2 simulation' },
    { type: '🔧 Tool', title: 'GNS3 + OpenSAND Integration', meta: 'Satellite network emulator' },
    { type: '📖 Paper', title: 'Post-Quantum Cryptography for Satellite Communications', meta: '2023–2024' },
    { type: '🏛 NIST', title: 'NIST SP 800-53 Rev. 5 — Security Controls', meta: 'SATCOM infrastructure' },
    { type: '📖 Paper', title: 'Analyzing the Security of Starlink User Terminal', meta: 'Lennert Wouters et al., 2022' },
  ]

  return (
    <div className={`panel-section ${active ? 'active' : ''}`} style={{ display: active ? 'flex' : 'none', flexDirection: 'column', gap: 14 }}>
      <div className="panel" style={{ width: '100%' }}>
        <div className="panel-title">📚 Từ Khóa Nghiên Cứu</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {keywords.map(k => <span className="tag" key={k} style={{ fontSize: 11, padding: '4px 10px' }}>{k}</span>)}
        </div>
      </div>
      <div style={{ width: '100%' }}>
        <div className="panel-title" style={{ border: 'none', marginBottom: 10 }}>📄 Tài liệu tham khảo</div>
        <div className="ref-grid">
          {refs.map((r, i) => (
            <div className="ref-card" key={i}>
              <div className="ref-type">{r.type}</div>
              <div className="ref-title">{r.title}</div>
              <div className="ref-meta">{r.meta}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
