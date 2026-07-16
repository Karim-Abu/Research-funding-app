import { readdir, readFile } from "node:fs/promises"
import path from "node:path"

const apiRoot = path.join(process.cwd(), "app", "api")

async function collectRouteFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await collectRouteFiles(entryPath)))
    } else if (entry.isFile() && entry.name === "route.ts") {
      files.push(entryPath)
    }
  }

  return files
}

const routeFiles = await collectRouteFiles(apiRoot)

// OneDrive Files On-Demand can expose route files as reparse points without
// hydrating their contents. Reading them before Next.js starts ensures nested
// App Router handlers are included in the initial route matcher.
await Promise.all(routeFiles.map((file) => readFile(file)))

console.log(`Prepared ${routeFiles.length} API routes for Next.js.`)
