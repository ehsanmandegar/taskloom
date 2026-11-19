# Deploy Task Loop to Render

## Prerequisites
- GitHub account (free)
- Render account (free tier available: render.com)
- Git installed locally
- Code pushed to GitHub

## Step 1: Push to GitHub

```bash
cd taskloom
git init
git add .
git commit -m "Initial Task Loop commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/taskloom.git
git push -u origin main
```

## Step 2: Deploy Backend to Render

### Option A: Via Render Dashboard (Easiest)

1. Go to [render.com](https://render.com) and sign in
2. Click "New +" → "Web Service"
3. Select your GitHub repository
4. Configure:
   - **Name**: `taskloom-backend`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free (or Starter for better performance)
5. Add Environment Variables:
   - `PYTHONUNBUFFERED`: `1`
   - `VITE_API_URL`: `https://taskloom-backend.onrender.com`
6. Click "Create Web Service"

### Option B: Via render.yaml (Infrastructure as Code)

```bash
git add render.yaml
git commit -m "Add Render deployment config"
git push

# Go to Render Dashboard → "New +" → "Blueprint"
# Select your repository → Deploy
```

## Step 3: Deploy Frontend to Render

1. Click "New +" → "Static Site"
2. Connect your GitHub repo
3. Configure:
   - **Name**: `taskloom-frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `frontend/dist`
4. Add Environment Variables:
   - `VITE_API_URL`: `https://taskloom-backend.onrender.com`
5. Click "Create Static Site"

## Step 4: Configure Environment Variables

**Backend:**
```
PYTHONUNBUFFERED=1
PYTHON_ENV=production
VITE_API_URL=https://taskloom-backend.onrender.com
```

**Frontend:**
```
VITE_API_URL=https://taskloom-backend.onrender.com
```

## Step 5: Update CORS

In `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Important Notes

### Free Tier Limitations
- Services spin down after 15 minutes of inactivity
- Limited CPU/memory
- Restarts weekly

### Ollama Integration
- Use external Ollama server or LLM API
- Configure `OLLAMA_HOST` environment variable

### Data Persistence
Currently using JSON files. For production add:
- PostgreSQL database
- Persistent storage
- Redis caching

## Deployment URLs

After successful deployment:
- **Frontend**: `https://taskloom-frontend.onrender.com`
- **Backend**: `https://taskloom-backend.onrender.com`
- **API Docs**: `https://taskloom-backend.onrender.com/docs`

## Monitoring

1. Go to your Render service dashboard
2. Click "Logs" tab to view real-time logs
3. Use `/api/logs` endpoint for structured logs
4. Use `/api/health` to check service status

## Next Steps

1. Set up PostgreSQL database
2. Configure external Ollama server
3. Set up custom domain
4. Monitor logs and performance

---

**Task Loop is now production-deployed! 🚀**
