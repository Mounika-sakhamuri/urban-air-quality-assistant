"use strict";

const DEFAULT_COORDS = [16.3067, 80.4365];
const AQI_THRESHOLDS = { GOOD_MAX: 50, MODERATE_MAX: 150 };

let currentCity = "Guntur, India";
let currentAqi = 165;
let latestPlan = null;

const map = L.map("city-map", { zoomControl: false }).setView(DEFAULT_COORDS, 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const cityMarker = L.circleMarker(DEFAULT_COORDS, {
  radius: 14,
  color: "#ef4444",
  fillColor: "#ef4444",
  fillOpacity: 0.45,
}).addTo(map);

function classifyAqi(aqi) {
  if (aqi <= AQI_THRESHOLDS.GOOD_MAX) {
    return { label: "Good", cls: "good", color: "#10b981" };
  }
  if (aqi <= AQI_THRESHOLDS.MODERATE_MAX) {
    return { label: "Moderate", cls: "moderate", color: "#f59e0b" };
  }
  return { label: "Unhealthy", cls: "unhealthy", color: "#ef4444" };
}

function updateAqiDisplay(aqi) {
  currentAqi = Math.max(10, Math.min(500, Number(aqi) || 100));
  const info = classifyAqi(currentAqi);

  document.getElementById("aqi-number").textContent = String(currentAqi);
  document.getElementById("aqi-slider").value = String(Math.min(450, currentAqi));

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

function renderHourlyForecast(forecastList) {
  const strip = document.getElementById("hourly-strip");
  strip.replaceChildren();

  (forecastList || []).forEach((point) => {
    const item = document.createElement("div");
    item.className = "hour-item";

    const timeEl = document.createElement("span");
    timeEl.textContent = String(point.time);

    const tempEl = document.createElement("strong");
    tempEl.textContent = `${point.temp}°`;

    item.append(timeEl, tempEl);
    strip.appendChild(item);
  });
}

function renderTimeRoutines(routines) {
  const list = document.getElementById("time-routines-list");
  list.replaceChildren();

  (routines || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = "slot-card";

    const slotEl = document.createElement("span");
    slotEl.className = "slot-time";
    slotEl.textContent = item.slot;

    const titleEl = document.createElement("h4");
    titleEl.textContent = item.title;

    const descEl = document.createElement("p");
    descEl.textContent = `${item.action} — Why: ${item.why}`;

    card.append(slotEl, titleEl, descEl);
    list.appendChild(card);
  });
}

function renderIndoorHacks(hacks) {
  const list = document.getElementById("hacks-list");
  list.replaceChildren();

  (hacks || []).forEach((hack) => {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = `${hack.title}: `;
    li.append(strong, document.createTextNode(`${hack.action} (${hack.benefit})`));
    list.appendChild(li);
  });
}

function renderSustainableAlternatives(alternatives) {
  const list = document.getElementById("alternatives-list");
  list.replaceChildren();

  (alternatives || []).forEach((alt) => {
    const box = document.createElement("div");
    box.className = "alt-item";

    const top = document.createElement("div");
    top.className = "alt-top";

    const title = document.createElement("strong");
    title.textContent = alt.title;

    const impact = document.createElement("span");
    impact.textContent = alt.impact;

    top.append(title, impact);

    const desc = document.createElement("p");
    desc.textContent = alt.action;

    box.append(top, desc);
    list.appendChild(box);
  });
}

async function loadCityTelemetry(cityName) {
  try {
    const res = await fetch(`/api/live-aqi?city=${encodeURIComponent(cityName)}`);
    if (!res.ok) return;
    const data = await res.json();

    currentCity = data.city;
    document.getElementById("banner-city").textContent = data.city;
    document.getElementById("aqi-city-label").textContent = data.city.split(",")[0].toUpperCase();
    document.getElementById("banner-temp").textContent = String(data.temp_c);
    document.getElementById("pm25-val").textContent = String(data.pm2_5);
    document.getElementById("pm10-val").textContent = String(data.pm10);
    document.getElementById("no2-val").textContent = String(data.no2);
    document.getElementById("o3-val").textContent = String(data.o3);
    document.getElementById("map-coords").textContent = `${data.lat.toFixed(2)}°N, ${data.lon.toFixed(2)}°E`;

    const skyBanner = document.getElementById("sky-banner");
    const kicker = document.getElementById("sky-kicker");
    skyBanner.className = data.is_day ? "sky-banner day-sky" : "sky-banner night-sky";
    kicker.textContent = data.is_day
      ? "☀️ DAYTIME ATMOSPHERIC TELEMETRY"
      : "🌙 NIGHTTIME ATMOSPHERIC TELEMETRY";

    renderHourlyForecast(data.forecast);
    map.setView([data.lat, data.lon], 11);
    cityMarker.setLatLng([data.lat, data.lon]);
    updateAqiDisplay(data.aqi);
  } catch (err) {
    console.warn("Telemetry fallback:", err);
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
    document.getElementById("bio-dose-val").textContent = `${plan.inhaled_bio_dose_ug || 22} µg/day`;
    document.getElementById("safe-window-val").textContent = plan.safest_window || "12:30 PM – 4:00 PM";
    document.getElementById("prevented-val").textContent = `-${plan.exposure_prevented_ug || 18} µg/day`;

    renderTimeRoutines(plan.time_routines);
    renderIndoorHacks(plan.indoor_air_hacks);
    renderSustainableAlternatives(plan.sustainable_alternatives);
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ Update Personalized Plan";
  }
}

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

document.getElementById("copy-brief-btn").addEventListener("click", async () => {
  if (!latestPlan) return;
  const { city, aqi, plan } = latestPlan;
  const text = `AeroGuard AI Brief — ${city} (AQI ${aqi})\n${plan.risk_summary}\nSafest Outdoor Window: ${plan.safest_window}`;
  await navigator.clipboard.writeText(text);
  const btn = document.getElementById("copy-brief-btn");
  btn.textContent = "✅ Copied!";
  setTimeout(() => {
    btn.textContent = "📋 Copy Family Air Brief";
  }, 2000);
});

(async () => {
  await loadCityTelemetry("Guntur");
  await generatePlan();
})();