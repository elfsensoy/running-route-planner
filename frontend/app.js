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
let userLocationMarker = null;
let userAccuracyCircle = null;
let selectionMode = null;
let activeRouteCoordinates = [];
let activeRouteDistances = [];
let trackingWatchId = null;

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
const routeOptionsEl = document.querySelector("#route-options");
const elevationSummaryEl = document.querySelector("#elevation-summary");
const elevationPreferenceEl = document.querySelector("#elevation-preference");
const elevationGainEl = document.querySelector("#elevation-gain");
const elevationAverageSlopeEl = document.querySelector("#elevation-average-slope");
const elevationMaxSlopeEl = document.querySelector("#elevation-max-slope");
const selectedPoisEl = document.querySelector("#selected-pois");
const trackingPanel = document.querySelector("#tracking-panel");
const trackingButton = document.querySelector("#tracking-button");
const trackingStateEl = document.querySelector("#tracking-state");
const trackingDistanceEl = document.querySelector("#tracking-distance");
const trackingProgressEl = document.querySelector("#tracking-progress");
const trackingRemainingEl = document.querySelector("#tracking-remaining");
const poiGroupsEl = document.querySelector("#poi-groups");
const loopRouteInput = document.querySelector("#loop-route");
const useFinalPointInput = document.querySelector("#use-final-point");
const finalPointFields = document.querySelector("#final-point-fields");
const startLatInput = document.querySelector("#start-lat");
const startLonInput = document.querySelector("#start-lon");
const endLatInput = document.querySelector("#end-lat");
const endLonInput = document.querySelector("#end-lon");
let allPois = [];
let latestRouteResponse = null;

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

