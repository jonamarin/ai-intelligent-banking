// Small vanilla-JS helpers for the demo UI (Phase 10) — no framework, per
// docs/architecture.md § 15's resolution of the frontend-framework OPEN
// QUESTION (server-rendered Jinja2 + this file only).

async function createCase(transactionId) {
  const res = await fetch("/api/v1/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transaction_id: transactionId }),
  });
  const body = await res.json();
  if (!res.ok) {
    alert("Could not create case: " + (body.error ? body.error.message : res.status));
    return;
  }
  window.location.href = "/analyst/cases/" + encodeURIComponent(body.case_id);
}

function onCreateCaseSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("transaction-id-input");
  const value = input.value.trim();
  if (!value) return false;
  createCase(value);
  return false;
}

async function reviewCase(caseId, action) {
  const reviewerId = document.getElementById("reviewer-id-input")?.value || "ANALYST-DEMO";
  const rationale = document.getElementById("rationale-input")?.value || null;
  const res = await fetch(`/api/v1/cases/${encodeURIComponent(caseId)}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_id: reviewerId, action, rationale }),
  });
  const body = await res.json();
  if (!res.ok) {
    alert("Review failed: " + (body.error ? body.error.message : res.status));
    return;
  }
  window.location.reload();
}
