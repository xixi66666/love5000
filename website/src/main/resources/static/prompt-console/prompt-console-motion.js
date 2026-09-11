(function () {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function onReady(callback) {
        if (document.readyState !== "loading") {
            callback();
        } else {
            document.addEventListener("DOMContentLoaded", callback);
        }
    }

    onReady(function () {
        if (reduce || typeof window.gsap === "undefined" || typeof window.ScrollTrigger === "undefined") {
            return;
        }

        var gsap = window.gsap;
        var ScrollTrigger = window.ScrollTrigger;
        gsap.registerPlugin(ScrollTrigger);

        // Hero entrance
        var heroTl = gsap.timeline({ defaults: { ease: "power3.out" } });
        heroTl
            .from(".hero-title", { y: 46, opacity: 0, duration: 1.1 })
            .from(".hero-copy", { y: 24, opacity: 0, duration: 0.8 }, "-=0.55")
            .from(".hero-actions .btn", { y: 18, opacity: 0, stagger: 0.12, duration: 0.7 }, "-=0.55")
            .from(".hero-hint", { opacity: 0, duration: 0.5 }, "-=0.25");

        // Hero media parallax
        gsap.to(".hero-media", {
            yPercent: 10,
            ease: "none",
            scrollTrigger: {
                trigger: ".hero",
                start: "top top",
                end: "bottom top",
                scrub: true
            }
        });

        // Capabilities bento entrance
        gsap.from(".bento-card", {
            y: 44,
            opacity: 0,
            stagger: 0.08,
            duration: 0.9,
            ease: "power3.out",
            scrollTrigger: {
                trigger: ".capabilities",
                start: "top 82%"
            }
        });

        // Image scale & fade for the capabilities photo card
        var bentoPhoto = document.querySelector(".bento-photo");
        if (bentoPhoto) {
            gsap.fromTo(bentoPhoto, { scale: 0.9, opacity: 0.6 }, {
                scale: 1,
                opacity: 1,
                ease: "power1.out",
                scrollTrigger: {
                    trigger: ".bento-card-img",
                    start: "top 88%",
                    end: "bottom 45%",
                    scrub: true
                }
            });
        }

        // Infinite marquee
        var track = document.querySelector(".marquee-track");
        if (track) {
            track.innerHTML += track.innerHTML;
            track.style.animation = "none";
            gsap.to(track, {
                xPercent: -50,
                ease: "none",
                duration: 44,
                repeat: -1
            });
        }

        window.addEventListener("load", function () {
            ScrollTrigger.refresh();
        });
    });
})();