# Subscribe

Receive RegLag by email.

RegLag publishes a daily financial regulatory briefing.
Subscribing means you’ll receive the full text of each published briefing by email, delivered at the same time it appears on the site.

There are no promotions, tracking, or marketing emails.
You can unsubscribe at any time.

<form id="subscribe-form">
  <label for="email"><strong>Email address</strong></label><br />
  <input
    id="email"
    name="email"
    type="email"
    autocomplete="email"
    required
    style="width:100%;max-width:420px;padding:10px;font-size:16px;margin-top:6px;"
  />

  <!-- Honeypot (hidden) -->
  <input
    type="text"
    name="company"
    tabindex="-1"
    autocomplete="off"
    style="position:absolute; left:-9999px; height:1px; width:1px;"
    aria-hidden="true"
  />

  <div style="margin-top:12px;">
    <button type="submit" style="padding:10px 14px;font-size:16px;">Subscribe</button>
  </div>

  <p id="msg" style="margin-top:12px;"></p>
</form>

<p><em>Unsubscribe anytime.</em></p>

<script>
(() => {
  const form = document.getElementById("subscribe-form");
  const msg = document.getElementById("msg");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "Submitting…";

    const fd = new FormData(form);
    const email = (fd.get("email") || "").toString().trim();
    const company = (fd.get("company") || "").toString().trim();

    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        msg.textContent = data.error || "Unable to subscribe right now. Please try again later.";
        return;
      }

      msg.textContent = "Subscribed.";
      form.reset();
    } catch {
      msg.textContent = "Network error. Please try again later.";
    }
  });
})();
</script>
