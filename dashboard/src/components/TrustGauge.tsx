import React from 'react';



interface TrustGaugeProps {

  score: number;

  size?: number;

  label?: string;

}



/** Circular trust gauge. Colours follow the backend thresholds: trusted ≥ 0.6, malicious < 0.3. */

export const TrustGauge: React.FC<TrustGaugeProps> = ({ score, size = 100, label }) => {

  const strokeWidth = size * 0.1;

  const radius = (size - strokeWidth) / 2;

  const circumference = radius * 2 * Math.PI;

  const strokeDashoffset = circumference - Math.max(0, Math.min(1, score)) * circumference;



  let color = '#f43f5e';

  if (score >= 0.6) color = '#10b981';

  else if (score >= 0.3) color = '#f59e0b';



  return (

    <div className="flex flex-col items-center justify-center">

      <div className="relative" style={{ width: size, height: size }}>

        <svg width={size} height={size} className="transform -rotate-90 trust-gauge-svg">

          <circle cx={size / 2} cy={size / 2} r={radius} stroke="rgba(148,163,184,0.14)" strokeWidth={strokeWidth} fill="none" />

          <circle

            cx={size / 2}

            cy={size / 2}

            r={radius}

            stroke={color}

            strokeWidth={strokeWidth}

            fill="none"

            strokeDasharray={circumference}

            strokeDashoffset={strokeDashoffset}

            className="trust-gauge-ring transition-all duration-1000 ease-out"

            strokeLinecap="round"

          />

        </svg>

        <div className="absolute inset-0 flex items-center justify-center">

          <span className="font-bold trust-gauge-value" style={{ color, fontSize: size * 0.2, textShadow: `0 0 18px ${color}55` }}>

            {(score * 100).toFixed(1)}

          </span>

        </div>

      </div>

      {label && <span className="mt-2 text-xs text-gray-400 font-medium">{label}</span>}

    </div>

  );

};
