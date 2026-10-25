/* groq-shim.js - sends Verity's Groq calls to the server-side proxy when the page
   only holds the public placeholder key. A visitor's own key (typed into AI settings)
   is left alone and still goes straight to Groq. Loaded before app.js. */
(function () {
  var PLACEHOLDER = "gsk_proxy_placeholder";
  var TARGET = "https://api.groq.com/openai/v1/chat/completions";
  var orig = window.fetch;
  if (!orig) return;
  window.fetch = function (input, init) {
    try {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf(TARGET) === 0 && init && init.headers) {
        var h = init.headers, auth = "", out = {}, k;
        for (k in h) {
          if (Object.prototype.hasOwnProperty.call(h, k)) {
            if (k.toLowerCase() === "authorization") auth = String(h[k]); else out[k] = h[k];
          }
        }
        if (auth.indexOf(PLACEHOLDER) >= 0) {
          var next = {}; for (k in init) next[k] = init[k];
          next.headers = out;
          return orig.call(this, "/api/groq", next);
        }
      }
    } catch (e) { /* fall through to the normal fetch */ }
    return orig.apply(this, arguments);
  };
})();
