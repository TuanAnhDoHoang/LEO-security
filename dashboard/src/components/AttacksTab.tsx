import { useState } from 'react'

interface AttacksTabProps { active: boolean }

const ATTACKS = [
  { id: 'jamming', icon: '📡', name: 'RF Jamming & Spoofing', desc: 'Nhiễu tín hiệu tần số vô tuyến, giả mạo tín hiệu GPS/GNSS.', severity: 'critical' },
  { id: 'eavesdrop', icon: '👂', name: 'Eavesdropping', desc: 'Nghe lén thụ động trên kênh vô tuyến. Không mã hóa → lộ dữ liệu.', severity: 'high' },
  { id: 'dos', icon: '💥', name: 'DoS / DDoS Uplink', desc: 'Bão hòa băng thông, làm quá tải bộ xử lý trên vệ tinh.', severity: 'critical' },
  { id: 'replay', icon: '🔁', name: 'Replay & MITM', desc: 'Tấn công lặp lại gói tin, xen giữa kênh điều khiển TT&C.', severity: 'critical' },
  { id: 'supply', icon: '🏭', name: 'Supply Chain Attack', desc: 'Cấy backdoor vào firmware/phần cứng vệ tinh.', severity: 'high' },
  { id: 'protocol', icon: '🔓', name: 'Protocol Vulnerability', desc: 'Khai thác lỗ hổng DVB-S2, DVB-RCS2.', severity: 'med' },
]

const DETAILS: Record<string, { title: string; steps: string[] }> = {
  jamming: { title: 'RF Jamming & GNSS Spoofing', steps: ['Phát nhiễu trên Ku: 14–14.5 GHz', 'Thu phát vệ tinh bị bão hòa', 'GPS Spoofing → sai lệch định vị', 'Phòng chống: FHSS, beamforming'] },
  eavesdrop: { title: 'Passive Eavesdropping', steps: ['Kênh vô tuyến broadcast → thu được', 'Giải mã DVB-S2 không E2EE', 'Lộ metadata → traffic analysis', 'Phòng chống: E2EE, TLS 1.3'] },
  dos: { title: 'DoS / DDoS Uplink Flooding', steps: ['Gửi lượng lớn gói tin uplink', 'Gateway bị quá tải', 'Amplification via UDP', 'Phòng chống: rate limiting, QoS'] },
  replay: { title: 'Replay Attack & MITM', steps: ['Capture lệnh TT&C', 'Phát lại gói lệnh cũ', 'MITM: thay đổi lệnh quỹ đạo', 'Phòng chống: Nonce + HMAC'] },
  supply: { title: 'Supply Chain Attack', steps: ['Cấy mã độc vào firmware', 'Backdoor kích hoạt khi trigger', 'Không thể kiểm tra vật lý', 'Phòng chống: Secure Boot, SBOM'] },
  protocol: { title: 'Protocol Vulnerability', steps: ['Overflow trong DVB-S2/RCS2 parser', 'SNMP v1/v2 không mã hóa', 'Web interface RCE', 'Phòng chống: fuzzing, patching'] },
}

export default function AttacksTab({ active }: AttacksTabProps) {
  const [sel, setSel] = useState<string | null>(null)
  const d = sel ? DETAILS[sel] : null

  return (
    <div className={`panel-section ${active ? 'active' : ''}`} style={{ display: active ? 'flex' : 'none', alignItems: 'flex-start' }}>
      <div className="panel" style={{ width: '100%', marginBottom: 4 }}>
        <div className="panel-title">⚠️ Bề mặt tấn công (Attack Surface) trong mạng LEO</div>
        <div style={{ color: 'var(--dim)', fontSize: 12, lineHeight: 1.7 }}>
          Hệ thống vệ tinh LEO có bề mặt tấn công rộng. ENISA (2023) xác định: <span style={{ color: 'var(--amber)' }}>Physical, Cyber, Supply Chain, Natural threats</span>.
        </div>
      </div>
      <div className="attack-grid">
        {ATTACKS.map(a => (
          <div key={a.id} className={`attack-card ${sel === a.id ? 'active-card' : ''}`} onClick={() => setSel(a.id)}>
            <div className="attack-icon">{a.icon}</div>
            <div className="attack-name">{a.name}</div>
            <div className="attack-desc">{a.desc}</div>
            <div><span className={`severity sev-${a.severity}`}>{a.severity.toUpperCase()}</span></div>
          </div>
        ))}
      </div>
      <div className="panel attack-detail">
        <div className="panel-title">🔍 Chi tiết tấn công</div>
        <div className="detail-content">
          {d ? (
            <>
              <div style={{ color: 'var(--amber)', fontFamily: "'Orbitron',monospace", fontSize: 10, letterSpacing: 1, marginBottom: 12 }}>{d.title}</div>
              {d.steps.map((s, i) => (
                <div className="step" key={i}><div className="step-num">[{String(i + 1).padStart(2, '0')}]</div><div>{s}</div></div>
              ))}
            </>
          ) : (
            <div style={{ color: 'var(--dim)', textAlign: 'center', padding: '30px 0', fontSize: 12 }}>← Chọn một loại tấn công</div>
          )}
        </div>
      </div>
    </div>
  )
}
