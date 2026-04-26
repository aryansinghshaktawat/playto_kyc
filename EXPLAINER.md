# Playto KYC System – Explainer

## 1. State Machine

The state machine is implemented inside the `KYCSubmission` model.

I created two methods:

* `can_transition(new_status)` → checks if transition is allowed
* `transition_to(new_status)` → applies transition or raises error

All valid transitions are defined in one place:

* draft → submitted
* submitted → under_review
* under_review → approved / rejected / more_info_requested
* more_info_requested → submitted

This ensures:

* No illegal transitions happen
* Business logic is centralized in the model (not scattered in views)

If an invalid transition is attempted, the system raises an error and returns HTTP 400.

---

## 2. File Upload Validation

The system supports uploading:

* PAN document
* Aadhaar document
* Bank statement

Validation is handled in the backend (not trusting frontend):

* Allowed file types: PDF, JPG, JPEG, PNG
* Max file size: 5MB

If invalid file is uploaded:

* The API returns a clear validation error

If a user uploads a 50MB file:

* It is rejected immediately by backend validation

---

## 3. Reviewer Queue

Reviewer dashboard uses:

* `order_by('created_at')`

This ensures:

* Oldest submissions appear first
* Matches real-world review queue behavior

---

## 4. SLA Tracking

SLA is implemented dynamically using time comparison.

A submission is marked `is_at_risk = true` if:

* Status is `submitted` or `under_review`
* It was created more than 24 hours ago

This is NOT stored in database to avoid stale data.

---

## 5. Authorization

Authorization is implemented using Django's built-in user system:

* Reviewer → `is_staff = True`
* Merchant → `is_staff = False`

Access control:

* Reviewer → can see all submissions
* Merchant → can only see their own submissions
* GET requests are temporarily public for demo purposes

This is enforced in `get_queryset()` in the ViewSet.

---

## 6. Notifications

A notification system logs events when state changes.

Each event stores:

* merchant_id
* event_type
* timestamp
* payload (new status)

This allows tracking of important system actions.

---

## 7. Error Format

API errors are normalized into a simple format:

* `{ "error": "message" }`

This keeps validation and business-rule failures easy to consume from the frontend.

---

## 8. AI Audit

While using AI tools, I encountered cases where:

* State transition logic was incomplete
* Validation was missing or incorrect

I manually reviewed and fixed:

* Centralized state machine logic
* Proper backend validation for files
* Correct authorization filtering

This ensured the system is secure and logically consistent.
