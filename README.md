# Eviot by MakeSense

**A context-intelligent document reasoning engine powered by Optimal Transport.**

If you've worked with Retrieval-Augmented Generation (RAG) systems before, the workflow is probably familiar: split documents into chunks, generate embeddings, retrieve the top-k matches, and pass them to an LLM.

For simple fact retrieval, that approach works reasonably well. But when a question requires connecting information from different parts of a document, retrieval becomes the bottleneck. The system often over-focuses on the most dominant concepts in the query, repeatedly pulling similar pieces of information while overlooking other evidence needed to form a complete answer.

MakeSense was built to tackle that problem.

Instead of treating retrieval as a ranking task, MakeSense treats it as a **context construction problem**. The goal is not to find the "best" sentence, but to build the most complete set of evidence for a given query. Using Optimal Transport (OT), the system continuously measures what parts of a query remain semantically uncovered and retrieves the sentence that contributes the most new information at each step.

The result is a compact, evidence-rich context that is better suited for reasoning tasks where information is distributed across a document.

---

# Why We Built This

While working on document reasoning systems, we kept running into the same issue: retrieval quality mattered far more than model quality.

You could swap in larger models, better prompts, or more sophisticated reasoning techniques, but if the retrieval step missed a critical piece of evidence, the final answer was already compromised.

Most retrieval pipelines optimize for similarity. We became more interested in optimizing for **coverage**.

The question shifted from:

> "Which sentence is most similar to the query?"

to:

> "What information is still missing, and which sentence helps fill that gap?"

That idea eventually evolved into MakeSense.

---

# How It Works

MakeSense is built on top of **Eviot**, an Optimal Transport-based retrieval library that we developed for adaptive context construction.

At a high level, the retrieval process works as follows:

### 1. Represent the Query

The query is treated as a collection of semantic requirements that need to be satisfied by evidence from the document.

### 2. Find the Highest Marginal Gain

Rather than independently ranking sentences, MakeSense evaluates the entire candidate pool and selects the sentence that provides the largest semantic contribution to the current context.

In simple terms, it asks:

> "Which sentence teaches us the most that we don't already know?"

### 3. Recalculate What Is Missing

Once a sentence is selected, the system updates its understanding of what parts of the query remain uncovered.

The process repeats, with each new sentence filling a different gap.

### 4. Stop When Additional Evidence Stops Helping

As more evidence is added, the remaining transport cost decreases.

When the gain from adding another sentence becomes negligible, the system reaches what we call **semantic saturation** and stops retrieving.

This allows retrieval to adapt naturally to the complexity of the query instead of relying on arbitrary top-k values.

---

# Key Features

### Optimal Transport-Based Retrieval

Retrieval is driven by semantic coverage rather than pure similarity scores.

### Adaptive Context Construction

The context grows dynamically based on what information is still missing from the current evidence set.

### Efficient Context Selection

Prioritizes complementary evidence and avoids unnecessary redundancy.

### Evidence-Grounded Reasoning

Answers are generated from explicitly retrieved evidence rather than broad document summaries.

### Traceable Retrieval Pipeline

Every retrieved sentence can be linked back to its original location in the source document.

---

# Getting Started

## Prerequisites

- Python 3.11+
- Node.js 20+
- OpenAI API Key or Any Local Model

---

## Backend Setup

The backend is built with FastAPI and hosts the retrieval engine.

```bash
cd backend

python -m venv venv
source venv/bin/activate

# Windows
# venv\Scripts\activate

pip install -r ../requirements.txt

python -m spacy download en_core_web_sm

cp .env.example .env
```

Add your API key to the `.env` file:

```env
OPENAI_API_KEY=your_api_key_here
HF_TOKEN=your_huggingface_token
```

Start the server:

```bash
uvicorn main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

The first startup may take a little longer while the embedding models are loaded.

---

## Frontend Setup

The frontend is built with Next.js and Tailwind CSS.

```bash
cd frontend

npm install

npm run dev
```

Open:

```text
http://localhost:3000
```

to access the application.

---

# Use Cases

### Multi-Hop Document Reasoning

Questions where the answer is spread across multiple sections of a document.

### Technical Documentation Analysis

Connecting requirements, specifications, and implementation details across large technical documents.

### Legal and Compliance Review

Following references and dependencies across contracts, policies, and supporting documents.

### Research Literature Exploration

Building focused evidence sets from long papers and academic publications.

### Enterprise Knowledge Systems

Improving retrieval quality for internal knowledge assistants and document intelligence platforms.