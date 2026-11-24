let currentCity = "Guntur, India";
let currentAqi = 165;
let latestPlan = null;

// Initialize Leaflet Map centered on Guntur
const map = L.map("city-map", { zoomControl: false }).setView([16.3067, 80.4365], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
}).addTo(map);
let cityMarker = L.circleMarker([16.3067, 80.4365], {
  radius: 14,
  color: "#ef4444",
  fillColor: "#ef4444",
  fillOpacity: 0.45,
}).addTo(map);

function classifyAqi(aqi) {
  if (aqi <= 50) return { label: "Good", cls: "good", color: "#10b981" };
  if (aqi <= 150) return { label: "Moderate", cls: "moderate", color: "#f59e0b" };
  return { label: "Unhealthy", cls: "unhealthy", color: "#ef4444" };
}

function updateAqiDisplay(aqi) {
  currentAqi = Math.max(10, Math.min(500, Number(aqi) || 100));
  const info = classifyAqi(currentAqi);

  document.getElementById("aqi-number").textContent = currentAqi;
  document.getElementById("aqi-slider").value = Math.min(450, currentAqi);

  const pill = document.getElementById("aqi-status-pill");
  pill.textContent = info.label;
  pill.className = `status-tag ${info.cls}`;

  const mapBadge = document.getElementById("map-badge");
  mapBadge.textContent = `AQI ${currentAqi}`;
  mapBadge.className = `status-tag ${info.cls}`;

  cityMarker.setStyle({ color: info.color, fillColor: info.color });
}

function getSelectedProfile() {
  const getChips = (group) =>
    Array.from(document.querySelectorAll(`.chip-grid[data-group="${group}"] .chip.active`)).map(
      (btn) => btn.dataset.val
    );
  const members = getChips("members").join(", ") || "General Household";
  const commute = getChips("commute").join(", ") || "Daily Commute";
  const indoor = getChips("indoor").join(", ") || "Standard Home";
  return {
    routine: `Household: ${members}; Primary Commute: ${commute}`,
    home_setup: indoor,
  };
}

async function loadCityTelemetry(cityName) {
  try {
    const res = await fetch(`/api/live-aqi?city=${encodeURIComponent(cityName)}`);
    if (!res.ok) return;
    const data = await res.json();

    currentCity = data.city;
    document.getElementById("banner-city").textContent = data.city;
    document.getElementById("aqi-city-label").textContent = data.city.split(",")[0].toUpperCase();
    document.getElementById("banner-temp").textContent = data.temp_c;
    document.getElementById("pm25-val").textContent = data.pm2_5;
    document.getElementById("pm10-val").textContent = data.pm10;
    document.getElementById("no2-val").textContent = data.no2;
    document.getElementById("o3-val").textContent = data.o3;
    document.getElementById("map-coords").textContent = `${data.lat.toFixed(2)}°N, ${data.lon.toFixed(2)}°E`;

    const skyBanner = document.getElementById("sky-banner");
    const kicker = document.getElementById("sky-kicker");
    if (data.is_day) {
      skyBanner.className = "sky-banner day-sky";
      kicker.textContent = "☀️ DAYTIME ATMOSPHERIC TELEMETRY";
    } else {
      skyBanner.className = "sky-banner night-sky";
      kicker.textContent = "🌙 NIGHTTIME ATMOSPHERIC TELEMETRY";
    }

    const hourlyStrip = document.getElementById("hourly-strip");
    hourlyStrip.innerHTML = (data.forecast || [])
      .map((f) => `<div class="hour-item"><span>${f.time}</span><strong>${f.temp}°</strong></div>`)
      .join("");

    map.setView([data.lat, data.lon], 11);
    cityMarker.setLatLng([data.lat, data.lon]);
    updateAqiDisplay(data.aqi);
  } catch (e) {
    console.warn("Telemetry fallback:", e);
  }
}

async function generatePlan() {
  const btn = document.getElementById("update-plan-btn");
  btn.disabled = true;
  btn.textContent = "⏳ Updating AI Plan...";

  const profile = getSelectedProfile();
  try {
    const res = await fetch("/api/generate-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        city: currentCity,
        aqi: currentAqi,
        routine: profile.routine,
        home_setup: profile.home_setup,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Plan generation error");

    const plan = data.plan;
    latestPlan = { city: currentCity, aqi: currentAqi, plan };

    document.getElementById("risk-summary").textContent = plan.risk_summary;
    document.getElementById("bio-dose-val").innerHTML = `${plan.inhaled_bio_dose_ug || 22} <small>µg/day</small>`;
    document.getElementById("safe-window-val").textContent = plan.safest_window || "12:30 PM – 4:00 PM";
    document.getElementById("prevented-val").innerHTML = `-${plan.exposure_prevented_ug || 18} <small>µg/day</small>`;

    document.getElementById("time-routines-list").innerHTML = (plan.time_routines || [])
      .map(
        (r) => `
        <article class="slot-card">
          <span class="slot-time">${r.slot}</span>
          <h4>${r.title}</h4>
          <p>${r.action} — <em>Why: ${r.why}</em></p>
        </article>`
      )
      .join("");

    document.getElementById("hacks-list").innerHTML = (plan.indoor_air_hacks || [])
      .map((h) => `<li><strong>${h.title}:</strong> ${h.action} <em>(${h.benefit})</em></li>`)
      .join("");

    document.getElementById("alternatives-list").innerHTML = (plan.sustainable_alternatives || [])
      .map(
        (a) => `
        <div class="alt-item">
          <div class="alt-top"><strong>${a.title}</strong><span>${a.impact}</span></div>
          <p>${a.action}</p>
        </div>`
      )
      .join("");
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ Update Personalized Plan";
  }
}

// Event Listeners
document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const city = document.getElementById("city-input").value.trim();
  if (!city) return;
  document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
  await loadCityTelemetry(city);
  await generatePlan();
});

document.querySelectorAll(".pill").forEach((pill) => {
  pill.addEventListener("click", async () => {
    document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    const city = pill.dataset.city;
    document.getElementById("city-input").value = city;
    await loadCityTelemetry(city);
    await generatePlan();
  });
});

document.querySelectorAll(".chip-grid").forEach((grid) => {
  grid.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    if (grid.dataset.group === "members") {
      chip.classList.toggle("active");
    } else {
      grid.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
    }
  });
});

document.getElementById("aqi-slider").addEventListener("input", (e) => {
  updateAqiDisplay(e.target.value);
});

document.getElementById("update-plan-btn").addEventListener("click", generatePlan);

document.getElementById("copy-brief-btn").addEventListener("click", () => {
  if (!latestPlan) return;
  const { city, aqi, plan } = latestPlan;
  const text = `AeroGuard AI Brief — ${city} (AQI ${aqi})\n${plan.risk_summary}\nSafest Outdoor Window: ${plan.safest_window}`;
  navigator.clipboard.writeText(text);
  const btn = document.getElementById("copy-brief-btn");
  btn.textContent = "✅ Copied!";
  setTimeout(() => (btn.textContent = "📋 Copy Family Air Brief"), 2000);
});

// Initial Boot
(async () => {
  await loadCityTelemetry("Guntur");
  await generatePlan();
})();