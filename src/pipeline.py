"""Reproducible analysis. Run from repository root: python -m src.pipeline."""
from pathlib import Path
import json, hashlib, warnings, platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.seasonal import STL
from statsmodels.stats.diagnostic import acorr_ljungbox
from src.allocation import allocate, SECTORS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results'
FIG = OUT/'figures'

def metrics(actual, predicted):
    a,p = np.asarray(actual,float),np.asarray(predicted,float)
    mask = a != 0
    return {'MAE':float(np.mean(abs(a-p))), 'RMSE':float(np.sqrt(np.mean((a-p)**2))),
            'MAPE':float(np.mean(abs((a[mask]-p[mask])/a[mask]))*100) if mask.any() else None,
            'MAPE_nonzero_n':int(mask.sum())}

def clean_records(frame):
    required = ['year_month','postal_code','customer_class','total_gallons']
    if not set(required).issubset(frame):
        raise ValueError('Missing required water columns.')
    frame = frame[required].copy()
    n = len(frame)
    frame = frame.drop_duplicates()
    duplicates = n-len(frame)
    frame['date'] = pd.to_datetime(frame.year_month.astype(str),format='%Y%m',errors='coerce')
    frame['total_gallons'] = pd.to_numeric(frame.total_gallons,errors='coerce')
    invalid = frame.date.isna() | frame.total_gallons.isna() | ~np.isfinite(frame.total_gallons)
    if invalid.any():
        raise ValueError(f'{invalid.sum()} invalid records: repair source before aggregation.')
    if frame.duplicated(['date','postal_code','customer_class']).any():
        raise ValueError('Conflicting records for a month, postal code and customer class.')
    return frame, {'raw_rows':n,'exact_duplicates_removed':duplicates,
                   'negative_adjustment_rows':int((frame.total_gallons<0).sum())}

def load_data():
    res,ar = clean_records(pd.read_csv(ROOT/'data/raw/austin_residential.csv',dtype={'postal_code':str}))
    com,ac = clean_records(pd.read_csv(ROOT/'data/raw/austin_commercial.csv',dtype={'postal_code':str}))
    res['sector'] = 'Residential'
    mapping = {'Commercial':'Commercial','Irrigation - Commercial':'Commercial',
               'Large Volume':'Large volume','Irrigation - Large Volume':'Large volume',
               'City of Austin':'Municipal','Irrigation - City of Austin':'Municipal'}
    com['sector'] = com.customer_class.map(mapping)
    excluded = com.loc[com.sector.isna()].groupby('customer_class').total_gallons.sum().to_dict()
    records = pd.concat([res,com.loc[com.sector.notna()]],ignore_index=True)
    records = records.loc[records.date.between('2012-01-01','2024-12-01')]
    df = records.groupby(['date','sector']).total_gallons.sum().unstack().reindex(columns=SECTORS)/1e6
    index = pd.date_range('2012-01-01','2024-12-01',freq='MS')
    df = df.reindex(index)
    missing = int(df.isna().sum().sum())
    # Causal only: a missing month carries forward; leading gaps require source repair.
    df = df.ffill()
    if df.isna().any().any() or (df<0).any().any():
        raise ValueError('Leading gaps or negative monthly demand require manual source repair.')
    df['total_mg'] = df[SECTORS].sum(axis=1)
    weather = json.loads((ROOT/'data/raw/weather.json').read_text())['daily']
    w = pd.DataFrame(weather)
    w.index = pd.to_datetime(w.pop('time'))
    if w[['temperature_2m_mean','precipitation_sum']].isna().any().any():
        raise ValueError('Weather gaps require source repair.')
    w = w.resample('MS').agg({'temperature_2m_mean':'mean','precipitation_sum':'sum'})
    df = df.join(w)
    df['days_in_month'] = df.index.days_in_month
    df['weekend_days'] = [sum(d.weekday()>=5 for d in pd.date_range(t,t+pd.offsets.MonthEnd())) for t in df.index]
    df['month'] = df.index.month
    df['year'] = df.index.year
    df['rolling_mean_12'] = df.total_mg.rolling(12).mean()
    df['rolling_variance_12'] = df.total_mg.rolling(12).var()
    df.index.name='date'
    df.to_csv(ROOT/'data/processed/monthly_water_weather.csv')
    audit = {'residential':ar,'commercial':ac,'missing_sector_months_ffilled':missing,
             'excluded_classes_gallons_all_source_dates':excluded,'analysis_rows':len(df),
             'start':str(df.index.min().date()),'end':str(df.index.max().date()),
             'industrial_caveat':'Large volume is a billing-class proxy; the source does not identify industrial end-use.',
             'scope':'Selected retail classes; wholesale and utility use excluded to avoid possible double counting.'}
    return df,audit

