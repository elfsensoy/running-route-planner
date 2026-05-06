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
let endMarker = null;
let selectionMode = null;

const categoryColors = {
  food: "#d95f02",
  museum_historic: "#6a3d9a",
  park_garden: "#1b9e77",
  viewpoint_attraction: "#1f78b4",
};
const defaultCategoryColor = "#7570b3";

const form = document.querySelector("#route-form");
const statusEl = document.querySelector("#status");
const generateButton = document.querySelector("#generate-button");
const currentLocationButton = document.querySelector("#current-location-button");
const pickStartButton = document.querySelector("#pick-start-button");
const pickFinalButton = document.querySelector("#pick-final-button");
const routeDistanceEl = document.querySelector("#route-distance");
const routeFitEl = document.querySelector("#route-fit");
const selectedPoisEl = document.querySelector("#selected-pois");
const poiGroupsEl = document.querySelector("#poi-groups");
const loopRouteInput = document.querySelector("#loop-route");
const useFinalPointInput = document.querySelector("#use-final-point");
const finalPointFields = document.querySelector("#final-point-fields");
const startLatInput = document.querySelector("#start-lat");
const startLonInput = document.querySelector("#start-lon");
const endLatInput = document.querySelector("#end-lat");
const endLonInput = document.querySelector("#end-lon");

function colorForGroup(group) {
  return categoryColors[group] || defaultCategoryColor;
}

function poiIcon(group, index) {
  const color = colorForGroup(group);
  return L.divIcon({
    className: "",
    html: `<div class="poi-marker" style="background:${color}">${index}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  });
}

function refreshMapSize() {
  window.requestAnimationFrame(() => {
    map.invalidateSize();
  });
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function setSelectionMode(mode) {
  selectionMode = selectionMode === mode ? null : mode;
  pickStartButton.classList.toggle("active", selectionMode === "start");
  pickFinalButton.classList.toggle("active", selectionMode === "final");

  if (selectionMode === "start") {
    setStatus("Click the map to set the start point.");
  } else if (selectionMode === "final") {
    setStatus("Click the map to set the final point.");
  } else {
    setStatus("Ready");
  }
}

function setStartMarker(lat, lon) {
  if (startMarker) {
    map.removeLayer(startMarker);
  }
  startMarker = L.circleMarker([lat, lon], {
    radius: 8,
    color: "#17211b",
    fillColor: "#ffffff",
    fillOpacity: 1,
    weight: 3,
  })
    .bindPopup("Start")
    .addTo(map);
}

function setEndMarker(lat, lon) {
  if (endMarker) {
    map.removeLayer(endMarker);
  }
  endMarker = L.circleMarker([lat, lon], {
    radius: 8,
    color: "#b45c16",
    fillColor: "#ffffff",
    fillOpacity: 1,
    weight: 3,
  })
    .bindPopup("Final point")
    .addTo(map);
}

function checkedPoiPreferences() {
  const preferences = {};
  poiGroupsEl.querySelectorAll("input[type='number']").forEach((input) => {
    const value = Math.max(0, Math.min(10, Number(input.value || 0)));
    input.value = value;
    preferences[input.dataset.group] = value;
  });
  return preferences;
}

function selectedAlgorithm() {
  return form.querySelector("input[name='routing_algorithm']:checked").value;
}

function buildPayload() {
  const useFinalPoint = useFinalPointInput.checked && !loopRouteInput.checked;
  const poiPreferences = checkedPoiPreferences();
  const totalPois = Object.values(poiPreferences).reduce((sum, value) => sum + value, 0);
  if (totalPois > 10) {
    throw new Error("Select at most 10 POIs in total for a fast route.");
  }
  if (totalPois === 0) {
    throw new Error("Select at least one POI.");
  }

  return {
    start_lat: Number(startLatInput.value),
    start_lon: Number(startLonInput.value),
    min_distance_km: Number(document.querySelector("#min-distance").value),
    max_distance_km: Number(document.querySelector("#max-distance").value),
    poi_preferences: poiPreferences,
    routing_algorithm: selectedAlgorithm(),
    elevation_preference: "none",
    loop_route: loopRouteInput.checked,
    end_lat: useFinalPoint ? Number(endLatInput.value) : null,
    end_lon: useFinalPoint ? Number(endLonInput.value) : null,
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
  if (endMarker) {
    map.removeLayer(endMarker);
  }
  poiLayer.clearLayers();

  routeLayer = L.polyline(latLngs, {
    color: "#177245",
    weight: 6,
    opacity: 0.9,
    lineJoin: "round",
  }).addTo(map);

  setStartMarker(data.start.lat, data.start.lon);

  if (data.end) {
    setEndMarker(data.end.lat, data.end.lon);
  } else {
    endMarker = null;
  }

  data.selected_pois.forEach((poi, index) => {
    L.marker([poi.lat, poi.lon], {
      icon: poiIcon(poi.poi_group, index + 1),
    })
      .bindPopup(`<strong>${index + 1}. ${poi.name}</strong><br>${poi.poi_group}`)
      .addTo(poiLayer);
  });

  map.fitBounds(routeLayer.getBounds().pad(0.18));
}

function renderSummary(data) {
  routeDistanceEl.textContent = `${data.route.total_length_km.toFixed(2)} km`;
  routeFitEl.textContent = data.route.within_target_range
    ? "Inside requested range"
    : `Suggestion: closest route is ${data.route.total_length_km.toFixed(2)} km`;

  selectedPoisEl.innerHTML = "";
  data.selected_pois.forEach((poi) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="poi-name">
        <span class="color-swatch" style="background:${colorForGroup(poi.poi_group)}"></span>
        ${poi.name}
      </span>
      <span>${poi.poi_group}</span>
    `;
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
      label.className = "poi-count-row";
      const labelText = document.createElement("span");
      labelText.className = "poi-label";
      labelText.innerHTML = `<span class="color-swatch" style="background:${colorForGroup(group)}"></span>${group.replaceAll("_", " ")}`;
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = "10";
      input.value = preferred.has(group) ? "1" : "0";
      input.dataset.group = group;
      label.appendChild(labelText);
      label.appendChild(input);
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
      `Evaluated ${data.metrics.route_orders_evaluated} route orders from ${data.metrics.candidate_count} candidate POIs. Reused ${Math.round(data.route.repeated_edge_distance_m)} m of road.`
    );
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    generateButton.disabled = false;
  }
});

