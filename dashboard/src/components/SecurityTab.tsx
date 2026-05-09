interface SecurityTabProps { active: boolean }

const SECURITY_LEFT = [
  { icon: '🔐', name: 'End-to-End Encryption (E2EE)', desc: 'Mã hóa toàn bộ kênh truyền từ đầu cuối. AES-256-GCM hoặc ChaCha20-Poly1305 cho data-in-transit.', tags: ['AES-256-GCM', 'ChaCha20', 'TLS 1.3', 'DTLS'] },
  { icon: '🔑', name: 'Key Management & PKI', desc: 'Hạ tầng khóa công khai cho xác thực vệ tinh. Certificate-based auth, rotation key, HSM.', tags: ['PKI / X.509', 'HSM', 'ECDH', 'Key Rotation'] },
  { icon: '📡', name: 'Anti-Jamming Techniques', desc: 'Spread Spectrum (FHSS/DSSS), Adaptive Beamforming, Dynamic Frequency Hopping.', tags: ['FHSS', 'DSSS', 'Beamforming', 'Adaptive Power'] },
]

const SECURITY_RIGHT = [
  { icon: '🛡️', name: 'Zero Trust Architecture', desc: 'Không tin tưởng mặc định. Mọi phiên liên lạc cần xác thực lại, least privilege.', tags: ['Zero Trust', 'MFA', 'Micro-segmentation'] },
  { icon: '🔭', name: 'Intrusion Detection (IDS/IPS)', desc: 'Phát hiện bất thường trong lưu lượng vệ tinh. ML-based anomaly detection.', tags: ['ML Anomaly', 'SIEM', 'RF Fingerprint'] },
  { icon: '🔬', name: 'Post-Quantum Cryptography (PQC)', desc: 'NIST PQC standards (CRYSTALS-Kyber, Dilithium) cho vệ tinh LEO 5-15 năm.', tags: ['CRYSTALS-Kyber', 'Dilithium', 'NIST PQC', 'Harvest-Now'] },
  { icon: '📋', name: 'Compliance & Standards', desc: 'ENISA 2023, NIST SP 800-53, ITU-R, NATO SATCOM, ISO 27001.', tags: ['ENISA 2023', 'NIST SP800-53', 'ISO 27001', 'ITU-R'] },
]

export default function SecurityTab({ active }: SecurityTabProps) {
  return (
    <div className={`panel-section ${active ? 'active' : ''}`} style={{ display: active ? 'flex' : 'none', alignItems: 'flex-start' }}>
      <div className="sec-col">
        <div className="panel-title" style={{ marginBottom: 0, border: 'none' }}>🔒 Cơ chế bảo mật cho mạng LEO</div>
        {SECURITY_LEFT.map(s => (
          <div className="sec-card" key={s.name}>
            <div className="sec-name">{s.icon} {s.name}</div>
            <div className="sec-desc">{s.desc}</div>
            <div>{s.tags.map(t => <span className="tag" key={t}>{t}</span>)}</div>
          </div>
        ))}
      </div>
      <div className="sec-col">
        {SECURITY_RIGHT.map(s => (
          <div className="sec-card" key={s.name}>
            <div className="sec-name">{s.icon} {s.name}</div>
            <div className="sec-desc">{s.desc}</div>
            <div>{s.tags.map(t => <span className="tag" key={t}>{t}</span>)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
