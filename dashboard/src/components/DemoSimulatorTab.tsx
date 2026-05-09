import { useState, useEffect, useRef, useCallback } from 'react'

interface DemoSimulatorTabProps { active: boolean }

interface LogEntry {
  id: number
  role: string
  message: string
  logType: string
  timestamp: string
}

type SimStatus = 'idle' | 'running' | 'stopped' | 'starting' | 'error'

const WS_URL = 'ws://localhost:3001'

export default function DemoSimulatorTab({ active }: DemoSimulatorTabProps) {
  const [status, setStatus] = useState<SimStatus>('idle')
  const [mode, setMode] = useState('all')
  const [senderLogs, setSenderLogs] = useState<LogEntry[]>([])
  const [receiverLogs, setReceiverLogs] = useState<LogEntry[]>([])
  const [eavesdropperLogs, setEavesdropperLogs] = useState<LogEntry[]>([])
  const [systemLogs, setSystemLogs] = useState<LogEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const logIdRef = useRef(0)
  const senderEndRef = useRef<HTMLDivElement>(null)
  const receiverEndRef = useRef<HTMLDivElement>(null)
  const eavesdropperEndRef = useRef<HTMLDivElement>(null)
  const systemEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs
  useEffect(() => {
    senderEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [senderLogs])
  useEffect(() => {
    receiverEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [receiverLogs])
  useEffect(() => {
    eavesdropperEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [eavesdropperLogs])
  useEffect(() => {
    systemEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [systemLogs])

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)

        if (data.type === 'status') {
          if (data.status === 'running' || data.status === 'starting') setStatus('running')
          else if (data.status === 'stopped') setStatus('stopped')
          else setStatus(data.status as SimStatus)
        }

        if (data.type === 'log') {
          const entry: LogEntry = {
            id: ++logIdRef.current,
            role: data.role,
            message: data.message,
            logType: data.logType || 'info',
            timestamp: new Date(data.timestamp).toLocaleTimeString('vi-VN', { hour12: false }),
          }

          switch (data.role) {
            case 'sender':
              setSenderLogs(prev => [...prev, entry])
              break
            case 'receiver':
              setReceiverLogs(prev => [...prev, entry])
              break
            case 'eavesdropper':
              setEavesdropperLogs(prev => [...prev, entry])
              break
            default:
              setSystemLogs(prev => [...prev, entry])
          }
        }

        if (data.type === 'error') {
          setStatus('error')
          setSystemLogs(prev => [...prev, {
            id: ++logIdRef.current,
            role: 'system',
            message: `ERROR: ${data.message}`,
            logType: 'attack',
            timestamp: new Date().toLocaleTimeString('vi-VN', { hour12: false }),
          }])
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setTimeout(connectWs, 2000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connectWs()
    return () => {
      wsRef.current?.close()
    }
  }, [connectWs])

  function startSimulation() {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      connectWs()
      setTimeout(() => startSimulation(), 500)
      return
    }

    // Clear logs
    setSenderLogs([])
    setReceiverLogs([])
    setEavesdropperLogs([])
    setSystemLogs([])
    logIdRef.current = 0
    setStatus('running')

    wsRef.current.send(JSON.stringify({
      action: 'start_eavesdropper',
      mode,
    }))
  }

  function stopSimulation() {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }))
    }
    setStatus('stopped')
  }

  const statusLabel = {
    idle: '◉ READY — Chọn attack simulator và nhấn Start',
    running: '◉ RUNNING — Simulation đang chạy...',
    starting: '◉ STARTING — Đang khởi động...',
    stopped: '◉ STOPPED — Simulation đã dừng',
    error: '◉ ERROR — Có lỗi xảy ra',
  }

  return (
    <div
      className={`panel-section demo-sim-section ${active ? 'active' : ''}`}
      style={{ display: active ? 'flex' : 'none' }}
    >
      {/* Controls Panel */}
      <div className="panel" style={{ width: '100%' }}>
        <div className="panel-title">🛰 Attack Simulator Dashboard</div>

        <div className="sim-controls">
          {/* Mode selector */}
          <select
            className="mode-select"
            value={mode}
            onChange={e => setMode(e.target.value)}
            disabled={status === 'running'}
          >
            <option value="all">All Phases (Plain → E2EE → Replay)</option>
            <option value="plain">Phase 1: Plaintext Only</option>
            <option value="encrypted">Phase 2: Encrypted (E2EE)</option>
            <option value="replay">Phase 3: Replay Attack</option>
          </select>

          {/* Attack buttons */}
          <button
            className={`btn btn-attack ${status === 'running' ? 'active-btn' : ''}`}
            onClick={startSimulation}
            disabled={status === 'running'}
          >
            👂 Eavesdropper
          </button>

          <button
            className="btn btn-attack"
            disabled={true}
            title="Coming soon"
          >
            📡 RF Jamming
          </button>

          <button
            className="btn btn-attack"
            disabled={true}
            title="Coming soon"
          >
            🔁 Replay MITM
          </button>

          {/* Stop button */}
          <button
            className="btn btn-stop"
            onClick={stopSimulation}
            disabled={status !== 'running'}
          >
            ⏹ Stop
          </button>

          {/* Status */}
          <div className={`sim-status ${status}`}>
            <div className={`dot ${status === 'running' ? 'green' : status === 'stopped' ? 'amber' : status === 'error' ? 'red' : ''}`}
              style={status === 'idle' ? { background: 'var(--dim)', boxShadow: 'none' } : {}}
            />
            {statusLabel[status]}
          </div>
        </div>
      </div>

      {/* Transfer order info */}
      <div style={{
        width: '100%',
        padding: '10px 16px',
        background: 'rgba(0,229,255,0.03)',
        border: '1px solid rgba(0,229,255,0.1)',
        borderRadius: 6,
        fontFamily: "'Share Tech Mono', monospace",
        fontSize: 11,
        color: 'var(--dim)',
        display: 'flex',
        gap: 24,
        flexWrap: 'wrap',
      }}>
        <span>Forward: <span style={{ color: 'var(--cyan)' }}>Sender</span> → SAT-A → <span style={{ color: 'var(--red)' }}>Eavesdropper</span> → SAT-B → <span style={{ color: 'var(--green)' }}>Receiver</span></span>
        <span>Delay: 6.0ms ± 0.9ms | Loss: 0.1% | Crypto: AES-256-GCM + ECDH X25519</span>
      </div>

      {/* 3-Column Log Grid */}
      <div className="log-grid">
        {/* Sender Panel */}
        <div className="log-panel sender-panel">
          <div className="log-panel-header">
            <span className="role-icon">📡</span>
            <span className="role-name">Sender</span>
            <span className="role-desc">GS-46 HCMC</span>
            <span className="log-count">{senderLogs.length}</span>
          </div>
          <div className="log-box">
            {senderLogs.length === 0 ? (
              <div className="log-empty">Sender logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              senderLogs.map(l => (
                <div key={l.id} className={`log-line log-${l.logType}`}>
                  <span className="log-time">[{l.timestamp}]</span> {l.message}
                </div>
              ))
            )}
            <div ref={senderEndRef} />
          </div>
        </div>

        {/* Receiver Panel */}
        <div className="log-panel receiver-panel">
          <div className="log-panel-header">
            <span className="role-icon">📡</span>
            <span className="role-name">Receiver</span>
            <span className="role-desc">GS-63 Singapore</span>
            <span className="log-count">{receiverLogs.length}</span>
          </div>
          <div className="log-box">
            {receiverLogs.length === 0 ? (
              <div className="log-empty">Receiver logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              receiverLogs.map(l => (
                <div key={l.id} className={`log-line log-${l.logType}`}>
                  <span className="log-time">[{l.timestamp}]</span> {l.message}
                </div>
              ))
            )}
            <div ref={receiverEndRef} />
          </div>
        </div>

        {/* Eavesdropper Panel */}
        <div className="log-panel eavesdropper-panel">
          <div className="log-panel-header">
            <span className="role-icon">👁</span>
            <span className="role-name">Hacker</span>
            <span className="role-desc">Eavesdropper MitM</span>
            <span className="log-count">{eavesdropperLogs.length}</span>
          </div>
          <div className="log-box">
            {eavesdropperLogs.length === 0 ? (
              <div className="log-empty">Eavesdropper logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              eavesdropperLogs.map(l => (
                <div key={l.id} className={`log-line log-${l.logType}`}>
                  <span className="log-time">[{l.timestamp}]</span> {l.message}
                </div>
              ))
            )}
            <div ref={eavesdropperEndRef} />
          </div>
        </div>
      </div>

      {/* System Log */}
      <div className="log-panel system-log-panel">
        <div className="log-panel-header">
          <span className="role-icon">⚙️</span>
          <span className="role-name" style={{ color: 'var(--cyan)' }}>System</span>
          <span className="role-desc">Transfer order & Infrastructure</span>
          <span className="log-count" style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}>{systemLogs.length}</span>
        </div>
        <div className="log-box">
          {systemLogs.length === 0 ? (
            <div className="log-empty">System events sẽ hiển thị ở đây...</div>
          ) : (
            systemLogs.map(l => (
              <div key={l.id} className={`log-line log-${l.logType}`}>
                <span className="log-time">[{l.timestamp}]</span> {l.message}
              </div>
            ))
          )}
          <div ref={systemEndRef} />
        </div>
      </div>
    </div>
  )
}
