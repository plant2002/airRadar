let map;

document.addEventListener("DOMContentLoaded", () => {
    // Initialize map
    map = L.map("map").setView([64, 15], 5);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const btnCustom = document.getElementById("btn-custom");
    const btnWeek = document.getElementById("btn-week");
    const btnMonth = document.getElementById("btn-month");

    const customControls = document.getElementById("custom-controls");
    const weekControls = document.getElementById("week-controls");
    const monthControls = document.getElementById("month-controls");

    const status = document.getElementById("status");
    const slider = document.getElementById("timeline-slider");
    const timelineValue = document.getElementById("timeline-value");
    const playPauseBtn = document.getElementById("play-pause");

    let isPlaying = false;
    let interval = null;

    function clearActiveButtons() {
        [btnCustom, btnWeek, btnMonth].forEach(btn => btn.classList.remove("active"));
    }

    function hideAllControls() {
        customControls.classList.add("hidden");
        weekControls.classList.add("hidden");
        monthControls.classList.add("hidden");
    }

    function setMode(mode) {
        clearActiveButtons();
        hideAllControls();

        if (mode === "custom") {
            btnCustom.classList.add("active");
            customControls.classList.remove("hidden");
        } else if (mode === "week") {
            btnWeek.classList.add("active");
            weekControls.classList.remove("hidden");
        } else if (mode === "month") {
            btnMonth.classList.add("active");
            monthControls.classList.remove("hidden");
        }
    }

    btnCustom.addEventListener("click", () => setMode("custom"));
    btnWeek.addEventListener("click", () => setMode("week"));
    btnMonth.addEventListener("click", () => setMode("month"));

    slider.addEventListener("input", () => {
        timelineValue.textContent = `Trenutni časovni korak: ${slider.value}`;
        pauseTimeline();
    });

    playPauseBtn.addEventListener("click", () => {
        if (isPlaying) {
            pauseTimeline();
        } else {
            playTimeline();
        }
    });

    function playTimeline() {
        isPlaying = true;
        playPauseBtn.textContent = "Pause";

        interval = setInterval(() => {
            const current = parseInt(slider.value, 10);
            const max = parseInt(slider.max, 10);

            if (current < max) {
                slider.value = current + 1;
                timelineValue.textContent = `Trenutni časovni korak: ${slider.value}`;
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

            const data = await response.json();
            status.textContent = `Loaded: ${JSON.stringify(payload)}`;

            if (data.max_steps !== undefined) {
                slider.max = data.max_steps;
                slider.value = 0;
                timelineValue.textContent = "Trenutni časovni korak: 0";
            }

            // Example: add marker if backend returns coordinates
            if (data.lat && data.lng) {
                L.marker([data.lat, data.lng]).addTo(map);
                map.setView([data.lat, data.lng], 8);
            }

        } catch (error) {
            status.textContent = "Error loading data.";
            console.error(error);
        }
    }

    document.getElementById("send-custom").addEventListener("click", () => {
        const date = document.getElementById("custom-date").value;
        const days = document.getElementById("custom-days").value;
        const hours = document.getElementById("custom-hours").value;

        sendToBackend({
            mode: "custom",
            date,
            days: parseInt(days, 10),
            hours: parseInt(hours, 10)
        });
    });

    document.querySelectorAll(".week-btn").forEach(button => {
        button.addEventListener("click", () => {
            sendToBackend({
                mode: "week",
                range: button.dataset.range
            });
        });
    });

    document.getElementById("send-month").addEventListener("click", () => {
        const month = document.getElementById("month-picker").value;

        sendToBackend({
            mode: "month",
            month
        });
    });

    setMode("custom");
});