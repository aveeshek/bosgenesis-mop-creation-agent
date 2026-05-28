# MoP: Deploy payments-api v2.4.1 to Production

---

## Document Header

| Field | Value |
|---|---|
| **MoP Title** | Deploy payments-api v2.4.1 to Production Kubernetes Cluster |
| **MoP ID** | MOP-2024-0087 |
| **Version** | 1.0 |
| **Author** | Jane Smith (Platform SRE) |
| **Reviewed By** | Bob Lee (Tech Lead), Alice Chen (QA) |
| **Change Ticket** | CHG-4421 |
| **Change Window** | Wednesday, 2026-05-20, 02:00–04:00 UTC |
| **Estimated Duration** | 45 minutes |
| **Risk Level** | Medium |
| **Rollback Time** | ~10 minutes |
| **Rollback Approver** | Bob Lee (on-call) |

---

## Change Summary

**What:** Upgrade `payments-api` from `v2.3.9` to `v2.4.1` in the `payments` namespace on the `prod-us-east-1` cluster.

**Why:** v2.4.1 includes a fix for payment timeout handling (BUG-8821) and adds Stripe webhook retry support.

**Impact:** Zero-downtime rolling deployment. No schema migrations. No config changes.

---

## Pre-change Checklist

Before starting, confirm all items are checked:

- [ ] Change ticket CHG-4421 is approved
- [ ] On-call engineer (Bob Lee) is available on Slack (`#sre-oncall`)
- [ ] PagerDuty alert suppression window is set (02:00–04:00 UTC)
- [ ] Image `registry.internal.io/payments-api:v2.4.1` is available in the registry
- [ ] QA has signed off on staging deployment (STAG-2024-0087)
- [ ] Rollback approver confirmed

---

## 1. Access & Environment Verification

**Step 1.1 — Set correct cluster context**

```bash
kubectl config use-context prod-us-east-1
kubectl config current-context
```

**Expected output:**
```
prod-us-east-1
```

> ⚠️ **STOP** if context is not `prod-us-east-1`. Do not proceed.

---

**Step 1.2 — Verify namespace and current deployment state**

```bash
kubectl get namespace payments
kubectl get deployment payments-api -n payments
kubectl get pods -n payments
```

**Expected output:**
```
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
payments-api   3/3     3            3           42d
```

> ⚠️ **STOP** if fewer than 3/3 pods are ready. Investigate before proceeding.

---

**Step 1.3 — Record current image version**

```bash
kubectl get deployment payments-api -n payments \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**Expected output:**
```
registry.internal.io/payments-api:v2.3.9
```

> 📝 Note this value — it is the rollback target.

---

**Step 1.4 — Confirm new image is accessible**

```bash
docker pull registry.internal.io/payments-api:v2.4.1
```

**Expected output:**
```
v2.4.1: Pulling from payments-api
...
Status: Image is up to date for registry.internal.io/payments-api:v2.4.1
```

> ⚠️ **STOP** if image pull fails. Contact the registry team before proceeding.

---

**Step 1.5 — Check cluster resource headroom**

```bash
kubectl describe nodes | grep -A5 "Allocated resources"
```

> ✅ Ensure CPU and memory are not above 80% allocated on any node.

---

## 2. Pre-change Backup

**Step 2.1 — Export current deployment manifest**

```bash
kubectl get deployment payments-api -n payments -o yaml \
  > ~/backups/payments-api-backup-$(date +%F-%H%M).yaml
```

**Step 2.2 — Export current HPA config**

```bash
kubectl get hpa payments-api -n payments -o yaml \
  > ~/backups/payments-api-hpa-backup-$(date +%F-%H%M).yaml
```

> 📝 Confirm files exist before proceeding:
> ```bash
> ls -lh ~/backups/payments-api-backup-*.yaml
> ```

---

## 3. Stakeholder Notification

**Step 3.1 — Notify in Slack**

Post in `#deployments`:
```
[STARTING] MOP-2024-0087 — payments-api v2.3.9 → v2.4.1
Cluster: prod-us-east-1 | Namespace: payments
Change window: 02:00–04:00 UTC
Rollback approver: @bob.lee
```

---

## 4. Deployment Execution

**Step 4.1 — Apply the new image**

```bash
kubectl set image deployment/payments-api \
  payments-api=registry.internal.io/payments-api:v2.4.1 \
  -n payments
```

**Expected output:**
```
deployment.apps/payments-api image updated
```

---

**Step 4.2 — Monitor the rolling rollout**

```bash
kubectl rollout status deployment/payments-api -n payments --timeout=5m
```

**Expected output:**
```
Waiting for deployment "payments-api" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "payments-api" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "payments-api" rollout to finish: 1 old replicas are pending termination...
deployment "payments-api" successfully rolled out
```

> ⚠️ **STOP and ROLLBACK** if this command times out or returns an error.

---

**Step 4.3 — Watch pod transitions**

```bash
kubectl get pods -n payments -w
```

**Expected state (final):**

