'use client';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
const Context = createContext<{ lowBandwidth: boolean; toggleLowBandwidth: () => void } | null>(null);
export function LowBandwidthProvider({ children }: { children: React.ReactNode }) {
  const [lowBandwidth,setLowBandwidth]=useState(false);
  useEffect(()=>{setLowBandwidth(localStorage.getItem('public-works-low-bandwidth')==='true');},[]);
  const toggleLowBandwidth=useCallback(()=>setLowBandwidth(value=>{const next=!value;localStorage.setItem('public-works-low-bandwidth',String(next));document.documentElement.classList.toggle('low-bandwidth',next);return next;}),[]);
  useEffect(()=>{document.documentElement.classList.toggle('low-bandwidth',lowBandwidth);},[lowBandwidth]);
  return <Context.Provider value={{lowBandwidth,toggleLowBandwidth}}>{children}</Context.Provider>;
}
export function usePreferences(){const value=useContext(Context);if(!value)throw new Error('usePreferences must be used within LowBandwidthProvider');return value;}
