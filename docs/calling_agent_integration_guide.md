# Secure Digital DMS — Calling Agent Integration Guide

This document defines the production API integration contract between the **Spring Boot DMS backend** and the **Calling Agent API** (part of the standalone AI Services API).

---

## 1. Architecture Overview

```
Spring Boot DMS Backend
        |
        | (1) Detect user activity — send to Monitoring
        v
POST /api/v1/monitoring/analyze
        |
        | (2) Monitoring returns deterministic risk assessment
        v
Spring Boot receives: risk_score, risk_level, requires_calling_agent, ...
        |
        | (3) Spring Boot decides whether to invoke Calling Agent
        |     (checks: requires_calling_agent == true)
        |
        v
POST /api/v1/agent/call
        |
        +-------> SMS  (Twilio)
        |
        +-------> Email  (SMTP)
        |
        +-------> Voice Call  (Twilio Programmable Voice + DTMF)
                        |
                        v
               POST /api/v1/agent/voice/status  (telephony webhook)
```

### Strict Architectural Boundaries

| Rule | Description |
|---|---|
| **Monitoring does NOT call Calling Agent** | Monitoring only evaluates the current activity and returns a risk assessment. |
| **Spring Boot owns the decision** | Spring Boot checks `requires_calling_agent` and decides whether to invoke the Calling Agent. |
| **Spring Boot owns officer contacts** | Officer phone, email, and identity are stored in the Spring Boot DMS. The AI Services API receives them as part of the Calling Agent request. |
| **Calling Agent does NOT classify incidents** | The Calling Agent only executes the notification channels it is instructed to use. It does not independently evaluate risk or make security decisions. |
| **Independent AI Services** | Face Recognition, Semantic Search, Monitoring, and Calling Agent are all independent services in this API. None calls another. |

---

## 2. Base URL

```
http://<AI-SERVICE-HOST>:8000
```

For Docker Compose:
```
http://ai-services:8000
```

---

## 3. Authentication

All protected endpoints require:

```http
X-API-Key: <YOUR_AI_SERVICES_API_KEY>
```

> **Security Note**: Never embed real API keys in source code, documentation examples, or version control. Use environment variables (e.g., `AI_SERVICES_API_KEY` in `application.properties` or Spring Boot secrets).

---

## 4. Monitoring API

### `POST /api/v1/monitoring/analyze`

Spring Boot sends the current user activity. Monitoring returns a deterministic risk assessment.

#### Request Headers

```http
POST /api/v1/monitoring/analyze HTTP/1.1
Host: <AI-SERVICE-HOST>:8000
Content-Type: application/json
X-API-Key: <YOUR_API_KEY>
```

#### Request Payload (`CurrentActivityRequest`)

```json
{
  "user_id": "USR-1024",
  "case_id": "CASE-2026-001",
  "document_id": "DOC-4582",
  "activity_type": "DOCUMENT_DELETE",
  "action": "DELETE",
  "timestamp": "2026-09-19T10:30:00+05:30",
  "source_ip": "10.0.0.25",
  "user_agent": "SpringBoot-DMS/2.0",
  "authentication_status": "SUCCESS",
  "permission_status": "DENIED",
  "document_sensitivity": "HIGHLY_CONFIDENTIAL",
  "access_type": "DELETE",
  "metadata": {
    "department": "investigation",
    "application": "dms-backend"
  }
}
```

**Key Request Fields:**

| Field | Type | Required | Accepted Values |
|---|---|---|---|
| `activity_type` | Enum | **Required** | `LOGIN`, `DOCUMENT_ACCESS`, `DOCUMENT_VIEW`, `DOCUMENT_DOWNLOAD`, `DOCUMENT_UPLOAD`, `DOCUMENT_UPDATE`, `DOCUMENT_DELETE`, `CASE_ACCESS`, `SEARCH`, `FACE_VERIFICATION`, `PERMISSION_CHECK` |
| `authentication_status` | Enum | Optional | `SUCCESS`, `FAILED`, `NOT_APPLICABLE` |
| `permission_status` | Enum | Optional | `ALLOWED`, `DENIED`, `NOT_APPLICABLE` |
| `document_sensitivity` | Enum | Optional | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `HIGHLY_CONFIDENTIAL` |
| `access_type` | Enum | Optional | `READ`, `WRITE`, `DOWNLOAD`, `DELETE`, `SHARE` |

#### Response Payload (`RiskAnalysisResponse`)

