(function () {
    "use strict";
    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var video = document.getElementById("workspace-film");
    var backgroundPoster = document.querySelector(".background-poster");
    var backgroundToggle = document.querySelector(".background-toggle");
    var wantsBackground = !reduceMotion.matches;
    var backgroundVisible = true;
    var backgroundFailed = false;

    function updateBackgroundButton() {
        if (!backgroundToggle) return;
        var active = wantsBackground && !reduceMotion.matches;
        backgroundToggle.hidden = reduceMotion.matches || backgroundFailed;
        backgroundToggle.setAttribute("aria-pressed", String(active));
        backgroundToggle.setAttribute("aria-label", active ? "暂停背景动画" : "播放背景动画");
        backgroundToggle.querySelector("[data-background-icon]").textContent = active ? "Ⅱ" : "▷";
        backgroundToggle.querySelector("[data-background-label]").textContent = active ? "暂停背景" : "播放背景";
    }

    function syncBackground() {
        if (!video || backgroundFailed) return;
        if (!wantsBackground || reduceMotion.matches || document.hidden || !backgroundVisible) {
            video.pause();
            return;
        }
        if (!video.getAttribute("src")) video.src = video.getAttribute("data-src");
        video.play().catch(function () {
            wantsBackground = false;
            updateBackgroundButton();
        });
    }

    if (video && backgroundToggle) {
        video.addEventListener("loadeddata", function () {
            video.hidden = false;
            if (backgroundPoster) backgroundPoster.hidden = true;
        });
        backgroundToggle.addEventListener("click", function () {
            wantsBackground = !wantsBackground;
            syncBackground();
            updateBackgroundButton();
        });
        video.addEventListener("error", function () {
            backgroundFailed = true;
            video.hidden = true;
            if (backgroundPoster) backgroundPoster.hidden = false;
            updateBackgroundButton();
        });
        document.addEventListener("visibilitychange", syncBackground);
        function handleBackgroundPreference() {
            wantsBackground = !reduceMotion.matches;
            syncBackground();
            updateBackgroundButton();
        }
        if (reduceMotion.addEventListener) reduceMotion.addEventListener("change", handleBackgroundPreference);
        else if (reduceMotion.addListener) reduceMotion.addListener(handleBackgroundPreference);
        if (window.IntersectionObserver) {
            new IntersectionObserver(function (entries) {
                backgroundVisible = entries[0].isIntersecting;
                syncBackground();
            }).observe(document.querySelector(".workspace-environment"));
        }
        updateBackgroundButton();
        syncBackground();
    }
    var slides = Array.prototype.slice.call(document.querySelectorAll("[data-preview-slide]"));
    var controls = Array.prototype.slice.call(document.querySelectorAll("[data-preview]"));
    var currentSlide = 0;

    controls.forEach(function (control) {
        control.addEventListener("click", function () {
            var next = Number(control.getAttribute("data-preview"));
            if (next === currentSlide || !slides[next]) return;
            if (window.gsap) window.gsap.killTweensOf(slides);
            slides.forEach(function (slide, index) { slide.hidden = index !== next; slide.classList.toggle("is-active", index === next); });
            controls.forEach(function (item, index) { item.setAttribute("aria-pressed", String(index === next)); });
            currentSlide = next;
            if (window.gsap && !reduceMotion.matches) window.gsap.fromTo(slides[next], { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: .35, ease: "power2.out" });
        });
    });

    if (!window.gsap || !window.ScrollTrigger) return;
    var gsap = window.gsap;
    gsap.registerPlugin(window.ScrollTrigger);
    var media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", function () {
        gsap.from(".hero-copy > *", { opacity: 0, y: 20, duration: .8, stagger: .1, ease: "power3.out", clearProps: "all" });
        gsap.from(".workspace-preview", { opacity: 0, y: 10, duration: .7, delay: .3, ease: "power3.out", clearProps: "all" });
        document.querySelectorAll(".service-art").forEach(function (art) {
            gsap.timeline({ scrollTrigger: { trigger: art.closest(".card"), start: "top bottom", end: "bottom top", scrub: .6 } })
                .fromTo(art, { scale: .8, opacity: .25 }, { scale: 1, opacity: 1, duration: 1, ease: "none" })
                .to(art, { scale: .95, opacity: .3, duration: 1, ease: "none" });
        });
        document.querySelectorAll(".workflow-step").forEach(function (step) {
            gsap.fromTo(step.querySelectorAll("[data-reveal-word]"), { opacity: .25 }, { opacity: 1, stagger: .18, ease: "none", scrollTrigger: { trigger: step, start: "top 85%", end: "bottom 60%", scrub: .6 } });
        });
    });
}());
