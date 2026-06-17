# MedFlow — Pharmacy AI Agent

Intelligent pharmacy system that detects drug interactions, contraindications, dosage issues, and allergy conflicts before dispensing.

## Stack
- PostgreSQL 16 (via Docker)
- Python 3.11+
- FastAPI
- Ollama (LLM inference)

## Quick Start

```bash
cp .env.example .env
docker compose up -d
# DB schema is auto-applied from db/migrations/
```

## Folder Structure

```
db/migrations/     → SQL migration scripts
knowledge_base/    → Data loaders (one per source) and raw source files
patients/          → Synthetic patient generation scripts
engine/            → Interaction detection logic
evaluation/        → End-to-end test scripts
docs/              → Source mapping and design documents
```

## Team

| Role | Name |
|------|------|
| Project Manager | Youssef Hamed |
| Intern | Arij Khemiri |
| Intern | Malak Abdelkhalek |
| Intern | Baha Eddine Ben Mahrez |
