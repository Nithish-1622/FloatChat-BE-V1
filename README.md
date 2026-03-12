# ARGO Ocean Analytics Backend

AI-powered ocean analytics system for ARGO float data, featuring natural language querying, automated visualizations, and advanced analytics.

## 🌊 Features

- **NetCDF Ingestion Pipeline**: Automated processing of ARGO ocean data
- **Natural Language Queries**: Ask questions in plain English
- **AI-Powered Analytics**: Automatic insights and trend detection
- **Dynamic Visualizations**: Auto-generated charts and maps
- **RESTful API**: Clean JSON responses for React frontend

## 🏗️ Architecture

```
backend/
├── argo_ai/              # Django project settings
│   ├── settings.py       # Configuration
│   ├── urls.py           # URL routing
│   └── wsgi.py           # WSGI application
│
├── apps/
│   ├── ingestion/        # NetCDF data ingestion
│   │   ├── models.py     # Django models
│   │   ├── sa_models.py  # SQLAlchemy models
│   │   ├── pipeline.py   # Ingestion pipeline
│   │   └── views.py      # API views
│   │
│   ├── chat/             # Chat API interface
│   │   ├── views.py      # API endpoints
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── tools/            # AI Tool modules
│   │   ├── python_tool.py    # Data processing
│   │   ├── sql_tool.py       # Text-to-SQL
│   │   └── plot_tool.py      # Visualization
│   │
│   └── services/         # AI Services
│       ├── nlp_service.py    # NLP processing
│       └── ai_pipeline.py    # Orchestration
│
├── scripts/              # Utility scripts
├── requirements.txt      # Dependencies
└── Dockerfile           # Container config
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (Neon recommended)
- Groq API key (optional, for enhanced AI)

### Installation

1. **Clone and setup**:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
copy .env.example .env
# Edit .env with your credentials
```

3. **Initialize database**:
```bash
python scripts/init_db.py
python manage.py migrate
```

4. **Run development server**:
```bash
python manage.py runserver
```

### Environment Variables

```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host.neon.tech/db?sslmode=require
GROQ_API_KEY=your-groq-key  # Optional
VITE_API_URL=http://localhost:5173
```

## 📡 API Endpoints

### Chat API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/` | POST | Natural language query |
| `/api/v1/chat/sql-preview/` | POST | Preview generated SQL |
| `/api/v1/chat/schema/` | GET | Database schema info |
| `/api/v1/chat/context/` | GET/DELETE | Conversation context |
| `/api/v1/chat/samples/` | GET | Sample queries |
| `/api/v1/health/` | GET | Health check |

### Ingestion API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ingestion/status/` | GET | Ingestion status |
| `/api/v1/ingestion/ingest/` | POST | Trigger ingestion |
| `/api/v1/ingestion/stats/` | GET | Database statistics |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the average temperature in the Indian Ocean?"}'
```

### Example Response

```json
{
  "status": "success",
  "text_response": "The average temperature is 24.5°C based on 150,000 measurements.",
  "numeric_summary": {
    "total_records": 150000,
    "columns_returned": ["temperature"],
    "numeric_stats": {
      "temperature": {
        "mean": 24.5,
        "std": 3.2,
        "min": 2.1,
        "max": 32.4
      }
    }
  },
  "analytics": {
    "insights": [
      "The average temperature is 24.5°C",
      "Analysis based on 150,000 records"
    ],
    "trends": null,
    "anomalies": null
  },
  "visualization": {
    "chart_type": "histogram",
    "title": "Temperature Distribution",
    "data": [...]
  },
  "query_info": {
    "intent": "statistics",
    "sql_query": "SELECT AVG(m.temperature)...",
    "execution_time_ms": 45.2
  }
}
```

## 🔧 Data Ingestion

### Ingest from URL

```bash
python scripts/ingest_data.py https://example.com/argo_data.nc --url
```

### Ingest from local file

```bash
python scripts/ingest_data.py /path/to/data.nc
```

### Ingest directory

```bash
python scripts/ingest_data.py /path/to/data/ --directory
```

## 🧠 AI Pipeline Flow

```
User Query
    ↓
NLP Service (Intent + Entities)
    ↓
Python Tool (Validation)
    ↓
SQL Tool (Query Generation)
    ↓
Database (Execution)
    ↓
Plot Tool (Visualization)
    ↓
JSON Response → React Frontend
```

## 📊 Database Schema

### Tables

- **floats**: ARGO float devices
- **profiles**: Measurement profiles (time/location)
- **measurements**: Individual readings (T, S, P)
- **processed_files**: Ingestion tracking

### Indexes

- `profile_time` - Time-based queries
- `latitude`, `longitude` - Geographic queries
- `platform_number` - Float-specific queries

## 🛡️ Security

- SELECT-only SQL enforcement
- Input sanitization
- Rate limiting (60/min)
- CORS restrictions
- SQL injection prevention

## 🚢 Deployment

### Using Docker

```bash
docker build -t argo-backend .
docker run -p 8000:8000 --env-file .env argo-backend
```

### Using Docker Compose

```bash
docker-compose up -d
```

### Production with Gunicorn

```bash
gunicorn --config gunicorn.conf.py argo_ai.wsgi:application
```

## 🧪 Testing

```bash
# Run pipeline tests
python scripts/test_pipeline.py

# Django tests
python manage.py test
```

## 📝 Sample Queries

- "How many floats are in the database?"
- "Show temperature trends over the last month"
- "What is the average salinity at 500m depth?"
- "Temperature profile for float 12345"
- "Map of temperature distribution"
- "Compare northern and southern Indian Ocean"

## 📄 License

MIT License
