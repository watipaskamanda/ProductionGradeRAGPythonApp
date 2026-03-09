// frontend/src/components/chat-layout.tsx
'use client';

import { Sidebar } from './sidebar';
import { ChatPanel } from './chat-panel';
import { AppProvider } from '@/context/app-context';

export function ChatLayout() {
  return (
    <AppProvider>
      <div className="flex h-screen bg-gray-50 text-gray-900">
        <Sidebar />
        <ChatPanel />
      </div>
    </AppProvider>
  );
}
