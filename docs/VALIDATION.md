# Validation record

The project was built and demonstrated on the user's Windows PC using Python 3.12.14 and the pinned package versions in requirements.txt.

- Full analysis pipeline completed successfully from the committed raw snapshots.
- All 10 automated tests passed, including actual Streamlit controls, supply/capacity bounds, emergency infeasibility, duplicate validation, zero-safe metrics and prevention of future-weather leakage. Full output: results/test_log.txt.
- Source SHA-256 hashes were independently rechecked against results/data_manifest.json.
- Exported MAE, RMSE and MAPE were independently recomputed from test_predictions.csv and matched metrics.csv.
- All 12 future forecast rows were checked for finite numerical values.
- All 288 saved allocation rows were checked for nonnegative allocations and compliance with demand and capacity bounds.
- The dashboard was run locally and inspected in the browser. Both feasible shortage and emergency behavior were demonstrated; screenshots are included in docs/.
- The revised 13-page Word report was exported through Microsoft Word and every page visually inspected. All rendered pages were verified to contain grayscale pixels only. The packaged LibreOffice renderer was unavailable.
- Report colours were changed at the user's request: black headings and borders, white table cells, and grayscale logos, figures and screenshots. GitHub/submission placeholders and duplicate screenshots were removed. Source media and section geometry were preserved; the original template file remained unchanged.
- Figure quality revision: charts regenerated at 600 DPI (about 5,900 pixels wide). Dashboard screenshots were recaptured natively at 3,839 pixels wide, with complete headings, metrics, tables and charts. The report embeds these full-resolution files and disables automatic picture compression. All 13 revised pages were visually checked and all 10 tests passed again.

Known limits: this is a historical December 2024 forecast-origin experiment, not a current operational forecast. Large-volume billing and municipal billing are proxies. Supply, network limits and service priorities are demonstration assumptions. Anomalies are unverified alerts. GitHub Actions configuration is included but has not run on GitHub before repository publication.
