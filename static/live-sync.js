(function () {
    const script = document.currentScript;
    if (!script) return;

    const initialVersion = script.dataset.liveVersion || "";
    if (!initialVersion) return;

    const endpoint = script.dataset.liveEndpoint || "/api/public-content-version";
    const intervalMs = Number(script.dataset.liveInterval || 5000);
    const message = script.dataset.liveMessage || "새 정보가 반영되어 화면을 업데이트합니다.";

    let currentVersion = initialVersion;
    let refreshing = false;
    let lastInteractionAt = Date.now();
    let toastEl = null;

    const markInteraction = () => {
        lastInteractionAt = Date.now();
    };

    const ensureToast = () => {
        if (toastEl) return toastEl;
        toastEl = document.createElement("div");
        toastEl.setAttribute("aria-live", "polite");
        toastEl.style.position = "fixed";
        toastEl.style.left = "50%";
        toastEl.style.bottom = "24px";
        toastEl.style.transform = "translateX(-50%) translateY(12px)";
        toastEl.style.background = "rgba(28, 24, 19, 0.94)";
        toastEl.style.color = "#fff";
        toastEl.style.padding = "12px 16px";
        toastEl.style.borderRadius = "999px";
        toastEl.style.fontSize = "13px";
        toastEl.style.fontWeight = "600";
        toastEl.style.boxShadow = "0 14px 30px rgba(18, 16, 12, 0.18)";
        toastEl.style.opacity = "0";
        toastEl.style.transition = "opacity 180ms ease, transform 180ms ease";
        toastEl.style.zIndex = "9999";
        toastEl.style.pointerEvents = "none";
        document.body.appendChild(toastEl);
        return toastEl;
    };

    const showToast = () => {
        const el = ensureToast();
        el.textContent = message;
        requestAnimationFrame(() => {
            el.style.opacity = "1";
            el.style.transform = "translateX(-50%) translateY(0)";
        });
    };

    const refreshSoon = () => {
        if (refreshing) return;
        refreshing = true;
        showToast();
        const idleMs = Date.now() - lastInteractionAt;
        const waitMs = idleMs > 1200 ? 650 : 1400;
        window.setTimeout(() => {
            window.location.reload();
        }, waitMs);
    };

    const checkVersion = async () => {
        if (document.hidden || refreshing) return;
        try {
            const response = await fetch(`${endpoint}?t=${Date.now()}`, {
                cache: "no-store",
                headers: { "Cache-Control": "no-store" },
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data.version && data.version !== currentVersion) {
                currentVersion = data.version;
                refreshSoon();
            }
        } catch (error) {
            console.debug("live-sync skipped", error);
        }
    };

    ["pointerdown", "touchstart", "keydown", "focusin", "scroll"].forEach((eventName) => {
        window.addEventListener(eventName, markInteraction, { passive: true });
    });

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            checkVersion();
        }
    });

    window.setInterval(checkVersion, intervalMs);
})();
