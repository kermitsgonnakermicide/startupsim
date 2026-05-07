# Test Credentials

## Admin / Creator Account
- Username: `admin`
- Password: `SCALEdaddySALLU67`
- isAdmin: true (sees the Admin tab to approve/reject user applications)

## Demo User (grandfathered, approved with 10-day expiry from signup)
- Username: `demo_user`
- Password: `demo123`
- Has 5 RELIANCE holdings from previous trade.

## Approved Pending Applicant (created during testing)
- Username: `newbie1`
- Password: `abc123`
- Status may be `rejected` (was rejected then re-applied; admin can approve again)

## Auth API
- Signup (creates pending account): POST /api/auth/signup body: {username, password, email, reason}
- Login: POST /api/auth/login body: {username, password} → 403 if pending/expired/rejected
- Reapply (when rejected/expired): POST /api/auth/reapply body: {username, password, reason}
- Me: GET /api/auth/me header: Authorization: Bearer <token>

## Admin API (requires admin token)
- GET /api/admin/applications → {pending:[], approved:[], rejected:[], counts}
- POST /api/admin/approve body: {userId}
- POST /api/admin/reject body: {userId}
- POST /api/admin/revoke body: {userId} → resets to pending
- POST /api/admin/leaderboard-visibility body: {userId, hidden}
- POST /api/admin/bulk/reject-pending → reject every pending user
- POST /api/admin/bulk/revoke-approved → revoke every approved user back to pending
- POST /api/admin/bulk/leaderboard-hide-all → hide all non-admins from leaderboard
- POST /api/admin/bulk/leaderboard-show-all → restore visibility for all non-admins

## Watchlist API (auth required)
- GET /api/watchlist → {symbols: [...]}
- POST /api/watchlist body: {symbol} → idempotent add; 400 if symbol unknown
- DELETE /api/watchlist/{symbol} → remove (no error if not present)

## Approval Rules
- New signups: status=pending, login blocked
- Approved users: 10-day window (approvedUntil = approvedAt + 10 days)
- After 10 days: login returns 403 with "expired" message; user can use Reapply tab
- Admin: never expires