```json
{
  "success": true,
  "user_id": "USR-1024",
  "risk_score": 92,
  "risk_level": "CRITICAL",
  "suspicious": true,
  "threat_type": "SUSPICIOUS_DELETE",
  "confidence": 0.95,
  "reasons": [
    {
      "code": "UNAUTHORIZED_DELETE_ATTEMPT",
      "message": "Delete attempted on a highly confidential document with DENIED permission.",
      "severity": "CRITICAL",
      "contribution": 50
    }
  ],
  "recommended_action": "BLOCK_AND_ALERT",
  "requires_calling_agent": true,
  "anomaly": {
    "available": false,
    "anomaly_score": 0.0,
    "is_anomalous": false
  }
}
```

**Key Response Fields Spring Boot Must Use:**

| Field | Type | Description |
|---|---|---|
| `risk_score` | Integer `[0–100]` | Calculated risk score |
| `risk_level` | Enum | `LOW` (0–24), `MEDIUM` (25–49), `HIGH` (50–74), `CRITICAL` (75–100) |
| `suspicious` | Boolean | `true` when `risk_level` is `HIGH` or `CRITICAL` |
| `threat_type` | Enum | Categorized threat classification |
| `recommended_action` | Enum | `ALLOW`, `MONITOR`, `REVIEW`, `TRIGGER_ALERT`, `BLOCK_AND_ALERT` |
| `requires_calling_agent` | Boolean | **Spring Boot checks this to decide whether to invoke the Calling Agent** |

---

## 5. Calling Agent API

### `POST /api/v1/agent/call`

Spring Boot sends the Monitoring risk assessment plus officer contact information. The Calling Agent dispatches notifications and returns channel statuses.

#### Request Headers

```http
POST /api/v1/agent/call HTTP/1.1
Host: <AI-SERVICE-HOST>:8000
Content-Type: application/json
X-API-Key: <YOUR_API_KEY>
```

#### Request Payload (`CallAgentRequest`)

```json
{
  "incident": {
    "incident_id": "INC-2026-00125",
    "user_id": "USR-1024",
    "case_id": "CASE-2026-001",
    "document_id": "DOC-4582",
    "risk_score": 92,
    "risk_level": "CRITICAL",
    "suspicious": true,
    "threat_type": "SUSPICIOUS_DELETE",
    "confidence": 0.95,
    "recommended_action": "BLOCK_AND_ALERT",
    "requires_calling_agent": true,
    "reasons": [
      {
        "code": "UNAUTHORIZED_DELETE_ATTEMPT",
        "message": "Delete attempted on a highly confidential document with DENIED permission.",
        "severity": "CRITICAL"
      }
    ]
  },
  "officer": {
    "officer_id": "OFF-1024",
    "name": "Officer Name",
    "phone": "+919876543210",
    "email": "officer@example.gov.in"
  },
  "notification": {
    "sms": true,
    "email": true,
    "voice_call": true,
    "simulation": false
  }
}
```

**`incident` Field Validation:**

| Field | Type | Validation |
|---|---|---|
| `incident_id` | String | Required, non-empty |
| `user_id` | String | Required, non-empty |
| `case_id` | String | Required, non-empty |
| `risk_score` | Integer | Required, `[0–100]` |
| `risk_level` | Enum | Required: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `confidence` | Float | Required, `[0.0–1.0]` |
| `recommended_action` | Enum | Required: `ALLOW`, `MONITOR`, `REVIEW`, `TRIGGER_ALERT`, `BLOCK_AND_ALERT` |
| `reasons` | Array | Required, at least 1 entry |

**`officer` Field Validation:**

| Field | Type | Validation |
|---|---|---|
| `officer_id` | String | Required, non-empty |
| `name` | String | Required, non-empty |
| `phone` | String | Required, international phone format |
| `email` | String | Required, valid email address |

**`notification` Channels:**

| Field | Type | Description |
|---|---|---|
| `sms` | Boolean | Send SMS alert to officer |
| `email` | Boolean | Send email alert to officer |
| `voice_call` | Boolean | Place AI voice call to officer |
| `simulation` | Boolean | `true` = simulate all channels without real calls (for SIH demo / testing) |

> **At least one channel** (`sms`, `email`, or `voice_call`) must be `true`. The request will return `422` otherwise.

#### Response Payload (`CallAgentResponse`)

