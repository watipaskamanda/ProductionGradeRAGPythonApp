// frontend/src/components/chat-panel.tsx
'use client';

import React, { useState } from 'react';
import { useApp } from '@/context/app-context';
import { useQueryDatabase } from '@/services/api-service';
import { ChatMessage as ChatMessageType } from '@/types/api';
import { Message } from './message';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send } from 'lucide-react';

export function ChatPanel() {
  const { state, dispatch } = useApp();
  const [input, setInput] = useState('');
  const { mutate: queryDatabase, isPending } = useQueryDatabase();

  const currentMessages = state.chatHistory[state.mode];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage: ChatMessageType = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };
    dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: userMessage } });

    queryDatabase(
      {
        question: input.trim(),
        chat_history: state.chatHistory[state.mode].slice(-5).map(m => ({ role: m.role, content: m.content })),
        currency: state.currency,
        debug_mode: state.debugMode,
        user_level: state.userLevel,
      },
      {
        onSuccess: (data) => {
          const assistantMessage: ChatMessageType = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: data.answer,
            timestamp: new Date(),
            metadata: data,
          };
          dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: assistantMessage } });
        },
        onError: (error) => {
          const errorMessage: ChatMessageType = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `Error: ${error.message}`,
            timestamp: new Date(),
          };
          dispatch({ type: 'ADD_MESSAGE', payload: { mode: state.mode, message: errorMessage } });
        },
      }
    );

    setInput('');
  };

  return (
    <main className="flex-1 flex flex-col">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {currentMessages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
          {isPending && (
            <div className="flex justify-center">
              <div className="text-gray-500">Analyzing...</div>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-gray-200 p-4 bg-white">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your data..."
            disabled={isPending}
            className="flex-1"
          />
          <Button type="submit" disabled={isPending || !input.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </main>
  );
}
