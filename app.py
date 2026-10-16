"""Decision support dashboard. Run: streamlit run app.py."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.allocation import allocate,SECTORS

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='Urban Water Intelligence',page_icon='💧',layout='wide')
st.markdown('''<style>.stApp {background:#f4f8fb;} h1,h2,h3 {color:#102f48;}
[data-testid="stMetric"] {background:white;border:1px solid #d8e5ed;border-radius:12px;padding:12px;}
[data-testid="stMetricValue"] {font-size:1.5rem;}
.block-container {padding-top:4rem;}
[data-testid="stMetricValue"] {overflow:visible;white-space:normal;}
</style>''',unsafe_allow_html=True)
# Larger text for native high-resolution report captures; data stays unchanged.
if st.query_params.get('capture') == 'hd':
    st.markdown('<style>html {font-size:36px;} [data-testid="stMetricValue"] {font-size:1.5rem;} </style>',unsafe_allow_html=True)
def show_plot(figure, **kwargs):
    if st.query_params.get('capture') == 'hd':
        figure.update_layout(font=dict(size=26),height=620)
    return st.plotly_chart(figure, **kwargs)

def show_frame(data, **kwargs):
    if st.query_params.get('capture') == 'hd':
        return st.table(data)
    return st.dataframe(data, **kwargs)

if not (ROOT/'results/summary.json').exists():
    st.error('Run python -m src.pipeline from the project folder first.');st.stop()

@st.cache_data
def load():
    summary=json.loads((ROOT/'results/summary.json').read_text())
    def csv(path): return pd.read_csv(ROOT/path,index_col=0,parse_dates=True)
    return summary,csv('data/processed/monthly_water_weather.csv'),csv('results/future_forecast.csv'),csv('results/test_predictions.csv'),csv('results/anomalies.csv')

summary,history,future,test,anomalies=load()
st.caption('DAV COMPLEX ENGINEERING PROBLEM  /  TIME SERIES ANALYSIS')
st.title('Urban Water Intelligence')
st.write('Forecast demand. Inspect unusual consumption. Plan water distribution under constraints.')
st.info('Historical demonstration: observed retail billing data, January 2012–December 2024. Forecast origin: December 2024; planning horizon: 2025. This is not a current 2026 forecast.')
st.sidebar.title('Planning controls')
period=st.sidebar.selectbox('Planning month',future.index.strftime('%Y-%m').tolist())
row=future.loc[pd.Timestamp(period)]
policy=st.sidebar.selectbox('Allocation policy',['Priority','Proportional'])
fraction=st.sidebar.slider('Available supply (% of demand)',0,120,75,5)
capacity_factor=st.sidebar.slider('Network capacity (% of sector demand)',20,120,100,5)
st.sidebar.caption('Scenario assumptions, not Austin operating policy. Minimum shares: residential 70%, commercial 35%, large volume 30%, municipal 90%. Municipal service is a priority-area proxy; no hospital-level data is available.')
st.sidebar.caption('Large volume is an industrial proxy. Wholesale and utility consumption are excluded.')
demand=row[SECTORS].to_numpy(dtype=float)
total=float(row.selected_forecast_mg); supply=total*fraction/100
capacity=demand*capacity_factor/100
table,status=allocate(demand,supply,policy,capacity)
c1,c2,c3,c4=st.columns(4)
c1.metric('Predicted demand',f'{total:,.1f} MG')
c2.metric('Available supply',f'{supply:,.1f} MG')
c3.metric('Supply gap',f'{max(total-supply,0):,.1f} MG')
c4.metric('Minimum service','Feasible' if status['feasible'] else 'INFEASIBLE')
st.caption('MG = million US gallons per month. 1 MG ≈ 3.785 million litres.')
tabs=st.tabs(['Forecast & evaluation','Consumption & weather','Stationarity & models','Abnormal consumption','Resource allocation','Data & downloads'])
with tabs[0]:
    st.subheader('Observed demand and planning forecast')
    chart=go.Figure()
    chart.add_scatter(x=history.index[-48:],y=history.total_mg.iloc[-48:],name='Observed',line=dict(color='#153c5b'))
    chart.add_scatter(x=future.index,y=future.selected_forecast_mg,name=summary['selected_model'],line=dict(color='#00a6a0',width=3))
    chart.add_scatter(x=future.index,y=future.ARIMA_upper95,name='ARIMA upper 95%',line=dict(width=0),showlegend=False)
    chart.add_scatter(x=future.index,y=future.ARIMA_lower95,name='ARIMA 95% interval',fill='tonexty',line=dict(width=0),fillcolor='rgba(0,166,160,.12)')
    chart.update_layout(yaxis_title='Million gallons / month',height=390,legend=dict(orientation='h'))
    show_plot(chart,width='stretch')
    st.caption('The shaded interval belongs to ARIMA only. It does not quantify uncertainty for the selected model when another model wins.')
    st.subheader('Model comparison on untouched observations')
    metrics=pd.read_csv(ROOT/'results/metrics.csv')
    show_frame(metrics[['model','validation_MAE','validation_RMSE','validation_MAPE','test_MAE','test_RMSE','test_MAPE']].round(3),hide_index=True,width='stretch')
    st.write(f"Selected by 2023 validation RMSE: **{summary['selected_model']}**. Model parameters never use the 2024 test set for selection. MAE/RMSE use MG; MAPE uses percent.")
    display=go.Figure()
    display.add_scatter(x=test.index,y=test.actual_mg,name='Actual',line=dict(color='black',width=3))
    for model in metrics.model: display.add_scatter(x=test.index,y=test[model],name=model)
    display.update_layout(height=360,yaxis_title='Million gallons / month',legend=dict(orientation='h'))
    show_plot(display,width='stretch')
with tabs[1]:
    st.subheader('Thirteen years of retail billing consumption')
    st.area_chart(history[SECTORS],color=['#123e5e','#00a6a0','#e5ad50','#8095b0'])
    a,b=st.columns(2)
    a.line_chart(history[['temperature_2m_mean']]);b.bar_chart(history[['precipitation_sum']])
    st.caption('Temperature in °C; monthly rainfall in mm. Weather: ERA5 reanalysis via Open-Meteo, aggregated from daily values. Correlation does not establish causality.')
    show_frame(history.groupby('month')[['total_mg','temperature_2m_mean','precipitation_sum']].mean().round(2),width='stretch')
    st.image(str(ROOT/'results/figures/decomposition.png'),caption='Robust STL decomposition with a 12-month seasonal period')
with tabs[2]:
    st.subheader(f"ARIMA order {tuple(summary['arima_order'])}")
    adfs=pd.DataFrame([{'difference_order':k,**{n:v for n,v in val.items() if n!='critical_values'}} for k,val in summary['adf_training'].items()])
    show_frame(adfs,hide_index=True)
    st.write('ADF null hypothesis: a unit root is present. p < 0.05 supports rejecting that null; it does not prove all forms of stationarity. The smallest supported difference order is used, then converged p,q ∈ {0,1,2} candidates are ranked by training AIC.')
    st.image(str(ROOT/'results/figures/stationarity.png'))
    st.image(str(ROOT/'results/figures/acf_pacf.png'))
    show_frame(pd.read_csv(ROOT/'results/arima_grid.csv'),hide_index=True,width='stretch')
    st.write(f"ARIMA residual Ljung–Box p-value at lag 12: {summary['ljung_box_12_pvalue']:.4g}. A small value suggests remaining serial dependence and supports investigating seasonal models.")
with tabs[3]:
    st.subheader('Months that need investigation')
    st.write('Compare each month with the same month one year earlier. Center and scale its residual using only the preceding 24 residuals (minimum 12); flag an absolute robust score above 3.5. Valid unusual observations are retained for modeling. The initial warm-up period is not scored.')
    st.image(str(ROOT/'results/figures/anomalies.png'))
    flagged=anomalies.loc[anomalies.flag.astype(str).str.lower()=='true']
    show_frame(flagged.round(3),width='stretch')
    st.caption('These are screening alerts, not confirmed leaks. Check billing adjustments, meter health, weather, restrictions and local events before action. No incident ground truth is available for precision/recall evaluation.')
with tabs[4]:
    st.subheader(f'Distribution scenario · {period}')
    (st.success if status['feasible'] else st.error)(status['action'])
    show_frame(table.round(2),hide_index=True,width='stretch')
    bars=go.Figure()
    for col,label,color in [('demand_mg','Predicted demand','#143e5b'),('minimum_mg','Minimum service','#e4ad4d'),('allocated_mg','Allocated','#00a6a0')]:
        bars.add_bar(x=table.sector,y=table[col],name=label,marker_color=color)
    bars.update_layout(barmode='group',yaxis_title='Million gallons / month',height=360)
    show_plot(bars,width='stretch')
    st.write(f"Unused supply due to demand/capacity limits: **{status['unused_supply_mg']:.2f} MG**. Unmet demand: **{table.shortfall_mg.sum():.2f} MG**.")
    st.write('Priority policy maximizes weighted served demand with weights municipal 5, residential 4, commercial 2 and large volume 1, while respecting service floors and network limits. Proportional policy distributes remaining supply in proportion to eligible unmet demand above the floors. If floors are infeasible, the emergency fallback explicitly reports violations.')
    st.caption('Sector forecasts use trailing 12-month measured shares. Network capacities, minimum-service fractions and priorities are adjustable planning assumptions; no hydraulic model or operational authorization is implied.')
    st.download_button('Download this allocation',table.to_csv(index=False),'allocation.csv','text/csv')
with tabs[5]:
    st.json(summary['audit'])
    st.write('[Austin residential data](https://data.austintexas.gov/d/sxk7-7k6z) · [Austin commercial data](https://data.austintexas.gov/d/5h9c-wmds) · [Weather data by Open-Meteo](https://open-meteo.com/)')
    st.caption('Water sources: City of Austin, Public Domain as stated in source metadata. Weather: CC BY 4.0; ERA5 via Open-Meteo. Source snapshots and SHA-256 hashes are included. Postal-code aggregates contain no customer identities.')
    for file in ['metrics.csv','future_forecast.csv','test_predictions.csv','anomalies.csv','allocation_scenarios.csv']:
        st.download_button('Download '+file,(ROOT/'results'/file).read_bytes(),file,'text/csv',key=file)
    show_frame(history,width='stretch')