```json
{
  "success": true,
  "incident_id": "INC-2026-00125",
  "mode": "PRODUCTION",
  "message": "Incident notification processed in production mode.",
  "overall_status": "SUCCESS",
  "channels": {
    "sms": {
      "requested": true,
      "status": "SENT",
      "message": null
    },
    "email": {
      "requested": true,
      "status": "SENT",
      "message": null
    },
    "voice_call": {
      "requested": true,
      "status": "INITIATED",
      "message": "Voice call initiated (SID: CA123456789)"
    }
  },
  "channels_requested": {
    "sms": true,
    "email": true,
    "voice_call": true,
    "simulation": false
  }
}
```

**`overall_status` Values:**

| Status | Meaning |
|---|---|
| `SIMULATED` | All channels simulated (simulation mode) |
| `SUCCESS` | All requested channels succeeded |
| `PARTIAL_FAILURE` | Some channels succeeded, some failed |
| `FAILED` | All requested channels failed |
| `DISABLED` | All requested channels are disabled (e.g., `VOICE_AGENT_ENABLED=false`) |

**`channels[].status` Values:**

| Status | Meaning |
|---|---|
| `SIMULATED` | Channel simulated, no real call made |
| `SENT` | SMS or email successfully sent |
| `INITIATED` | Voice call successfully placed with telephony provider |
| `ANSWERED` | Voice call was answered |
| `ACKNOWLEDGED` | Officer acknowledged the incident via DTMF keypad |
| `FAILED` | Channel dispatch failed (exception caught safely) |
| `CONFIGURATION_ERROR` | Provider credentials/configuration missing |
| `DISABLED` | Provider disabled via environment variable |
| `NOT_REQUESTED` | Channel was not requested in `notification` |
| `NOT_IMPLEMENTED` | Feature not yet implemented |

---

## 6. Voice Status Webhook API

### `POST /api/v1/agent/voice/status`

Receives telephony status updates and DTMF keypad inputs from the Twilio webhook. Spring Boot does not need to call this endpoint — it is called by the telephony provider.

#### Request Payload (`VoiceWebhookRequest`)

```json
{
  "incident_id": "INC-2026-00125",
  "call_sid": "CA1234567890abcdef",
  "call_status": "in-progress",
  "digits": "1",
  "officer_id": "OFF-1024"
}
```

**DTMF Keypad Interactions:**

| Digit | Action |
|---|---|
| `1` | Officer acknowledges the incident |
| `2` | Repeat the incident summary |
| `3` | Officer declines / ends call |

#### Response Payload (`VoiceWebhookResponse`)

```json
{
  "success": true,
  "incident_id": "INC-2026-00125",
  "call_status": "in-progress",
  "conversation_state": "ACKNOWLEDGED",
  "acknowledged": true,
  "acknowledged_by": "OFF-1024"
}
```

---

## 7. End-to-End Integration Flow

### Step-by-Step: Critical Incident → Calling Agent Notification

```
STEP 1 — Spring Boot Detects Suspicious Activity
=========================================================
Spring Boot DMS detects a suspicious DELETE on a HIGHLY_CONFIDENTIAL document.

Spring Boot sends:
POST /api/v1/monitoring/analyze
{
  "user_id": "USR-1024",
  "case_id": "CASE-2026-001",
  "document_id": "DOC-4582",
  "activity_type": "DOCUMENT_DELETE",
  "permission_status": "DENIED",
  "document_sensitivity": "HIGHLY_CONFIDENTIAL"
}


STEP 2 — Monitoring Evaluates
=========================================================
Monitoring applies deterministic domain rules.
No external calls. No LLM. Pure CPU evaluation.
Latency: < 5ms.


STEP 3 — Monitoring Returns Risk Assessment
=========================================================
{
  "risk_score": 92,
  "risk_level": "CRITICAL",
  "suspicious": true,
  "threat_type": "SUSPICIOUS_DELETE",
  "recommended_action": "BLOCK_AND_ALERT",
  "requires_calling_agent": true
}


STEP 4 — Spring Boot Checks Decision Signal
=========================================================
if (monitoringResponse.requiresCallingAgent) {
    // Build Calling Agent request
}


STEP 5 — Spring Boot Builds Calling Agent Request
=========================================================
Spring Boot retrieves officer contact details from its own database.
Spring Boot constructs:

POST /api/v1/agent/call
{
  "incident": {
    "incident_id": "INC-2026-00125",   // Spring Boot generates this
    "user_id": "USR-1024",
    "case_id": "CASE-2026-001",
    "document_id": "DOC-4582",
    "risk_score": 92,                   // From Monitoring response
    "risk_level": "CRITICAL",           // From Monitoring response
    "suspicious": true,
    "threat_type": "SUSPICIOUS_DELETE",
    "confidence": 0.95,
    "recommended_action": "BLOCK_AND_ALERT",
    "requires_calling_agent": true,
    "reasons": [ ... ]                  // From Monitoring response
  },
  "officer": {
    "officer_id": "OFF-1024",           // From Spring Boot officer database
    "name": "Officer Name",
    "phone": "+919876543210",
    "email": "officer@example.gov.in"
  },
  "notification": {
    "sms": true,
    "email": true,
    "voice_call": true,
    "simulation": false
  }
}


STEP 6 — Calling Agent Dispatches Notifications
=========================================================
Calling Agent concurrently dispatches:
  - SMS via Twilio
  - Email via SMTP
  - Voice call via Twilio Programmable Voice


STEP 7 — Calling Agent Returns Channel Statuses
=========================================================
{
  "success": true,
  "incident_id": "INC-2026-00125",
  "mode": "PRODUCTION",
  "overall_status": "SUCCESS",
  "channels": {
    "sms": { "requested": true, "status": "SENT" },
    "email": { "requested": true, "status": "SENT" },
    "voice_call": { "requested": true, "status": "INITIATED", "message": "Voice call initiated (SID: CA123)" }
  }
}


STEP 8 — Spring Boot Records the Result
=========================================================
Spring Boot updates the incident record with notification statuses.
Spring Boot may poll or receive webhook updates for voice acknowledgement.
```

