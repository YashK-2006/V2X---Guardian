import React from 'react';



interface StatsCardProps {

  title: string;

  value: string | number;

  change?: string;

  icon: React.ReactNode;

  color: 'indigo' | 'cyan' | 'emerald' | 'amber' | 'rose';

}



export const StatsCard: React.FC<StatsCardProps> = ({ title, value, change, icon, color }) => {

  const colorMap = {

    indigo: 'text-indigo-400',

    cyan: 'text-cyan-400',

    emerald: 'text-emerald-400',

    amber: 'text-amber-400',

    rose: 'text-rose-400'

  };



  const bgMap = {

    indigo: 'bg-indigo-500/10',

    cyan: 'bg-cyan-500/10',

    emerald: 'bg-emerald-500/10',

    amber: 'bg-amber-500/10',

    rose: 'bg-rose-500/10'

  };



  return (

    <div className="stat-card">

      <div className="flex justify-between items-start mb-2">

        <h3 className="text-gray-400 text-sm font-medium">{title}</h3>

        <div className={`p-2 rounded-lg ${bgMap[color]} ${colorMap[color]}`}>

          {icon}

        </div>

      </div>

      <div className="flex items-baseline gap-2">

        <span className="text-2xl font-bold text-gray-100">{value}</span>

        {change && (

          <span className={`text-xs font-medium ${change.startsWith('+') ? 'text-emerald-400' : 'text-rose-400'}`}>

            {change}

          </span>

        )}

      </div>

    </div>

  );

};