function formatDistance(meters) {
  if (!Number.isFinite(meters)) {
    return "--";
  }
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(2)} km`;
  }
  return `${Math.round(meters)} m`;
}

function buildRouteDistances(coordinates) {
  const distances = [0];
  for (let index = 1; index < coordinates.length; index += 1) {
    const previous = coordinates[index - 1];
    const current = coordinates[index];
    distances.push(
      distances[index - 1] + map.distance([previous.lat, previous.lon], [current.lat, current.lon])
    );
  }
  return distances;
}

function projectPointToSegment(point, segmentStart, segmentEnd) {
  const latScale = 111320;
  const lonScale = 111320 * Math.cos((point.lat * Math.PI) / 180);
  const px = (point.lon - segmentStart.lon) * lonScale;
  const py = (point.lat - segmentStart.lat) * latScale;
  const vx = (segmentEnd.lon - segmentStart.lon) * lonScale;
  const vy = (segmentEnd.lat - segmentStart.lat) * latScale;
  const segmentLengthSq = vx * vx + vy * vy;
  const t = segmentLengthSq === 0 ? 0 : Math.max(0, Math.min(1, (px * vx + py * vy) / segmentLengthSq));
  const projectedLat = segmentStart.lat + (segmentEnd.lat - segmentStart.lat) * t;
  const projectedLon = segmentStart.lon + (segmentEnd.lon - segmentStart.lon) * t;
  return {
    t,
    lat: projectedLat,
    lon: projectedLon,
    distance_m: map.distance([point.lat, point.lon], [projectedLat, projectedLon]),
  };
}

function nearestRouteProgress(lat, lon) {
  if (activeRouteCoordinates.length < 2) {
    return null;
  }

  const point = { lat, lon };
  let nearest = null;
  for (let index = 1; index < activeRouteCoordinates.length; index += 1) {
    const segmentStart = activeRouteCoordinates[index - 1];
    const segmentEnd = activeRouteCoordinates[index];
    const projection = projectPointToSegment(point, segmentStart, segmentEnd);
    const segmentLength =
      activeRouteDistances[index] - activeRouteDistances[index - 1];
    const traveled_m = activeRouteDistances[index - 1] + segmentLength * projection.t;
    const candidate = {
      ...projection,
      traveled_m,
    };
    if (!nearest || candidate.distance_m < nearest.distance_m) {
      nearest = candidate;
    }
  }
  return nearest;
}

function resetTrackingMetrics() {
  trackingStateEl.textContent = "Stopped";
  trackingDistanceEl.textContent = "--";
  trackingProgressEl.textContent = "--";
  trackingRemainingEl.textContent = "--";
}

function stopTracking() {
  if (trackingWatchId !== null) {
    navigator.geolocation.clearWatch(trackingWatchId);
    trackingWatchId = null;
  }
  trackingButton.textContent = "Start tracking";
  resetTrackingMetrics();
  if (userLocationMarker) {
    map.removeLayer(userLocationMarker);
    userLocationMarker = null;
  }
  if (userAccuracyCircle) {
    map.removeLayer(userAccuracyCircle);
    userAccuracyCircle = null;
  }
}

function updateUserLocation(position) {
  const lat = position.coords.latitude;
  const lon = position.coords.longitude;
  const accuracy = position.coords.accuracy;
  const routeProgress = nearestRouteProgress(lat, lon);
  const totalDistance = activeRouteDistances[activeRouteDistances.length - 1] || 0;

  if (!userLocationMarker) {
    userLocationMarker = L.circleMarker([lat, lon], {
      radius: 8,
      color: "#0f5db8",
      fillColor: "#2d6cdf",
      fillOpacity: 1,
      weight: 3,
    })
      .bindPopup("You")
      .addTo(map);
  } else {
    userLocationMarker.setLatLng([lat, lon]);
  }

  if (!userAccuracyCircle) {
    userAccuracyCircle = L.circle([lat, lon], {
      radius: accuracy || 0,
      color: "#2d6cdf",
      fillColor: "#2d6cdf",
      fillOpacity: 0.12,
      weight: 1,
    }).addTo(map);
  } else {
    userAccuracyCircle.setLatLng([lat, lon]);
    userAccuracyCircle.setRadius(accuracy || 0);
  }

  if (!routeProgress || totalDistance === 0) {
    trackingStateEl.textContent = "Tracking";
    return;
  }

  const remaining_m = Math.max(0, totalDistance - routeProgress.traveled_m);
  const progress = Math.max(0, Math.min(100, (routeProgress.traveled_m / totalDistance) * 100));
  trackingStateEl.textContent = routeProgress.distance_m > 50 ? "Off route" : "On route";
  trackingDistanceEl.textContent = formatDistance(routeProgress.distance_m);
  trackingProgressEl.textContent = `${Math.round(progress)}%`;
  trackingRemainingEl.textContent = formatDistance(remaining_m);
}

function startTracking() {
  if (trackingWatchId !== null) {
    stopTracking();
    return;
  }
  if (!navigator.geolocation) {
    setStatus("Live tracking is not available in this browser.", true);
    return;
  }
  if (activeRouteCoordinates.length < 2) {
    setStatus("Generate a route before starting live tracking.", true);
    return;
  }

  trackingStateEl.textContent = "Starting";
  trackingButton.textContent = "Stop tracking";
  trackingWatchId = navigator.geolocation.watchPosition(
    (position) => {
      updateUserLocation(position);
      setStatus("Live tracking active.");
    },
    () => {
      stopTracking();
      setStatus("Could not get live location. Check browser permission.", true);
    },
    { enableHighAccuracy: true, maximumAge: 2000, timeout: 12000 }
  );
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

function selectedPoiIds() {
  return Array.from(poiGroupsEl.querySelectorAll(".poi-option-list input[type='checkbox']:checked")).map(
    (input) => input.value
  );
}

function poiCountForGroup(group) {
  const input = poiGroupsEl.querySelector(`input[data-group="${group}"]`);
  return input ? Number(input.value || 0) : 0;
}

function updatePoiOptionStates() {
  poiGroupsEl.querySelectorAll(".poi-option-group").forEach((groupEl) => {
    const group = groupEl.dataset.group;
    const maxSelected = poiCountForGroup(group);
    const chooseInput = groupEl.querySelector(".poi-choose-toggle");
    const checkboxes = Array.from(
      groupEl.querySelectorAll(".poi-option-list input[type='checkbox']")
    );
    const isChoosing = chooseInput?.checked && maxSelected > 0;

    groupEl.classList.toggle("choosing", Boolean(isChoosing));

    if (!isChoosing) {
      checkboxes.forEach((checkbox) => {
        checkbox.checked = false;
        checkbox.disabled = true;
      });
    } else {
      let keptSelected = 0;
      checkboxes.forEach((checkbox) => {
        if (!checkbox.checked) {
          return;
        }
        if (keptSelected >= maxSelected) {
          checkbox.checked = false;
          return;
        }
        keptSelected += 1;
      });
      const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
      checkboxes.forEach((checkbox) => {
        checkbox.disabled = !checkbox.checked && selectedCount >= maxSelected;
      });
    }

    const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
    const countEl = groupEl.querySelector(".poi-option-count");
    if (countEl) {
      countEl.textContent = `${selectedCount}/${maxSelected}`;
    }
    if (chooseInput) {
      chooseInput.disabled = maxSelected <= 0;
      if (maxSelected <= 0) {
        chooseInput.checked = false;
      }
    }
  });
}

function createPoiOptionGroup(group, pois) {
  const groupEl = document.createElement("div");
  groupEl.className = "poi-option-group";
  groupEl.dataset.group = group;

  const chooseLabel = document.createElement("label");
  chooseLabel.className = "poi-choose-row";
  const chooseInput = document.createElement("input");
  chooseInput.type = "checkbox";
  chooseInput.className = "poi-choose-toggle";
  chooseInput.dataset.group = group;
  const chooseText = document.createElement("span");
  chooseText.textContent = "I want to choose";
  const chooseCount = document.createElement("span");
  chooseCount.className = "poi-option-count";
  chooseCount.textContent = `0/${poiCountForGroup(group)}`;
  chooseLabel.appendChild(chooseInput);
  chooseLabel.appendChild(chooseText);
  chooseLabel.appendChild(chooseCount);
  groupEl.appendChild(chooseLabel);

  const list = document.createElement("div");
  list.className = "poi-option-list";
  pois.forEach((poi) => {
    const label = document.createElement("label");
    label.className = "poi-option-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = poi.poi_id;
    checkbox.dataset.group = poi.poi_group;
    const name = document.createElement("span");
    name.textContent = poi.name;
    label.appendChild(checkbox);
    label.appendChild(name);
    list.appendChild(label);
  });
  groupEl.appendChild(list);

  return groupEl;
}

function renderPoiOptionsInGroups() {
  const groupInputs = Array.from(poiGroupsEl.querySelectorAll("input[data-group]"));
  if (groupInputs.length === 0 || allPois.length === 0) {
    return;
  }

  groupInputs.forEach((groupInput) => {
    const group = groupInput.dataset.group;
    const row = groupInput.closest(".poi-count-row");
    if (!row || row.nextElementSibling?.dataset?.group === group) {
      return;
    }

    const pois = allPois.filter((poi) => poi.poi_group === group);
    if (pois.length === 0) {
      return;
    }

    row.insertAdjacentElement("afterend", createPoiOptionGroup(group, pois));
  });
  updatePoiOptionStates();
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
    selected_poi_ids: selectedPoiIds(),
    elevation_preference: form.querySelector("input[name='elevation_preference']:checked").value,
    loop_route: loopRouteInput.checked,
    end_lat: useFinalPoint ? Number(endLatInput.value) : null,
    end_lon: useFinalPoint ? Number(endLonInput.value) : null,
  };
}

function selectedRouteOption(data, optionIndex = 0) {
  if (Array.isArray(data.route_options) && data.route_options[optionIndex]) {
    return data.route_options[optionIndex];
  }
  return {
    id: 1,
    route: data.route,
    selected_pois: data.selected_pois,
  };
}

function drawRoute(data, optionIndex = 0) {
  refreshMapSize();
  const option = selectedRouteOption(data, optionIndex);
  const route = option.route;
  const selectedPois = option.selected_pois;
  const latLngs = route.coordinates.map((point) => [point.lat, point.lon]);
  stopTracking();
  activeRouteCoordinates = route.coordinates;
  activeRouteDistances = buildRouteDistances(activeRouteCoordinates);
  trackingPanel.classList.remove("hidden");
  resetTrackingMetrics();

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

  selectedPois.forEach((poi, index) => {
    L.marker([poi.lat, poi.lon], {
      icon: poiIcon(poi.poi_group, index + 1),
    })
      .bindPopup(`<strong>${index + 1}. ${poi.name}</strong><br>${poi.poi_group}`)
      .addTo(poiLayer);
  });

  map.fitBounds(routeLayer.getBounds().pad(0.18));
}

function renderRouteOptions(data, selectedIndex = 0) {
  const options = Array.isArray(data.route_options) && data.route_options.length > 0
    ? data.route_options
    : [selectedRouteOption(data, 0)];

  routeOptionsEl.innerHTML = "";
  routeOptionsEl.classList.toggle("hidden", options.length <= 1);
  options.forEach((option, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "route-option-button";
    button.classList.toggle("active", index === selectedIndex);
    const poiNames = option.selected_pois.map((poi) => poi.name).join(", ");
    const title = document.createElement("strong");
    title.textContent = option.title || `Route ${index + 1}`;
    const meta = document.createElement("span");
    const elevation = option.route.elevation;
    meta.textContent = `${option.route.total_length_km.toFixed(2)} km · ${
      option.route.within_target_range ? "inside range" : "suggestion"
    } · ${Math.round(elevation?.total_gain_m || 0)} m gain`;
    const pois = document.createElement("small");
    pois.textContent = option.kind === "distance"
      ? "Distance based route"
      : poiNames;
    button.appendChild(title);
    button.appendChild(meta);
    button.appendChild(pois);
    button.addEventListener("click", () => {
      drawRoute(data, index);
      renderSummary(data, index);
    });
    routeOptionsEl.appendChild(button);
  });
}

function renderSummary(data, optionIndex = 0) {
  const option = selectedRouteOption(data, optionIndex);
  const route = option.route;
  const selectedPois = option.selected_pois;

  routeDistanceEl.textContent = `${route.total_length_km.toFixed(2)} km`;
  routeFitEl.textContent = route.within_target_range
    ? "Inside requested range"
    : `Suggestion: closest route is ${route.total_length_km.toFixed(2)} km`;

  const elevation = route.elevation;
  if (elevation) {
    elevationSummaryEl.classList.remove("hidden");
    elevationPreferenceEl.textContent = elevation.preference;
    elevationGainEl.textContent = `${elevation.total_gain_m.toFixed(1)} m`;
    elevationAverageSlopeEl.textContent = `${(elevation.average_abs_slope * 100).toFixed(1)}%`;
    elevationMaxSlopeEl.textContent = `${(elevation.max_abs_slope * 100).toFixed(1)}%`;
  } else {
    elevationSummaryEl.classList.add("hidden");
  }

  renderRouteOptions(data, optionIndex);

  selectedPoisEl.innerHTML = "";
  if (selectedPois.length === 0) {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="poi-name">Distance based route</span>
      <span>No POI stops</span>
    `;
    selectedPoisEl.appendChild(item);
    return;
  }

  selectedPois.forEach((poi) => {
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
      input.addEventListener("input", updatePoiOptionStates);
      label.appendChild(labelText);
      label.appendChild(input);
      poiGroupsEl.appendChild(label);
    });
    renderPoiOptionsInGroups();
    refreshMapSize();
  } catch {
    setStatus("Could not load POI groups. Using defaults.", true);
  }
}

