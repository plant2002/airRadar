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
                let current = parseInt(slider.value);
                if (current < parseInt(slider.max)) {
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

                // Example update
                // Here you can replace map image, markers, graph, etc.
                document.getElementById("map").innerHTML = `
                    <div style="padding:20px;">
                        <h2>Returned data</h2>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                `;

                // Optional: backend can return max timeline steps
                if (data.max_steps !== undefined) {
                    slider.max = data.max_steps;
                    slider.value = 0;
                    timelineValue.textContent = "Trenutni časovni korak: 0";
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
                date: date,
                days: parseInt(days),
                hours: parseInt(hours)
            });
        });

        document.querySelectorAll(".week-btn").forEach(button => {
            button.addEventListener("click", () => {
                const range = button.dataset.range;
                sendToBackend({
                    mode: "week",
                    range: range
                });
            });
        });

        document.getElementById("send-month").addEventListener("click", () => {
            const month = document.getElementById("month-picker").value;

            sendToBackend({
                mode: "month",
                month: month
            });
        });

        setMode("custom");