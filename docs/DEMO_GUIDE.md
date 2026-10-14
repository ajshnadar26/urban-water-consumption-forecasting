# Demonstration guide

1. Follow the README setup commands, then open the local Streamlit URL.
2. On Forecast and evaluation, explain the training/validation/test split. Show that Holt–Winters was selected on 2023 validation, although ARIMA has lower 2024 test RMSE. Explain why selection is not changed after seeing test results.
3. Open Consumption and weather. Show monthly seasonality, the four retail sectors, temperature/rainfall and STL decomposition.
4. Open Stationarity and models. Read the ADF null hypothesis, show rolling mean/variance and ACF/PACF, then show the converged ARIMA (2,1,2) grid result.
5. Open Abnormal consumption. Show the four flagged months and explain the causal robust-residual rule, warm-up period and lack of confirmed incident labels.
6. Open Resource allocation. Set supply to 75%, capacity to 100% and policy to Priority. January 2025 demand is approximately 3,394.65 MG; supply is 2,545.99 MG. Minimum service is feasible and the gap is approximately 848.66 MG.
7. Switch to Proportional and compare sector allocations. Then lower supply to 35%: the emergency message and minimum-service violations must appear. Restore supply to 75% and lower network capacity to 50% to show that capacity can independently make floors infeasible.
8. Restore default controls. Download allocation and forecast CSVs. Explain that capacities/priorities are scenario assumptions and that large volume is an industrial proxy.
9. Open the report, fill group details and actual contributions, and submit the repository link through the teacher's required channel.

Likely viva questions: Why difference the series? Why chronological splitting? Why compare with seasonal naive? Why avoid using actual future weather? Why can ample total supply still leave a shortage? Why are unusual billing values not automatically deleted? What does an ADF p-value actually establish? What extra data is required for real deployment?
