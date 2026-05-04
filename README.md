# Qatar Foundation — Admin Portal Backend

A Flask + SQLite backend for the Qatar Foundation Admin Portal.

## Project Structure

```
qatar_admin/
├── app.py               ← Flask application & all API routes
├── requirements.txt
├── README.md
├── instance/
│   └── qatar.db         ← SQLite database (auto-created on first run)
├── static/
│   ├── admin.css        ← Original UI stylesheet (unchanged)
│   └── admin.js         ← Frontend JS (updated to call Flask APIs)
└── templates/
    └── index.html       ← Original admin UI (paths updated, hardcoded
                           opportunity cards removed as per US-2.1)
```

## Setup & Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
python app.py
```

The app starts at **http://localhost:5000**

The SQLite database is created automatically at `instance/qatar.db` on first run.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/me` | Check current session |
| POST | `/api/signup` | Register new admin |
| POST | `/api/login` | Login (supports Remember Me) |
| POST | `/api/logout` | Logout |
| POST | `/api/forgot-password` | Request password reset link (logged to console) |
| GET | `/api/reset-password?token=` | Validate reset token |
| POST | `/api/reset-password` | Reset password with token |
| GET | `/api/opportunities` | Get all opportunities for logged-in admin |
| POST | `/api/opportunities` | Create a new opportunity |
| PUT | `/api/opportunities/<id>` | Edit an opportunity |
| DELETE | `/api/opportunities/<id>` | Delete an opportunity |

## User Stories Implemented

### Task 1 — Login & Signup
- **US-1.1** Admin Sign Up — full name, email, password, confirm password; validates format & duplicates
- **US-1.2** Admin Login — email + password; remember me; generic error message
- **US-1.3** Forgot Password — always shows same message; reset token logged to console; expires in 1 hour

### Task 2 — Opportunity Management
- **US-2.1** View All Opportunities — loads from DB; empty state shown when none exist
- **US-2.2** Add New Opportunity — modal form with validation; saved to DB; card appears without refresh
- **US-2.3** Opportunities Persist — stored in SQLite; loaded fresh on each login
- **US-2.4** View Opportunity Details — details modal with all saved fields
- **US-2.5** Edit an Opportunity — Edit button pre-fills form; updates DB; card updates without refresh
- **US-2.6** Delete an Opportunity — Delete button with confirmation; removed from DB and UI immediately

## Notes

- Password reset links are printed to the **server console** (no email sending needed at this stage).
- Each admin can only see, edit, and delete their own opportunities.
- Session persists for 30 days when "Remember Me" is checked, or ends on browser close otherwise.
