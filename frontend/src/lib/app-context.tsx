'use client';

import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { AppMode, Currency, UserLevel, ChatMessage } from '@/types/api';

interface AppState {
  mode: AppMode;
  currency: Currency;
  userLevel: UserLevel;
  debugMode: boolean;
  chatHistory: Record<AppMode, ChatMessage[]>;
}

type AppAction =
  | { type: 'SET_MODE'; payload: AppMode }
  | { type: 'SET_CURRENCY'; payload: Currency }
  | { type: 'SET_USER_LEVEL'; payload: UserLevel }
  | { type: 'TOGGLE_DEBUG_MODE' }
  | { type: 'ADD_MESSAGE'; payload: { mode: AppMode; message: ChatMessage } }
  | { type: 'CLEAR_CHAT'; payload: AppMode };

const initialState: AppState = {
  mode: 'database',
  currency: 'MWK',
  userLevel: 'business',
  debugMode: false,
  chatHistory: {
    document: [],
    database: [],
    upload: []
  }
};

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_MODE':
      return { ...state, mode: action.payload };
    case 'SET_CURRENCY':
      return { ...state, currency: action.payload };
    case 'SET_USER_LEVEL':
      return { ...state, userLevel: action.payload };
    case 'TOGGLE_DEBUG_MODE':
      return { ...state, debugMode: !state.debugMode };
    case 'ADD_MESSAGE':
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          [action.payload.mode]: [
            ...state.chatHistory[action.payload.mode],
            action.payload.message
          ]
        }
      };
    case 'CLEAR_CHAT':
      return {
        ...state,
        chatHistory: {
          ...state.chatHistory,
          [action.payload]: []
        }
      };
    default:
      return state;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}