# E-Commerce WhatsApp Automation — API Integration Guide

**Base URL:** `https://jwl-whatsapp-crm.onrender.com`  
**Content-Type:** `application/json`

---

## Authentication Overview

The external software authenticates with the WhatsApp CRM platform using standard **Bearer JWT authentication**:

1. **Step 1:** Call `/api/auth/login` with your assigned `username` and `password` to obtain a short-lived `access_token`.
2. **Step 2:** Pass the token in the `Authorization` header for all subsequent API requests:
   ```http
   Authorization: Bearer <access_token>
   ```

*(Tokens are valid for 30 minutes. If you receive an `HTTP 401 Unauthorized`, simply call `/api/auth/login` again to refresh your token).*

---

## STEP 1: Authenticate (Login)

* **Method:** `POST`
* **Endpoint:** `/api/auth/login`
* **URL:** `https://jwl-whatsapp-crm.onrender.com/api/auth/login`
* **Headers:**
  ```http
  Content-Type: application/json
  ```
* **Request Body:**
  ```json
  {
    "username": "your_assigned_username",
    "password": "your_assigned_password"
  }
  ```
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "username": "your_assigned_username",
    "role": "agent",
    "requires_2fa": false
  }
  ```

---

## STEP 2: Abandoned Cart Webhook

Call this endpoint as soon as a customer enters checkout and provides contact info, but abandons the cart without completing payment. This enrolls the customer into the automated recovery sequence (or scheduled reminder).

* **Method:** `POST`
* **Endpoint:** `/api/webhooks/cart-event`
* **URL:** `https://jwl-whatsapp-crm.onrender.com/api/webhooks/cart-event`
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <access_token>
  ```
* **Request Body:**
  ```json
  {
    "cart_token": "checkout_9876543210_1740000000",
    "customer_phone": "+919876543210",
    "customer_name": "Ramesh Patel",
    "first_name": "Ramesh",
    "cart_value": 750.00,
    "delivery_address": "Satellite, Ahmedabad, Gujarat",
    "items": [
      {
        "item": "Gold Pendant & Chain",
        "quantity": 2,
        "price": 350
      },
      {
        "item": "Khaman Chutney (200g)",
        "quantity": 1,
        "price": 50
      }
    ],
    "extra_data": {
      "checkout_url": "https://jwl-billion.com/checkout?token=checkout_9876543210_1740000000",
      "platform": "store"
    }
  }
  ```

### Field Specifications:
| Field | Type | Required | Description |
|---|---|---|---|
| `cart_token` | String | **Yes** | Unique identifier for this cart/checkout session. |
| `customer_phone` | String | **Yes** | Phone number with country code (e.g. `+919876543210` or `9876543210`). Normalized to E.164 automatically. |
| `customer_name` / `first_name` | String | No | Used for template variable personalization `{{1}}`. |
| `cart_value` | Float | No | Total cart value in INR (e.g., `750.00`). |
| `items` | Array | No | Array of objects detailing items in the cart. |
| `delivery_address` | String | No | Shipping or delivery address. |
| `extra_data` | Object | No | Custom attributes (e.g. `checkout_url`). |

* **Success Response (HTTP 202 Accepted):**
  ```json
  {
    "status": "received",
    "cart_event_id": 105,
    "workflow_session_id": 42,
    "message": "Multi-step journey enrolled (Session #42)"
  }
  ```

---

## STEP 3: Order Completed / Purchased Webhook

Call this endpoint **immediately** when an order is placed and payment succeeds.

### Why this is essential:
1. Marks the cart as **`RECOVERED`**.
2. **Cancels any pending abandoned cart messages** immediately so customers never receive recovery messages or discounts for orders they already paid for.
3. Automatically updates customer lifetime order statistics (`total_orders += 1`).

* **Method:** `POST`
* **Endpoint:** `/api/webhooks/order-completed`
* **URL:** `https://jwl-whatsapp-crm.onrender.com/api/webhooks/order-completed`
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <access_token>
  ```
* **Request Body:**
  ```json
  {
    "cart_token": "checkout_9876543210_1740000000",
    "customer_phone": "+919876543210"
  }
  ```
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "status": "success",
    "message": "Cart checkout_9876543210_1740000000 marked as RECOVERED. Recovery message cancelled.",
    "milestone": null,
    "total_orders": 3
  }
  ```

---

## STEP 4: Client Information APIs

### 4A. Search / Lookup Client Information
Retrieve existing customer record, order history, tags, city, and custom attributes:

* **Method:** `GET`
* **Endpoint:** `/api/contacts?search=+919876543210`
* **URL:** `https://jwl-whatsapp-crm.onrender.com/api/contacts?search=%2B919876543210`
* **Headers:**
  ```http
  Authorization: Bearer <access_token>
  ```
* **Success Response (HTTP 200 OK):**
  ```json
  [
    {
      "id": 18,
      "phone": "+919876543210",
      "name": "Ramesh Patel",
      "email": "ramesh@example.com",
      "city": "Ahmedabad",
      "tags": "VIP, Gold Necklace Fan",
      "total_orders": 3,
      "last_order_date": "2026-09-24T18:30:00",
      "is_active": true,
      "custom_attributes": {
        "favorite_item": "Gold Necklace"
      }
    }
  ]
  ```

---

### 4B. Push / Sync Customer Details (Create or Update)
Push newly registered customers or update profile data:

* **Method:** `POST`
* **Endpoint:** `/api/webhooks/customer-sync`
* **URL:** `https://jwl-whatsapp-crm.onrender.com/api/webhooks/customer-sync`
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <access_token>
  ```
* **Request Body:**
  ```json
  {
    "phone": "+919876543210",
    "name": "Ramesh Patel",
    "email": "ramesh@example.com",
    "city": "Ahmedabad",
    "tags": "Wholesale, Regular",
    "total_orders": 4,
    "last_order_date": "2026-09-25T14:00:00Z"
  }
  ```
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "status": "success",
    "action": "updated",
    "contact": {
      "id": 18,
      "phone": "+919876543210",
      "name": "Ramesh Patel",
      "total_orders": 4
    }
  }
  ```

---

## Integration Lifecycle Diagram

```
       [Customer enters checkout]
                   │
                   ▼
       [Customer abandons cart]
                   │
                   ├──▶ POST /api/webhooks/cart-event (Initiates recovery)
                   │
                   ▼
       [Customer completes payment]
                   │
                   └──▶ POST /api/webhooks/order-completed (Cancels recovery, marks RECOVERED)
```

---

## HTTP Response Codes Reference

| Code | Status | Meaning |
|---|---|---|
| `200` / `202` | OK / Accepted | Request successfully processed. |
| `400` | Bad Request | Missing required parameters (`cart_token` or invalid `customer_phone`). |
| `401` | Unauthorized | Missing or expired Bearer token. Re-run `/api/auth/login`. |
| `429` | Too Many Requests | Rate limit exceeded. Back off and retry. |
