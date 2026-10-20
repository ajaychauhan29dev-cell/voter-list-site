// GA4 for the Voter List Portal. Loaded async; every call is wrapped so analytics can never break the site.
// PRIVACY: never send voter names, relative names, addresses, serial/ID numbers, phones, emails or login details.
(function () {
  var C = window.GA_CFG || {}; var ID = C.id; var Q = window._tq || [];
  var ok = !!ID; var sent = {}; var errs = 0; var lastView = '';
  function consent() { try { return localStorage.getItem('ga_consent') === 'denied' ? 'denied' : 'granted'; } catch (e) { return 'granted'; } }
  if (ok) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag('consent', 'default', { analytics_storage: consent(), ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
    gtag('js', new Date());
    var cfg = { send_page_view: false, page_location: location.origin + location.pathname, allow_google_signals: false, allow_ad_personalization_signals: false };
    if (C.debug) cfg.debug_mode = true;
    gtag('config', ID, cfg);
    var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(ID);
    s.onerror = function () { ok = false; }; document.head.appendChild(s);
  }
  // Institution keywords: a search term is only sent when it clearly names an institution.
  var KW = /\b(college|colege|collage|school|schoole|inter|int|university|univ|uni|academy|institute|inst|vidyalaya|vidyalay|mahavidyalaya|public|pg|degree|digree|polytechnic|iti|convent|kanya|engineering|eng|engg|management|pharmacy|nursing)\b|कॉलेज|कालिज|स्कूल|विद्यालय|महाविद्यालय|इंटर|पब्लिक|यूनिवर्सिटी|पीजी|डिग्री/i;
  function redact(t) {
    return (t || '').toLowerCase().replace(/[0-9०-९]+/g, '').replace(/[^a-z\u0900-\u097f ]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60);
  }
  function instLike(t, acronymMatch) {
    var r = redact(t); if (!r) return '';
    if (/@|\d{4,}/.test(t)) return '';
    if (KW.test(r)) return r;
    if (acronymMatch && /^[a-z]{2,6}$/.test(r.replace(/ /g, ''))) return r; // e.g. "dps", "iimt" exactly naming an institution
    return '';
  }
  function ev(name, p, key) {
    try {
      if (!ok) return;
      if (key) { if (sent[key]) return; sent[key] = 1; }
      gtag('event', name, p || {});
    } catch (e) {}
  }
  var A = {
    instLike: instLike,
    view: function (v) { if (v === lastView) return; lastView = v; ev('page_view', { page_title: v === 'login' ? 'Login' : 'Voter list', page_location: location.origin + '/' + v, page_path: '/' + v }); },
    login: function (method, success) { ev('login', { method: method, login_status: success ? 'success' : 'fail' }); },
    district: function (name, id) {
      try { if (ok) gtag('set', 'user_properties', { selected_district: name }); } catch (e) {}
      ev('select_district', { district_name: name, district_id: String(id) });
    },
    search: function (d) {
      // d: {q, total, district, instMatch(bool), acronym(bool), page}
      var term = d.instMatch ? instLike(d.q, d.acronym) : '';
      var p = { search_type: term ? 'institution' : 'voter', result_count: d.total, has_results: d.total > 0, district_name: d.district };
      if (term) p.search_term = term;
      var k = 's:' + d.district + ':' + redact(d.q) + ':' + d.total;
      ev(d.total > 0 ? 'view_search_results' : 'search_no_results', p, k);
    },
    filter: function (inst, district, n) {
      var name = instLike(inst, true);
      ev('filter_institution', { institution_name: name || 'other', has_filter: !!inst, result_count: n, district_name: district });
    },
    page: function (n, dir, district) { ev('page_change', { page_number: n, direction: dir, district_name: district }); },
    geo: function (district, state, acc) {
      try { if (ok) gtag('set', 'user_properties', { geo_district: district }); } catch (e) {}
      ev('location_shared', { geo_district: district, geo_state: state, accuracy_bucket: acc }, 'geo');
    },
    geoNo: function (kind) { ev(kind === 'denied' ? 'location_denied' : 'location_dismissed', {}, 'geono'); },
    upload: function (status, size, district) { ev('file_upload', { upload_status: status, file_size_kb: Math.round((size || 0) / 1024), district_name: district }); },
    error: function (type, detail) {
      if (errs >= 10) return; errs++;
      var d = String(detail || '').replace(/[0-9]+/g, 'N').replace(/\S+@\S+/g, '[email]').slice(0, 90);
      ev('app_error', { error_type: type, error_detail: d }, 'e:' + type + d);
    },
    consent: function (v) { try { localStorage.setItem('ga_consent', v); if (ok) gtag('consent', 'update', { analytics_storage: v }); } catch (e) {} }
  };
  window.GA = A;
  window.addEventListener('error', function (e) { A.error('js_error', (e.message || '') + ' @' + String(e.filename || '').split('/').pop() + ':' + (e.lineno || 0)); });
  window.addEventListener('unhandledrejection', function (e) { var r = e.reason; if (r === 0) return; A.error('promise_rejection', r && r.message || String(r)); });
  // replay calls made before this script loaded
  window.track = function (fn) { try { var a = [].slice.call(arguments, 1); A[fn] && A[fn].apply(null, a); } catch (e) {} };
  Q.forEach(function (c) { window.track.apply(null, c); });
})();