---

## 8. SIH Demo / Testing: Simulation Mode

Set `simulation: true` in the `notification` object to simulate all channels without making any real network calls. Useful for demo, development, and automated testing.

```json
"notification": {
  "sms": true,
  "email": true,
  "voice_call": true,
  "simulation": true
}
```

Expected response:

```json
{
  "mode": "SIMULATION",
  "overall_status": "SIMULATED",
  "channels": {
    "sms": { "requested": true, "status": "SIMULATED" },
    "email": { "requested": true, "status": "SIMULATED" },
    "voice_call": { "requested": true, "status": "SIMULATED" }
  }
}
```

---

## 9. Error Contract

| HTTP Status | Condition |
|---|---|
| `200 OK` | Request processed (check `success`, `overall_status`, and individual `channels[].status` for failures) |
| `401 Unauthorized` | Missing or invalid `X-API-Key` header |
| `422 Unprocessable Entity` | Validation failure (invalid `risk_level`, bad `email`, `risk_score` out of range, no channels selected, etc.) |
| `500 Internal Server Error` | Server error (stack traces are suppressed; channel-level failures return `200` with `status: FAILED`) |

---

## 10. Security & Privacy Guarantees

- **No Secret Exposure**: The Calling Agent API never returns officer phone numbers, officer emails, Twilio credentials, SMTP passwords, API keys, or provider secrets in any response body or log.
- **No Face Embeddings**: Face recognition biometric data is never included in Calling Agent requests or responses.
- **No Raw Document Content**: Document contents are never transmitted through the Calling Agent.
- **Credential Isolation**: Twilio Account SID, Auth Token, SMTP credentials, and all provider secrets are loaded from environment variables only. They are never logged or echoed in responses.
- **Authentication Required**: All endpoints require `X-API-Key` header authentication.

---

## 11. Environment Configuration Reference

```bash
# AI Services API
AI_SERVICES_API_KEY=<your_shared_secret_key>

# Twilio SMS (Task 8C)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<twilio_auth_token>
TWILIO_FROM_NUMBER=+1XXXXXXXXXX

# SMTP Email (Task 8C)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=notifications@example.gov.in
SMTP_PASSWORD=<smtp_password>
SMTP_FROM_EMAIL=notifications@example.gov.in
SMTP_USE_TLS=true

# Voice Agent (Task 8D)
VOICE_AGENT_ENABLED=false        # Set to true for production voice calls
VOICE_TWIML_URL=                 # Optional: external TwiML webhook URL
```

> All defaults are safe: voice calling is disabled by default (`VOICE_AGENT_ENABLED=false`). Missing provider credentials result in `CONFIGURATION_ERROR` channel status — not an application crash.

---

## 12. Swagger / OpenAPI Documentation

Interactive API documentation is available at:

```
GET http://<AI-SERVICE-HOST>:8000/docs
```

OpenAPI JSON schema:

```
GET http://<AI-SERVICE-HOST>:8000/openapi.json
```

All protected endpoints are documented with `ApiKeyAuth` security scheme.
