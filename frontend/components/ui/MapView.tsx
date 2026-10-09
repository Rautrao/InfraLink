'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { GeoJSONSource, Map as MapLibreMap, LngLatBoundsLike } from 'maplibre-gl';
import type { Feature, FeatureCollection, Geometry, Point } from 'geojson';
import { useT } from '@/lib/i18n';

export type WorkProperties = { id: string; ref_no?: string; title?: string; status?: string; delayed?: boolean; category?: string; agency?: string; last_update_at?: string; [key: string]: unknown };
export type WorkFeature = Feature<Geometry, WorkProperties>;
function centerFor(feature: WorkFeature): [number, number] {
  const coords: number[][] = [];
  const visit = (value: unknown) => { if (!Array.isArray(value)) return; if (typeof value[0] === 'number' && typeof value[1] === 'number') coords.push(value as number[]); else value.forEach(visit); };
  visit((feature.geometry as any)?.coordinates);
  if (!coords.length) return [73.8567, 18.5204];
  return [coords.reduce((sum, p) => sum + p[0], 0) / coords.length, coords.reduce((sum, p) => sum + p[1], 0) / coords.length];
}
function syncMapData(map: MapLibreMap, data: FeatureCollection<Geometry, WorkProperties>, fitToken: number, lastFitToken: { current: number }) {
  const works=map.getSource('works') as GeoJSONSource|undefined;const markers=map.getSource('markers') as GeoJSONSource|undefined;
  if(!works||!markers)return;
  works.setData(data);
  const features=data.features.filter((item):item is WorkFeature=>!!item.geometry).map(feature=>({type:'Feature' as const,geometry:{type:'Point' as const,coordinates:centerFor(feature)},properties:{...feature.properties,source_id:String(feature.id??feature.properties.id)}}));
  markers.setData({type:'FeatureCollection',features} as FeatureCollection<Point,WorkProperties>);
  if(data.features.length&&lastFitToken.current!==fitToken){
    const points=data.features.flatMap(f=>{const coords:number[][]=[];const visit=(v:unknown)=>{if(!Array.isArray(v))return;if(typeof v[0]==='number'&&typeof v[1]==='number')coords.push(v as number[]);else v.forEach(visit);};if(f.geometry)visit((f.geometry as any).coordinates);return coords;});
    if(points.length){const bounds=points.reduce((b,p)=>b.extend(p as [number,number]),new maplibregl.LngLatBounds(points[0] as [number,number],points[0] as [number,number]));map.fitBounds(bounds,{padding:52,maxZoom:14,duration:450});}
    lastFitToken.current=fitToken;
  }
}

