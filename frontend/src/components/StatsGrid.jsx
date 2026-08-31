import { Swiper, SwiperSlide } from "swiper/react";
import { EffectCoverflow } from "swiper/modules";

// Import Swiper core and required modules styles
import "swiper/css";
import "swiper/css/effect-coverflow";

export function StatsGrid() {
  const cards = [
    {
      title: "PIPELINE VIDÉO",
      value: "ACTIF",
      footer: "TRAITEMENT LOCAL",
      details: [
        "Ingestion et validation disponibles",
        "Vidéo annotée et JSON local",
        "Métriques tactiques non calculées"
      ]
    },
    {
      title: "DÉTECTEUR PAR DÉFAUT",
      value: "HOG",
      footer: "BASELINE PERSONNES SUR CPU",
      details: [
        "Fonctionne sans poids externe",
        "Détection du ballon indisponible",
        "Précision football non benchmarkée"
      ]
    },
    {
      title: "DÉTECTEUR FACULTATIF",
      value: "YOLO",
      footer: "CONFIGURATION EXPÉRIMENTALE",
      details: [
        "Dépendances vidéo séparées",
        "Poids local requis",
        "Profil H250 non validé golden"
      ]
    },
    {
      title: "SUIVI TEMPOREL",
      value: "EXP.",
      footer: "OBSERVATIONS ET PRÉDICTIONS SÉPARÉES",
      details: [
        "Tracking personnes limité",
        "Ballon couvert par tests synthétiques",
        "Validation terrain absente"
      ]
    },
    {
      title: "MÉTRIQUES TACTIQUES V1",
      value: "ABSENT",
      footer: "EN ATTENTE DES PRÉREQUIS",
      details: [
        "Équipes et calibration absentes",
        "État de jeu 2D indisponible",
        "Résultats non affichés comme calculés"
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
