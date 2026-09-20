# Secure Digital DMS — AI Security Monitoring Integration Guide

This document defines the production API integration contract between the **Spring Boot DMS backend** and the **AI Security Monitoring API**.

---

## 1. Overview & Architecture

- **Endpoint**: `POST /api/v1/monitoring/analyze`
- **Authentication**: `X-API-Key` header (`verify_api_key` dependency)
- **Execution**: Synchronous, deterministic, local rule-based CPU evaluation (`< 5ms` latency).
- **Scope**: Evaluates **ONLY the current user activity** details sent by Spring Boot. Does not require or manage historical activity data.
- **Calling Agent Integration**: The AI Monitoring API returns a recommended flag `requires_calling_agent: boolean`. **The AI Monitoring API does NOT call the Calling Agent.** Spring Boot receives this assessment and decides whether to trigger external agents or workflows.

---

## 2. API Contract

### Request Headers
```http
POST /api/v1/monitoring/analyze HTTP/1.1
Host: ai-services-gateway:8000
Content-Type: application/json
X-API-Key: <YOUR_AI_SERVICES_API_KEY>
```

### Request Payload (`CurrentActivityRequest`)
```json
{
  "user_id": "USR-1024",
  "case_id": "CASE-2026-001",
  "document_id": "DOC-4582",
  "activity_type": "DOCUMENT_DOWNLOAD",
  "action": "DOWNLOAD",
  "timestamp": "2026-09-19T10:30:00+05:30",
  "source_ip": "10.0.0.25",
  "user_agent": "SpringBoot-DMS",
  "authentication_status": "SUCCESS",
  "permission_status": "ALLOWED",
  "document_sensitivity": "CONFIDENTIAL",
  "access_type": "DOWNLOAD",
  "metadata": {
    "department": "investigation",
    "application": "dms-backend"
  }
}
```

### Response Payload (`RiskAnalysisResponse`)
```json
{
  "success": true,
  "user_id": "USR-1024",
  "risk_score": 25,
  "risk_level": "MEDIUM",
  "suspicious": false,
  "threat_type": "SUSPICIOUS_DOCUMENT_ACCESS",
  "confidence": 0.95,
  "reasons": [
    {
      "code": "MEDIUM_HIGH_SENSITIVITY",
      "message": "Activity targets a confidential document.",
      "severity": "MEDIUM",
      "contribution": 10
    },
    {
      "code": "DOWNLOAD_CONFIDENTIAL",
      "message": "Attempted download of a confidential document.",
      "severity": "MEDIUM",
      "contribution": 15
    }
  ],
  "recommended_action": "MONITOR",
  "requires_calling_agent": false,
  "anomaly": {
    "available": false,
    "anomaly_score": 0.0,
    "is_anomalous": false
  }
}
```

---

## 3. Data Field Specifications

### Request Fields (Spring Boot → AI Monitoring)
| Field | Type | Required | Description / Accepted Values |
|---|---|---|---|
| `user_id` | String | Optional | Unique user identifier in DMS |
| `case_id` | String | Optional | Case identifier |
| `document_id` | String | Optional | Target document identifier |
| `activity_type` | Enum | **Required** | `LOGIN`, `DOCUMENT_ACCESS`, `DOCUMENT_VIEW`, `DOCUMENT_DOWNLOAD`, `DOCUMENT_UPLOAD`, `DOCUMENT_UPDATE`, `DOCUMENT_DELETE`, `CASE_ACCESS`, `SEARCH`, `FACE_VERIFICATION`, `PERMISSION_CHECK` |
| `action` | String | Optional | Action label (e.g. `READ`, `WRITE`, `DOWNLOAD`, `DELETE`, `SHARE`) |
| `timestamp` | ISO-8601 | Optional | UTC or offset ISO timestamp (e.g. `2026-09-19T10:30:00Z`) |
| `source_ip` | String | Optional | Client IP address |
| `user_agent` | String | Optional | User agent string |
| `authentication_status` | Enum | Optional | `SUCCESS`, `FAILED`, `NOT_APPLICABLE` (default: `NOT_APPLICABLE`) |
| `permission_status` | Enum | Optional | `ALLOWED`, `DENIED`, `NOT_APPLICABLE` (default: `NOT_APPLICABLE`) |
| `document_sensitivity` | Enum | Optional | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `HIGHLY_CONFIDENTIAL` (default: `INTERNAL`) |
| `access_type` | Enum | Optional | `READ`, `WRITE`, `DOWNLOAD`, `DELETE`, `SHARE` |
| `metadata` | Object | Optional | Key-value dictionary for contextual key-value attributes |

