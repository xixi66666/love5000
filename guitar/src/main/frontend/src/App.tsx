import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView } from 'framer-motion';
import { Menu, X } from 'lucide-react';

const videos = [
  {
    url: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260702_081127_0992a171-d3c6-4978-8213-0ec5df8b6d63.mp4',
    label: 'Golden Hour'
  },
  {
    url: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260702_092026_dd05b805-ea0f-40b2-8c52-332b88502592.mp4',
    label: 'Still Water'
  },
  {
    url: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260702_081042_df7202bf-bd80-4b2b-bbc6-1f09ba2870e9.mp4',
    label: 'Deep Woods'
  },
  {
    url: 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260702_080959_4cac5234-3573-464e-a5b7-76b94b8a7d61.mp4',
    label: 'Quiet Dawn'
  }
];

const stats = ['60+ Deep Sessions', '12,000+ Creators', '4.8 User Satisfaction', 'Intentional-First Design'];
const navLinks = ['How It Works', 'Features', 'Pricing', 'Community'];

function StaggeredFade({ text }: { text: string }) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });

  return (
    <span ref={ref} className="inline-flex flex-wrap justify-center leading-[1.08]">
      {Array.from(text).map((char, index) => (
        <motion.span
          key={`${text}-${index}`}
          className="inline-block"
          initial={{ opacity: 0, y: 24 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
          transition={{ duration: 0.45, delay: index * 0.07, ease: 'easeOut' }}
        >
          {char === ' ' ? '\u00A0' : char}
        </motion.span>
      ))}
    </span>
  );
}

export default function App() {
  const [activeVideo, setActiveVideo] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsTransitioning(false), 1000);
    return () => window.clearTimeout(timer);
  }, [activeVideo]);

  const contentDark = activeVideo === 2;

  const handleSwitch = (index: number) => {
    if (index === activeVideo || isTransitioning) return;
    setIsTransitioning(true);
    setActiveVideo(index);
  };

  const contentTone = contentDark ? 'text-[#182C41]' : 'text-white';
  const contentMuted = contentDark ? 'text-[#182C41]/80' : 'text-white/70';
  return (
    <section className="relative h-screen w-full overflow-hidden bg-black">
      <div className="absolute inset-0">
        {videos.map((video, index) => (
          <video
            key={video.label}
            className={`absolute inset-0 h-full w-full object-cover object-center transition-opacity duration-1000 ease-in-out ${
              index === activeVideo ? 'opacity-100' : 'opacity-0'
            }`}
            src={video.url}
            autoPlay
            muted
            loop
            playsInline
            aria-hidden="true"
          />
        ))}
        <div className="absolute inset-0 z-[1] bg-black/45" />
        <img
          src="https://soft-zoom-63098134.figma.site/_assets/v11/0b4a435b2df2747593c43d7a1c9b4578f7d8d90c.png"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-[1] h-full w-full animate-[train-bob_3s_ease-in-out_infinite] scale-[1.03] object-cover object-center"
        />
      </div>

      <div className="relative z-20 flex h-full flex-col">
        <header className="relative z-20">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 pt-5 sm:px-8 sm:pt-6 md:px-10">
            <a
              href="/"
              className="font-garamond text-xl font-normal italic tracking-[0.3em] text-white sm:text-2xl"
            >
              Lumora
            </a>

            <div className="hidden items-center gap-3 md:flex">
              <div className="liquid-glass flex items-center gap-6 rounded-full px-6 py-3">
                {navLinks.map(link => (
                  <a
                    key={link}
                    href="/"
                    className="text-sm font-light tracking-[0.2em] text-white/90 transition-colors duration-300 hover:text-white"
                  >
                    {link}
                  </a>
                ))}
              </div>
              <a
                href="/"
                className="rounded-full bg-white px-5 py-3 text-sm font-medium tracking-[0.14em] text-black transition-transform duration-300 hover:scale-[1.02]"
              >
                Get Started
              </a>
            </div>

            <button
              type="button"
              aria-label="Toggle menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(open => !open)}
              className="liquid-glass grid h-12 w-12 place-items-center rounded-full text-white md:hidden"
            >
              <span className="relative h-[22px] w-[22px]">
                <motion.span
                  className="absolute inset-0 flex items-center justify-center"
                  animate={menuOpen ? { rotate: 90, scale: 0.75, opacity: 0 } : { rotate: 0, scale: 1, opacity: 1 }}
                  transition={{ duration: 0.3, ease: 'easeInOut' }}
                >
                  <Menu size={22} />
                </motion.span>
                <motion.span
                  className="absolute inset-0 flex items-center justify-center"
                  animate={menuOpen ? { rotate: 0, scale: 1, opacity: 1 } : { rotate: -90, scale: 0.75, opacity: 0 }}
                  transition={{ duration: 0.3, ease: 'easeInOut' }}
                >
                  <X size={22} />
                </motion.span>
              </span>
            </button>
          </div>
        </header>

        <AnimatePresence>
          {menuOpen ? (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
              className="fixed left-4 right-4 top-16 z-50 md:hidden"
            >
              <div className="mobile-menu-glass flex flex-col items-center justify-center gap-5 rounded-2xl px-6 py-8">
                {navLinks.map((link, index) => (
                  <motion.a
                    key={link}
                    href="/"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 16 }}
                    transition={{ duration: 0.5, delay: 0.1 + index * 0.05, ease: [0.4, 0, 0.2, 1] }}
                    className="text-3xl font-light tracking-[0.25em] text-white/90 hover:text-white"
                  >
                    {link}
                  </motion.a>
                ))}
                <motion.a
                  href="/"
                  initial={{ opacity: 0, y: 16, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 16, scale: 0.96 }}
                  transition={{ duration: 0.5, delay: 0.3, ease: [0.4, 0, 0.2, 1] }}
                  className="rounded-full bg-white px-6 py-3 text-sm font-medium tracking-[0.16em] text-black"
                >
                  Get Started
                </motion.a>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div className="relative z-10 flex flex-1 flex-col px-5 pb-5 pt-12 sm:px-8 sm:pt-16 md:px-10 md:pt-24">
          <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col items-center justify-center text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className={`liquid-glass mb-6 rounded-full px-5 py-2 text-[11px] font-light uppercase tracking-[0.22em] ${contentTone} transition-colors duration-700 sm:mb-8`}
            >
              Over 10,000 minds already finding their clarity
            </motion.div>

            <motion.h1
              className={`mx-auto mb-6 max-w-4xl font-garamond text-4xl font-normal leading-[1.1] tracking-tight transition-colors duration-700 sm:mb-8 sm:text-5xl md:text-7xl lg:text-[5.5rem] ${contentTone}`}
            >
              <span className="block">
                <StaggeredFade text="Clarity in an Endlessly" />
              </span>
              <span className="block">
                <StaggeredFade text="Noisy Universe" />
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 1.6, ease: 'easeOut' }}
              className={`mx-auto mb-8 max-w-xl text-sm font-light leading-relaxed transition-colors duration-700 sm:mb-10 sm:text-base md:text-lg ${contentMuted}`}
            >
              Rise above the chaos of pings, infinite scrolling, and relentless demands.
              <span className="hidden sm:inline"> </span>
              <br className="hidden sm:block" />
              Discover how to protect your presence and create with intention.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 2, ease: 'easeOut' }}
              className="mb-8 w-full max-w-xs sm:mb-10 sm:max-w-sm"
            >
              <div className="liquid-glass flex items-center gap-2 rounded-full p-1.5">
                <input
                  type="email"
                  placeholder="Your Best Email"
                  className="min-w-0 flex-1 bg-transparent px-4 py-3 text-[13px] font-light text-white outline-none placeholder:text-white/45 sm:text-sm"
                />
                <button
                  type="button"
                  className="rounded-full bg-white px-4 py-3 text-[11px] font-medium uppercase tracking-[0.18em] text-black transition-transform duration-300 hover:scale-[1.01] sm:px-6 sm:text-xs sm:tracking-[0.2em]"
                >
                  Get Early Access
                </button>
              </div>
            </motion.div>

            <div className={`mb-8 flex flex-wrap items-center justify-center gap-3 text-xs font-light uppercase transition-colors duration-700 sm:text-sm ${contentTone}`}>
              {videos.map((video, index) => {
                const active = index === activeVideo;
                return (
                  <button
                    key={video.label}
                    type="button"
                    onClick={() => handleSwitch(index)}
                    className={`border-b px-2 pb-2 transition-all duration-300 ${
                      active
                        ? `${contentTone === 'text-white' ? 'border-white bg-white/10' : 'border-[#182C41] bg-[#182C41]/10'} opacity-100`
                        : 'border-transparent opacity-50 hover:opacity-80'
                    }`}
                    disabled={isTransitioning}
                  >
                    {video.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-auto hidden items-center justify-center gap-4 border-t border-white/15 pt-5 text-white/70 md:flex">
            {stats.map((stat, index) => (
              <span key={stat} className="text-xs font-light uppercase tracking-[0.16em] sm:text-sm">
                {stat}
                {index < stats.length - 1 ? <span className="ml-4 text-white/30">|</span> : null}
              </span>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        html, body, #root {
          height: 100%;
          margin: 0;
        }
      `}</style>
    </section>
  );
}
