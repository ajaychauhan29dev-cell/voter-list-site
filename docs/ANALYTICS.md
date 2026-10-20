# Google Analytics 4 – Voter List Portal

## Summary
GA4 (property "Voter List Site", stream 16168972608, Measurement ID `G-H222BYZLFJ`) is loaded asynchronously on the production site only. The site is a single-page app, so page views are sent manually (one per view change, no duplicates). Custom events cover login, district selection, search, institution filter, paging, the institution-name language toggle, admin uploads and errors. **No voter personal data is ever sent** (see Privacy).

## Files
| File | Purpose |
|---|---|
| `app/app.py` | `/ga.js` route: injects `window.GA_CFG` (ID + debug flag) in front of `static/analytics.js` |
| `app/static/analytics.js` | Consent mode, async gtag loader, safe event helpers, PII redaction, error capture |
| `app/static/app.js` | Calls `track(...)` at each user action |
| `app/static/index.html` | Tiny inline queue stub, `<script src="/ga.js" async>`, analytics notice |
| `app/static/style.css` | Notice styles |

## Configuration (env vars on Render)
| Var | Default | Effect |
|---|---|---|
| `GA_MEASUREMENT_ID` | unset | If set, used everywhere except localhost. If unset, `G-H222BYZLFJ` is used **only** when the host is `voter-list-site.onrender.com`. |
| `GA_DEBUG` | unset | `1` adds `debug_mode: true` so events show in GA4 DebugView. |
| `GA_DISABLED` | unset | Any value turns analytics off. |
Localhost / 127.0.0.1 / `*.local` never load GA. Failures (blocked script, ad blocker, errors) are swallowed: the site works the same without GA.

## Events
All names are snake_case. `district_name` is the district the user **picked in the dropdown**; it is never a claim about where the visitor is.

| Event | When | Parameters |
|---|---|---|
| `page_view` | Login screen or voter-list screen shown (once per change) | `page_title`, `page_path` (`/login`, `/app`), `page_location` (no query string) |
| `login` | Guest button or admin login attempt | `method` (`guest`/`admin`), `login_status` (`success`/`fail`). No email/password. |
| `select_district` | User picks a district | `district_name`, `district_id`; also sets user property `selected_district` |
| `view_search_results` | Search with ≥1 result (page 1, after typing settles 1.2 s, deduped per term) | `search_type` (`institution`/`voter`), `result_count`, `has_results`, `district_name`, `search_term` (institution searches only, redacted) |
| `search_no_results` | Search with 0 results | same as above |
| `filter_institution` | Institution chosen/cleared in the School/Institution dropdown (once per distinct pick; re-picking the same one does not re-send) | `institution_name` (institution as in the data, lowercased, digits/punctuation removed; person-name-looking entries → `other`; cleared → `(all)`), `has_filter`, `result_count`, `district_name`, `district_id`; sets user properties `selected_institution`, `selected_institution_district` |
| `page_change` | Next / Prev | `page_number`, `direction`, `district_name` |
| `location_shared` | User clicked **Share** on the optional location prompt and the browser gave a position | `geo_district` (UP district or `unknown`), `geo_state` (`Uttar Pradesh` or `unknown`), `accuracy_bucket` (`<100m`, `100m-1km`, `1-10km`, `>10km`); sets user property `geo_district` |
| `tour_language` | Language picked in the guided tour's first question | `tour_lang` (`en`/`hi`) |
| `tour_start` | Guided tour starts (first visit after login, or "?" replay) | `step` |
| `tour_complete` | User finished the last step | `step` |
| `tour_skip` | Skip / ✕ / Esc | `step` (0 = on the language question) |
| `location_denied` | User clicked Share but blocked/failed the browser permission | – |
| `location_dismissed` | User clicked "No thanks" on the prompt | – |
| `file_upload` | Admin PDF upload (started / finished / error / fail) | `upload_status`, `file_size_kb`, `district_name` (no file name) |
| `app_error` | JS error, unhandled promise rejection, failed district/voter API call (max 10 per page load, deduped) | `error_type`, `error_detail` (digits → N, emails removed, ≤90 chars) |

The institution-name EN/हिंदी toggle was removed (names show as in the source data; Hindi search still matches), so `institution_lang_toggle` is no longer sent. Not applicable today: `language_toggle` (the UI is always bilingual; there is no UI-language switch – the event name is reserved for it), `file_download` (the site has no downloads – add `file_download` with `file_type` if a download/export is added), search result clicks (rows are not clickable).

User properties: `selected_district`, `geo_district`, `selected_institution`, `selected_institution_district`. (Register as custom dimensions.)

## Optional location share
After login a small bilingual prompt ("अपना स्थान साझा करें · Share your location…") appears once. The browser permission is requested only when the user clicks **Share**; the answer is remembered in localStorage (`geo_asked`) and the prompt is never shown if analytics consent was declined. The browser sends lat/lng rounded to 3 decimals (~100 m) to `POST /api/geo` on our own server, which finds the district by point-in-polygon against the bundled offline file `app/up_districts.json` (75 UP districts, simplified from udit-001/india-maps-data). Coordinates are not stored, logged or sent to GA or any third party; only the district/state name and an accuracy bucket go to GA. Points outside UP or failed lookups give `unknown`. Note: the boundary file's upstream repo has no explicit licence; replace it with a licensed source (e.g. Survey of India / DataMeet) if that matters.

