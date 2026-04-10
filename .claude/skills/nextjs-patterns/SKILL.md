---
name: nextjs-patterns
description: "Next.js App Router patterns for DungeonMasterONE web frontend — file conventions, Zustand, WebSocket, Tailwind v4, wizard forms"
---

## When to use

Invoke this skill when:
- Building or modifying the `frontend/` Next.js application
- Creating new pages or routes in the App Router
- Working on the campaign creation wizard (multi-step form)
- Integrating WebSocket for gameplay streaming
- Setting up Zustand stores for client state
- Working on auth (JWT token management, protected routes)
- Configuring Tailwind v4 theme for DM1

## Current API Shape (Next.js 16.2.x)

### Key Breaking Changes from v14/15
- **Turbopack** is the default bundler (no config needed)
- **All request APIs are async** — `await cookies()`, `await headers()`, `await params`
- **`proxy.ts`** replaces `middleware.ts` for route protection
- **Tailwind v4** uses CSS-first config (`@theme` in CSS, no `tailwind.config.js`)
- **React Compiler** is stable — automatic memoization

### File Conventions (App Router)
| File | Purpose |
|---|---|
| `page.tsx` | Route UI (Server Component by default) |
| `layout.tsx` | Persistent wrapper (survives navigation) |
| `loading.tsx` | Instant loading fallback |
| `error.tsx` | Error boundary (must be `"use client"`) |
| `route.ts` | API endpoint (Route Handler) |

### Server vs Client Components
- **Default = Server Component** — no `useState`, `useEffect`, or browser APIs
- **`"use client"`** at top of file → Client Component (interactivity, hooks, WebSocket)
- Push `"use client"` to leaf components — keep the tree server-rendered as much as possible

## DM1 Integration Pattern

### App Directory Structure
```
app/
├── layout.tsx                    # Root (fonts, global CSS, providers)
├── (auth)/login/page.tsx         # Login
├── (auth)/register/page.tsx      # Register
├── (protected)/layout.tsx        # Auth guard, Zustand providers
├── (protected)/dashboard/page.tsx
├── (protected)/campaign/new/page.tsx  # Creation wizard
├── (protected)/campaign/[id]/game/page.tsx  # Gameplay
├── (protected)/settings/page.tsx
└── api/auth/refresh/route.ts     # Token refresh proxy
```

### Zustand Store (Provider Pattern)
```typescript
// stores/game-store.ts
import { createStore } from "zustand/vanilla";
export const createGameStore = () => createStore<GameState>((set) => ({
  narrative: [], suggestions: [], /* ... */
  appendNarrative: (text) => set((s) => ({ narrative: [...s.narrative, text] })),
}));

// providers/game-store-provider.tsx
"use client";
// Use useRef to create store per-request, wrap in Context
```

### WebSocket (Client Component)
```typescript
"use client";
useEffect(() => {
  const ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_URL}/ws/game/${id}?token=${token}`);
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "narrative_chunk") appendNarrative(data.text);
    if (data.type === "suggestions") setSuggestions(data.actions);
  };
  return () => ws.close();
}, [id, token]);
```

### Multi-Step Wizard (React Hook Form + Zod)
```typescript
"use client";
const [step, setStep] = useState(0);
const methods = useForm({ resolver: zodResolver(schemas[step]), mode: "onChange" });
// FormProvider shares state across step components
// Each step component uses useFormContext()
```

### Auth (JWT in memory, refresh via httpOnly cookie)
- Access token: Zustand store (memory only)
- Refresh token: httpOnly cookie (set by backend)
- Route protection: `proxy.ts` checks cookie existence

### Tailwind v4 Theme
```css
@import "tailwindcss";
@theme {
  --color-dm-gold: oklch(0.75 0.15 85);
  --color-dm-dark: oklch(0.15 0.02 260);
  --font-display: "Cinzel", serif;
  --font-body: "Inter", sans-serif;
}
```

### Environment Variables
```
NEXT_PUBLIC_API_URL=http://localhost:8000   # Client-visible
NEXT_PUBLIC_WS_URL=ws://localhost:8000      # Client-visible
API_URL=http://localhost:8000               # Server-only
```

## Common Pitfalls

1. **`"use client"` scope** — everything imported by a client component is also client. Keep client boundaries small.
2. **Zustand + SSR** — never use module-level stores. Use the provider/useRef pattern to create per-request instances.
3. **WebSocket only in Client Components** — `useEffect` with cleanup on unmount.
4. **`proxy.ts` not `middleware.ts`** — v16 renamed it. Use `jose` for JWT in Edge Runtime (not `jsonwebtoken`).
5. **`NEXT_PUBLIC_` vars are build-time** — changes require rebuild, not just restart.
6. **Async request APIs** — `const c = await cookies()` not `cookies()`. Missing `await` is a runtime error in v16.
