const map = L.map("map", {
  zoomControl: true,
}).setView([41.015, 28.96], 14);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

let routeLayer = null;
let poiLayer = L.layerGroup().addTo(map);
let startMarker = null;

const form = document.querySelector("#route-form");
const statusEl = document.querySelector("#status");
const generateButton = document.querySelector("#generate-button");
const routeDistanceEl = document.querySelector("#route-distance");
const routeFitEl = document.querySelector("#route-fit");
const selectedPoisEl = document.querySelector("#selected-pois");
const poiGroupsEl = document.querySelector("#poi-groups");

function refreshMapSize() {
  window.requestAnimationFrame(() => {
    map.invalidateSize();
  });
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function checkedPoiPreferences() {
  const preferences = {};
  poiGroupsEl.querySelectorAll("input[type='checkbox']").forEach((input) => {
    preferences[input.value] = input.checked ? 1 : 0;
  });
  return preferences;
}

function selectedAlgorithm() {
  return form.querySelector("input[name='routing_algorithm']:checked").value;
}

function buildPayload() {
  return {
    start_lat: Number(document.querySelector("#start-lat").value),
    start_lon: Number(document.querySelector("#start-lon").value),
    min_distance_km: Number(document.querySelector("#min-distance").value),
    max_distance_km: Number(document.querySelector("#max-distance").value),
    poi_preferences: checkedPoiPreferences(),
    routing_algorithm: selectedAlgorithm(),
    elevation_preference: "none",
  };
}

function drawRoute(data) {
  refreshMapSize();
  const latLngs = data.route.coordinates.map((point) => [point.lat, point.lon]);

  if (routeLayer) {
    map.removeLayer(routeLayer);
  }
  if (startMarker) {
    map.removeLayer(startMarker);
  }
  poiLayer.clearLayers();

  routeLayer = L.polyline(latLngs, {
    color: "#177245",
    weight: 6,
    opacity: 0.9,
    lineJoin: "round",
  }).addTo(map);

  startMarker = L.circleMarker([data.start.lat, data.start.lon], {
    radius: 8,
    color: "#17211b",
    fillColor: "#ffffff",
    fillOpacity: 1,
    weight: 3,
  })
    .bindPopup("Start")
    .addTo(map);

  data.selected_pois.forEach((poi, index) => {
    L.marker([poi.lat, poi.lon])
      .bindPopup(`<strong>${index + 1}. ${poi.name}</strong><br>${poi.poi_group}`)
      .addTo(poiLayer);
  });

  map.fitBounds(routeLayer.getBounds().pad(0.18));
}

function renderSummary(data) {
  routeDistanceEl.textContent = `${data.route.total_length_km.toFixed(2)} km`;
  routeFitEl.textContent = data.route.within_target_range
    ? "Inside requested range"
    : `${Math.round(data.route.distance_error_m)} m from target`;

  selectedPoisEl.innerHTML = "";
  data.selected_pois.forEach((poi) => {
    const item = document.createElement("li");
    item.innerHTML = `${poi.name}<span>${poi.poi_group}</span>`;
    selectedPoisEl.appendChild(item);
  });
}

async function loadPoiGroups() {
  try {
    const response = await fetch("/api/poi-groups");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    if (!Array.isArray(data.groups) || data.groups.length === 0) {
      return;
    }

    const preferred = new Set(["museum_historic", "park_garden", "viewpoint_attraction", "food"]);
    poiGroupsEl.innerHTML = "";

    data.groups.forEach((group) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = group;
      input.checked = preferred.has(group);
      label.appendChild(input);
      label.append(` ${group.replaceAll("_", " ")}`);
      poiGroupsEl.appendChild(label);
    });
    refreshMapSize();
  } catch {
    setStatus("Could not load POI groups. Using defaults.", true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  generateButton.disabled = true;
  setStatus("Generating route...");

  try {
    const response = await fetch("/api/routes/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildPayload()),
    });

    const responseText = await response.text();
    let data = null;
    try {
      data = responseText ? JSON.parse(responseText) : null;
    } catch {
      throw new Error(responseText || "Route generation failed.");
    }

    if (!response.ok) {
      throw new Error(data?.detail || "Route generation failed.");
    }

    drawRoute(data);
    renderSummary(data);
    setStatus(
      `Evaluated ${data.metrics.permutations_evaluated} route orders from ${data.metrics.candidate_count} candidate POIs.`
    );
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    generateButton.disabled = false;
  }
});

loadPoiGroups();
window.addEventListener("load", refreshMapSize);
window.addEventListener("resize", refreshMapSize);
setTimeout(refreshMapSize, 250);