## Privacy / PII rules
Never sent: voter names, relative names, addresses, serial numbers, EPIC/ID numbers, phone numbers, emails, passwords or the admin ID.
- `search_term` is only sent when the search matches an institution in the chosen district **and** contains an institution word (college, school, inter, PG, university, कॉलेज, स्कूल, विद्यालय …) or is an exact institution acronym (e.g. `dps`). Digits and punctuation are removed and it is truncated to 60 chars. Everything else (name, address, number searches) sends only `search_type: voter`, `result_count`, `has_results`.
- `institution_name` uses the same rule (some institution entries in the data are person names; those are sent as `other`).
- `page_location` never includes query strings. Google signals and ad personalisation are off; ad storage consent is denied.

## Consent (India DPDP Act 2023)
Analytics here collects no personal data of voters, but GA sets cookies/identifiers for visitors, so a short bilingual notice is shown on first visit with **OK** and **Decline**. Consent mode v2: `analytics_storage` is `granted` by default (notice-based), `ad_storage`, `ad_user_data`, `ad_personalization` are always `denied`. **Decline** stores `ga_consent=denied` in localStorage and calls `gtag('consent','update',{analytics_storage:'denied'})` (GA then only sends cookieless pings). This is a pragmatic notice approach; have counsel review if the site starts collecting user accounts or targets regulated processing.

## GA4 setup (one-time, in GA Admin)
1. Admin → Custom definitions → Create custom dimensions (event scope): `district_name`, `search_type`, `institution_name`, `login_status`, `method`, `direction`, `upload_status`, `error_type`, `error_detail`; `geo_district`, `geo_state`, `accuracy_bucket`, `tour_lang`, `step`; `district_id`; user scope: `selected_district`, `geo_district`, `selected_institution`, `selected_institution_district`. Metrics: `result_count`, `page_number`, `file_size_kb`.
2. Admin → Data streams → Enhanced measurement: keep Page views on but turn **off** "Page changes based on browser history events" (we send page_view manually) and "Site search" (we send our own redacted event).
3. Admin → Data retention → 14 months.
4. Mark `login` as a key event if useful.

## Reports and Explorations
- **Users by geography**: Reports → User → Demographics → Demographic details → Country / Region (state) / City. GA geography is from IP and approximate.
- **District interest**: Explore → Free form; rows `district_name` (or user dim `selected_district`), values Event count, Total users; filter Event name = `select_district`.
- **Search**: Free form; rows `search_term`, columns `search_type`; values Event count; filter Event name in (`view_search_results`,`search_no_results`). The no-results table shows missing institutions / OCR issues.
- **Funnel**: Explore → Funnel: `page_view` (/login) → `login` → `select_district` → `view_search_results` or `page_change`.
- **Guest vs admin**: Free form, rows `method`, filter `login`, breakdown `login_status`.
- **Errors**: Free form, rows `error_type`, `error_detail`, event `app_error`.

### Institutions by district
Explore → Free form: rows `institution_name`, then `district_name`; values Event count, Total users; filter Event name = `filter_institution` and `institution_name` ≠ `(all)`. For a per-user view use the user dimensions `selected_institution` / `selected_institution_district`.

## Looker Studio
1. lookerstudio.google.com → Create → Report → Add data → Google Analytics → account → "Voter List Site".
2. Page 1 "Overview": scorecards Active users, Sessions, Event count; time series Active users by Date; geo map Region (India).
3. Page 2 "Districts": table Dimension `district_name` (custom dim appears after step 1 above, up to 24–48 h), Metric Event count, filter Event name = `select_district`; bar chart same.
4. Page 3 "Search": table `search_term`, `search_type`, Event count; filter Event name contains `search`; second table for `search_no_results`.
5. Add a date-range control and a `district_name` drop-down filter control. Share as view-only.

## Limitations
- District = what users choose, not where they are. Visitor location comes only from GA's IP geography (country/state/city), which is approximate and often shows the ISP's city.
- Ad blockers / declined consent reduce counts; cookieless pings are modelled only on large properties.
- Custom dimensions only populate from the date they are created; not retroactive.
- Search terms are deliberately incomplete (voter searches are not recorded).

## Validation checklist
- [ ] `https://voter-list-site.onrender.com/ga.js` contains `"id": "G-H222BYZLFJ"`; on localhost it has `"id": ""`.
- [ ] Network tab: `googletagmanager.com/gtag/js` loads async; `…/g/collect?…tid=G-H222BYZLFJ` requests fire.
- [ ] `en=page_view` on load, `en=login` with `ep.method=guest`, `en=select_district` with `ep.district_name`, `en=page_change`, `en=filter_institution`, `en=location_shared` with `ep.geo_district` after clicking Share (no `lat`/`lng` anywhere), `en=view_search_results`/`search_no_results`.
- [ ] No voter name, address, serial, email or password appears in any collect URL/body.
- [ ] Set `GA_DEBUG=1` on Render, redeploy, open Admin → DebugView and walk through the flow; then remove it.
- [ ] Decline in the notice → later requests carry `gcs=G100`/`gcd` denied; the site still works.
- [ ] Block googletagmanager.com (ad blocker) → site works normally.

## Recommendations
- Create the custom dimensions now so data accrues.
- Use the `search_no_results` report to find institutions with OCR/spelling issues.
- Add `file_download` if an export is added; add `select_content` if result rows become clickable.
- Review the event list quarterly; keep the PII rules when adding events.
