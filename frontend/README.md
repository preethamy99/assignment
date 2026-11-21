# Packwell Frontend

Angular client for the shipping box calculator API.

## Run locally

Start the FastAPI backend at `http://127.0.0.1:8000` and set its
`API_AUTH_TOKEN`. From this folder, run:

```powershell
npm.cmd install
npm.cmd start
```

Open `http://localhost:4200` and enter the same API token configured on the
backend. The development server proxies API requests to FastAPI.

## Test and build

```powershell
npm.cmd test -- --watch=false
npm.cmd run build
```
