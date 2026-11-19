# Task Loop - Quick Deployment Guide

Choose your platform and follow the steps.

## 🚀 Deploy in 5 Minutes

### Option A: Render (Recommended)

1. **Create GitHub Repository**
   ```bash
   cd taskloom
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/taskloom.git
   git push -u origin main
   ```

2. **Deploy Backend**
   - Go to https://render.com → Sign up (free)
   - Click "New +" → "Web Service"
   - Select your GitHub repo
   - Configure:
     - Build: `pip install -r backend/requirements.txt`
     - Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - Add env var: `VITE_API_URL=<your-backend-url>`
   - Deploy!

3. **Deploy Frontend**
   - Click "New +" → "Static Site"
   - Same repo
   - Configure:
     - Build: `npm install && npm run build`
     - Publish: `frontend/dist`
   - Add env var: `VITE_API_URL=<backend-url>`
   - Deploy!

4. **Connect Backend to Ollama**
   - Add env var to backend: `OLLAMA_HOST=<external-ollama-url>`
   - Or deploy Ollama separately

**Done!** Your app is now live 🎉

### Option B: Docker (Local/VPS)

1. **Build & Run**
   ```bash
   docker-compose up -d
   ```

2. **Access**
   - Frontend: http://localhost
   - Backend: http://localhost:8003

### Option C: Railway

1. Go to https://railway.app
2. Connect GitHub
3. Deploy (Railway auto-detects)
4. Set environment variables
5. Done!

## 📍 Environment Variables

**Backend:**
```
PYTHON_ENV=production
VITE_API_URL=https://your-backend.onrender.com
OLLAMA_HOST=http://ollama:11434
```

**Frontend:**
```
VITE_API_URL=https://your-backend.onrender.com
```

## 🔗 URLs After Deployment

- **Frontend**: https://taskloom-frontend.onrender.com (or Railway/Heroku URL)
- **Backend API**: https://taskloom-backend.onrender.com
- **API Docs**: https://taskloom-backend.onrender.com/docs
- **Health**: https://taskloom-backend.onrender.com/api/health

## ⚡ First Task

After deployment:

1. Go to frontend URL
2. Create a project
3. Create a task
4. Watch the SDLC pipeline run
5. Approve when ready

```bash
# Or use API
curl -X POST https://taskloom-backend.onrender.com/api/sdlc/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","description":"Test task","project_id":"test","priority":"high"}'
```

## 🆘 Troubleshooting

### "Cannot connect to backend"
- Check `VITE_API_URL` in frontend
- Check CORS in backend
- Verify backend is running: `/api/health`

### "Ollama not responding"
- Is Ollama running?
- Check `OLLAMA_HOST` env var
- Pull model: `ollama pull qwen3.5:0.8b`

### "Build failed"
- Check logs on Render/Railway dashboard
- Verify `requirements.txt` has all dependencies
- Check Node version (need 18+)

### "Services timing out"
- Free tier takes time to start
- Increase timeout
- Check logs

## 📊 Next Steps

1. **Monitoring**: Check logs at `/api/logs`
2. **Scaling**: Upgrade from free tier
3. **Database**: Add PostgreSQL
4. **Custom Domain**: Add your domain
5. **SSL**: Enable HTTPS (automatic on most platforms)

## 💰 Estimated Monthly Cost

| Component | Free | Basic | Pro |
|-----------|------|-------|-----|
| Backend | $0 | $7 | $30 |
| Frontend | $0 | $0 | $20 |
| Database | - | $15 | $50+ |
| **Total** | **$0** | **$22** | **$100+** |

*Free tier: limited resources, auto-sleeps*

## 📚 More Info

- [Full Deployment Guide](./DEPLOYMENT_OPTIONS.md)
- [Render Detailed Steps](./DEPLOY_RENDER.md)
- [Production Checklist](./PRODUCTION_CHECKLIST.md)
- [README](./README.md)

---

**Questions?** Check the docs or open an issue on GitHub!

**Ready to deploy?** Follow the steps above! 🚀
