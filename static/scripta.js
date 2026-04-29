let map;
let heatLayer = null;
let frames = [];

document.addEventListener("DOMContentLoaded", () => {
    const bounds = L.latLngBounds([44, 11], [48, 19]);

    map = L.map("map", {
        maxBounds: bounds,
        maxBoundsViscosity: 1.0,
        minZoom: 6
    });

    map.fitBounds(bounds);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
        bounds: bounds,
        noWrap: true
    }).addTo(map);

    const btn12h = document.getElementById("btn-12h");
    const btnDay = document.getElementById("btn-day");
    const btnCustom = document.getElementById("btn-custom");

    const controls12h = document.getElementById("controls-12h");
    const controlsDay = document.getElementById("controls-day");
    const controlsCustom = document.getElementById("controls-custom");

    const status = document.getElementById("status");
    const slider = document.getElementById("timeline-slider");
    const timelineValue = document.getElementById("timeline-value");
    const playPauseBtn = document.getElementById("play-pause");

    let isPlaying = false;
    let interval = null;

    function hideAllControls() {
        controls12h.classList.add("hidden");
        controlsDay.classList.add("hidden");
        controlsCustom.classList.add("hidden");
    }

    function clearActiveButtons() {
        btn12h.classList.remove("active");
        btnDay.classList.remove("active");
        btnCustom.classList.remove("active");
    }

    function setMode(mode) {
        hideAllControls();
        clearActiveButtons();

        if (mode === "12h") {
            btn12h.classList.add("active");
            controls12h.classList.remove("hidden");
        } else if (mode === "day") {
            btnDay.classList.add("active");
            controlsDay.classList.remove("hidden");
        } else if (mode === "custom") {
            btnCustom.classList.add("active");
            controlsCustom.classList.remove("hidden");
        }
    }

    function showFrame(index) {
        if (!frames.length) return;

        const frame = frames[index];

        const heatData = frame.points.map(p => [
            Number(p.lat),
            Number(p.lon),
            Number(p.density)
        ]);

        if (heatLayer) {
            map.removeLayer(heatLayer);
        }

        heatLayer = L.heatLayer(heatData, {
            radius: 25,
            blur: 20,
            maxZoom: 10,
            minOpacity: 0.25
        }).addTo(map);

        timelineValue.textContent = `Čas: ${frame.time}`;
        slider.value = index;
    }

    async function sendToBackend(payload) {
        status.textContent = "Loading data...";

        try {
            const response = await fetch("/get-data", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error("Backend error:", errorText);
                status.textContent = "Backend error. Check console.";
                return;
            }

            const data = await response.json();

            console.log("Received data:", data);

            frames = data.frames;

            console.log("Frames:", frames);
            console.log("First frame:", frames[0]);
            console.log("First points:", frames[0].points.slice(0, 5));

            slider.min = 0;
            slider.max = frames.length - 1;
            slider.value = 0;

            showFrame(0);

            status.textContent = `Loaded ${frames.length} frames`;

        } catch (error) {
            console.error("Frontend error:", error);
            status.textContent = "Error loading data. Check console.";
        }
    }
    function playTimeline() {
        isPlaying = true;
        playPauseBtn.textContent = "Pause";

        interval = setInterval(() => {
            const current = parseInt(slider.value, 10);
            const max = parseInt(slider.max, 10);

            if (current < max) {
                showFrame(current + 1);
            } else {
                pauseTimeline();
            }
        }, 500);
    }

    function pauseTimeline() {
        isPlaying = false;
        playPauseBtn.textContent = "Play";
        clearInterval(interval);
    }

    btn12h.addEventListener("click", () => setMode("12h"));
    btnDay.addEventListener("click", () => setMode("day"));
    btnCustom.addEventListener("click", () => setMode("custom"));

    document.getElementById("send-12h").addEventListener("click", () => {
        sendToBackend({
            mode: "12h",
            date: document.getElementById("date-12h").value,
            start_hour: parseInt(document.getElementById("hour-12h").value, 10)
        });
    });

    document.getElementById("send-day").addEventListener("click", () => {
        sendToBackend({
            mode: "day",
            date: document.getElementById("date-day").value
        });
    });

    document.getElementById("send-custom").addEventListener("click", () => {
        sendToBackend({
            mode: "custom",
            date_from: document.getElementById("date-from").value,
            date_to: document.getElementById("date-to").value
        });
    });

    slider.addEventListener("input", () => {
        pauseTimeline();
        showFrame(parseInt(slider.value, 10));
    });

    playPauseBtn.addEventListener("click", () => {
        if (isPlaying) {
            pauseTimeline();
        } else {
            playTimeline();
        }
    });

    setMode("12h");
});