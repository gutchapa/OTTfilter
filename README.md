# StreamFilter - OTT Aggregator Platform

> Your intelligent movie discovery assistant across 10+ Indian OTT platforms

**Live Demo:** https://ott-finder-1.preview.emergentagent.com

---

## 🎯 Overview

StreamFilter solves the frustrating problem of hopping between multiple OTT apps to find movies. Users can search across Netflix, Prime Video, Disney+ Hotstar, Jio Cinema, Zee5, SonyLIV, Voot, MX Player, Aha, and Sun NXT in one place - with AI-powered natural language search, family-safe content ratings, and personalized recommendations.

### Key Problem Solved
*"I want to watch a Tamil romcom but don't know which OTT has it"* → StreamFilter shows all matches with ratings, cast, and platform availability instantly.

---

## ✨ Features

### Core Features
- 🔍 **AI-Powered Natural Language Search** - Type naturally: "latest tamil thriller above 7 rating"
- 🎬 **Multi-Platform Discovery** - Search across 10 Indian OTT platforms simultaneously
- 🌍 **Multi-Language Support** - Tamil, Hindi, Telugu, Malayalam, Kannada, English, Bengali, Marathi, Punjabi, Gujarati
- ⭐ **Dual Rating System** - TMDB + IMDb ratings for better decision making
- 👨‍👩‍👧 **Family-Safe Content Warnings** - Detailed ratings (U, U/A, A, PG, PG-13, R) with AI-generated explanations
- 🎭 **Lead Actor Filtering** - Search only movies where actor is in top 2 cast positions
- 📺 **YouTube Integration** - Find songs, trailers, and comedy scenes
- 🎯 **Smart Typo Correction** - "fahid fasil" → "Fahadh Faasil" automatically

### Advanced Features
- **Theme Understanding** - "brilliant mind movies" → Drama + Thriller genres
- **Platform Variations** - Understands "jio star", "netflix", "prime video"
- **Fuzzy Actor Matching** - Handles name variations and spellings
- **Dynamic TMDB Fetching** - Auto-fetches fresh data when cache insufficient
- **Content Warning Details** - Click "Why A?" to see violence/language/horror specifics

---

## 🛠 Tech Stack

### Frontend
- **Framework:** React 18.x | **Build:** Create React App
- **Styling:** Tailwind CSS 3.x + Custom CSS
- **UI Components:** Shadcn/UI (Dialog, Sheet, Button, Badge, Slider)
- **Icons:** Lucide React | **HTTP:** Axios | **Notifications:** Sonner

### Backend
- **Framework:** FastAPI 0.115+ | **Runtime:** Python 3.11+
- **Async:** asyncio + motor (MongoDB driver) + httpx (connection pooling)
- **AI:** OpenAI GPT-4o-mini | **Validation:** Pydantic v2

### Database
- **MongoDB 7.x** with Motor (async driver)

### APIs
- **TMDB** (movie metadata) | **OMDb** (IMDb ratings) | **YouTube Data v3** (videos) | **OpenAI** (NLP)

### Infrastructure
- **Container:** Kubernetes | **Process:** Supervisor | **Proxy:** K8s Ingress

---

## 💰 Monetization Strategy

### Revenue Models

**1. Freemium ($4.99/month Premium)**
- Free: 10 searches/day with ads
- Premium: Unlimited searches, ad-free, advanced filters, watchlists
- **Projection:** 10k users × 5% conversion = $2,495/month

**2. Affiliate Commissions**
- OTT platform referrals: ₹50-100 per signup
- **Potential:** ₹5,000-10,000/month

**3. API Access ($99/month)**
- 100k requests for developers/entertainment sites

**4. Sponsored Listings**
- ₹10,000/month per featured movie slot (5 slots = ₹50,000/month)

**5. Analytics Dashboard**
- Sell trend data to studios: ₹1,00,000/quarter per client

### Cost Structure
- Infrastructure: $50-100/month
- APIs: $50-100/month (OpenAI primary cost)
- **Total:** ~$150-250/month
- **Break-even:** 30-50 premium subscribers

---

## 🚀 Setup & Installation

### API Keys Required
1. **TMDB** - https://www.themoviedb.org/settings/api (Free)
2. **OMDb** - http://www.omdbapi.com/apikey.aspx (Free 1k/day)
3. **YouTube** - https://console.cloud.google.com/ (Free 10k units/day)
4. **OpenAI** - https://platform.openai.com/api-keys (Paid)

### Environment Variables

**Backend `.env`:**
```bash
MONGO_URL="mongodb://localhost:27017"
TMDB_API_KEY="your_tmdb_bearer_token"
OMDB_API_KEY="your_omdb_key"
YOUTUBE_API_KEY="your_youtube_key"
OPENAI_API_KEY="your_openai_key"
```

**Frontend `.env`:**
```bash
REACT_APP_BACKEND_URL="https://your-domain.com"
```

### Local Development
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend && yarn install && yarn start
```

---

## 📖 Usage Examples

```
"conjuring"                           → Movie title search
"vijay movies"                        → Actor filmography
"tamil action netflix above 7"        → Multi-filter
"brilliant mind thriller"             → Theme understanding
"vadivelu comedy scenes"              → YouTube + movies
"fahad fazil latest"                  → Typo correction
```

---

## 🏗 Architecture

```
User → K8s Ingress → Frontend (React) + Backend (FastAPI)
                          ↓
        MongoDB Cache + OpenAI + External APIs (TMDB/OMDb/YouTube)
```

**Data Flow:** Natural Language → AI Parsing → Cache Check → TMDB Fetch → Enrichment → Display

---

## 🔐 Security
- No personal data (guest mode)
- API keys in environment only
- HTTPS enforced
- Rate limiting enabled

---

## 📊 Performance
- Connection pooling (50 concurrent)
- Batch processing (10 movies parallel)
- Bulk DB writes
- Sub-second cache retrieval

---

## 🚀 Roadmap

**Short Term:** User accounts, watchlists, mobile responsive
**Medium Term:** Personalized recommendations, social features
**Long Term:** Mobile app, voice search, multi-region

---

## 📜 License
APIs: TMDB, OMDb, YouTube (attribution required)
Stack: React, FastAPI, MongoDB, Tailwind, Shadcn/UI

---

**Version:** 1.0.0 | **Status:** Production Ready ✅
**Last Updated:** October 2025
