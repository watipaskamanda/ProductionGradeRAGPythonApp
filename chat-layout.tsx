'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Settings, History, Code, ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { useApp } from '../app-context';
import { useDatabaseQuery, useDocumentQuery } from '../api-service';
import { InteractiveChart } from './interactive-chart';
import { ChatMessage } from '../types-api';

export function ChatLayout() {
  const { state, dispatch } = useApp();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const databaseQuery = useDatabaseQuery();
  const documentQuery = useDocumentQuery();

  const currentMessages = state.chatHistory[state.mode];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: userMessage } });
    setInput('');
    setIsLoading(true);

    try {
      if (state.mode === 'database') {
        const response = await databaseQuery.mutateAsync({
          question: input.trim(),
          chat_history: currentMessages,
          currency: state.currency,
          debug_mode: state.debugMode,
          user_level: state.userLevel,
        });

        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.answer,
          timestamp: new Date(),
          metadata: {
            chart_config: response.chart_config,
            debug_info: response.debug_info,
            sql: response.debug_info?.sql,
            plan: response.debug_info?.plan,
          },
        };

        dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: assistantMessage } });
      } else if (state.mode === 'document') {
        const response = await documentQuery.mutateAsync({
          question: input.trim(),
          top_k: 5,
        });

        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.answer,
          timestamp: new Date(),
        };

        dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: assistantMessage } });
      }
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
        timestamp: new Date(),
      };

      dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: errorMessage } });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-80 border-r bg-muted/10 flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold">BIZINEZI AI</h1>
          <p className="text-sm text-muted-foreground">Enterprise Analytics Assistant</p>
        </div>

        {/* Mode Selector */}
        <div className="p-4 border-b">
          <div className="space-y-2">
            {(['database', 'document', 'upload'] as const).map((mode) => (
              <Button
                key={mode}
                variant={state.mode === mode ? 'default' : 'ghost'}
                className="w-full justify-start"
                onClick={() => dispatch({ type: 'SET_MODE', payload: mode })}
              >
                {mode === 'database' && '📊 Database Analytics'}
                {mode === 'document' && '📄 Document Q&A'}
                {mode === 'upload' && '📤 Upload Documents'}
              </Button>
            ))}
          </div>
        </div>

        {/* Settings */}
        <div className="p-4 border-b space-y-4">
          <div>
            <label className="text-sm font-medium">Currency</label>
            <select
              value={state.currency}
              onChange={(e) => dispatch({ type: 'SET_CURRENCY', payload: e.target.value as any })}
              className="w-full mt-1 p-2 border rounded-md"
            >
              <option value="MWK">MWK (Malawi Kwacha)</option>
              <option value="USD">USD (US Dollar)</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">User Level</label>
            <select
              value={state.userLevel}
              onChange={(e) => dispatch({ type: 'SET_USER_LEVEL', payload: e.target.value as any })}
              className="w-full mt-1 p-2 border rounded-md"
            >
              <option value="business">Business User</option>
              <option value="analyst">Data Analyst</option>
              <option value="developer">Developer</option>
            </select>
          </div>

          {(state.userLevel === 'analyst' || state.userLevel === 'developer') && (
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="debug-mode"
                checked={state.debugMode}
                onChange={() => dispatch({ type: 'TOGGLE_DEBUG_MODE' })}
              />
              <label htmlFor="debug-mode" className="text-sm">Debug Mode</label>
            </div>
          )}
        </div>

        {/* Chat History */}
        <div className="flex-1 p-4">
          <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
            <History className="w-4 h-4" />
            Chat History
          </h3>
          <ScrollArea className="h-full">
            <div className="space-y-2">
              {currentMessages.filter(m => m.role === 'user').map((message) => (
                <div
                  key={message.id}
                  className="p-2 text-xs bg-muted rounded cursor-pointer hover:bg-muted/80"
                  onClick={() => setInput(message.content)}
                >
                  {message.content.slice(0, 50)}...
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        <div className="p-4 border-t">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => dispatch({ type: 'CLEAR_CHAT', payload: state.mode })}
          >
            Clear Chat
          </Button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <ScrollArea className="flex-1 p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {currentMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex justify-center">
                <div className="animate-pulse">Analyzing...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  state.mode === 'database'
                    ? 'Ask about your data...'
                    : 'Ask about your documents...'
                }
                disabled={isLoading}
                className="flex-1"
              />
              <Button type="submit" disabled={isLoading || !input.trim()}>
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const [showTechnical, setShowTechnical] = useState(false);

  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-3xl ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'} rounded-lg p-4`}>
        <div className="prose prose-sm max-w-none">
          {message.content}
        </div>

        {/* Chart Visualization */}
        {message.metadata?.chart_config && (
          <div className="mt-4">
            <InteractiveChart config={message.metadata.chart_config} />
          </div>
        )}

        {/* Technical Insights (Progressive Disclosure) */}
        {message.metadata?.debug_info && (
          <Collapsible open={showTechnical} onOpenChange={setShowTechnical} className="mt-4">
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="flex items-center gap-2">
                {showTechnical ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <Code className="w-4 h-4" />
                Technical Insights
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Debug Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {message.metadata.debug_info.sql && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Generated SQL</h4>
                      <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                        {message.metadata.debug_info.sql}
                      </pre>
                    </div>
                  )}
                  
                  {message.metadata.debug_info.execution_steps && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Execution Steps</h4>
                      <div className="space-y-1">
                        {message.metadata.debug_info.execution_steps.map((step, index) => (
                          <Badge key={index} variant="secondary" className="text-xs">
                            {step}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {message.metadata.debug_info.complexity_reason && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Complexity Analysis</h4>
                      <p className="text-xs text-muted-foreground">
                        {message.metadata.debug_info.complexity_reason}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </CollapsibleContent>
          </Collapsible>
        )}

        <div className="mt-2 text-xs text-muted-foreground">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}