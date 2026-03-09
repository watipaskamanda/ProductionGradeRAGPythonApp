// frontend/src/components/sidebar.tsx
'use client';

import { useApp } from '@/context/app-context';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

export function Sidebar() {
  const { state, dispatch } = useApp();

  return (
    <aside className="w-80 flex flex-col bg-white border-r border-gray-200 p-4 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">BIZINEZI AI</h1>
        <p className="text-sm text-gray-500">Enterprise Analytics Assistant</p>
      </header>

      <div className="space-y-2">
        <Button
          variant={state.mode === 'database' ? 'secondary' : 'ghost'}
          className="w-full justify-start"
          onClick={() => dispatch({ type: 'SET_MODE', payload: 'database' })}
        >
          📊 Database Analytics
        </Button>
        <Button
          variant={state.mode === 'document' ? 'secondary' : 'ghost'}
          className="w-full justify-start"
          onClick={() => dispatch({ type: 'SET_MODE', payload: 'document' })}
        >
          📄 Document Q&A
        </Button>
      </div>

      <div className="border-t border-gray-200 pt-4 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="currency">Currency</Label>
          <Select
            value={state.currency}
            onValueChange={(value: 'MWK' | 'USD') => dispatch({ type: 'SET_CURRENCY', payload: value })}
          >
            <SelectTrigger id="currency">
              <SelectValue placeholder="Select currency" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="MWK">MWK (Malawi Kwacha)</SelectItem>
              <SelectItem value="USD">USD (US Dollar)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="user-level">User Level</Label>
          <Select
            value={state.userLevel}
            onValueChange={(value: 'business' | 'analyst' | 'developer') => dispatch({ type: 'SET_USER_LEVEL', payload: value })}
          >
            <SelectTrigger id="user-level">
              <SelectValue placeholder="Select user level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="business">Business User</SelectItem>
              <SelectItem value="analyst">Data Analyst</SelectItem>
              <SelectItem value="developer">Developer</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {(state.userLevel === 'analyst' || state.userLevel === 'developer') && (
          <div className="flex items-center justify-between">
            <Label htmlFor="debug-mode">Developer Mode</Label>
            <Switch
              id="debug-mode"
              checked={state.debugMode}
              onCheckedChange={() => dispatch({ type: 'TOGGLE_DEBUG_MODE' })}
            />
          </div>
        )}
      </div>

      <div className="flex-1" />

      <Button
        variant="outline"
        onClick={() => dispatch({ type: 'CLEAR_CHAT', payload: state.mode })}
      >
        Clear Chat
      </Button>
    </aside>
  );
}
