# MakeSense

Context-intelligent document reasoning engine powered by Optimal Transport.

## Backend Setup
1. `cd backend`
2. `pip install -r ../requirements.txt`
3. Download the spaCy model: `python -m spacy download en_core_web_sm`
4. Copy `.env.example` to `.env` and add your OpenAI Key.
5. Run server: `uvicorn main:app --reload`

## Frontend Setup
1. `cd frontend`
2. `npm install` (or `pnpm install`)
3. `npm run dev`