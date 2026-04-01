# ARGO Ocean Analytics - FloatChat Backend

AI-powered ARGO Ocean Analytics backend system with natural language querying capabilities.

## Project Structure

```
FloatChat-BE-V1/
└── backend/           # Django REST API
    ├── argo_ai/       # Django project settings
    ├── apps/          # Application modules
    │   ├── chat/      # Chat API endpoints
    │   ├── ingestion/ # NetCDF data ingestion
    │   ├── tools/     # AI tools (Python, SQL, Plot)
    │   └── services/  # NLP and AI pipeline
    ├── scripts/       # Utility scripts
    └── README.md      # Detailed documentation
```

## Quick Start

1. Navigate to `backend/` directory
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file with your credentials
4. Run: `python manage.py runserver`

See `backend/README.md` for detailed documentation