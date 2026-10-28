# Visual Guide — Pharma Lab Deployment

## Step 1: Streamlit Cloud (3 minutes, no token needed)

1. Open https://share.streamlit.io
2. Click "Continue with GitHub"
3. Click "+ New app"
4. Fill in:
   - Repository: tibatechapp-ship-it/pharma-sdl
   - Branch: main
   - Main file: app.py
   - App URL: pharma-lab (optional)
5. Click "Deploy!"
6. Wait 1-2 minutes
7. App is live at: https://tibatechapp-ship-it-pharma-sdl.streamlit.app

## Step 2: Get HF_TOKEN

1. Open https://huggingface.co/settings/tokens
2. Click "New token"
3. Name: github-deploy
4. Type: Write (NOT Read!)
5. Click "Create token"
6. Copy the token (starts with hf_)

## Step 3: Add HF_TOKEN to GitHub

1. Open https://github.com/tibatechapp-ship-it/pharma-sdl/settings/secrets/actions
2. Click "New repository secret"
3. Name: HF_TOKEN
4. Value: paste token
5. Click "Add secret"
6. Verify: "HF_TOKEN Updated now" appears

## Step 4: Re-enable HF Deploy

```bash
cd ~/pharma-sdl
mv .github/workflows/deploy-hf.yml.disabled .github/workflows/deploy-hf.yml
git add .github/workflows/
git commit -m "ci: re-enable HF deploy"
git push origin main
```

7. Watch: https://github.com/tibatechapp-ship-it/pharma-sdl/actions
8. HF live at: https://huggingface.co/spaces/tibatechapp/pharma-lab

## Final Result: 3 Platforms Live

| Platform | URL | Status |
|----------|-----|--------|
| Streamlit Cloud | tibatechapp-ship-it-pharma-sdl.streamlit.app | Live |
| Hugging Face | huggingface.co/spaces/tibatechapp/pharma-lab | Live |
| GitHub Pages | tibatechapp-ship-it.github.io/pharma-sdl | Live |