def adf(series):
    result = adfuller(series.dropna(),autolag='AIC',result_object=False)
    return {'statistic':float(result[0]),'pvalue':float(result[1]),'lags':int(result[2]),
            'nobs':int(result[3]),'critical_values':{k:float(v) for k,v in result[4].items()}}

def fit_arima(history, order):
    # Fit in billion gallons for numerical conditioning; outputs are converted to MG.
    fit = ARIMA(history/1000.,order=order).fit(method_kwargs={'maxiter':1000})
    if not fit.mle_retvals.get('converged',True):
        fit = ARIMA(history/1000.,order=order).fit(method_kwargs={'method':'powell','maxiter':2000})
    if not fit.mle_retvals.get('converged',True):
        raise RuntimeError('ARIMA optimization did not converge after numerical retry.')
    return fit

def choose_arima(train):
    tests = {str(d):adf(train.diff(d).dropna() if d else train) for d in [0,1]}
    d = 0 if tests['0']['pvalue']<.05 else 1
    if tests[str(d)]['pvalue'] >= .05:
        raise ValueError('ADF does not support d=0 or d=1; review transformations before fitting.')
    candidates=[]
    for p in range(3):
        for q in range(3):
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    fit=fit_arima(train,(p,d,q))
                converged=bool(fit.mle_retvals.get('converged',True))
                candidates.append({'p':p,'d':d,'q':q,'AIC':float(fit.aic),
                                   'converged':converged,'warnings':'; '.join(str(w.message) for w in caught)})
            except Exception as e:
                candidates.append({'p':p,'d':d,'q':q,'AIC':np.nan,'converged':False,'warnings':str(e)})
    grid=pd.DataFrame(candidates)
    valid=grid.loc[grid.converged & grid.AIC.notna()]
    if valid.empty: raise RuntimeError('No converged ARIMA model.')
    best=valid.sort_values('AIC').iloc[0]
    return tuple(int(best[k]) for k in ['p','d','q']),grid,tests

def weather_features(index, weather, origin):
    # Predictor weather is supplied explicitly, never pulled from validation/test observations.
    month=index.month.to_numpy()
    trend=((index.year-origin.year)*12+index.month-origin.month).to_numpy()/120
    return np.column_stack([np.ones(len(index)),trend,np.sin(2*np.pi*month/12),
                            np.cos(2*np.pi*month/12),np.asarray(weather)/[10.,100.],index.days_in_month.to_numpy()/30])

def predict(name, history, frame, index, order):
    if name=='ARIMA':
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit=fit_arima(history,order)
        if not fit.mle_retvals.get('converged',True): raise RuntimeError('ARIMA fit did not converge.')
        pred=fit.get_forecast(len(index))
        return np.maximum(np.asarray(pred.predicted_mean)*1000.,0),np.maximum(np.asarray(pred.conf_int())*1000.,0)
    if name=='Holt Winters':
        fit=ExponentialSmoothing(history,trend='add',damped_trend=True,seasonal='add',seasonal_periods=12,
                                 initialization_method='estimated').fit(optimized=True)
        return np.maximum(np.asarray(fit.forecast(len(index))),0),None
    if name=='Seasonal naive':
        last=history.iloc[-12:].to_numpy()
        return np.resize(last,len(index)),None
    if name=='Weather calendar regression':
        columns=['temperature_2m_mean','precipitation_sum']
        observed=frame.loc[history.index,columns]
        climate=observed.groupby(observed.index.month).mean()
        expected=climate.loc[index.month].to_numpy()
        x=weather_features(history.index,observed,history.index[0])
        beta=np.linalg.lstsq(x,history.to_numpy(),rcond=None)[0]
        return np.maximum(weather_features(index,expected,history.index[0])@beta,0),None
    raise ValueError(name)

def savefig(name):
    plt.tight_layout(); plt.savefig(FIG/f'{name}.png',dpi=600,bbox_inches='tight'); plt.close()

