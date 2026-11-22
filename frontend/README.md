# Packwell Frontend

Angular client for the shipping box calculator API.

## Run locally

Start the FastAPI backend at `http://127.0.0.1:8000` with `JWT_SECRET_KEY`
configured. From this folder, run:

```powershell
npm.cmd install
npm.cmd start
```

Open `http://localhost:4200` and sign in with the local demo account:

- Email: `test@example.com`
- Password: `1234567890`

The frontend fetches a JWT on sign-in and attaches it automatically to packing
requests. It keeps the token in memory only. The development server proxies API
requests to FastAPI.

## Import package files

After signing in, use **Choose file** below **Add package** to import `.csv`,
`.xls`, or `.xlsx` files. Imports append to the current package list and use the
first worksheet in Excel workbooks. Include these columns in the header row:

```csv
id,width,height,length,weight
123,10,10,10,5
125,5,5,10,10
```

Headers are case-insensitive and can appear in any order. Blank rows are
skipped; invalid rows reject the entire import without changing the package
list. Files may be up to 10 MB, with at most 500 packages total. The app
includes a [CSV template](./public/package-template.csv) you can download and
edit before importing.

## Test and build

```powershell
npm.cmd test -- --watch=false
npm.cmd run build
```
