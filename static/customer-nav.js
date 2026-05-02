(() => {
    const CATALOG_URL = "/catalog?view=products&category=all&room=all";
    const WISHLIST_KEY = "affilistay_wishlist";

    const readWishlistCount = () => {
        try {
            return JSON.parse(localStorage.getItem(WISHLIST_KEY) || "[]").length;
        } catch (error) {
            return 0;
        }
    };

    const updateBadge = () => {
        const count = readWishlistCount();
        document.querySelectorAll("[data-wishlist-count]").forEach((badge) => {
            badge.textContent = count;
            badge.classList.toggle("is-visible", count > 0);
        });
    };

    const sameDestination = (href) => {
        try {
            const next = new URL(href, window.location.origin);
            return next.pathname + next.search === window.location.pathname + window.location.search;
        } catch (error) {
            return false;
        }
    };

    const navigate = (link) => {
        const href = link.getAttribute("href");
        if (!href || href.startsWith("#") || sameDestination(href)) return;
        if (link.dataset.fastNavBusy === "true") return;
        link.dataset.fastNavBusy = "true";
        link.classList.add("is-active");
        window.location.assign(link.href);
    };

    const handleFastNav = (event) => {
        const target = event.target instanceof Element ? event.target : event.target?.parentElement;
        const link = target?.closest?.(".bottom-tabbar a[href], .landing-tabbar a[href], .af-bottom-tabbar a[href], .bottom-nav a[href]");
        if (!link || link.target || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
        navigate(link);
    };

    const bindFastNav = () => {
        if (window.__affilistayFastNavBound) return;
        window.__affilistayFastNavBound = true;
        document.addEventListener("pointerup", handleFastNav, true);
        document.addEventListener("click", handleFastNav, true);
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            handleFastNav(event);
        }, true);
    };

    if (document.querySelector(".bottom-tabbar, .landing-tabbar, #affilistay-customer-nav")) {
        updateBadge();
        bindFastNav();
        return;
    }

    document.querySelectorAll(".bottom-nav").forEach((node) => node.remove());

    const path = window.location.pathname;
    const active = path === "/" ? "home" :
        path.startsWith("/wishlist") ? "wishlist" :
        path.startsWith("/mypage") || path.startsWith("/customer/login") ? "mypage" :
        "shopping";

    const style = document.createElement("style");
    style.textContent = `
        body.af-has-customer-nav {
            padding-bottom: calc(76px + env(safe-area-inset-bottom));
        }
        .af-bottom-tabbar {
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 90;
            border-top: 1px solid rgba(24, 22, 18, 0.09);
            background: rgba(255, 253, 249, 0.95);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            padding: 0.45rem 0.75rem calc(0.45rem + env(safe-area-inset-bottom));
        }
        .af-bottom-tabbar-inner {
            margin: 0 auto;
            display: grid;
            max-width: 620px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.25rem;
        }
        .af-bottom-tab {
            position: relative;
            display: flex;
            min-height: 3.15rem;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.18rem;
            border-radius: 1rem;
            color: #8a8279;
            font-size: 0.72rem;
            font-weight: 800;
            text-decoration: none;
            line-height: 1;
            touch-action: manipulation;
        }
        .af-bottom-tab .icon {
            font-size: 1.25rem;
            line-height: 1;
        }
        .af-bottom-tab.is-active {
            background: #221f1a;
            color: #fff;
        }
        .af-bottom-badge {
            position: absolute;
            top: 0.28rem;
            right: calc(50% - 1.35rem);
            min-width: 1.05rem;
            height: 1.05rem;
            padding: 0 0.25rem;
            border-radius: 999px;
            background: #e65d58;
            color: #fff;
            display: none;
            font-size: 0.65rem;
            font-weight: 900;
            line-height: 1.05rem;
            text-align: center;
        }
        .af-bottom-badge.is-visible {
            display: inline-block;
        }
    `;
    document.head.appendChild(style);
    document.body.classList.add("af-has-customer-nav");

    const nav = document.createElement("nav");
    nav.id = "affilistay-customer-nav";
    nav.className = "af-bottom-tabbar";
    nav.setAttribute("aria-label", "고객 메뉴");
    nav.innerHTML = `
        <div class="af-bottom-tabbar-inner">
            <a href="/" class="af-bottom-tab ${active === "home" ? "is-active" : ""}">
                <span class="icon" aria-hidden="true">⌂</span><span>홈</span>
            </a>
            <a href="${CATALOG_URL}" class="af-bottom-tab ${active === "shopping" ? "is-active" : ""}">
                <span class="icon" aria-hidden="true">▦</span><span>쇼핑</span>
            </a>
            <a href="/wishlist" class="af-bottom-tab ${active === "wishlist" ? "is-active" : ""}">
                <span class="af-bottom-badge" data-wishlist-count></span>
                <span class="icon" aria-hidden="true">♡</span><span>찜목록</span>
            </a>
            <a href="/mypage" class="af-bottom-tab ${active === "mypage" ? "is-active" : ""}">
                <span class="icon" aria-hidden="true">♙</span><span>마이</span>
            </a>
        </div>
    `;
    document.body.appendChild(nav);
    updateBadge();
    bindFastNav();
})();