async function loadPoiOptions() {
  try {
    const response = await fetch("/api/pois");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    allPois = Array.isArray(data.pois) ? data.pois : [];
    renderPoiOptionsInGroups();
  } catch {
    setStatus("Could not load POI options.", true);
  }
}

poiGroupsEl.addEventListener("change", (event) => {
  if (event.target.matches(".poi-choose-toggle")) {
    updatePoiOptionStates();
    return;
  }

  if (!event.target.matches("input[type='checkbox']")) {
    return;
  }

  const group = event.target.dataset.group;
  const maxSelected = poiCountForGroup(group);
  const selectedCount = poiGroupsEl.querySelectorAll(
    `.poi-option-list input[data-group="${group}"]:checked`
  ).length;

  if (selectedCount > maxSelected) {
    event.target.checked = false;
    setStatus(`You can select at most ${maxSelected} ${group.replaceAll("_", " ")} POIs.`, true);
  }

  updatePoiOptionStates();
});

trackingButton.addEventListener("click", startTracking);

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

    latestRouteResponse = data;
    drawRoute(latestRouteResponse, 0);
    renderSummary(latestRouteResponse, 0);
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
loadPoiOptions();
updateFinalPointVisibility();
window.addEventListener("load", refreshMapSize);
window.addEventListener("resize", refreshMapSize);
setTimeout(refreshMapSize, 250);
