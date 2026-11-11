"use client";
import { Fragment, useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import type { Network } from "@/lib/api";

// 색은 네 가지 의미만 쓴다: 주황=출발(반품), 검정=허브, 초록=확정 경로, 회색=후보·배경
const C = { amber: "#F59E0B", ink: "#0B1513", green: "#0E9F6E", grey: "#A7B3B0", faint: "#C9D3D0" };
const R = 6371, rad = (d: number) => d * Math.PI / 180;
const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) =>
  2 * R * Math.asin(Math.sqrt(Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2)) * 1.3;

function Fit({ pts }: { pts: [number, number][] }) {
  const map = useMap();
  const key = JSON.stringify(pts);
  useEffect(() => { if (pts.length > 1) map.fitBounds(pts, { padding: [70, 70], maxZoom: 15 }); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function LiveMap({ net, focus, mode }: { net: Network; focus?: string; mode: "mine" | "city" }) {
  const hub = Object.fromEntries(net.hubs.map(h => [h.hub_id, h]));
  const order = Object.fromEntries(net.orders.map(o => [o.order_id, o]));
  const ret = Object.fromEntries(net.returns.map(r => [r.return_id, r]));
  const me = focus ? ret[focus] : undefined;
  const myMatch = net.matches.find(m => m.return_id === focus);
  const myHub = me ? hub[myMatch?.hub_id ?? me.nearest_hub] : undefined;
  const candidates = me && myHub
    ? net.orders.filter(o => o.sku === me.sku && (o.status === "open" || o.order_id === myMatch?.order_id))
      .map(o => ({ o, d: km(myHub, o) })).sort((a, b) => a.d - b.d).slice(0, 3)
    : [];
  const mine = mode === "mine" && me && myHub;
  const fitPts: [number, number][] = mine ? [[me.lat, me.lng], [myHub.lat, myHub.lng], ...candidates.map(c => [c.o.lat, c.o.lng] as [number, number])] : [];

  return (
    <MapContainer center={[35.225, 128.64]} zoom={11} scrollWheelZoom className="h-[560px] w-full">
      <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" attribution="&copy; OpenStreetMap &copy; CARTO" />
      {mine && <Fit pts={fitPts} />}
      {/* 배경 레이어: 내 반품 모드에서는 작은 회색 점으로 물린다 */}
      {net.orders.filter(o => o.status === "open").map(o => (
        <CircleMarker key={o.order_id} center={[o.lat, o.lng]} radius={mine ? 2.5 : 4}
          pathOptions={{ color: mine ? C.faint : C.grey, weight: 1, fillColor: mine ? C.faint : "#fff", fillOpacity: mine ? .7 : 1 }} />
      ))}
      {!mine && net.matches.map(m => {
        const h = hub[m.hub_id], o = order[m.order_id], r = ret[m.return_id];
        if (!h || !o || !r) return null;
        return <Polyline key={m.return_id} positions={[[r.lat, r.lng], [h.lat, h.lng], [o.lat, o.lng]]} pathOptions={{ color: C.green, weight: m.return_id === focus ? 5 : 2.5, opacity: m.return_id === focus ? 1 : .6 }}>
          <Tooltip sticky>{m.return_id} → {m.order_id} · {m.km_hub_buyer.toFixed(1)}km · +{m.cost_saved.toLocaleString("ko-KR")}원</Tooltip></Polyline>;
      })}
      {!mine && net.returns.filter(r => ["atp", "matched"].includes(r.status)).map(r => (
        <CircleMarker key={r.return_id} center={[r.lat, r.lng]} radius={5} pathOptions={{ color: "#fff", weight: 1.5, fillColor: C.amber, fillOpacity: 1 }}><Tooltip>{r.return_id} · {r.name}</Tooltip></CircleMarker>
      ))}
      {net.hubs.map(h => {
        const rel = !mine || h.hub_id === myHub?.hub_id;
        return (
          <CircleMarker key={h.hub_id} center={[h.lat, h.lng]} radius={rel ? 8 : 4} pathOptions={{ color: rel ? C.ink : C.faint, weight: 2, fillColor: rel ? C.ink : C.faint, fillOpacity: 1 }}>
            <Tooltip permanent={rel} direction="top" offset={[0, -8]}>{h.name}{mine && rel ? " · 검수" : ""}</Tooltip>
          </CircleMarker>
        );
      })}
      {/* 내 반품 레이어 */}
      {mine && candidates.map((c, i) => {
        const won = c.o.order_id === myMatch?.order_id;
        if (won) return null;
        return (
          <Fragment key={c.o.order_id}>
            <Polyline positions={[[myHub.lat, myHub.lng], [c.o.lat, c.o.lng]]} pathOptions={{ color: C.grey, weight: 2, dashArray: "6 6" }} />
            <CircleMarker center={[c.o.lat, c.o.lng]} radius={7} pathOptions={{ color: C.grey, weight: 2, fillColor: "#fff", fillOpacity: 1 }}>
              <Tooltip permanent direction="right" offset={[8, 0]}>{`후보 ${i + 1} · ${c.d.toFixed(1)}km`}</Tooltip>
            </CircleMarker>
          </Fragment>
        );
      })}
      {mine && myMatch && order[myMatch.order_id] && (
        <>
          <Polyline positions={[[me.lat, me.lng], [myHub.lat, myHub.lng], [order[myMatch.order_id].lat, order[myMatch.order_id].lng]] as LatLngExpression[]} pathOptions={{ color: C.green, weight: 5 }}>
            <Tooltip sticky>{`허브 → 구매자 ${myMatch.km_hub_buyer.toFixed(1)}km · +${myMatch.cost_saved.toLocaleString("ko-KR")}원`}</Tooltip>
          </Polyline>
          <CircleMarker center={[order[myMatch.order_id].lat, order[myMatch.order_id].lng]} radius={9} pathOptions={{ color: C.green, weight: 3, fillColor: "#fff", fillOpacity: 1 }}>
            <Tooltip permanent direction="right" offset={[10, 0]}>{`다음 구매자 · ${myMatch.km_hub_buyer.toFixed(1)}km`}</Tooltip>
          </CircleMarker>
        </>
      )}
      {mine && (
        <CircleMarker center={[me.lat, me.lng]} radius={9} pathOptions={{ color: "#fff", weight: 2, fillColor: C.amber, fillOpacity: 1 }}>
          <Tooltip permanent direction="left" offset={[-10, 0]}>반품 출발</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
