# Orion dashboard

React/Mapbox frontend and FastAPI backend for the district-wide Dakshina Kannada
flood-risk demonstrator.

## Run locally

From the repository root, refresh the generated data first:

```bash
make app-data
```

Then run the API and frontend in separate terminals:

```bash
cd flood-risk-app/backend
../../.venv/bin/uvicorn server:app --reload --port 8000
```

```bash
cd flood-risk-app/frontend
npm install --legacy-peer-deps
npm start
```

The frontend reads precomputed district assets from `frontend/public/data` and
uses the API for live rainfall, model explanations, metrics, and arbitrary-point
emergency routing. A Mapbox token is required in `frontend/.env` as
`REACT_APP_MAPBOX_TOKEN`.

The hospital layer contains curated routing origins across all nine taluks. It
must not be interpreted as a verified list of facilities with currently available
ambulances, emergency departments, or beds.
