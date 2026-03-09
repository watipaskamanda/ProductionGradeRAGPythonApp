# BIZINEZI Frontend Setup Instructions

## 1. Initialize Next.js Project

```bash
npx create-next-app@latest bizinezi-web --typescript --tailwind --eslint --app
cd bizinezi-web
```

## 2. Install Dependencies

```bash
npm install @tanstack/react-query @radix-ui/react-collapsible @radix-ui/react-scroll-area @radix-ui/react-separator @radix-ui/react-toast recharts lucide-react class-variance-authority clsx tailwind-merge
npm install -D tailwindcss-animate
```

## 3. Project Structure

```
src/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   └── ui/
├── lib/
├── types/
└── hooks/
```

## 4. File Organization

1. **Copy the generated files to your project:**
   - `types-api.ts` → `src/types/api.ts`
   - `app-context.tsx` → `src/lib/context/app-context.tsx`
   - `api-service.ts` → `src/lib/api/service.ts`
   - `interactive-chart.tsx` → `src/components/visualization/interactive-chart.tsx`
   - `chat-layout.tsx` → `src/components/chat/chat-layout.tsx`
   - `ui-components.tsx` → Split into individual files in `src/components/ui/`

2. **Update your main files:**
   - Replace `src/app/page.tsx` with the App component
   - Update `tailwind.config.js` with the provided configuration

## 5. Environment Variables

Create `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 6. Key Features Implemented

### ✅ Modular Architecture
- Separate components for chat, visualization, and UI
- Clean separation of concerns
- TypeScript interfaces for type safety

### ✅ Progressive Disclosure
- Technical details hidden by default
- Automatic complexity detection
- User-level based feature access
- Collapsible debug information

### ✅ State Management
- React Context for global state
- Mode switching with preserved chat history
- Currency and user level persistence

### ✅ API Integration
- TanStack Query for robust data fetching
- Retry logic and error handling
- TypeScript-first API service

### ✅ Interactive Visualization
- Dynamic chart type switching
- Recharts integration
- Responsive design

### ✅ Enterprise UI
- Shadcn/UI components
- Tailwind CSS styling
- Professional ChatGPT-style interface

## 7. Development Commands

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Type checking
npm run type-check
```

## 8. Production Deployment

The application is ready for deployment on:
- Vercel (recommended for Next.js)
- Netlify
- AWS Amplify
- Docker containers

## 9. Integration with Your FastAPI Backend

The frontend expects these API endpoints:
- `POST /api/v1/query/database` - Database analytics
- `POST /api/v1/query` - Document Q&A
- `POST /api/v1/ingest` - File upload
- `GET /health` - Health check

Make sure your FastAPI backend includes CORS middleware for the frontend domain.

## 10. Customization

- **Branding**: Update colors in `tailwind.config.js`
- **API**: Modify `src/lib/api/service.ts` for custom endpoints
- **UI**: Extend Shadcn/UI components in `src/components/ui/`
- **Charts**: Add new chart types in `interactive-chart.tsx`