currentLocationButton.addEventListener("click", () => {
  if (!navigator.geolocation) {
    setStatus("Current location is not available in this browser.", true);
    return;
  }

  setStatus("Getting current location...");
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position.coords.latitude.toFixed(6);
      const lon = position.coords.longitude.toFixed(6);
      startLatInput.value = lat;
      startLonInput.value = lon;
      setStartMarker(Number(lat), Number(lon));
      map.setView([Number(lat), Number(lon)], 15);
      setStatus("Current location set.");
    },
    () => {
      setStatus("Could not get current location. Check browser permission.", true);
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

function updateFinalPointVisibility() {
  const showFinal = useFinalPointInput.checked;
  finalPointFields.classList.toggle("hidden", !showFinal);
  pickFinalButton.classList.toggle("hidden", !showFinal);
}

loopRouteInput.addEventListener("change", () => {
  if (loopRouteInput.checked) {
    useFinalPointInput.checked = false;
  }
  updateFinalPointVisibility();
});

useFinalPointInput.addEventListener("change", () => {
  if (useFinalPointInput.checked) {
    loopRouteInput.checked = false;
  }
  updateFinalPointVisibility();
});

pickStartButton.addEventListener("click", () => {
  setSelectionMode("start");
});

pickFinalButton.addEventListener("click", () => {
  setSelectionMode("final");
});

map.on("click", (event) => {
  if (selectionMode === "start") {
    startLatInput.value = event.latlng.lat.toFixed(6);
    startLonInput.value = event.latlng.lng.toFixed(6);
    setStartMarker(event.latlng.lat, event.latlng.lng);
    setSelectionMode(null);
    setStatus("Start point set from map click.");
    return;
  }

  if (selectionMode === "final" || useFinalPointInput.checked) {
    if (!useFinalPointInput.checked) {
      useFinalPointInput.checked = true;
      loopRouteInput.checked = false;
      updateFinalPointVisibility();
    }
    endLatInput.value = event.latlng.lat.toFixed(6);
    endLonInput.value = event.latlng.lng.toFixed(6);
    setEndMarker(event.latlng.lat, event.latlng.lng);
    setSelectionMode(null);
    setStatus("Final point set from map click.");
  }
});

loadPoiGroups();
updateFinalPointVisibility();
window.addEventListener("load", refreshMapSize);
window.addEventListener("resize", refreshMapSize);
setTimeout(refreshMapSize, 250);
