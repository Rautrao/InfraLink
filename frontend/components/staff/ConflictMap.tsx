'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';

type Geometry=GeoJSON.Geometry|null;
export function ConflictMap({a,b,bufferA,bufferB}:{a:Geometry;b:Geometry;bufferA?:Geometry;bufferB?:Geometry}){
 const el=useRef<HTMLDivElement>(null);const mapRef=useRef<MapLibreMap|null>(null);
 useEffect(()=>{if(!el.current||mapRef.current)return;const map=new maplibregl.Map({container:el.current,center:[73.8567,18.5204],zoom:13,style:{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]}});mapRef.current=map;map.addControl(new maplibregl.NavigationControl({showCompass:false}));return()=>{map.remove();mapRef.current=null}},[]);
 useEffect(()=>{const map=mapRef.current;if(!map)return;const draw=()=>{const sources=[['work-a',a],['work-b',b],['buffer-a',bufferA],['buffer-b',bufferB]] as const;for(const [id,geometry] of sources){const data:GeoJSON.FeatureCollection={type:'FeatureCollection',features:geometry?[{type:'Feature',geometry,properties:{}}]:[]};const source=map.getSource(id) as maplibregl.GeoJSONSource|undefined;if(source)source.setData(data);else map.addSource(id,{type:'geojson',data});if(!map.getLayer(`${id}-line`)){map.addLayer({id:`${id}-line`,type:'line',source:id,paint:{'line-color':id.includes('a')?'#1565c0':'#c2410c','line-width':id.startsWith('buffer')?10:5,'line-opacity':id.startsWith('buffer') ? 0.24 : 0.98}})}};const bounds=new maplibregl.LngLatBounds();for(const geometry of [a,b]){const visit=(v:any)=>{if(!Array.isArray(v))return;if(typeof v[0]==='number'&&typeof v[1]==='number')bounds.extend(v as [number,number]);else v.forEach(visit)};if(geometry&&'coordinates'in geometry)visit(geometry.coordinates)}if(!bounds.isEmpty())map.fitBounds(bounds,{padding:48,maxZoom:15});};if(map.loaded())draw();else map.once('load',draw)},[a,b,bufferA,bufferB]);
 return <div ref={el} className="conflict-map" aria-label="Map comparing the two work geometries"/>;
}
