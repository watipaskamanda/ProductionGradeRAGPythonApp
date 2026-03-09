'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Paperclip, ArrowUp, Menu, X, Upload, FileText, Settings, History, Database, MessageSquare, User, DollarSign } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
}

const suggestedPrompts = [
  "Show me total transaction volume for this month",
  "What are the top 5 clients by transaction value?", 
  "Analyze payment trends over the last 30 days",
  "Which transaction types generate the most revenue?"
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('analytics') // 'analytics' or 'documents'
  const [userLevel, setUserLevel] = useState('business')
  const [currency, setCurrency] = useState('MWK')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (messageText?: string) => {
    const text = messageText || input
    if (!text.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      content: text,
      role: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const endpoint = activeTab === 'analytics' ? '/api/database' : '/api/chat'
      const body = activeTab === 'analytics' 
        ? { question: text, currency, user_level: userLevel }
        : { message: text }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      const data = await response.json()
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: data.response || data.answer || 'I apologize, but I encountered an error processing your request.',
        role: 'assistant',
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex h-screen bg-[#212121] text-white">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#404040]">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-blue-400" />
            <div>
              <h2 className="text-lg font-medium">BIZINEZI Database Analytics</h2>
              <p className="text-sm text-gray-400">SQL-powered business intelligence</p>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-[#2f2f2f] rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>

        {/* Chat Content */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            /* Welcome Screen */
            <div className="flex flex-col items-center justify-center h-full px-4">
              <div className="text-center mb-8">
                <Database className="w-16 h-16 mx-auto mb-4 text-blue-400" />
                <h1 className="text-4xl font-light mb-2">Database Analytics</h1>
                <p className="text-gray-400 text-lg">Ask questions about your business data</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl w-full mb-8">
                {suggestedPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => handleSubmit(prompt)}
                    className="p-4 text-left bg-[#2f2f2f] hover:bg-[#404040] rounded-xl border border-[#404040] transition-colors"
                  >
                    <span className="text-sm">{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Messages */
            <div className="max-w-3xl mx-auto px-4 py-8">
              {messages.map((message) => (
                <div key={message.id} className="mb-8">
                  <div className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-[#10a37f] flex items-center justify-center flex-shrink-0 mt-1">
                        <Database className="w-4 h-4 text-white" />
                      </div>
                    )}
                    
                    <div className={`max-w-[80%] ${message.role === 'user' ? 'order-first' : ''}`}>
                      <div className={`rounded-2xl px-4 py-3 ${
                        message.role === 'user' 
                          ? 'bg-[#2f2f2f] ml-auto' 
                          : 'bg-transparent'
                      }`}>
                        {message.role === 'assistant' ? (
                          <ReactMarkdown className="prose prose-invert max-w-none">
                            {message.content}
                          </ReactMarkdown>
                        ) : (
                          <p>{message.content}</p>
                        )}
                      </div>
                    </div>
                    
                    {message.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-[#ab68ff] flex items-center justify-center flex-shrink-0 mt-1">
                        <span className="text-white text-sm font-medium">U</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="mb-8">
                  <div className="flex gap-4">
                    <div className="w-8 h-8 rounded-full bg-[#10a37f] flex items-center justify-center flex-shrink-0 mt-1">
                      <Database className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex items-center">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4">
          <div className="max-w-3xl mx-auto">
            <div className="relative bg-[#2f2f2f] rounded-3xl border border-[#404040] focus-within:border-[#565656]">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your business data..."
                disabled={isLoading}
                rows={1}
                className="w-full bg-transparent px-4 py-3 pr-12 text-white placeholder-gray-400 resize-none focus:outline-none"
                style={{ minHeight: '52px', maxHeight: '200px' }}
              />
              
              <div className="absolute right-2 bottom-2 flex gap-2">
                <button
                  onClick={() => handleSubmit()}
                  disabled={isLoading || !input.trim()}
                  className={`p-2 rounded-lg transition-colors ${
                    input.trim() && !isLoading
                      ? 'bg-white text-black hover:bg-gray-200'
                      : 'bg-[#404040] text-gray-500'
                  }`}
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            <div className="text-center mt-2">
              <p className="text-xs text-gray-500">
                <span className="bg-[#2f2f2f] px-2 py-1 rounded">Sentinel AI v1</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 overflow-hidden bg-[#171717] border-l border-[#404040]`}>
        <div className="p-4 h-full">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-medium">Tools & Settings</h3>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1 hover:bg-[#2f2f2f] rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-4">
            {/* User Level */}
            <div className="bg-[#2f2f2f] rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <User className="w-5 h-5 text-purple-400" />
                <h4 className="font-medium">👤 User Level</h4>
              </div>
              <select 
                value={userLevel} 
                onChange={(e) => setUserLevel(e.target.value)}
                className="w-full bg-[#404040] text-white p-2 rounded border border-[#565656]"
              >
                <option value="business">Business User</option>
                <option value="analyst">Data Analyst</option>
                <option value="developer">Developer</option>
              </select>
            </div>

            {/* Currency */}
            <div className="bg-[#2f2f2f] rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <DollarSign className="w-5 h-5 text-green-400" />
                <h4 className="font-medium">💰 Currency</h4>
              </div>
              <select 
                value={currency} 
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-[#404040] text-white p-2 rounded border border-[#565656]"
              >
                <option value="MWK">MWK (Malawi Kwacha)</option>
                <option value="USD">USD (US Dollar)</option>
                <option value="EUR">EUR (Euro)</option>
              </select>
            </div>

            {/* Document Q&A */}
            <div className="bg-[#2f2f2f] rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <MessageSquare className="w-5 h-5 text-blue-400" />
                <h4 className="font-medium">Document Q&A</h4>
              </div>
              <p className="text-sm text-gray-400 mb-3">Ask questions about uploaded documents</p>
              <button 
                onClick={() => setActiveTab('documents')}
                className={`w-full py-2 px-4 rounded-lg transition-colors ${
                  activeTab === 'documents' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-[#404040] hover:bg-[#565656] text-gray-300'
                }`}
              >
                Switch to Documents
              </button>
            </div>

            {/* Upload Documents */}
            <div className="bg-[#2f2f2f] rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <Upload className="w-5 h-5 text-orange-400" />
                <h4 className="font-medium">📤 Upload Documents</h4>
              </div>
              <p className="text-sm text-gray-400 mb-3">Add PDFs to your knowledge base</p>
              <button className="w-full bg-orange-600 hover:bg-orange-700 text-white py-2 px-4 rounded-lg transition-colors">
                Choose Files
              </button>
            </div>

            {/* Settings */}
            <div className="bg-[#2f2f2f] rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <Settings className="w-5 h-5 text-gray-400" />
                <h4 className="font-medium">Settings</h4>
              </div>
              <p className="text-sm text-gray-400 mb-3">Configure preferences</p>
              <button className="text-sm text-blue-400 hover:text-blue-300 transition-colors">
                Open Settings
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}