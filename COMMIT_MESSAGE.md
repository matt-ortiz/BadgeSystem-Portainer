Fix: Resolve API authentication and "<!DOCTYPE" JSON parsing errors

Root Cause:
After moving to new server, API endpoints were intermittently redirecting to login page 
instead of returning JSON data, causing frontend JavaScript to receive HTML and fail 
with "Unexpected token '<', '<!DOCTYPE'..." errors.

Backend Changes (main.py):
- Enhanced session management with 8-hour timeouts and remember cookies
- New API authentication decorator @api_auth_required() returns JSON instead of redirects  
- Updated /api/AMAG/badging and /api/AMAG/badging_date routes with proper error handling
- Added /api/auth/status endpoint for frontend authentication checking
- Added /admin/clear-cache route and automatic cache clearing on login
- Improved login route with permanent sessions and remember functionality

Frontend Changes:
- dashboard.html: Enhanced updateList() with proper error handling and auth checks
- activity.html: Updated DataTables AJAX calls to handle authentication errors
- Both templates: Added checks for HTML responses and automatic redirects

Technical Details:
- API endpoints now return {"error": "message", "redirect": "/login"} instead of HTTP 302
- Frontend checks response content-type and handles unexpected HTML responses  
- Session persistence improved with proper cookie configuration
- Cache clearing prevents stale authentication state

Fixes intermittent authentication failures and eliminates "<!DOCTYPE" parsing errors.