```
NAME                            READY   STATUS    RESTARTS   AGE
payments-api-7d9f6b8c4-abc12    1/1     Running   0          2m
payments-api-7d9f6b8c4-def34    1/1     Running   0          90s
payments-api-7d9f6b8c4-ghi56    1/1     Running   0          60s
```

> ⚠️ **STOP and ROLLBACK** if any pod shows `CrashLoopBackOff`, `Error`, or `RESTARTS > 0`.

---

## 5. Validation

**Step 5.1 — Confirm new image is active**

```bash
kubectl get deployment payments-api -n payments \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

**Expected output:**
```
registry.internal.io/payments-api:v2.4.1
```

---

**Step 5.2 — Confirm replica health**

```bash
kubectl get deployment payments-api -n payments
```

**Expected output:**
```
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
payments-api   3/3     3            3           42d
```

---

**Step 5.3 — Check application logs for errors**

```bash
kubectl logs -l app=payments-api -n payments --tail=100 | grep -iE "error|exception|fatal"
```

**Expected output:** No error lines. If errors appear, assess severity before proceeding.

---

**Step 5.4 — Smoke test: health endpoint**

```bash
curl -sf https://payments-api.internal.prod/health | jq .
```

**Expected output:**
```json
{
  "status": "ok",
  "version": "2.4.1",
  "db": "connected"
}
```

---

**Step 5.5 — Smoke test: payment processing (staging payload)**

```bash
curl -sf -X POST https://payments-api.internal.prod/v1/test-transaction \
  -H "Authorization: Bearer $SMOKE_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "currency": "USD", "test": true}' | jq .status
```

**Expected output:**
```json
"success"
```

> ⚠️ **STOP and ROLLBACK** if health check or smoke test fails.

---

## 6. Go / No-Go Decision Points

| # | Checkpoint | Expected Result | Outcome | Action if Failed |
|---|---|---|---|---|
| 1 | Cluster context confirmed | `prod-us-east-1` | ☐ Pass ☐ Fail | STOP — fix context |
| 2 | Namespace and pods healthy | 3/3 READY | ☐ Pass ☐ Fail | STOP — investigate |
| 3 | Image pull successful | Exit 0 | ☐ Pass ☐ Fail | STOP — fix registry |
| 4 | Rollout completed | "successfully rolled out" | ☐ Pass ☐ Fail | ROLLBACK |
| 5 | All pods Running | 3/3, RESTARTS=0 | ☐ Pass ☐ Fail | ROLLBACK |
| 6 | Health endpoint | `{"status":"ok"}` | ☐ Pass ☐ Fail | ROLLBACK |
| 7 | Smoke test | `"success"` | ☐ Pass ☐ Fail | ROLLBACK |

---

## 7. Rollback Procedure

> Trigger rollback if **any** Go/No-Go check fails after deployment begins.

**Step 7.1 — Notify rollback is starting**

Post in `#deployments`:
```
[ROLLBACK STARTING] MOP-2024-0087 — reverting payments-api to v2.3.9
Reason: <describe failure>
```

---

**Step 7.2 — Execute rollback**

```bash
# Option A: Kubernetes native undo
kubectl rollout undo deployment/payments-api -n payments

# Monitor rollback
kubectl rollout status deployment/payments-api -n payments
```

OR

```bash
# Option B: Restore from backup manifest
kubectl apply -f ~/backups/payments-api-backup-<timestamp>.yaml -n payments
```

---

**Step 7.3 — Verify rollback**

```bash
# Confirm image is back to v2.3.9
kubectl get deployment payments-api -n payments \
  -o jsonpath='{.spec.template.spec.containers[0].image}'

# Confirm pods are healthy
kubectl get pods -n payments

# Re-run health check
curl -sf https://payments-api.internal.prod/health | jq .
```

**Expected output:**
```
registry.internal.io/payments-api:v2.3.9
```

---

**Step 7.4 — Notify rollback complete**

Post in `#deployments`:
```
[ROLLBACK COMPLETE] MOP-2024-0087 — payments-api reverted to v2.3.9
Rollback duration: <X> minutes
Follow-up ticket: <link>
```

---

## 8. Post-Change Activities

- [ ] Update CHG-4421 with completion status (Success / Rolled Back)
- [ ] Post final status in `#deployments`
- [ ] Archive backup manifests to shared storage
- [ ] If rolled back: open a follow-up bug ticket and link to CHG-4421
- [ ] If rolled back: schedule post-incident review within 48 hours
- [ ] Update deployment runbook if any steps deviated from this MoP

---

## Execution Log

| Time (UTC) | Step | Operator | Result | Notes |
|---|---|---|---|---|
| 02:00 | Start — context verified | | ☐ | |
| 02:05 | Pre-checks complete | | ☐ | |
| 02:10 | Backup captured | | ☐ | |
| 02:12 | Stakeholders notified | | ☐ | |
| 02:15 | Image applied | | ☐ | |
| 02:20 | Rollout complete | | ☐ | |
| 02:25 | Validation complete | | ☐ | |
| 02:30 | Change closed | | ☐ | |

---

*MoP generated for CHG-4421 | payments-api v2.3.9 → v2.4.1 | prod-us-east-1*
