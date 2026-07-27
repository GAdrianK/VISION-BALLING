import React, { useState, useRef, useEffect } from 'react'

export default function RAG_Interface({ messages, onSendMessage }) {
  const [inputValue, setInputValue] = useState('')
  const historyRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputValue.trim()) return
    onSendMessage(inputValue)
    setInputValue('')
  }

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight
    }
  }, [messages])

  return (
    <>
      {/* Top Left: Chat History Panel */}
      <div className="chat-history-panel">
        <div className="panel-header">
          <span className="panel-dot" style={{ background: '#06b6d4' }} />
          Assistant RAG Tactique
        </div>
        <div className="chat-messages-container" ref={historyRef}>
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.sender}`}>
              <div className="message-header">
                {msg.sender === 'user' ? '👤 Vous' : '🤖 IA Assistant'}
              </div>
              <div className="message-content">
                <p>{msg.text}</p>
                {msg.visualizationActive && (
                  <div className="visual-indicator-tag">
                    {msg.visualizationActive === 'pressing' && '🔥 Visualisation : Pressing Haut'}
                    {msg.visualizationActive === 'passes' && '↗️ Visualisation : Passes Clés'}
                    {msg.visualizationActive === 'xt' && '⚡ Visualisation : Expected Threat (xT)'}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Center: Hero Prompt Input */}
      <div className="hero-prompt-container">
        <form onSubmit={handleSubmit} className="hero-prompt-form">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Demandez une analyse tactique ou recherchez des données RAG..."
            className="hero-prompt-input"
          />
          <button type="submit" className="hero-prompt-button">
            <span>Analyser</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>
    </>
  )
}
