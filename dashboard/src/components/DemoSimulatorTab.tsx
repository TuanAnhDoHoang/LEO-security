import { useCallback, useEffect, useRef, useState } from 'react'

interface DemoSimulatorTabProps {
  active: boolean
}

interface LogEntry {
  id: number
  role: string
  message: string
  logType: string
  timestamp: string
}

type AttackType = 'eavesdropper' | 'ddos' | 'jamming' | 'mitm'
type SimAttackMode = 'normal' | 'eavesdrop' | 'ddos' | 'relay' | 'mitm'
type SimNodeType = 'sat' | 'gs' | 'hacker'

interface SimNodeConfig {
  label: string
  type: SimNodeType
  xr: number
  yr: number
}

interface SimLink {
  a: string
  b: string
  style?: string
  dashed?: boolean
}

interface SimFlow {
  path: string[]
  color: string
  label: string
  delay: number
  repeat?: number
  dim?: boolean
  blocked?: boolean
  fork?: string
  forkAt?: number
}

interface SimModeConfig {
  label: string
  nodes: Record<string, SimNodeConfig>
  links: SimLink[]
  flows: SimFlow[]
  note?: string
}

const WS_URL = 'ws://localhost:3001'

const ATTACK_TO_SIM_MODE: Record<AttackType, SimAttackMode> = {
  eavesdropper: 'eavesdrop',
  ddos: 'ddos',
  jamming: 'relay',
  mitm: 'mitm',
}

const SIM_COLORS = {
  sat: '#4aaeff',
  gs: '#34d399',
  atk: '#f87171',
  normal: '#4aaeff',
  sniff: '#a78bfa',
  ddos: '#f87171',
  relay: '#fb923c',
  mitm: '#f472b6',
  blocked: '#374151',
} as const

