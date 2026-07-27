import React, { useEffect, useRef, useState } from "react";

const checkIsMobile = () => {
  if (typeof window === "undefined") return false;
  const mobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  const smallScreen = window.innerWidth < 1024;
  return mobileUA || smallScreen;
};

export function LiquidVideoCanvas({ 
  videoUrl, 
  scrollProgress, 
  onVideoError,
  onVideoReady,
  onEntranceComplete
}) {
  const videoRef = useRef(null);
  const targetPercentRef = useRef(0);
  const smoothPercentRef = useRef(0);
  const consecutiveErrorsRef = useRef(0);
  const [isMobile, setIsMobile] = useState(() => checkIsMobile());
  const isMobileRef = useRef(isMobile);

  useEffect(() => {
    isMobileRef.current = isMobile;
  }, [isMobile]);

  const onVideoReadyRef = useRef(onVideoReady);
  const onEntranceCompleteRef = useRef(onEntranceComplete);
  const onVideoErrorRef = useRef(onVideoError);

  useEffect(() => {
    onVideoReadyRef.current = onVideoReady;
    onEntranceCompleteRef.current = onEntranceComplete;
    onVideoErrorRef.current = onVideoError;
  }, [onVideoReady, onEntranceComplete, onVideoError]);

  const entrancePhaseRef = useRef("loading");
  const entranceStartTimeRef = useRef(null);
  const hasNotifiedReadyRef = useRef(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(checkIsMobile());
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    entrancePhaseRef.current = "loading";
    entranceStartTimeRef.current = null;
    hasNotifiedReadyRef.current = false;
  }, [videoUrl]);

  useEffect(() => {
    targetPercentRef.current = scrollProgress;
  }, [scrollProgress]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (videoUrl) {
      video.currentTime = 0;
      video.preload = "auto";
      video.load();
    }

    let rafId;
    let isSeeking = false;
    let nextSeekTime = null;

    const safetyTimeout = setTimeout(() => {
      if (entrancePhaseRef.current === "loading") {
        entrancePhaseRef.current = "animating";
        entranceStartTimeRef.current = performance.now();
        if (onVideoReadyRef.current && !hasNotifiedReadyRef.current) {
          hasNotifiedReadyRef.current = true;
          onVideoReadyRef.current();
        }
      }
    }, 3500);

    const checkViewportAndConfig = () => {
      video.autoplay = false;
      video.pause();
    };

    const handleSeeking = () => {
      isSeeking = true;
    };

    const handleSeeked = () => {
      isSeeking = false;
      if (nextSeekTime !== null) {
        const target = nextSeekTime;
        nextSeekTime = null;
        if (video.readyState >= 1 && video.duration > 0) {
          isSeeking = true;
          video.currentTime = target;
        }
      }
    };

    video.addEventListener("seeking", handleSeeking);
    video.addEventListener("seeked", handleSeeked);
    video.addEventListener("loadedmetadata", checkViewportAndConfig);
    checkViewportAndConfig();

    const tick = () => {
      const targetPercent = targetPercentRef.current;
      let smoothPercent = smoothPercentRef.current;

      smoothPercent += (targetPercent - smoothPercent) * 0.12;

      if (Math.abs(targetPercent - smoothPercent) < 0.0001) {
        smoothPercent = targetPercent;
      }

      smoothPercentRef.current = smoothPercent;

      const subtleBaseProgress = Math.max(0, Math.min(1, (smoothPercent - 0.1) / 0.45));
      const progressiveFactor = Math.max(0, Math.min(1, (smoothPercent - 0.55) / 0.4));
      
      const blurVal = (subtleBaseProgress * 5) + (progressiveFactor * 50);
      const scaleVal = 1.03 + Math.max(0, Math.min(1, (smoothPercent - 0.1) / 0.9)) * 0.08;

      let entranceZoom = 1.0;
      let entranceOpacity = 1.0;

      if (entrancePhaseRef.current === "loading") {
        entranceZoom = 1.12;
        entranceOpacity = 0;
        
        if (video && video.readyState >= 3) {
          entrancePhaseRef.current = "animating";
          entranceStartTimeRef.current = performance.now();
          if (onVideoReadyRef.current && !hasNotifiedReadyRef.current) {
            hasNotifiedReadyRef.current = true;
            onVideoReadyRef.current();
          }
        }
      }

      if (entrancePhaseRef.current === "animating") {
        const startTime = entranceStartTimeRef.current || performance.now();
        const duration = 1400;
        const elapsed = performance.now() - startTime;
        const progress = Math.min(1, elapsed / duration);

        const easeOut = 1 - Math.pow(1 - progress, 3);
        
        entranceZoom = 1.12 - 0.12 * easeOut;
        entranceOpacity = Math.min(1.0, elapsed / 500);

        if (progress >= 1) {
          entrancePhaseRef.current = "complete";
          if (onEntranceCompleteRef.current) {
            onEntranceCompleteRef.current();
          }
        }
      }

      if (video) {
        video.style.filter = `blur(${blurVal}px)`;
        video.style.transform = `scale(${scaleVal * entranceZoom})`;
        video.style.opacity = `${entranceOpacity}`;
      }

      if (video.readyState >= 1 && video.duration > 0) {
        const calculatedTime = smoothPercent * video.duration;
        const clampedTime = Math.max(0, Math.min(video.duration, calculatedTime));
        
        if (Math.abs(video.currentTime - clampedTime) > 0.008) {
          if (!isSeeking && !video.seeking) {
            isSeeking = true;
            video.currentTime = clampedTime;
          } else {
            nextSeekTime = clampedTime;
          }
        }
      }

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);

    const handleResize = () => {
      checkViewportAndConfig();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      clearTimeout(safetyTimeout);
      cancelAnimationFrame(rafId);
      video.removeEventListener("seeking", handleSeeking);
      video.removeEventListener("seeked", handleSeeked);
      video.removeEventListener("loadedmetadata", checkViewportAndConfig);
      window.removeEventListener("resize", handleResize);
    };
  }, [videoUrl]);

  const handleVideoError = (e) => {
    console.warn("LiquidVideoCanvas: Video source error or load interruption.", e);
    consecutiveErrorsRef.current += 1;
    
    if (consecutiveErrorsRef.current <= 3 && onVideoErrorRef.current) {
      setTimeout(() => {
        onVideoErrorRef.current();
      }, 1000);
    }
  };

  const handleLoadedData = () => {
    consecutiveErrorsRef.current = 0;
  };

  return (
    <div className="fixed inset-0 w-full h-full overflow-hidden select-none bg-black z-[1]">
      <video
        ref={videoRef}
        src={videoUrl || undefined}
        id="scrubbable-liquid-video"
        loop
        muted
        playsInline
        preload="auto"
        onError={handleVideoError}
        onLoadedData={handleLoadedData}
        style={{
          opacity: 0,
          willChange: "transform, filter, opacity",
        }}
        className="absolute inset-0 w-full h-full object-cover pointer-events-none"
      />
    </div>
  );
}
