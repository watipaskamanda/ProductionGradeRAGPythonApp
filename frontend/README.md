# Frontend Setup

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

## What's Included

✅ **Next.js 14** with TypeScript
✅ **Tailwind CSS** for styling  
✅ **React Query** for API calls
✅ **Progressive Disclosure** - Technical details hidden by default
✅ **State Management** - Mode switching with chat history
✅ **Responsive Design** - ChatGPT-style interface

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   └── chat-layout.tsx
│   ├── lib/
│   │   └── app-context.tsx
│   └── types/
│       └── api.ts
├── package.json
├── tailwind.config.js
└── tsconfig.json
```

## Next Steps

1. **Install dependencies**: `npm install`
2. **Start development**: `npm run dev`
3. **Connect to your FastAPI backend** (update API_URL in components)
4. **Add Recharts** for visualization: `npm install recharts`
5. **Deploy** to Vercel/Netlify when ready

The frontend is ready to connect to your existing FastAPI backend!