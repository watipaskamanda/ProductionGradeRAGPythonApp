'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Paperclip, ArrowUp, Menu, X, Upload, FileText, Settings, History, Database, MessageSquare, User, DollarSign } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { DataTable } from '@/components/ui/data-table'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
  sql?: string
  question?: string
  markdown_table?: string
  // New fields for raw data table rendering
  raw_data?: {
    columns: string[]
    rows: any[][]
    total_count: number
  }
  // Metadata including suggested prompts
  metadata?: {
    suggested_prompts?: string[]
    [key: string]: any
  }
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
  
  // Chat history for API context
  const [chatHistory, setChatHistory] = useState<Array<{role: string, content: string, sql?: string, question?: string}>>([])
  
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

    // Add user message to chat history BEFORE API call
    const newChatHistory = [...chatHistory, {
      role: "user",
      content: text
    }]

    // DEBUG: Log chat history state
    console.log('🔍 Current chatHistory state:', chatHistory)
    console.log('🔍 New chatHistory being sent:', newChatHistory)

    try {
      const endpoint = activeTab === 'analytics' ? '/api/v1/query/database' : '/api/v1/query'
      const body = activeTab === 'analytics' 
        ? { 
            question: text, 
            chat_history: newChatHistory, // Send accumulated history
            currency, 
            user_level: userLevel 
          }
        : { message: text }

      // DEBUG: Log full request body
      console.log('🔍 Full request body being sent:', JSON.stringify(body, null, 2))
      console.log("Sending chat history:", chatHistory)

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      const data = await response.json()
      
      // DEBUG: Log the full API response to see what we're getting
      console.log('🔍 Full API response:', data)
      
      // Extract raw data for table rendering if available
      let rawData = null
      if (activeTab === 'analytics') {
        // First, check if backend already provided raw_data
        if (data.raw_data && data.raw_data.columns && data.raw_data.rows) {
          rawData = data.raw_data
          console.log('✅ Using raw_data from backend:', rawData)
        }
        // Fallback: try to parse markdown table if no raw_data
        else if (data.metadata && data.metadata.row_count > 0 && data.markdown_table) {
          console.log('⚠️ Fallback: parsing markdown table')
          const tableLines = data.markdown_table.split('\n').filter(line => line.trim())
          if (tableLines.length >= 3) { // Header + separator + at least one data row
            const headerLine = tableLines[0]
            const dataLines = tableLines.slice(2) // Skip header and separator
            
            // Extract columns from header (remove | and trim)
            const columns = headerLine.split('|').map(col => col.trim()).filter(col => col)
            
            // Extract rows from data lines
            const rows = dataLines
              .filter(line => !line.includes('---')) // Skip separator lines
              .map(line => 
                line.split('|')
                  .map(cell => cell.trim())
                  .filter((cell, index, arr) => index > 0 && index < arr.length - 1) // Remove empty first/last elements
              )
              .filter(row => row.length > 0)
            
            if (columns.length > 0 && rows.length > 0) {
              rawData = {
                columns,
                rows,
                total_count: data.metadata.row_count || rows.length
              }
              console.log('✅ Parsed raw_data from markdown:', rawData)
            }
          }
        }
      }
      
      console.log('🔍 Final rawData being set:', rawData)
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: data.answer || 'I apologize, but I encountered an error processing your request.',
        role: 'assistant',
        timestamp: new Date(),
        sql: data.debug_info?.sql || data.sql,
        question: text,
        markdown_table: data.markdown_table,
        raw_data: rawData,
        metadata: {
          suggested_prompts: data.suggested_prompts || [],
          ...data.metadata
        }
      }

      setMessages(prev => [...prev, assistantMessage])

      // Add assistant response to chat history AFTER API call
      const updatedHistory = [...newChatHistory, {
        role: "assistant",
        content: assistantMessage.content,
        sql: data.sql,
        question: text
      }]

      // Keep only last 10 messages to avoid sending too much data
      if (updatedHistory.length > 10) {
        setChatHistory(updatedHistory.slice(-10))
      } else {
        setChatHistory(updatedHistory)
      }

    } catch (error) {
      console.error('Error:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: 'I encountered an error processing your request. Please try again.',
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
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
            <div className="max-w-4xl mx-auto px-4 py-8">
              {messages.map((message) => (
                <div key={message.id} className="mb-8">
                  <div className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-[#10a37f] flex items-center justify-center flex-shrink-0 mt-1">
                        <Database className="w-4 h-4 text-white" />
                      </div>
                    )}
                    
                    <div className={`max-w-[85%] ${message.role === 'user' ? 'order-first' : ''}`}>
                      <div className={`rounded-2xl px-4 py-3 ${
                        message.role === 'user' 
                          ? 'bg-[#2f2f2f] ml-auto' 
                          : 'bg-transparent'
                      }`}>
                        {message.role === 'assistant' ? (
                          <div>
                            <ReactMarkdown className="prose prose-invert max-w-none">
                              {message.content}
                            </ReactMarkdown>
                            
                            {/* Render suggested prompts for zero results */}
                            {(() => {
                              const hasZeroResults = (message.raw_data?.rows?.length === 0) || 
                                                    (message.markdown_table && message.markdown_table.includes('No data to display')) ||
                                                    (message.content && message.content.includes("couldn't find any"))
                              const hasSuggestedPrompts = hasZeroResults && 
                                                        message.metadata?.suggested_prompts && 
                                                        message.metadata.suggested_prompts.length > 0
                              
                              if (hasSuggestedPrompts) {
                                return (
                                  <div className="mt-4 p-4 bg-[#1a1a1a] rounded-lg border border-[#404040]">
                                    <h4 className="text-sm font-medium text-gray-300 mb-3">Try these suggestions:</h4>
                                    <div className="flex flex-wrap gap-2">
                                      {message.metadata!.suggested_prompts!.map((prompt, index) => (
                                        <button
                                          key={index}
                                          onClick={() => handleSubmit(prompt)}
                                          className="px-3 py-2 text-sm bg-[#2f2f2f] hover:bg-[#404040] text-blue-400 hover:text-blue-300 rounded-lg border border-[#404040] hover:border-[#565656] transition-colors"
                                        >
                                          {prompt}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                )
                              }
                              return null
                            })()}
                            
                            {/* Render DataTable for database analytics mode */}
                            {(() => {
                              const shouldRenderTable = activeTab === 'analytics' && message.raw_data && message.raw_data.columns && message.raw_data.rows
                              console.log('🔍 DataTable render check:', {
                                activeTab,
                                hasRawData: !!message.raw_data,
                                hasColumns: message.raw_data?.columns?.length > 0,
                                hasRows: message.raw_data?.rows?.length > 0,
                                shouldRender: shouldRenderTable
                              })
                              
                              if (shouldRenderTable) {
                                console.log('✅ Rendering DataTable with data:', message.raw_data)
                                return (
                                  <div className="mt-6">
                                    <DataTable
                                      columns={message.raw_data.columns}
                                      data={message.raw_data.rows}
                                      title={`Query Results (${message.raw_data.total_count || message.raw_data.rows.length} total records)`}
                                      className="border rounded-lg bg-[#1a1a1a] text-white"
                                    />
                                  </div>
                                )
                              }
                              return null
                            })()}
                            
                            {/* Fallback to markdown table for non-analytics or when no raw data */}
                            {(!message.raw_data || activeTab !== 'analytics') && message.markdown_table && (
                              <div className="mt-4">
                                <ReactMarkdown className="prose prose-invert max-w-none">
                                  {message.markdown_table}
                                </ReactMarkdown>
                              </div>
                            )}
                            
                            {/* Render SQL query if present */}
                            {message.sql && (
                              <details className="mt-4 bg-[#1a1a1a] rounded-lg border border-[#404040]">
                                <summary className="px-3 py-2 cursor-pointer text-sm text-gray-400 hover:text-gray-300">
                                  View SQL Query
                                </summary>
                                <pre className="px-3 pb-3 text-xs text-green-400 overflow-x-auto">
                                  <code>{message.sql}</code>
                                </pre>
                              </details>
                            )}
                          </div>
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

      {/* Sidebar - keeping existing sidebar code unchanged */}
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