export function MapView({ data, onSelect, onBoundsChange, fitToken = 0, height = 460 }: {
  data: FeatureCollection<Geometry, WorkProperties>; onSelect?: (feature: WorkFeature) => void; onBoundsChange?: (bbox: string) => void; fitToken?: number; height?: number;
}) {
  const { t, language } = useT();
  const element = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelect); onSelectRef.current = onSelect;
  const onBoundsRef = useRef(onBoundsChange); onBoundsRef.current = onBoundsChange;
  const timer = useRef<number | undefined>(undefined);
  const lastFitToken = useRef(-1);
  const dataRef = useRef(data); dataRef.current = data;

  useEffect(() => {
    if (!element.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: element.current,
      center: [73.8567, 18.5204], zoom: 12,
      style: { version: 8, sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' }, works: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } as FeatureCollection }, markers: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } as FeatureCollection, cluster: true, clusterRadius: 48, clusterMaxZoom: 13 } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] },
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: false }, trackUserLocation: false }), 'top-right');
    map.on('load', () => {
      const statusColor:any=['case',['==',['get','delayed'],true],'#b42318',['match',['get','status'],'ongoing','#b45309','completed','#16804a','permitted','#4338ca','paused','#667085','restoration_verified','#0f766e','#2563eb']];
      map.addLayer({ id: 'work-fill', type: 'fill', source: 'works', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': statusColor, 'fill-opacity': 0.22 } });
      map.addLayer({ id: 'work-line', type: 'line', source: 'works', filter: ['!=',['get','delayed'],true], paint: { 'line-color': statusColor, 'line-width': 4, 'line-opacity': 0.9 } });
      map.addLayer({ id: 'work-delayed-outline', type: 'line', source: 'works', filter: ['==',['get','delayed'],true], paint: { 'line-color': '#b42318', 'line-width': 6, 'line-dasharray': [2, 1.5], 'line-opacity': 0.95 } });
      map.addLayer({ id: 'work-clusters', type: 'circle', source: 'markers', filter: ['has','point_count'], paint: { 'circle-color':'#164e63','circle-radius':['step',['get','point_count'],17,8,22,20,28],'circle-stroke-color':'#ffffff','circle-stroke-width':2 } });
      map.addLayer({ id: 'work-cluster-count', type: 'symbol', source: 'markers', filter: ['has','point_count'], layout: { 'text-field':['get','point_count_abbreviated'],'text-size':13 }, paint:{'text-color':'#ffffff'} });
      map.addLayer({ id: 'work-marker', type:'circle', source:'markers', filter:['!',['has','point_count']], paint:{'circle-color':['case',['==',['get','delayed'],true],'#b42318','#0e7490'],'circle-radius':7,'circle-stroke-color':'#fff','circle-stroke-width':2} });
      map.getContainer().querySelector('.maplibregl-ctrl-zoom-in')?.setAttribute('aria-label',t('zoomIn'));
      map.getContainer().querySelector('.maplibregl-ctrl-zoom-out')?.setAttribute('aria-label',t('zoomOut'));
      map.getContainer().querySelector('.maplibregl-ctrl-geolocate')?.setAttribute('aria-label',t('locate'));
      map.on('click','work-clusters',async(event)=>{ const feature=map.queryRenderedFeatures(event.point,{layers:['work-clusters']})[0]; const clusterId=feature?.properties?.cluster_id; if(clusterId===undefined)return; const source=map.getSource('markers') as GeoJSONSource; try{const zoom=await source.getClusterExpansionZoom(Number(clusterId));const center=(feature.geometry as Point).coordinates as [number,number];map.easeTo({center,zoom});}catch{return;} });
      const select = (event: maplibregl.MapMouseEvent) => { const feature=map.queryRenderedFeatures(event.point,{layers:['work-line','work-fill','work-marker']})[0] as unknown as WorkFeature | undefined; if(feature) onSelectRef.current?.(feature); };
      map.on('click','work-line',select); map.on('click','work-fill',select); map.on('click','work-marker',select);
      map.on('mouseenter','work-line',()=>map.getCanvas().style.cursor='pointer'); map.on('mouseleave','work-line',()=>map.getCanvas().style.cursor='');
      map.on('mouseenter','work-marker',()=>map.getCanvas().style.cursor='pointer'); map.on('mouseleave','work-marker',()=>map.getCanvas().style.cursor='');
      map.on('moveend',()=>{ if(timer.current) window.clearTimeout(timer.current); timer.current=window.setTimeout(()=>{ const b=map.getBounds(); onBoundsRef.current?.([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',')); },350); });
      ready.current=true;
      syncMapData(map,dataRef.current,fitToken,lastFitToken);
    });
    return () => { if(timer.current) window.clearTimeout(timer.current); map.remove(); mapRef.current=null; ready.current=false; };
  }, []);

  useEffect(()=>{const container=mapRef.current?.getContainer();container?.querySelector('.maplibregl-ctrl-zoom-in')?.setAttribute('aria-label',t('zoomIn'));container?.querySelector('.maplibregl-ctrl-zoom-out')?.setAttribute('aria-label',t('zoomOut'));container?.querySelector('.maplibregl-ctrl-geolocate')?.setAttribute('aria-label',t('locate'));},[language,t]);

  useEffect(() => {
    const map=mapRef.current; if(!map||!ready.current) return;
    syncMapData(map,data,fitToken,lastFitToken);
  }, [data, fitToken]);

  return <div className="map-shell"><div ref={element} style={{ height, width:'100%' }} role="application" aria-label={t('map')} /><button type="button" className="map-reset" onClick={()=>mapRef.current?.easeTo({center:[73.8567,18.5204],zoom:12})}>{t('reset')}</button></div>;
}