def run():
    OUT.mkdir(exist_ok=True); FIG.mkdir(exist_ok=True)
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,
                         'grid.alpha':.2,'figure.figsize':(10,4),'font.size':10})
    frame,audit=load_data(); y=frame.total_mg
    train,validation,test=y.iloc[:-24],y.iloc[-24:-12],y.iloc[-12:]
    order,grid,adfs=choose_arima(train)
    grid.to_csv(OUT/'arima_grid.csv',index=False)
    names=['ARIMA','Holt Winters','Seasonal naive','Weather calendar regression']
    rows=[]; predictions=pd.DataFrame({'actual_mg':test})
    for name in names:
        vp,_=predict(name,train,frame,validation.index,order)
        tp,ci=predict(name,y.iloc[:-12],frame,test.index,order)
        rows.append({'model':name,**{'validation_'+k:v for k,v in metrics(validation,vp).items()},
                     **{'test_'+k:v for k,v in metrics(test,tp).items()}})
        predictions[name]=tp
        if name=='ARIMA': predictions['ARIMA_lower95'],predictions['ARIMA_upper95']=ci[:,0],ci[:,1]
    comparison=pd.DataFrame(rows).sort_values('validation_RMSE')
    winner=str(comparison.iloc[0].model)
    comparison.to_csv(OUT/'metrics.csv',index=False); predictions.to_csv(OUT/'test_predictions.csv')
    future_index=pd.date_range(y.index[-1]+pd.offsets.MonthBegin(),periods=12,freq='MS')
    future=pd.DataFrame(index=future_index); future.index.name='date'
    for name in names:
        fp,ci=predict(name,y,frame,future_index,order); future[name]=fp
        if name=='ARIMA': future['ARIMA_lower95'],future['ARIMA_upper95']=ci[:,0],ci[:,1]
    future['selected_forecast_mg']=future[winner]
    shares=frame[SECTORS].iloc[-12:].sum()/frame[SECTORS].iloc[-12:].sum().sum()
    for sector in SECTORS: future[sector]=future.selected_forecast_mg*shares[sector]
    future.to_csv(OUT/'future_forecast.csv')
    # Historical one-step seasonal baseline; thresholds calibrated using past errors only.
    baseline=y.shift(12); errors=y-baseline
    center=errors.shift(1).rolling(24,min_periods=12).median()
    scale=errors.shift(1).rolling(24,min_periods=12).apply(lambda a:np.median(abs(a-np.median(a))),raw=True)*1.4826
    score=(errors-center)/scale.replace(0,np.nan)
    anomaly=pd.DataFrame({'actual_mg':y,'seasonal_baseline_mg':baseline,'robust_score':score,
                          'flag':score.abs()>3.5,'temperature_c':frame.temperature_2m_mean,
                          'rainfall_mm':frame.precipitation_sum})
    anomaly['demand_change_yoy_mg']=errors
    anomaly['temperature_change_yoy_c']=frame.temperature_2m_mean.diff(12)
    anomaly['rainfall_change_yoy_mm']=frame.precipitation_sum.diff(12)
    anomaly['possible_explanation']='No unusual seasonal residual'
    anomaly.loc[anomaly.flag,'possible_explanation']='Weather does not clearly explain alert direction; review billing, restrictions and leaks; cause unverified'
    anomaly.loc[anomaly.flag & (score>0) & (anomaly.temperature_change_yoy_c>1),'possible_explanation']='Warmer than year-earlier month may support increased outdoor demand; unverified'
    anomaly.loc[anomaly.flag & (score<0) & (anomaly.temperature_change_yoy_c< -1),'possible_explanation']='Cooler than year-earlier month may support reduced outdoor demand; unverified'
    anomaly.loc[anomaly.flag & (score>0) & (anomaly.rainfall_change_yoy_mm< -50),'possible_explanation']='Drier than year-earlier month may support increased irrigation; unverified'
    anomaly.loc[anomaly.flag & (score<0) & (anomaly.rainfall_change_yoy_mm>50),'possible_explanation']='Wetter than year-earlier month may support reduced irrigation; unverified'
    anomaly.to_csv(OUT/'anomalies.csv')
    scenario_rows=[]
    for fraction in [1.1,.75,.35]:
        for policy in ['Priority','Proportional']:
            for date,row in future.iterrows():
                demand=row[SECTORS].to_numpy(dtype=float)
                capacity=np.array([1.1,.95,.90,1.0])*demand # Assumed network limits.
                table,status=allocate(demand,float(row.selected_forecast_mg*fraction),policy,capacity)
                table['date']=str(date.date()); table['supply_fraction']=fraction; table['policy']=policy
                table['minimum_service_feasible']=status['feasible']; table['recommended_action']=status['action']
                scenario_rows.append(table)
    pd.concat(scenario_rows).to_csv(OUT/'allocation_scenarios.csv',index=False)
    fit=fit_arima(y.iloc[:-12],order)
    burn=max(12,sum(order))
    ljung=acorr_ljungbox(fit.resid.iloc[burn:],lags=[12],model_df=order[0]+order[2],return_df=True)
    summary={'audit':audit,'arima_order':order,'adf_training':adfs,'selected_model':winner,
             'selection_rule':'Lowest 12-month validation RMSE; final 12 months reserved for test.',
             'train_period':[str(train.index[0].date()),str(train.index[-1].date())],
             'validation_period':[str(validation.index[0].date()),str(validation.index[-1].date())],
             'test_period':[str(test.index[0].date()),str(test.index[-1].date())],
             'forecast_period':[str(future.index[0].date()),str(future.index[-1].date())],
             'forecast_note':'Historical-origin demonstration forecast, issued after December 2024; not a current 2026 forecast.',
             'flagged_months':int(anomaly.flag.sum()),'ljung_box_12_pvalue':float(ljung.lb_pvalue.iloc[0]),
             'sector_shares':shares.to_dict(),'metrics':comparison.to_dict(orient='records'),
             'weather_correlations':frame[['total_mg','temperature_2m_mean','precipitation_sum']].corr().total_mg.to_dict(),
             'python':platform.python_version()}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    manifest={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in (ROOT/'data/raw').glob('*')}
    (OUT/'data_manifest.json').write_text(json.dumps(manifest,indent=2))
    frame[SECTORS].plot.area(colormap='viridis',alpha=.85); plt.ylabel('Million US gallons per month'); plt.title('Retail billing consumption by sector'); savefig('consumption')
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True)
    axes[0].plot(y,label='Observed'); axes[0].plot(frame.rolling_mean_12,label='12-month mean'); axes[0].legend(); axes[0].set_ylabel('Million gallons')
    axes[1].plot(frame.rolling_variance_12,color='#ab5b20'); axes[1].set_ylabel('Rolling variance'); axes[0].set_title('Stationarity exploration'); savefig('stationarity')
    fig,axes=plt.subplots(1,2,figsize=(10,3.5)); diff=train.diff(order[1]).dropna() if order[1] else train
    plot_acf(diff,lags=24,ax=axes[0]);plot_pacf(diff,lags=24,method='ywm',ax=axes[1]); savefig('acf_pacf')
    stl=STL(y,period=12,robust=True).fit(); stl.plot(); savefig('decomposition')
    fig,ax=plt.subplots(figsize=(10,4)); ax.plot(test,label='Actual',color='black',linewidth=2)
    for name in names: ax.plot(predictions[name],label=name)
    ax.set_title('Untouched 2024 test set'); ax.set_ylabel('Million US gallons per month'); ax.legend(fontsize=8); savefig('test_forecast')
    plt.plot(y.iloc[-36:],label='Observed'); plt.plot(future.selected_forecast_mg,label=winner)
    plt.fill_between(future.index,future.ARIMA_lower95,future.ARIMA_upper95,alpha=.15,label='ARIMA 95% interval')
    plt.title('2025 forecast from the December 2024 origin'); plt.ylabel('Million US gallons per month'); plt.legend();savefig('future_forecast')
    plt.plot(y,label='Observed'); flagged=anomaly.loc[anomaly.flag]; plt.scatter(flagged.index,flagged.actual_mg,color='#ce3747',label='Flagged for review',zorder=3)
    plt.ylabel('Million US gallons per month');plt.title('Causal seasonal-residual anomaly screening');plt.legend();savefig('anomalies')
    fig,axes=plt.subplots(1,2,figsize=(10,4)); axes[0].scatter(frame.temperature_2m_mean,y,alpha=.6); axes[0].set_xlabel('Monthly mean temperature C');axes[1].scatter(frame.precipitation_sum,y,alpha=.6);axes[1].set_xlabel('Monthly rainfall mm');axes[0].set_ylabel('Million gallons');savefig('weather')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': run()
