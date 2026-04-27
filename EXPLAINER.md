# KYC Submission & Review System

##  Overview

This project implements a **production-ready KYC (Know Your Customer) workflow system** using Django and Django REST Framework.

It is designed to simulate a real-world onboarding pipeline where merchants submit KYC details and reviewers process them through a controlled lifecycle.

---

##  Key Design Principles

* **State Machine Driven Workflow**
* **Role-Based Access Control**
* **Secure File Handling**
* **Scalable API Design**
* **Audit & Notification System**

---

##  KYC Lifecycle (State Machine)

The system enforces strict transitions:

```
Draft → Submitted → Under Review → Approved / Rejected
                          ↓
                  More Info Requested → Submitted
```

###  Allowed Transitions

| From                | To                                        |
| ------------------- | ----------------------------------------- |
| Draft               | Submitted                                 |
| Submitted           | Under Review                              |
| Under Review        | Approved / Rejected / More Info Requested |
| More Info Requested | Submitted                                 |

###  Invalid transitions are blocked at model level

This ensures:

* Data integrity
* No illegal state jumps
* Predictable workflow

---

## 👥 Roles & Permissions

###  Merchant

* Create KYC submission
* Upload required documents
* Submit KYC

###  Reviewer (Admin/Staff)

* View review queue
* Approve / Reject submissions
* Request additional information

###  Enforcement

* Merchants can only access their own data
* Review actions restricted to staff users

---

##  File Upload Handling

* Supported formats: **PDF, JPG, PNG**
* Max file size: **5MB**
* Validation includes:

  * Extension check
  * File size limit
* Files stored per merchant:

```
kyc_documents/<merchant_id>/
```

---

## ⏱ SLA Monitoring

Each submission is monitored for processing delay.

* SLA threshold: **24 hours**
* Submissions in `submitted` or `under_review`:

  * Marked `is_at_risk = true` if delayed

This helps identify bottlenecks in processing.

---

##  Reviewer Queue

Dedicated endpoint:

```
GET /api/v1/kyc/reviewer_queue/
```

* Returns submissions requiring action
* Sorted by creation time (FIFO)

---

##  Notification System

Every status change generates a notification:

```json
{
  "event_type": "status_changed",
  "from": "submitted",
  "to": "approved"
}
```

This enables:

* Audit trails
* Event tracking
* Future integrations (email/webhooks)

---

##  API Endpoints

### Merchant Actions

* `POST /api/v1/kyc/` → Create submission
* `POST /api/v1/kyc/{id}/submit/` → Submit KYC

---

### Reviewer Actions

* `POST /api/v1/kyc/{id}/approve/`
* `POST /api/v1/kyc/{id}/reject/`
* `POST /api/v1/kyc/{id}/request_info/`

---

### System Endpoints

* `GET /api/v1/kyc/reviewer_queue/`
* `GET /api/v1/kyc/at_risk/`

---

##  Technical Decisions

###  State Machine at Model Level

* Prevents bypass via API or admin
* Ensures business rules are always enforced

###  Atomic Transactions

* Guarantees consistency during create/update

###  Query Optimization

* Uses `select_related` for efficient joins

###  Separation of Concerns

* Models → Business logic
* Views → API control
* Serializers → Data validation

---

##  Challenges Faced

* Handling file uploads safely on limited storage (Render free tier)
* Preventing unauthorized status changes
* Designing a flexible but strict workflow system

---

##  Future Improvements

* JWT Authentication (instead of session-based)
* Cloud storage integration (AWS S3 / GCP)
* Async processing (Celery)
* Email/SMS notification system
* Reviewer assignment strategies (load balancing)

---

##  Conclusion

This system demonstrates:

* Real-world backend design
* Workflow enforcement using state machines
* Secure and scalable API architecture

It is structured to be **production-ready and extensible**.
