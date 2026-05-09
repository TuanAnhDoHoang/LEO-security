import { useEffect, useRef } from 'react'

interface TopologyTabProps {
  active: boolean
}

export default function TopologyTab({ active }: TopologyTabProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (active) drawTopology()
  }, [active])

  useEffect(() => {
    const handleResize = () => {
      if (active) drawTopology()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [active])

  function drawTopology() {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const W = canvas.offsetWidth || 700
    canvas.width = W
    canvas.height = 400
    ctx.clearRect(0, 0, W, 400)

    // Earth arc
    ctx.beginPath()
    ctx.arc(W / 2, 580, 520, Math.PI * 1.1, Math.PI * 1.9)
    ctx.strokeStyle = '#00e5ff22'
    ctx.lineWidth = 60
    ctx.stroke()
    ctx.strokeStyle = '#00e5ff44'
    ctx.lineWidth = 2
    ctx.stroke()

    // Orbit rings
    ;[180, 130, 80].forEach((y, i) => {
      ctx.beginPath()
      ctx.ellipse(W / 2, y, W * 0.42 - i * 30, 18, 0, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(0,229,255,0.12)'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 8])
      ctx.stroke()
      ctx.setLineDash([])
    })

    // Satellites
    const sats = [
      { x: 0.18, y: 0.22 }, { x: 0.35, y: 0.18 }, { x: 0.52, y: 0.15 },
      { x: 0.68, y: 0.18 }, { x: 0.82, y: 0.22 }, { x: 0.12, y: 0.35 },
      { x: 0.88, y: 0.35 }, { x: 0.25, y: 0.42 }, { x: 0.75, y: 0.42 },
    ]
    sats.forEach(s => {
      const sx = s.x * W, sy = s.y * 400
      ctx.beginPath(); ctx.arc(sx, sy, 5, 0, Math.PI * 2)
      ctx.fillStyle = '#00e5ff'; ctx.shadowColor = '#00e5ff'; ctx.shadowBlur = 12; ctx.fill()
      ctx.shadowBlur = 0
      ctx.font = '11px serif'; ctx.fillStyle = '#00e5ffaa'; ctx.fillText('🛰', sx - 7, sy - 10)
    })

    // ISL links
    const islPairs: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 4], [5, 0], [6, 4], [5, 7], [6, 8]]
    islPairs.forEach(([a, b]) => {
      const s1 = sats[a], s2 = sats[b]
      ctx.beginPath()
      ctx.moveTo(s1.x * W, s1.y * 400)
      ctx.lineTo(s2.x * W, s2.y * 400)
      ctx.strokeStyle = 'rgba(21,101,255,0.5)'; ctx.lineWidth = 1.2
      ctx.setLineDash([3, 4]); ctx.stroke(); ctx.setLineDash([])
    })

    // Ground stations
    const gs = [
      { x: 0.15, y: 0.78, label: 'GS-HN' },
      { x: 0.50, y: 0.82, label: 'GS-SGN' },
      { x: 0.85, y: 0.76, label: 'GS-INT' },
    ]
    gs.forEach(g => {
      const gx = g.x * W, gy = g.y * 400
      ctx.beginPath(); ctx.arc(gx, gy, 7, 0, Math.PI * 2)
      ctx.fillStyle = '#00ff88'; ctx.shadowColor = '#00ff88'; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0
      ctx.fillStyle = '#00ff88aa'; ctx.font = '10px Exo 2,sans-serif'; ctx.fillText(g.label, gx - 12, gy + 18)
      const nearSat = sats[g.x < 0.3 ? 0 : g.x < 0.6 ? 2 : 4]
      ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(nearSat.x * W, nearSat.y * 400)
      ctx.strokeStyle = 'rgba(0,255,136,0.4)'; ctx.lineWidth = 1.5; ctx.setLineDash([2, 4]); ctx.stroke(); ctx.setLineDash([])
    })

    // User terminals
    const uts = [{ x: 0.30, y: 0.88 }, { x: 0.62, y: 0.92 }, { x: 0.78, y: 0.86 }]
    uts.forEach((u, i) => {
      const ux = u.x * W, uy = u.y * 400
      ctx.beginPath(); ctx.arc(ux, uy, 5, 0, Math.PI * 2)
      ctx.fillStyle = '#ffb300'; ctx.shadowColor = '#ffb300'; ctx.shadowBlur = 8; ctx.fill(); ctx.shadowBlur = 0
      ctx.fillStyle = '#ffb300aa'; ctx.font = '10px Exo 2,sans-serif'; ctx.fillText('UT-' + (i + 1), ux - 10, uy + 16)
      const nearSat = sats[u.x < 0.4 ? 1 : u.x < 0.7 ? 2 : 3]
      ctx.beginPath(); ctx.moveTo(ux, uy); ctx.lineTo(nearSat.x * W, nearSat.y * 400)
      ctx.strokeStyle = 'rgba(255,179,0,0.3)'; ctx.lineWidth = 1; ctx.setLineDash([1, 4]); ctx.stroke(); ctx.setLineDash([])
    })

    // Attacker
    const ax = 0.72 * W, ay = 0.70 * 400
    ctx.beginPath(); ctx.arc(ax, ay, 6, 0, Math.PI * 2)
    ctx.fillStyle = '#ff3355'; ctx.shadowColor = '#ff3355'; ctx.shadowBlur = 12; ctx.fill(); ctx.shadowBlur = 0
    ctx.font = '13px serif'; ctx.fillText('⚡', ax - 8, ay - 10)
    ctx.fillStyle = '#ff3355bb'; ctx.font = '10px Exo 2,sans-serif'; ctx.fillText('Attacker', ax - 18, ay + 18)
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(sats[3].x * W, sats[3].y * 400)
    ctx.strokeStyle = 'rgba(255,51,85,0.6)'; ctx.lineWidth = 2; ctx.setLineDash([4, 3]); ctx.stroke(); ctx.setLineDash([])

    // Label
    ctx.fillStyle = '#00e5ff55'; ctx.font = '11px Orbitron,monospace'; ctx.fillText('LEO ORBIT ZONE (~550km)', W / 2 - 80, 25)
  }

  return (
    <div className={`panel-section ${active ? 'active' : ''}`} style={{ display: active ? 'flex' : 'none' }}>
      <div className="metric-row" style={{ marginBottom: 0, width: '100%' }}>
        <div className="metric"><span className="metric-val">550km</span><div className="metric-label">Độ cao quỹ đạo (Starlink)</div></div>
        <div className="metric"><span className="metric-val">~20ms</span><div className="metric-label">Độ trễ RTT trung bình</div></div>
        <div className="metric"><span className="metric-val">6,000+</span><div className="metric-label">Vệ tinh trong constellation</div></div>
        <div className="metric"><span className="metric-val">Ku/Ka</span><div className="metric-label">Băng tần phổ biến</div></div>
        <div className="metric"><span className="metric-val">ISL</span><div className="metric-label">Inter-Satellite Link</div></div>
      </div>
      <div className="panel" style={{ flex: 1, minWidth: 320 }}>
        <div className="panel-title">🌐 Mô Hình Kiến Trúc LEO Constellation</div>
        <canvas ref={canvasRef} width={700} height={400} style={{ borderRadius: 6, border: '1px solid #00e5ff18', background: '#010812', display: 'block', width: '100%' }} />
      </div>
      <div style={{ width: 240, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="panel" style={{ flex: 1 }}>
          <div className="panel-title">📡 Chú thích</div>
          {[
            { color: '#00e5ff', label: 'Vệ tinh LEO', desc: 'Altitude 160–2000km, orbital period ~90min' },
            { color: '#00ff88', label: 'Ground Station (GS)', desc: 'Trạm mặt đất điều khiển & uplink' },
            { color: '#ffb300', label: 'User Terminal (UT)', desc: 'Thiết bị đầu cuối người dùng' },
            { color: '#ff3355', label: 'Attacker Node', desc: 'Nguồn tấn công tiềm năng' },
            { color: '#1565ff', label: 'ISL Link', desc: 'Inter-Satellite Link laser/RF' },
          ].map(item => (
            <div key={item.label} className="legend-item" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 5, marginBottom: 6, background: 'rgba(0,229,255,0.03)', border: '1px solid #00e5ff14', fontSize: 12 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0, background: item.color, boxShadow: `0 0 6px ${item.color}` }} />
              <div>
                <div>{item.label}</div>
                <div style={{ color: 'var(--dim)', fontSize: 11, marginTop: 2 }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="panel">
          <div className="panel-title">📋 Thành phần hệ thống</div>
          <div style={{ fontSize: '11.5px', color: 'var(--dim)', lineHeight: 1.8 }}>
            <div>▸ <span style={{ color: 'var(--text)' }}>Space Segment:</span> Satellite constellation</div>
            <div>▸ <span style={{ color: 'var(--text)' }}>Ground Segment:</span> TT&C, Gateway</div>
            <div>▸ <span style={{ color: 'var(--text)' }}>User Segment:</span> Terminal devices</div>
            <div>▸ <span style={{ color: 'var(--text)' }}>ISL:</span> Liên kết inter-satellite</div>
            <div>▸ <span style={{ color: 'var(--text)' }}>Feeder Link:</span> GS ↔ Satellite</div>
            <div>▸ <span style={{ color: 'var(--text)' }}>Service Link:</span> Satellite ↔ User</div>
          </div>
        </div>
      </div>
    </div>
  )
}
