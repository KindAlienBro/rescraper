---
title: Rescraper - VTU Result Scraper
sdk: docker
app_port: 7860
---

# Rescraper

Project By [**VORNIITY GROUPS**](https://vorniity.com/)

Fetch, view and export VTU results for an entire batch in seconds.

## 🚀 Features

- **Fast**: Uses lightweight HTTP requests instead of browser automation (~3s per USN)
- **Accurate**: Deep learning captcha solver (ddddocr) with 95%+ first-try accuracy
- **Export**: Download batch results as Excel (.xlsx)
- **Live Progress**: Real-time status updates while scraping
- **Deployable**: Runs on Hugging Face Spaces via Docker

## 📂 Running Locally

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:7860` in your browser.

## 📦 Deploying to Hugging Face Spaces

1. Create a new Space on [huggingface.co](https://huggingface.co/new-space)
2. Select **Docker** as the SDK
3. Push this repository to the Space
4. The app will auto-deploy on port 7860

---

> **Note**: Make sure to scrape results for 20–25 USNs at a time and keep an interval between each attempt.
