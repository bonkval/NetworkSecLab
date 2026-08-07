(() => {
    const root = document.documentElement;
    const stored = localStorage.getItem("security-lab-theme");
    const preferred = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";

    function apply(theme) {
        root.dataset.theme = theme;
        root.style.colorScheme = theme;
        localStorage.setItem("security-lab-theme", theme);
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            const isLight = theme === "light";
            button.setAttribute("aria-label", `Switch to ${isLight ? "dark" : "light"} mode`);
            button.setAttribute("title", `Switch to ${isLight ? "dark" : "light"} mode`);
            button.innerHTML = `<span aria-hidden="true">${isLight ? "&#9789;" : "&#9728;"}</span><em>${isLight ? "Dark" : "Light"}</em>`;
        });
        window.dispatchEvent(new CustomEvent("themechange", {detail: {theme}}));
    }

    apply(stored === "light" || stored === "dark" ? stored : preferred);
    document.addEventListener("DOMContentLoaded", () => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "theme-toggle";
        button.dataset.themeToggle = "";
        const actions = document.querySelector(".topbar-actions");
        const topbar = document.querySelector(".topbar");
        if (actions) actions.prepend(button);
        else if (topbar) topbar.lastElementChild?.append(button);
        else {
            button.classList.add("theme-toggle-floating");
            document.body.append(button);
        }
        button.addEventListener("click", async () => {
            const nextTheme = root.dataset.theme === "light" ? "dark" : "light";
            const bounds = button.getBoundingClientRect();
            root.style.setProperty("--theme-wave-x", `${bounds.left + bounds.width / 2}px`);
            root.style.setProperty("--theme-wave-y", `${bounds.top + bounds.height / 2}px`);
            button.disabled = true;
            if (document.startViewTransition && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
                const transition = document.startViewTransition(() => apply(nextTheme));
                await transition.finished;
            } else {
                root.classList.add("theme-fade");
                apply(nextTheme);
                await new Promise((resolve) => setTimeout(resolve, 650));
                root.classList.remove("theme-fade");
            }
            button.disabled = false;
            button.focus();
        });
        apply(root.dataset.theme);
    });
})();