### Response Fields (AI Monitoring → Spring Boot)
| Field | Type | Description |
|---|---|---|
| `success` | Boolean | Always `true` for successful analysis |
| `user_id` | String | Echoes `user_id` provided in request |
| `risk_score` | Integer | Calculated risk score `[0 - 100]` |
| `risk_level` | Enum | `LOW` (0-24), `MEDIUM` (25-49), `HIGH` (50-74), `CRITICAL` (75-100) |
| `suspicious` | Boolean | `true` if `risk_level` is `HIGH` or `CRITICAL` |
| `threat_type` | Enum | `NORMAL_ACTIVITY`, `AUTHENTICATION_FAILURE`, `UNAUTHORIZED_ACCESS`, `SUSPICIOUS_DOCUMENT_ACCESS`, `SENSITIVE_DOCUMENT_ACTION`, `PERMISSION_VIOLATION`, `SUSPICIOUS_DELETE`, `SUSPICIOUS_DOWNLOAD`, `FACE_VERIFICATION_FAILURE`, `POSSIBLE_SECURITY_INCIDENT` |
| `confidence` | Float | Data completeness rating `[0.0 - 1.0]` |
| `reasons` | Array | Array of `RiskReason` objects containing `code`, `message`, `severity`, and `contribution` |
| `recommended_action` | Enum | `ALLOW`, `MONITOR`, `REVIEW`, `TRIGGER_ALERT`, `BLOCK_AND_ALERT` |
| `requires_calling_agent` | Boolean | Recommended flag indicating whether Calling Agent should be invoked |
| `anomaly` | Object | Optional local ML anomaly evaluation (`available`, `anomaly_score`, `is_anomalous`) |

---

## 4. Local ML Anomaly Detection (Optional Signal)

- **Nature**: Local ML anomaly detection is an **optional additive signal** evaluated via a lightweight local `IsolationForest`.
- **Primary Decision Engine**: The deterministic domain rules in `RiskAnalyzer` remain the primary security decision engine. Anomaly detection **NEVER downgrades or overrides** rule-based risk levels or explicit security violations.
- **Score Cap**: When an ML anomaly model is trained and available (`available: true`), an anomalous pattern adds at most **+10** to the score.
- **Non-Probability Indicator**: The `anomaly_score` is a normalized score `[0.0 - 1.0]` indicating relative feature space isolation. **It is NOT a statistical probability or ML confidence percentage.**
- **Model Availability**: If no trained model is supplied, `anomaly.available` is `false`, `anomaly_score` is `0.0`, `is_anomalous` is `false`, and rule-based evaluation proceeds unaffected.
- **Integration Guidance for Spring Boot**: Spring Boot should continue relying on `risk_level`, `recommended_action`, and `requires_calling_agent` as the primary integration decision signals.

---

## 5. Error Contract

| Status Code | Error Code | Description |
|---|---|---|
| `401 Unauthorized` | `UNAUTHORIZED` | Invalid or missing `X-API-Key` header |
| `422 Unprocessable Entity` | `VALIDATION_ERROR` | Missing required fields, invalid enum value, or malformed data type |
| `500 Internal Server Error` | `INTERNAL_SERVER_ERROR` | Server processing error (internal stack traces are suppressed) |

---

## 6. Security & Privacy Guarantees

- **No Secret Exposure**: The API never logs or returns passwords, API keys, bearer tokens, face embeddings, or raw document content.
- **Automatic Sanitization**: All key-value metadata fields matching sensitive names (`password`, `token`, `api_key`, `secret`, `biometric_data`, etc.) are redacted automatically in logs.
- **Stateless Analysis**: The engine operates purely on the current activity payload provided by Spring Boot.