const SIM_MODES: Record<SimAttackMode, SimModeConfig> = {
  normal: {
    label: 'Normal Transmission',
    nodes: {
      sat1: { label: 'SAT-1', type: 'sat', xr: 0.28, yr: 0.22 },
      sat2: { label: 'SAT-2', type: 'sat', xr: 0.72, yr: 0.22 },
      gs1: { label: 'GS-Alpha', type: 'gs', xr: 0.18, yr: 0.78 },
      gs2: { label: 'GS-Beta', type: 'gs', xr: 0.82, yr: 0.78 },
    },
    links: [
      { a: 'gs1', b: 'sat1', style: 'normal' },
      { a: 'sat1', b: 'sat2', style: 'normal' },
      { a: 'sat2', b: 'gs2', style: 'normal' },
    ],
    flows: [
      { path: ['gs1', 'sat1', 'sat2', 'gs2'], color: SIM_COLORS.normal, label: 'DATA', delay: 0 },
      { path: ['gs2', 'sat2', 'sat1', 'gs1'], color: '#34d399', label: 'ACK', delay: 60 },
    ],
  },
  eavesdrop: {
    label: 'Eavesdropper Attack',
    nodes: {
      sat1: { label: 'SAT-1', type: 'sat', xr: 0.25, yr: 0.2 },
      sat2: { label: 'SAT-2', type: 'sat', xr: 0.5, yr: 0.18 },
      sat3: { label: 'SAT-3', type: 'sat', xr: 0.75, yr: 0.2 },
      gs1: { label: 'GS-Source', type: 'gs', xr: 0.15, yr: 0.78 },
      gs2: { label: 'GS-Dest', type: 'gs', xr: 0.85, yr: 0.78 },
      hacker: { label: 'HACKER', type: 'hacker', xr: 0.22, yr: 0.48 },
    },
    links: [
      { a: 'gs1', b: 'sat1', style: 'normal' },
      { a: 'sat1', b: 'sat2', style: 'normal' },
      { a: 'sat2', b: 'sat3', style: 'normal' },
      { a: 'sat3', b: 'gs2', style: 'normal' },
      { a: 'hacker', b: 'sat1', style: 'sniff', dashed: true },
    ],
    flows: [
      { path: ['gs1', 'sat1', 'sat2', 'sat3', 'gs2'], color: SIM_COLORS.normal, label: 'DATA', delay: 0 },
      { path: ['gs1', 'sat1'], color: SIM_COLORS.sniff, label: 'COPY', delay: 30, fork: 'hacker', forkAt: 1 },
    ],
    note: 'Hacker passively copies traffic on GS-Alpha → SAT-1 link',
  },
  ddos: {
    label: 'DDoS Attack',
    nodes: {
      sat1: { label: 'SAT-1', type: 'sat', xr: 0.35, yr: 0.22 },
      sat2: { label: 'SAT-2', type: 'sat', xr: 0.65, yr: 0.22 },
      gs1: { label: 'GS-Send', type: 'gs', xr: 0.15, yr: 0.78 },
      gs2: { label: 'GS-Recv', type: 'gs', xr: 0.85, yr: 0.78 },
      hacker: { label: 'HACKER', type: 'hacker', xr: 0.5, yr: 0.62 },
    },
    links: [
      { a: 'gs1', b: 'sat1', style: 'normal' },
      { a: 'sat1', b: 'sat2', style: 'normal' },
      { a: 'sat2', b: 'gs2', style: 'normal' },
      { a: 'hacker', b: 'sat1', style: 'ddos', dashed: true },
    ],
    flows: [
      { path: ['gs1', 'sat1', 'sat2', 'gs2'], color: SIM_COLORS.normal, label: 'DATA', delay: 0, blocked: true },
      { path: ['hacker', 'sat1'], color: SIM_COLORS.ddos, label: 'FLOOD', delay: 5, repeat: 3 },
      { path: ['hacker', 'sat1'], color: SIM_COLORS.ddos, label: 'FLOOD', delay: 20, repeat: 3 },
      { path: ['hacker', 'sat1'], color: SIM_COLORS.ddos, label: 'JUNK', delay: 35, repeat: 3 },
      { path: ['sat1', 'sat2', 'gs2'], color: '#f87171', label: 'TOXIC', delay: 55, dim: true },
    ],
    note: 'DDoS floods SAT-1 — degraded traffic reaches GS-Recv',
  },
  relay: {
    label: 'Relay Jamming Attack',
    nodes: {
      sat1: { label: 'SAT-1', type: 'sat', xr: 0.3, yr: 0.22 },
      sat2: { label: 'SAT-2', type: 'sat', xr: 0.7, yr: 0.22 },
      gs1: { label: 'GS-Send', type: 'gs', xr: 0.2, yr: 0.78 },
      gs2: { label: 'GS-Recv', type: 'gs', xr: 0.8, yr: 0.78 },
      hacker: { label: 'HACKER', type: 'hacker', xr: 0.5, yr: 0.12 },
    },
    links: [
      { a: 'gs1', b: 'sat1', style: 'blocked' },
      { a: 'sat1', b: 'sat2', style: 'normal' },
      { a: 'sat2', b: 'gs2', style: 'normal' },
      { a: 'hacker', b: 'sat1', style: 'relay', dashed: true },
      { a: 'hacker', b: 'sat2', style: 'relay', dashed: true },
    ],
    flows: [
      { path: ['gs1', 'sat1'], color: SIM_COLORS.normal, label: 'DATA', delay: 0, blocked: true },
      { path: ['hacker', 'sat1'], color: SIM_COLORS.relay, label: 'JAM', delay: 8, repeat: 2 },
      { path: ['hacker', 'sat2'], color: SIM_COLORS.relay, label: 'JAM', delay: 18, repeat: 2 },
      { path: ['hacker', 'sat1'], color: SIM_COLORS.relay, label: 'JAM', delay: 45, repeat: 2 },
    ],
    note: 'Hacker jams both satellites — sender cannot reach receiver',
  },
  mitm: {
    label: 'Man-in-the-Middle Attack',
    nodes: {
      sat1: { label: 'SAT-1', type: 'sat', xr: 0.22, yr: 0.22 },
      sat2: { label: 'SAT-2', type: 'sat', xr: 0.78, yr: 0.22 },
      gs1: { label: 'GS-Alpha', type: 'gs', xr: 0.12, yr: 0.78 },
      gs2: { label: 'GS-Beta', type: 'gs', xr: 0.88, yr: 0.78 },
      hacker: { label: 'HACKER', type: 'hacker', xr: 0.5, yr: 0.25 },
    },
    links: [
      { a: 'gs1', b: 'sat1', style: 'normal' },
      { a: 'sat1', b: 'hacker', style: 'mitm', dashed: true },
      { a: 'hacker', b: 'sat2', style: 'mitm', dashed: true },
      { a: 'sat2', b: 'gs2', style: 'normal' },
    ],
    flows: [
      { path: ['gs1', 'sat1', 'hacker'], color: SIM_COLORS.normal, label: 'DATA', delay: 0 },
      { path: ['hacker', 'sat2', 'gs2'], color: SIM_COLORS.mitm, label: 'FAKED', delay: 50 },
    ],
    note: 'Hacker intercepts SAT-1↔SAT-2 ISL, relays modified data',
  },
}

