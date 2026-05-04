(() => {
    const CATALOG_URL = "/catalog?view=products&category=all&room=all";
    const WISHLIST_KEY = "affilistay_wishlist";

    const readWishlist = () => {
        try {
            const items = JSON.parse(localStorage.getItem(WISHLIST_KEY) || "[]");
            return Array.isArray(items) ? items : [];
        } catch (error) {
            return [];
        }
    };

    const compactWishlistItems = (items) => items.map((item) => ({
        ...item,
        image: typeof item.image === "string" && item.image.startsWith("data:image") ? "" : item.image
    }));

    const writeWishlist = (items) => {
        try {
            localStorage.setItem(WISHLIST_KEY, JSON.stringify(items));
            return true;
        } catch (error) {
            try {
                localStorage.setItem(WISHLIST_KEY, JSON.stringify(compactWishlistItems(items)));
                return true;
            } catch (retryError) {
                console.warn("wishlist save failed", retryError);
                return false;
            }
        }
    };

    const wishlistItemId = (item) => String(item?.id ?? item?.product_id ?? "");
    const wishlistButtonId = (button) => String(button?.dataset?.productId ?? "");

    const readWishlistCount = () => readWishlist().length;

    const updateBadge = () => {
        const count = readWishlistCount();
        document.querySelectorAll("[data-wishlist-count]").forEach((badge) => {
            badge.textContent = count;
            badge.classList.toggle("is-visible", count > 0);
        });
    };

    const injectWishlistStyle = () => {
        if (document.getElementById("affilistay-wishlist-style")) return;
        const style = document.createElement("style");
        style.id = "affilistay-wishlist-style";
        style.textContent = `
            [data-wishlist-toggle] {
                -webkit-tap-highlight-color: transparent;
                touch-action: manipulation;
            }
            [data-wishlist-toggle].is-liked {
                color: #e65d58 !important;
                border-color: rgba(230, 93, 88, 0.38) !important;
            }
            [data-wishlist-toggle].is-liked svg,
            [data-wishlist-toggle].is-liked path {
                fill: currentColor !important;
                stroke: currentColor !important;
            }
            .affilistay-wishlist-toast {
                position: fixed;
                left: 50%;
                bottom: calc(88px + env(safe-area-inset-bottom));
                z-index: 9999;
                max-width: calc(100vw - 32px);
                transform: translate(-50%, 14px);
                border-radius: 999px;
                background: rgba(34, 31, 26, 0.94);
                color: #fff;
                padding: 0.78rem 1rem;
                font-size: 0.86rem;
                font-weight: 800;
                opacity: 0;
                pointer-events: none;
                transition: opacity 160ms ease, transform 160ms ease;
                box-shadow: 0 18px 44px rgba(18, 16, 12, 0.2);
            }
            .affilistay-wishlist-toast.is-visible {
                opacity: 1;
                transform: translate(-50%, 0);
            }
        `;
        document.head.appendChild(style);
    };

    let toastTimer = null;
    const showWishlistToast = (message) => {
        let toast = document.querySelector(".affilistay-wishlist-toast");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "affilistay-wishlist-toast";
            toast.setAttribute("role", "status");
            toast.setAttribute("aria-live", "polite");
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add("is-visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1350);
    };

    const setButtonState = (button, liked) => {
        button.classList.toggle("is-liked", liked);
        button.classList.toggle("is-wishlisted", liked);
        button.setAttribute("aria-pressed", liked ? "true" : "false");
        if (button.childElementCount === 0) {
            button.textContent = liked ? "♥" : "♡";
        }
    };

    const syncWishlistButtons = () => {
        const ids = new Set(readWishlist().map(wishlistItemId));
        document.querySelectorAll("[data-wishlist-toggle]").forEach((button) => {
            setButtonState(button, ids.has(wishlistButtonId(button)));
        });
        updateBadge();
    };

    const productPayloadFromButton = (button) => {
        const card = button.closest("[data-product-card], article, .rec-card");
        const imageNode = card?.querySelector?.("img");
        const linkNode = card?.querySelector?.("a[href]");
        const productId = Number(button.dataset.productId || card?.dataset?.productId || 0);
        const url = button.dataset.url || linkNode?.getAttribute("href") || window.location.pathname + window.location.search;
        return {
            product_id: productId,
            qr_code_id: button.dataset.qrCodeId || (url.split("/shop/")[1]?.split("/")[0] || ""),
            product_name: button.dataset.productName || card?.dataset?.productName || "",
            brand_name: button.dataset.brandName || card?.dataset?.brandName || "",
            price: Number(button.dataset.price || card?.dataset?.price || 0),
            url,
            image: button.dataset.image || imageNode?.getAttribute("src") || "/static/product.png"
        };
    };

    const serverWishlistPayload = (payload) => ({
        product_id: Number(payload.product_id || 0),
        qr_code_id: payload.qr_code_id || null,
        product_name: payload.product_name || null,
        brand_name: payload.brand_name || null,
        price: Number(payload.price || 0) || null,
        url: payload.url || window.location.pathname + window.location.search
    });

    const syncWishlistToServer = async (payload) => {
        if (!payload.product_id) return;
        try {
            await fetch("/api/wishlist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(serverWishlistPayload(payload))
            });
        } catch (error) {
            console.warn("wishlist sync failed", error);
        }
    };

    const toggleWishlist = (button) => {
        const payload = productPayloadFromButton(button);
        const id = String(payload.product_id || button.dataset.productId || "");
        if (!payload.product_id || !id) return;

        const items = readWishlist();
        const existingIndex = items.findIndex((item) => wishlistItemId(item) === id);
        if (existingIndex >= 0) {
            items.splice(existingIndex, 1);
            if (!writeWishlist(items)) return;
            syncWishlistButtons();
            showWishlistToast("찜목록에서 뺐어요.");
            return;
        }

        items.unshift({
            id,
            product_id: payload.product_id,
            name: payload.product_name,
            product_name: payload.product_name,
            brand: payload.brand_name,
            brand_name: payload.brand_name,
            price: payload.price,
            url: payload.url,
            image: payload.image,
            added_at: Date.now()
        });
        if (!writeWishlist(items)) return;
        syncWishlistButtons();
        syncWishlistToServer(payload);
        showWishlistToast(`${payload.product_name || "상품"}을 찜목록에 담았어요.`);
    };

    const handleWishlistActivation = (event, forcedButton) => {
        const target = event.target instanceof Element ? event.target : event.target?.parentElement;
        const button = forcedButton || target?.closest?.("[data-wishlist-toggle]");
        if (!button) return;
        if (event.__affilistayWishlistHandled) return;
        event.__affilistayWishlistHandled = true;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();

        const now = Date.now();
        const last = Number(button.dataset.wishlistActivatedAt || 0);
        if (now - last < 1000) return;
        button.dataset.wishlistActivatedAt = String(now);
        toggleWishlist(button);
    };

    window.affilistayToggleWishlistFromButton = (button, event) => {
        if (!button) return false;
        if (event) {
            handleWishlistActivation(event, button);
        } else {
            toggleWishlist(button);
        }
        return false;
    };

    const bindWishlist = () => {
        injectWishlistStyle();
        if (!window.__affilistayWishlistBound) {
            window.__affilistayWishlistBound = true;
            document.addEventListener("pointerdown", handleWishlistActivation, true);
            document.addEventListener("touchend", handleWishlistActivation, true);
            document.addEventListener("click", handleWishlistActivation, true);
            document.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                handleWishlistActivation(event);
            }, true);
            window.addEventListener("storage", syncWishlistButtons);
        }
        syncWishlistButtons();
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

    bindWishlist();

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
