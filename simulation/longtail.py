import pandas as pd
from r_route_sim import simulate, kpis
rows=[]
for n_sku in [2000, 20000]:
    for z in [0.8, 1.1]:
        P,W,O,R,B,X = simulate(n_sku=n_sku, zipf_s=z)
        K = kpis(R,B,X,P)
        top1 = W["pop"][:int(0.01*n_sku)].sum()*100
        rows.append(dict(n_sku=n_sku, zipf_s=z, top1pct_share=top1,
            match_pct=K.loc["직송 매칭률(%, 직송가능 대비)","R_ROUTE"],
            km_cut_pct=100*(1-K.loc["반품 1건 평균 이동거리(km)","R_ROUTE"]/K.loc["반품 1건 평균 이동거리(km)","기존 방식"]),
            cost_cut_pct=100*(1-K.loc["반품 1건 물류비(원)","R_ROUTE"]/K.loc["반품 1건 물류비(원)","기존 방식"]),
            co2_cut_pct=100*(1-K.loc["반품 1건 CO2(kg)","R_ROUTE"]/K.loc["반품 1건 CO2(kg)","기존 방식"]),
            resale_R=K.loc["직송가능 반품 재판매 소요(일)","R_ROUTE"], resale_B=K.loc["직송가능 반품 재판매 소요(일)","기존 방식"],
            refund_R=K.loc["평균 환불 소요(일)","R_ROUTE"]))
S=pd.DataFrame(rows); pd.set_option("display.width",250); print(S.round(2))
S.round(3).to_csv("sensitivity_longtail.csv",index=False,encoding="utf-8-sig")
