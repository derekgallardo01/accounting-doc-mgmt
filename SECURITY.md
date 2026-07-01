# Security

## Reporting a vulnerability

Email derekgallardo01@gmail.com.

## Scope

- The kit ships a deterministic **mock** SharePoint tenant. No live
  Graph authentication happens by default.
- Real Graph credentials are read from `AZURE_TENANT_ID`,
  `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` environment variables only.
  Nothing is written to disk.
- Client + matter + document data in the mock is fictional. No real
  PHI, PII, or financial data is present.

## Dependencies

Runtime default: stdlib only. `msgraph-sdk` + `msal` are optional
extras for the production path.
