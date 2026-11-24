---
paths:
  - "frontend/**"
---

# Frontend

Run from `frontend/`: `npm run dev`, `npm run build`, `npm run lint`.

- React 19, TypeScript, Vite, Tailwind v4, shadcn/ui (base-nova, built on Base UI, not Radix).
- Feature folders under `src/features/` mirror the backend modules. This is not Feature-Sliced Design; revisit only if several features grow real dependency conflicts.
- `VITE_API_URL` must be `http://localhost:8000`, not `127.0.0.1`: the auth cookie is `samesite=lax` and is not sent across that host mismatch, so `/auth/me` returns 401.
- `shadcn init` overwrites CSS variables of the same name; the violet accent lives in `--primary` and `--ring`.
