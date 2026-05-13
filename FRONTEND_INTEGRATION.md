# ARGO Ocean Analytics - Frontend Integration Guide

## Overview

This document provides complete API integration details for the ARGO Ocean Analytics backend. The API enables natural language querying of ARGO ocean float data with AI-powered insights and auto-generated visualizations.

---

## Base Configuration

```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';

// Default headers
const headers = {
  'Content-Type': 'application/json',
};
```

---

## API Endpoints

### 1. Health Check

Check if the backend is operational and get database statistics.

**Endpoint:** `GET /api/v1/health/`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-03T17:11:16.219265",
  "components": {
    "database": {
      "status": "connected",
      "floats": 20,
      "profiles": 1341,
      "measurements": 13410
    },
    "ai": {
      "status": "available",
      "provider": "groq"
    }
  }
}
```

**Frontend Usage:**
```javascript
async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health/`);
  const data = await response.json();
  return data;
}
```

---

### 2. Natural Language Query (Main Endpoint)

Process natural language queries about ocean data.

**Endpoint:** `POST /api/v1/chat/`

**Request Body:**
```json
{
  "query": "What is the average temperature in the Indian Ocean?",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "context": {},
  "include_data": true,
  "max_rows": 100
}
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Natural language query (max 5000 chars) |
| `session_id` | string | No | auto-generated | Existing chat session ID to append messages |
| `context` | object | No | `{}` | Context from previous queries |
| `include_data` | boolean | No | `true` | Include raw data in response |
| `max_rows` | integer | No | `100` | Max rows to return (1-10000) |

**Response:**
```json
{
  "status": "success",
  "query_id": "a1b2c3d4",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "text_response": "The average temperature in the Indian Ocean is 18.5°C based on 13,410 measurements across 20 floats.",
  "numeric_summary": {
    "total_records": 13410,
    "columns_returned": ["temperature", "salinity", "pressure"],
    "numeric_stats": {
      "temperature": {
        "mean": 18.5,
        "min": 2.1,
        "max": 29.8,
        "std": 7.2
      }
    }
  },
  "analytics": {
    "insights": [
      "Average temperature: 18.5°C",
      "Temperature range: 2.1°C to 29.8°C",
      "Higher temperatures observed in surface waters"
    ],
    "trends": "Temperature shows seasonal variation with higher values in summer months",
    "anomalies": null,
    "recommendations": "Consider filtering by depth for more specific analysis"
  },
  "visualization": {
    "chart_type": "line",
    "chart_data": {
      "labels": ["Jan", "Feb", "Mar", "..."],
      "datasets": [{
        "label": "Temperature (°C)",
        "data": [18.2, 18.5, 19.1, "..."]
      }]
    },
    "chart_options": {
      "responsive": true,
      "plugins": {
        "title": {
          "display": true,
          "text": "Temperature Trends"
        }
      }
    }
  },
  "data": [
    {
      "platform_number": "2901001",
      "latitude": -15.2345,
      "longitude": 65.4321,
      "temperature": 24.5,
      "salinity": 35.2,
      "pressure": 10.0,
      "profile_time": "2025-06-15T12:30:00Z"
    }
  ],
  "query_info": {
    "intent": "aggregation",
    "query_type": "temperature_analysis",
    "parameters": {
      "metric": "temperature",
      "aggregation": "average"
    },
    "sql_query": "SELECT AVG(temperature) as avg_temp FROM measurements..."
  },
  "execution_time_ms": 245.67,
  "error": null
}
```

---

### 3. Chat Sessions (MongoDB)

Create/list chat sessions for persistent conversation history.

**Endpoint:** `GET /api/v1/chat/sessions/`

**Response:**
```json
{
  "status": "success",
  "sessions": [
    {
      "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
      "title": "What was the average temperature in 2023?",
      "pinned": false,
      "created_at": "2026-04-09T08:31:12.000000+00:00",
      "updated_at": "2026-04-09T08:33:50.000000+00:00",
      "last_message_preview": "The average temperature in 2023 is...",
      "message_count": 6
    }
  ]
}
```

**Endpoint:** `POST /api/v1/chat/sessions/`

**Request Body:**
```json
{
  "title": "New Ocean Analysis"
}
```

**Response:**
```json
{
  "status": "success",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "title": "New Ocean Analysis"
}
```

---

### 4. Session Message History

Fetch ordered messages for one chat session.

**Endpoint:** `GET /api/v1/chat/sessions/{session_id}/messages/`

**Response:**
```json
{
  "status": "success",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "messages": [
    {
      "role": "user",
      "content": "What was the average temperature in 2023?",
      "created_at": "2026-04-09T08:31:12.000000+00:00",
      "query_id": "a1b2c3d4"
    },
    {
      "role": "assistant",
      "content": "The average temperature in 2023 is ...",
      "created_at": "2026-04-09T08:31:13.000000+00:00",
      "query_id": "a1b2c3d4"
    }
  ]
}
```

---

### 5. Delete Session

Delete one session and all its persisted messages.

**Endpoint:** `DELETE /api/v1/chat/sessions/{session_id}/`

**Success Response (200):**
```json
{
  "status": "success",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "messages_deleted": 12
}
```

**Not Found (404):**
```json
{
  "status": "error",
  "session_id": "c95f6d39-7b2b-4c74-a5e4-591f5a6e4f6e",
  "error": "Session not found"
}
```

**Frontend Usage:**
```javascript
async function queryData(query, options = {}) {
  const response = await fetch(`${API_BASE_URL}/chat/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      query,
      include_data: options.includeData ?? true,
      max_rows: options.maxRows ?? 100,
      context: options.context ?? {}
    })
  });
  
  if (!response.ok) {
    throw new Error(`Query failed: ${response.status}`);
  }
  
  return await response.json();
}

// Example usage
const result = await queryData("Show me temperature trends for the last month");
```

---

### 3. SQL Preview

Preview the generated SQL without executing the query.

**Endpoint:** `POST /api/v1/chat/sql-preview/`

**Request Body:**
```json
{
  "query": "Show me temperature data for float 2901001"
}
```

**Response:**
```json
{
  "sql": "SELECT m.temperature, m.pressure, p.latitude, p.longitude, p.profile_time FROM measurements m JOIN profiles p ON m.profile_id = p.id JOIN floats f ON p.float_id = f.id WHERE f.platform_number = '2901001' ORDER BY p.profile_time DESC LIMIT 1000",
  "intent": {
    "primary_intent": "data_retrieval",
    "query_type": "float_specific",
    "parameters": {
      "float_id": "2901001",
      "metric": "temperature"
    }
  },
  "valid": true
}
```

**Frontend Usage:**
```javascript
async function previewSQL(query) {
  const response = await fetch(`${API_BASE_URL}/chat/sql-preview/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query })
  });
  return await response.json();
}
```

---

### 4. Database Schema

Get the database structure for reference.

**Endpoint:** `GET /api/v1/chat/schema/`

**Response:**
```json
{
  "schema": "Table: floats\n  - id: INTEGER (PRIMARY KEY)\n  - platform_number: VARCHAR(20)\n  - first_seen: DATETIME\n  - last_seen: DATETIME\n\nTable: profiles\n  - id: INTEGER (PRIMARY KEY)\n  - float_id: INTEGER (FOREIGN KEY -> floats.id)\n  - latitude: FLOAT\n  - longitude: FLOAT\n  - profile_time: DATETIME\n\nTable: measurements\n  - id: INTEGER (PRIMARY KEY)\n  - profile_id: INTEGER (FOREIGN KEY -> profiles.id)\n  - pressure: FLOAT\n  - temperature: FLOAT\n  - salinity: FLOAT",
  "tables": [
    {
      "name": "floats",
      "description": "ARGO float devices",
      "columns": ["id", "platform_number", "first_seen", "last_seen"]
    },
    {
      "name": "profiles",
      "description": "Measurement profiles at specific times/locations",
      "columns": ["id", "float_id", "latitude", "longitude", "profile_time"]
    },
    {
      "name": "measurements",
      "description": "Individual measurements",
      "columns": ["id", "profile_id", "pressure", "temperature", "salinity"]
    }
  ]
}
```

---

### 5. Sample Queries

Get example queries to display in the UI.

**Endpoint:** `GET /api/v1/chat/samples/`

**Response:**
```json
{
  "samples": [
    {
      "category": "Basic Queries",
      "queries": [
        "How many floats are in the database?",
        "Show me the latest temperature data",
        "What is the average salinity?"
      ]
    },
    {
      "category": "Time-based Analysis",
      "queries": [
        "Show temperature trends over the last month",
        "What was the average temperature in 2023?",
        "Monthly temperature variations"
      ]
    },
    {
      "category": "Depth Profiles",
      "queries": [
        "Show temperature profile by depth",
        "How does salinity change with depth?",
        "Temperature at 500 meters depth"
      ]
    },
    {
      "category": "Geographic Analysis",
      "queries": [
        "Map of temperature distribution",
        "Show data from the northern Indian Ocean",
        "Temperature comparison between regions"
      ]
    },
    {
      "category": "Statistical Analysis",
      "queries": [
        "Statistics for temperature data",
        "What is the temperature distribution?",
        "Maximum and minimum temperatures recorded"
      ]
    }
  ]
}
```

---

### 6. Conversation Context

Manage conversation context for multi-turn queries.

#### Get Context
**Endpoint:** `GET /api/v1/chat/context/`

**Response:**
```json
{
  "context": {
    "last_query": "Show temperature data",
    "entities": {
      "metric": "temperature",
      "region": "Indian Ocean"
    },
    "history": []
  },
  "status": "active"
}
```

#### Reset Context
**Endpoint:** `DELETE /api/v1/chat/context/`

**Response:**
```json
{
  "status": "reset",
  "message": "Conversation context has been reset"
}
```

---

### 7. Submit Feedback

Allow users to rate query responses.

**Endpoint:** `POST /api/v1/chat/feedback/`

**Request Body:**
```json
{
  "query_id": "a1b2c3d4",
  "rating": 4,
  "feedback_text": "Good response but could include more details",
  "correct_response": ""
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query_id` | string | Yes | ID from query response |
| `rating` | integer | Yes | Rating 1-5 |
| `feedback_text` | string | No | Optional feedback text (max 1000 chars) |
| `correct_response` | string | No | What the correct response should be |

**Response:**
```json
{
  "status": "received",
  "message": "Thank you for your feedback"
}
```

---

## Visualization Types

The API returns different chart types based on the query. Handle these in your frontend:

| Chart Type | When Used | Data Structure |
|------------|-----------|----------------|
| `line` | Time series, trends | `{ labels: [], datasets: [{ data: [] }] }` |
| `bar` | Comparisons, counts | `{ labels: [], datasets: [{ data: [] }] }` |
| `scatter` | Correlations | `{ datasets: [{ data: [{x, y}] }] }` |
| `histogram` | Distributions | `{ labels: [], datasets: [{ data: [] }] }` |
| `profile` | Depth profiles | `{ labels: [], datasets: [{ data: [] }] }` |
| `map` | Geographic data | `{ points: [{lat, lon, value}] }` |

### Example: Rendering Charts with Chart.js

```javascript
import { Chart } from 'chart.js/auto';

function renderVisualization(visualization, canvasElement) {
  if (!visualization) return null;
  
  const { chart_type, chart_data, chart_options } = visualization;
  
  if (chart_type === 'map') {
    // Handle map separately with Leaflet/Mapbox
    return renderMap(chart_data);
  }
  
  return new Chart(canvasElement, {
    type: chart_type,
    data: chart_data,
    options: chart_options
  });
}
```

---

## React Integration Example

```jsx
import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000/api/v1';

function ArgoQueryComponent() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [samples, setSamples] = useState([]);

  // Load sample queries on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/chat/samples/`)
      .then(res => res.json())
      .then(data => setSamples(data.samples))
      .catch(console.error);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          include_data: true,
          max_rows: 100
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSampleClick = (sampleQuery) => {
    setQuery(sampleQuery);
  };

  const handleFeedback = async (rating) => {
    if (!result?.query_id) return;
    
    await fetch(`${API_BASE_URL}/chat/feedback/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_id: result.query_id,
        rating
      })
    });
  };

  return (
    <div className="argo-query">
      {/* Sample Queries */}
      <div className="samples">
        {samples.map(category => (
          <div key={category.category}>
            <h4>{category.category}</h4>
            {category.queries.map(q => (
              <button key={q} onClick={() => handleSampleClick(q)}>
                {q}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Query Input */}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about ocean data..."
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Ask'}
        </button>
      </form>

      {/* Error Display */}
      {error && <div className="error">{error}</div>}

      {/* Results */}
      {result && (
        <div className="results">
          {/* Text Response */}
          <div className="text-response">
            <p>{result.text_response}</p>
          </div>

          {/* Insights */}
          {result.analytics?.insights?.length > 0 && (
            <div className="insights">
              <h4>Insights</h4>
              <ul>
                {result.analytics.insights.map((insight, i) => (
                  <li key={i}>{insight}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Visualization */}
          {result.visualization && (
            <div className="chart-container">
              {/* Render chart based on result.visualization */}
            </div>
          )}

          {/* Data Table */}
          {result.data?.length > 0 && (
            <div className="data-table">
              <h4>Data ({result.numeric_summary?.total_records} records)</h4>
              <table>
                <thead>
                  <tr>
                    {Object.keys(result.data[0]).map(key => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.data.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((val, j) => (
                        <td key={j}>{val}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Feedback */}
          <div className="feedback">
            <span>Rate this response:</span>
            {[1, 2, 3, 4, 5].map(rating => (
              <button key={rating} onClick={() => handleFeedback(rating)}>
                {rating}⭐
              </button>
            ))}
          </div>

          {/* Execution Info */}
          <div className="meta">
            <small>
              Query ID: {result.query_id} | 
              Time: {result.execution_time_ms?.toFixed(2)}ms
            </small>
          </div>
        </div>
      )}
    </div>
  );
}

export default ArgoQueryComponent;
```

---

## TypeScript Interfaces

```typescript
// Types for API responses

interface HealthResponse {
  status: 'healthy' | 'degraded' | 'error';
  timestamp: string;
  components: {
    database: {
      status: 'connected' | 'error';
      floats: number;
      profiles: number;
      measurements: number;
    };
    ai: {
      status: 'available' | 'limited' | 'error';
      provider: string;
    };
  };
}

interface NumericStats {
  mean?: number;
  min?: number;
  max?: number;
  std?: number;
  count?: number;
}

interface NumericSummary {
  total_records: number;
  columns_returned: string[];
  numeric_stats: Record<string, NumericStats>;
}

interface Analytics {
  insights: string[];
  trends: string | null;
  anomalies: string | null;
  recommendations: string | null;
}

interface ChartData {
  labels?: string[];
  datasets: Array<{
    label: string;
    data: number[] | Array<{ x: number; y: number }>;
    backgroundColor?: string;
    borderColor?: string;
  }>;
}

interface Visualization {
  chart_type: 'line' | 'bar' | 'scatter' | 'histogram' | 'profile' | 'map';
  chart_data: ChartData;
  chart_options: Record<string, any>;
}

interface QueryInfo {
  intent: string;
  query_type: string;
  parameters: Record<string, any>;
  sql_query?: string;
}

interface QueryResponse {
  status: 'success' | 'error';
  query_id: string;
  text_response: string;
  numeric_summary: NumericSummary;
  analytics: Analytics;
  visualization: Visualization | null;
  data: Record<string, any>[] | null;
  data_truncated?: boolean;
  total_rows_available?: number;
  query_info: QueryInfo;
  execution_time_ms: number;
  error: string | null;
}

interface SQLPreviewResponse {
  sql: string;
  intent: {
    primary_intent: string;
    query_type: string;
    parameters: Record<string, any>;
  };
  valid: boolean;
}

interface SampleCategory {
  category: string;
  queries: string[];
}

interface SamplesResponse {
  samples: SampleCategory[];
}

interface FeedbackRequest {
  query_id: string;
  rating: 1 | 2 | 3 | 4 | 5;
  feedback_text?: string;
  correct_response?: string;
}
```

---

## Error Handling

All error responses follow this format:

```json
{
  "status": "error",
  "error": "Error message description",
  "code": 400
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request - Invalid query or parameters |
| 429 | Too Many Requests - Rate limit exceeded (60/min) |
| 500 | Internal Server Error |

**Rate Limiting:**
- 60 requests per minute per IP
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## CORS Configuration

The backend allows CORS from all origins in development. For production, update `CORS_ALLOWED_ORIGINS` in settings.

---

## Environment Variables

Frontend `.env` file:
```env
VITE_API_URL=http://localhost:8000/api/v1
```

---

## Quick Start Checklist

1. ✅ Backend running at `http://localhost:8000`
2. ✅ Test health endpoint: `GET /api/v1/health/`
3. ✅ Load sample queries: `GET /api/v1/chat/samples/`
4. ✅ Send first query: `POST /api/v1/chat/`
5. ✅ Handle visualization rendering
6. ✅ Implement feedback submission

---

## Support

For issues or questions, check:
- Backend logs: `backend/logs/`
- Health endpoint for system status
- Database statistics in health response
