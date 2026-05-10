# Member 4 — Frontend / UI & Deployment

**Your job:** Build the HVAC Technician Copilot chat interface and deploy the
full stack (backend + frontend) using Docker or cloud hosting.

---

## Prerequisites

Member 3's backend must be running at `http://localhost:8000`.

---

## Tech Stack Recommendation

| Layer | Tech |
|-------|------|
| UI Framework | React + Vite (or Next.js) |
| HTTP client | axios |
| Icons | lucide-react |
| State | React hooks (useState, useReducer) |
| Styling | Vanilla CSS (glassmorphism dark theme) |

---

## Setup

```powershell
# From the project root
npx create-vite@latest frontend --template react
cd frontend
npm install axios lucide-react
npm run dev
```

Set in your frontend `.env`:
```
VITE_API_BASE_URL=http://localhost:8000
```

---

## What to Build

### Core UI Components

1. **`ChatWindow`** — scrollable message thread
2. **`MessageBubble`** — renders user + bot messages, shows source citations
3. **`InputBar`** — text input + send button + image upload icon
4. **`QuickButtons`** — Troubleshoot / Maintenance / Parts / Safety
5. **`SourceCitation`** — shows `[Manual Name, Page X]` below each bot answer
6. **`FilterBar`** — optional brand/model filter dropdowns

### API Integration

```js
// POST /query
const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/query`, {
  question: userInput,
  brand: selectedBrand,  // optional
  model: selectedModel,  // optional
});
const { answer, sources } = response.data;
```

### Design Guidelines (from roadmap)
- Mobile-first, dark theme
- Quick action buttons: **Troubleshoot** | **Maintenance** | **Parts** | **Safety**
- Upload button for error display / PCB photos
- Fast, field-friendly — large touch targets

---

## Deployment (Step 11)

### Docker Compose (recommended)
Create `docker-compose.yml` at project root:
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./data:/app/data"]
    env_file: .env

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    environment:
      - VITE_API_BASE_URL=http://backend:8000
    depends_on: [backend]
```

### Cloud Options
- **Backend:** Google Cloud Run, Render, Railway
- **Frontend:** Vercel, Netlify, Firebase Hosting
- **ChromaDB:** Self-hosted on a VPS or use Chroma Cloud

---

*Refer to `config.py` for `VITE_API_BASE_URL` and `BACKEND_PORT`.*