const STATUS_LABELS: Record<'idle' | 'running' | 'stopped' | 'starting' | 'error', string> = {
  idle: '◉ READY — Chọn attack simulator và nhấn Start',
  running: '◉ RUNNING — Simulation đang chạy...',
  starting: '◉ STARTING — Đang khởi động...',
  stopped: '◉ STOPPED — Simulation đã dừng',
  error: '◉ ERROR — Có lỗi xảy ra',
}

const INITIAL_STATS = { pkt: 0, intercepted: 0, dropped: 0 }

export default function DemoSimulatorTab({ active }: DemoSimulatorTabProps) {
  const [status, setStatus] = useState<'idle' | 'running' | 'stopped' | 'starting' | 'error'>('idle')
  const [mode, setMode] = useState('all')
  const [phase, setPhase] = useState('')
  const [senderLogs, setSenderLogs] = useState<LogEntry[]>([])
  const [receiverLogs, setReceiverLogs] = useState<LogEntry[]>([])
  const [eavesdropperLogs, setEavesdropperLogs] = useState<LogEntry[]>([])
  const [systemLogs, setSystemLogs] = useState<LogEntry[]>([])
  const [simMode, setSimMode] = useState<SimAttackMode | null>(null)
  const [simStats, setSimStats] = useState(INITIAL_STATS)

  const wsRef = useRef<WebSocket | null>(null)
  const logIdRef = useRef(0)
  const senderEndRef = useRef<HTMLDivElement>(null)
  const receiverEndRef = useRef<HTMLDivElement>(null)
  const eavesdropperEndRef = useRef<HTMLDivElement>(null)
  const systemEndRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const particlesRef = useRef<any[]>([])
  const flowQueueRef = useRef<{ ticks: number; flow: SimFlow }[]>([])
  const scheduleTickRef = useRef(0)
  const rafRef = useRef<number | null>(null)
  const simModeRef = useRef<SimAttackMode | null>(null)
  const canvasSizeRef = useRef({ width: 0, height: 340 })
  const [wsReady, setWsReady] = useState(false)

  useEffect(() => {
    if (senderEndRef.current) senderEndRef.current.scrollTop = senderEndRef.current.scrollHeight
  }, [senderLogs])

  useEffect(() => {
    if (receiverEndRef.current) receiverEndRef.current.scrollTop = receiverEndRef.current.scrollHeight
  }, [receiverLogs])

  useEffect(() => {
    if (eavesdropperEndRef.current) eavesdropperEndRef.current.scrollTop = eavesdropperEndRef.current.scrollHeight
  }, [eavesdropperLogs])

  useEffect(() => {
    if (systemEndRef.current) systemEndRef.current.scrollTop = systemEndRef.current.scrollHeight
  }, [systemLogs])

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setWsReady(true)
    }

    ws.onmessage = ({ data }) => {
      try {
        const message = JSON.parse(data)
        if (message.type === 'status') {
          if (message.status === 'running' || message.status === 'starting') setStatus('running')
          else if (message.status === 'stopped') setStatus('stopped')
          else setStatus(message.status)
          if (message.phase) setPhase(message.phase)
        }

        if (message.type === 'log') {
          const entry: LogEntry = {
            id: ++logIdRef.current,
            role: message.role,
            message: message.message,
            logType: message.logType || 'info',
            timestamp: new Date(message.timestamp).toLocaleTimeString('vi-VN', { hour12: false }),
          }

          if (message.role === 'sender') setSenderLogs(prev => [...prev, entry])
          else if (message.role === 'receiver') setReceiverLogs(prev => [...prev, entry])
          else if (message.role === 'eavesdropper') setEavesdropperLogs(prev => [...prev, entry])
          else setSystemLogs(prev => [...prev, entry])
        }

        if (message.type === 'error') {
          setStatus('error')
          setSystemLogs(prev => [
            ...prev,
            {
              id: ++logIdRef.current,
              role: 'system',
              message: `ERROR: ${message.message}`,
              logType: 'attack',
              timestamp: new Date().toLocaleTimeString('vi-VN', { hour12: false }),
            },
          ])
        }
      } catch {
        // ignore invalid JSON
      }
    }

    ws.onclose = () => {
      setWsReady(false)
      setTimeout(connectWs, 2000)
    }

    ws.onerror = () => {
      setWsReady(false)
      ws.close()
    }
  }, [])

  useEffect(() => {
    connectWs()
    return () => wsRef.current?.close()
  }, [connectWs])

  const sendWsAction = (action: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action }))
      return true
    }

    setSystemLogs(prev => [
      ...prev,
      {
        id: ++logIdRef.current,
        role: 'system',
        message: `Cannot send ${action}: websocket not connected`,
        logType: 'warn',
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour12: false }),
      },
    ])

    return false
  }

  const startHping3Attack = () => sendWsAction('start_hping3')
  const stopHping3Attack = () => sendWsAction('stop_hping3')
  const createDdosRules = () => sendWsAction('create_ddos_rules')
  const removeDdosRules = () => sendWsAction('remove_ddos_rules')

  const resetSimulation = () => {
    cancelAnimationFrame(rafRef.current ?? 0)
    flowQueueRef.current = []
    particlesRef.current = []
    scheduleTickRef.current = 0
    simModeRef.current = null
    setSimMode(null)
    setSimStats(INITIAL_STATS)
    drawCanvas()
  }

  const startSimulation = (attackType: AttackType) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      connectWs()
      setTimeout(() => startSimulation(attackType), 500)
      return
    }

    setSenderLogs([])
    setReceiverLogs([])
    setEavesdropperLogs([])
    setSystemLogs([])
    logIdRef.current = 0
    setStatus('running')
    setSimStats(INITIAL_STATS)
    setSimMode(ATTACK_TO_SIM_MODE[attackType])
    setVisualMode(ATTACK_TO_SIM_MODE[attackType])

    wsRef.current.send(JSON.stringify({ action: `start_${attackType}`, mode }))
  }

  const stopSimulation = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }))
    }
    setStatus('stopped')
    resetSimulation()
  }

  const resizeCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.width = canvas.offsetWidth
    canvas.height = 340
    canvasSizeRef.current = { width: canvas.width, height: canvas.height }
  }

  const nodePos = (key: string, config: SimModeConfig) => {
    const node = config.nodes[key]
    return { x: node.xr * canvasSizeRef.current.width, y: node.yr * canvasSizeRef.current.height }
  }

  const spawnFlow = (flow: SimFlow, config: SimModeConfig) => {
    const points = flow.path.map(point => nodePos(point, config))
    particlesRef.current.push({
      points,
      color: flow.color,
      label: flow.label,
      t: 0,
      speed: 0.008 + Math.random() * 0.004,
      done: false,
      dim: flow.dim || false,
      blocked: flow.blocked || false,
      fork: flow.fork ? nodePos(flow.fork, config) : null,
      forkAt: flow.forkAt ?? null,
      forkDone: false,
    })
  }

  const scheduleFlows = (config: SimModeConfig) => {
    const queue: { ticks: number; flow: SimFlow }[] = []
    config.flows.forEach(flow => {
      const count = flow.repeat || 1
      for (let i = 0; i < count; i += 1) {
        queue.push({ ticks: (flow.delay || 0) + i * 40, flow })
      }
    })
    flowQueueRef.current = queue
  }

  const linkStyle = (type?: string) => {
    if (type === 'sniff') return { color: 'rgba(167,139,250,0.5)', dash: [5, 4] }
    if (type === 'ddos') return { color: 'rgba(248,113,113,0.6)', dash: [4, 3] }
    if (type === 'relay') return { color: 'rgba(251,146,60,0.55)', dash: [5, 3] }
    if (type === 'mitm') return { color: 'rgba(244,114,182,0.6)', dash: [4, 3] }
    if (type === 'blocked') return { color: 'rgba(55,65,81,0.5)', dash: [2, 5] }
    return { color: 'rgba(74,174,255,0.25)', dash: [] }
  }

  const drawCanvas = () => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!simModeRef.current) return drawIdle(ctx)

    const config = SIM_MODES[simModeRef.current]
    drawLinks(ctx, config)
    drawNodes(ctx, config)
    drawParticles(ctx)
  }

  const drawIdle = (ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = 'rgba(74,174,255,0.06)'
    ctx.fillRect(0, 0, canvasSizeRef.current.width, canvasSizeRef.current.height)
    ctx.fillStyle = 'rgba(74,174,255,0.3)'
    ctx.font = `14px ${getComputedStyle(document.body).fontFamily || 'monospace'}`
    ctx.textAlign = 'center'
    ctx.fillText('Click an attack to start the demo', canvasSizeRef.current.width / 2, canvasSizeRef.current.height / 2)
    ctx.textAlign = 'left'
  }

  const drawLinks = (ctx: CanvasRenderingContext2D, config: SimModeConfig) => {
    config.links.forEach(link => {
      const from = nodePos(link.a, config)
      const to = nodePos(link.b, config)
      const style = linkStyle(link.style)
      ctx.beginPath()
      ctx.moveTo(from.x, from.y)
      ctx.lineTo(to.x, to.y)
      ctx.strokeStyle = style.color
      ctx.lineWidth = 1.2
      ctx.setLineDash(style.dash)
      ctx.stroke()
      ctx.setLineDash([])
    })
  }

  const drawNodes = (ctx: CanvasRenderingContext2D, config: SimModeConfig) => {
    Object.values(config.nodes).forEach(node => {
      const x = node.xr * canvasSizeRef.current.width
      const y = node.yr * canvasSizeRef.current.height
      if (node.type === 'sat') drawSat(ctx, x, y, node.label)
      else if (node.type === 'gs') drawGS(ctx, x, y, node.label)
      else drawHacker(ctx, x, y, node.label)
    })

    if (config.note) {
      ctx.fillStyle = 'rgba(255,255,255,0.25)'
      ctx.font = '10px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(config.note, canvasSizeRef.current.width / 2, canvasSizeRef.current.height - 10)
      ctx.textAlign = 'left'
    }
  }

  const drawSat = (ctx: CanvasRenderingContext2D, x: number, y: number, label: string) => {
    ctx.save()
    ctx.shadowColor = SIM_COLORS.sat
    ctx.shadowBlur = 8
    ctx.beginPath()
    ctx.arc(x, y, 7, 0, Math.PI * 2)
    ctx.fillStyle = SIM_COLORS.sat
    ctx.fill()
    ctx.restore()

    ctx.fillStyle = 'rgba(74,174,255,0.85)'
    ctx.font = '10px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(label, x, y - 13)
    ctx.textAlign = 'left'
  }

  const drawGS = (ctx: CanvasRenderingContext2D, x: number, y: number, label: string) => {
    ctx.save()
    ctx.shadowColor = SIM_COLORS.gs
    ctx.shadowBlur = 8
    ctx.beginPath()
    ctx.arc(x, y, 8, 0, Math.PI * 2)
    ctx.fillStyle = SIM_COLORS.gs
    ctx.fill()
    ctx.restore()

    ctx.fillStyle = 'rgba(52,211,153,0.85)'
    ctx.font = '10px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(label, x, y + 20)
    ctx.textAlign = 'left'
  }

  const drawHacker = (ctx: CanvasRenderingContext2D, x: number, y: number, label: string) => {
    ctx.save()
    ctx.shadowColor = SIM_COLORS.atk
    ctx.shadowBlur = 14
    ctx.beginPath()
    ctx.arc(x, y, 9, 0, Math.PI * 2)
    ctx.fillStyle = SIM_COLORS.atk
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = 'rgba(248,113,113,0.5)'
    ctx.stroke()
    ctx.restore()

    ctx.fillStyle = 'rgba(248,113,113,0.9)'
    ctx.font = 'bold 10px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(label, x, y - 15)
    ctx.textAlign = 'left'
  }

  const drawParticles = (ctx: CanvasRenderingContext2D) => {
    particlesRef.current.forEach(particle => {
      if (particle.done) return

      const segment = Math.floor(particle.t * (particle.points.length - 1))
      const start = segment / (particle.points.length - 1)
      const end = (segment + 1) / (particle.points.length - 1)
      const progress = (particle.t - start) / (end - start + 0.0001)
      const from = particle.points[Math.min(segment, particle.points.length - 2)]
      const to = particle.points[Math.min(segment + 1, particle.points.length - 1)]
      const x = from.x + (to.x - from.x) * progress
      const y = from.y + (to.y - from.y) * progress

      ctx.save()
      ctx.globalAlpha = particle.dim ? 0.45 : 1
      ctx.shadowColor = particle.color
      ctx.shadowBlur = 10
      ctx.beginPath()
      ctx.arc(x, y, 4, 0, Math.PI * 2)
      ctx.fillStyle = particle.blocked && particle.t > 0.85 ? SIM_COLORS.blocked : particle.color
      ctx.fill()
      ctx.restore()

      if (particle.label) {
        ctx.fillStyle = particle.dim ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.85)'
        ctx.font = '9px monospace'
        ctx.fillText(particle.label, x + 6, y - 4)
      }

      if (particle.fork && particle.forkAt !== null) {
        const forkPoint = particle.points[particle.forkAt]
        const forkProgress = particle.forkAt / (particle.points.length - 1)
        if (particle.t >= forkProgress && !particle.forkDone) {
          const phase = Math.min(((particle.t - forkProgress) / (1 - forkProgress)) * 2.5, 1)
          const fx = forkPoint.x + (particle.fork.x - forkPoint.x) * phase
          const fy = forkPoint.y + (particle.fork.y - forkPoint.y) * phase

          ctx.save()
          ctx.shadowColor = SIM_COLORS.sniff
          ctx.shadowBlur = 8
          ctx.beginPath()
          ctx.arc(fx, fy, 4, 0, Math.PI * 2)
          ctx.fillStyle = SIM_COLORS.sniff
          ctx.fill()
          ctx.restore()

          ctx.fillStyle = 'rgba(167,139,250,0.85)'
          ctx.font = '9px monospace'
          ctx.fillText('COPY', fx + 6, fy - 4)

          if (phase >= 1) particle.forkDone = true
        }
      }
    })
  }

  const setVisualMode = (mode: SimAttackMode | null) => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    particlesRef.current = []
    flowQueueRef.current = []
    scheduleTickRef.current = 0
    simModeRef.current = mode
    setSimMode(mode)
    setSimStats(INITIAL_STATS)

    if (!mode) {
      drawCanvas()
      return
    }

    scheduleFlows(SIM_MODES[mode])
    rafRef.current = requestAnimationFrame(function loop() {
      scheduleTickRef.current += 1
      const currentConfig = simModeRef.current ? SIM_MODES[simModeRef.current] : null

      if (currentConfig) {
        flowQueueRef.current.forEach(queueItem => {
          if (queueItem.ticks === scheduleTickRef.current) {
            spawnFlow(queueItem.flow, currentConfig)
            setSimStats(prev => ({
              ...prev,
              pkt: prev.pkt + 1,
              intercepted: prev.intercepted + ((queueItem.flow.color === SIM_COLORS.sniff || queueItem.flow.color === SIM_COLORS.mitm) ? 1 : 0),
              dropped: prev.dropped + (queueItem.flow.blocked || queueItem.flow.color === SIM_COLORS.ddos ? 1 : 0),
            }))
          }
        })
      }

      particlesRef.current.forEach(particle => {
        if (particle.done) return
        particle.t = Math.min(particle.t + particle.speed, 1)
        if (particle.t >= 1) particle.done = true
      })
      particlesRef.current = particlesRef.current.filter(particle => !particle.done)

      if (scheduleTickRef.current > 180) {
        scheduleTickRef.current = 0
        if (currentConfig) scheduleFlows(currentConfig)
      }

      drawCanvas()
      rafRef.current = requestAnimationFrame(loop)
    })
  }

  useEffect(() => {
    const onResize = () => {
      resizeCanvas()
      drawCanvas()
    }

    resizeCanvas()
    drawCanvas()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <div className={`panel-section demo-sim-section ${active ? 'active' : ''}`} style={{ display: active ? 'flex' : 'none' }}>
      <div className="panel" style={{ width: '100%' }}>
        <div className="panel-title">🛰 Attack Simulator Dashboard</div>
        <div className="sim-controls">
          <select className="mode-select" value={mode} onChange={e => setMode(e.target.value)} disabled={status === 'running'}>
            <option value="all">All Phases (Plain → E2EE)</option>
            <option value="plain">Phase 1: Plaintext Only</option>
            <option value="encrypted">Phase 2: Encrypted (E2EE)</option>
          </select>

          <button className={`btn btn-attack ${status === 'running' ? 'active-btn' : ''}`} onClick={() => startSimulation('eavesdropper')} disabled={status === 'running'}>
            👂 Eavesdropper
          </button>
          <button className={`btn btn-attack ${status === 'running' ? 'active-btn' : ''}`} onClick={() => startSimulation('ddos')} disabled={status === 'running'}>
            💥 DDoS Attack
          </button>
          <button className={`btn btn-attack ${status === 'running' ? 'active-btn' : ''}`} onClick={() => startSimulation('jamming')} disabled={status === 'running'}>
            📡 RF Jamming
          </button>
          <button className={`btn btn-attack ${status === 'running' ? 'active-btn' : ''}`} onClick={() => startSimulation('mitm')} disabled={status === 'running'}>
            🔁 Replay MITM
          </button>

          <button className="btn btn-stop" onClick={stopSimulation} disabled={status !== 'running'}>
            ⏹ Stop
          </button>

          <div className={`sim-status ${status}`}>
            <div className={`dot ${status === 'running' ? 'green' : status === 'stopped' ? 'amber' : status === 'error' ? 'red' : ''}`} style={status === 'idle' ? { background: 'var(--dim)', boxShadow: 'none' } : {}} />
            {STATUS_LABELS[status]}
          </div>
        </div>
      </div>

      <div className="sim-visual-panel">
        <div className="sim-visual-header">
          <div className="panel-title">🧪 Visual Demo Simulator</div>
        </div>

        <div className="sim-visual-body">
          <div className="sim-canvas-wrapper">
            <canvas ref={canvasRef} className="sim-canvas" />
          </div>
          <div className="sim-visual-sidebar">
            <div className="sim-stat-row"><span>Mode</span><span>{simMode ? SIM_MODES[simMode].label : 'Idle'}</span></div>
            <div className="sim-stat-row"><span>Packets</span><span>{simStats.pkt}</span></div>
            <div className="sim-stat-row"><span>Intercepted</span><span>{simStats.intercepted}</span></div>
            <div className="sim-stat-row"><span>Dropped</span><span>{simStats.dropped}</span></div>
          </div>
        </div>
      </div>

      <div style={{ width: '100%', padding: '10px 16px', background: 'rgba(0,229,255,0.03)', border: '1px solid rgba(0,229,255,0.1)', borderRadius: 6, fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: 'var(--dim)', display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <span>Topology: <span style={{ color: 'var(--cyan)' }}>Sender</span> (10.0.0.1) → SAT-A → SAT-B → SAT-C → <span style={{ color: 'var(--green)' }}>Receiver</span> (10.0.0.3)</span>
        <span>Eavesdropping: <span style={{ color: 'var(--red)' }}>Passive Sniffer</span> (10.0.0.1) monitor Sender</span>
        <span>Crypto: End-to-End Encryption (AES-256-GCM + ECDH X25519)</span>
      </div>

      <div className="log-grid">
        <div className="log-panel sender-panel">
          <div className="log-panel-header">
            <span className="role-icon">📡</span>
            <span className="role-name">Sender</span>
            <span className="role-desc">GS-46 HCMC</span>
            <span className="log-count">{senderLogs.length}</span>
          </div>
          <div className="log-box" ref={senderEndRef}>
            {senderLogs.length === 0 ? (
              <div className="log-empty">Sender logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              senderLogs.map(log => (
                <div key={log.id} className={`log-line log-${log.logType}`}>
                  <span className="log-time">[{log.timestamp}]</span> {log.message}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="log-panel receiver-panel">
          <div className="log-panel-header">
            <span className="role-icon">📡</span>
            <span className="role-name">Receiver</span>
            <span className="role-desc">GS-63 Singapore</span>
            <span className="log-count">{receiverLogs.length}</span>
          </div>
          <div className="log-box" ref={receiverEndRef}>
            {receiverLogs.length === 0 ? (
              <div className="log-empty">Receiver logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              receiverLogs.map(log => (
                <div key={log.id} className={`log-line log-${log.logType}`}>
                  <span className="log-time">[{log.timestamp}]</span> {log.message}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="log-panel eavesdropper-panel">
          <div className="log-panel-header">
            <span className="role-icon">👁</span>
            <span className="role-name">Hacker</span>
            <span className="role-desc">Eavesdropper MitM</span>
            <span className="log-count">{eavesdropperLogs.length}</span>
            {phase.includes('ddos') && (
              <>
                <button className="btn btn-attack-small" onClick={startHping3Attack} disabled={!wsReady} title="Launch DDoS attack (hping3)">🔨 Attack</button>
                <button className="btn btn-stop btn-attack-small" onClick={stopHping3Attack} disabled={!wsReady} title="Stop hping3 attack">⏹ Stop Attack</button>
                <button className="btn btn-attack-small" onClick={createDdosRules} disabled={!wsReady} title="Create DDoS mitigation rules">🛡 Create Rules</button>
                <button className="btn btn-stop btn-attack-small" onClick={removeDdosRules} disabled={!wsReady} title="Remove DDoS mitigation rules">🧹 Remove Rules</button>
              </>
            )}
          </div>
          <div className="log-box" ref={eavesdropperEndRef}>
            {eavesdropperLogs.length === 0 ? (
              <div className="log-empty">Eavesdropper logs sẽ hiển thị ở đây khi simulation chạy...</div>
            ) : (
              eavesdropperLogs.map(log => (
                <div key={log.id} className={`log-line log-${log.logType}`}>
                  <span className="log-time">[{log.timestamp}]</span> {log.message}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="log-panel system-log-panel">
        <div className="log-panel-header">
          <span className="role-icon">⚙️</span>
          <span className="role-name" style={{ color: 'var(--cyan)' }}>System</span>
          <span className="role-desc">Transfer order & Infrastructure</span>
          <span className="log-count" style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}>{systemLogs.length}</span>
        </div>
        <div className="log-box" ref={systemEndRef}>
          {systemLogs.length === 0 ? (
            <div className="log-empty">System events sẽ hiển thị ở đây...</div>
          ) : (
            systemLogs.map(log => (
              <div key={log.id} className={`log-line log-${log.logType}`}>
                <span className="log-time">[{log.timestamp}]</span> {log.message}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
