export default function Header() {
  return (
    <header className="header">
      <div className="logo-icon">🛰️</div>
      <div className="header-text">
        <h1>LEO SAT NET — Security Demo</h1>
        <p>Mạng Vệ Tinh Quỹ Đạo Thấp &amp; An Toàn Thông Tin // Nhóm Nghiên Cứu</p>
      </div>
      <div className="status-bar">
        <div className="status-item"><div className="dot green"></div>NETWORK ONLINE</div>
        <div className="status-item"><div className="dot red"></div>THREAT DETECTED</div>
        <div className="status-item"><div className="dot amber"></div>ENCRYPTION ACTIVE</div>
      </div>
    </header>
  )
}
