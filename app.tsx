'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppProvider } from './app-context';
import { ChatLayout } from './chat-layout';
import { Toaster } from './ui/toaster';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <div className="min-h-screen bg-background font-sans antialiased">
          <ChatLayout />
          <Toaster />
        </div>
      </AppProvider>
    </QueryClientProvider>
  );
}