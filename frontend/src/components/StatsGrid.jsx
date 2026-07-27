import React from "react";
import { Swiper, SwiperSlide } from "swiper/react";
import { EffectCoverflow } from "swiper/modules";

// Import Swiper core and required modules styles
import "swiper/css";
import "swiper/css/effect-coverflow";

export function StatsGrid() {
  const cards = [
    {
      title: "RAG HEALTH INDEX",
      value: "98.2%",
      footer: "ACTIVE DOCUMENT RETRIEVAL",
      details: [
        "1024 chunks processed in real-time",
        "Low vector distance (0.12 threshold)",
        "Metadata mapping match active"
      ]
    },
    {
      title: "EXPECTED THREAT (xT)",
      value: "0.91 xT",
      footer: "TACTICAL EXPECTED THREAT FLOW",
      details: [
        "Dangerous zone progression tracked",
        "Deep threat vector calculation",
        "High-availability flow prediction"
      ]
    },
    {
      title: "DEFENSIVE COMPACTNESS",
      value: "12.4m",
      footer: "BLOC DEFENSIVE COHERENCE",
      details: [
        "Dynamic team compactness index",
        "Defensive line coordinate tracking",
        "Inter-line pass suppression active"
      ]
    },
    {
      title: "PRESSING INTENSITY",
      value: "7.8 PPDA",
      footer: "PASSES PER DEFENSIVE ACTION",
      details: [
        "High opponent build-up pressure",
        "Active pressing triggers registered",
        "Defensive recovery coefficient: 1.25"
      ]
    },
    {
      title: "MODEL COHERENCE",
      value: "94.6%",
      footer: "PREDICTIVE TACTICAL ALIGNMENT",
      details: [
        "Reinforced model state coherence",
        "Context window optimization active",
        "Transformer-based tactical routing"
      ]
    }
  ];

  const css = `
    .Carousal_003 {
      width: 100%;
      height: 520px;
      padding-bottom: 20px !important;
      overflow: visible !important;
    }
    
    .Carousal_003 .swiper-slide {
      background-position: center;
      background-size: cover;
      width: 380px;
      max-width: 85%;
      height: 480px;
    }
  `;

  return (
    <div id="edra-stats-panel" className="w-full pointer-events-auto">
      <style>{css}</style>
      
      <Swiper
        effect="coverflow"
        grabCursor={true}
        slidesPerView="auto"
        centeredSlides={true}
        loop={false}
        observer={true}
        observeParents={true}
        spaceBetween={32}
        coverflowEffect={{
          rotate: 30,
          stretch: 0,
          depth: 100,
          modifier: 1,
          slideShadows: false,
        }}
        className="Carousal_003"
        modules={[EffectCoverflow]}
      >
        {cards.map((card, index) => (
          <SwiperSlide key={index}>
            <div className="double-glass-outer h-[480px] flex flex-col justify-between">
              <div className="double-glass-inner flex flex-col justify-between h-full">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-bold text-white uppercase tracking-[0.08em] opacity-80">
                      {card.title}
                    </span>
                  </div>

                  <div className="mt-[24px] text-left">
                    <span className="font-sans font-normal text-[60px] md:text-[68px] lg:text-[76px] tracking-[-0.04em] text-white leading-none block">
                      {card.value}
                    </span>
                  </div>
                </div>

                <div className="space-y-2 pt-4">
                  {card.details.map((detail, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-[11px] text-white/60 font-medium">
                      <span className="w-1.5 h-1.5 rounded-full bg-white/30 mt-1 shrink-0" />
                      <span>{detail}</span>
                    </div>
                  ))}
                </div>

                <div className="pt-3 pb-0">
                  <span className="font-mono text-[10px] font-medium text-white/55 uppercase tracking-widest block truncate">
                    {card.footer}
                  </span>
                </div>
              </div>
            </div>
          </SwiperSlide>
        ))}
      </Swiper>
    </div>
  );
}
