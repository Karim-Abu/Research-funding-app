import { setupServer } from "msw/node"

// Shared MSW server; tests register handlers per case via server.use(...).
export const server = setupServer()
