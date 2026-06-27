// AsyncOperation client + a single generic poller (1–2 s, unmount-safe,
// terminal-stop, bounded error retry, no duplicate loops per operation).

export type OperationStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"

export interface AsyncOperationDto {
  operation_id: string
  resource_type: string
  resource_id: string
  status: OperationStatus
  created_at: string
  updated_at?: string | null
  progress_percent?: number | null
  result?: Record<string, unknown> | null
  error?: { code?: string; detail?: string } | null
}

const TERMINAL: ReadonlyArray<OperationStatus> = ["succeeded", "failed", "cancelled"]

export async function getOperation(
  operationId: string
): Promise<AsyncOperationDto> {
  const res = await fetch(`/api/operations/${encodeURIComponent(operationId)}`)
  if (!res.ok) throw new Error(`operation_poll_failed_${res.status}`)
  return (await res.json()) as AsyncOperationDto
}

export interface PollHandle {
  stop: () => void
}

export interface PollOptions {
  onUpdate?: (op: AsyncOperationDto) => void
  onTerminal?: (op: AsyncOperationDto) => void
  intervalMs?: number
  maxErrors?: number
}

/** Poll one operation until a terminal status, with bounded error retry. */
export function pollOperation(
  operationId: string,
  options: PollOptions = {}
): PollHandle {
  const { onUpdate, onTerminal, intervalMs = 1500, maxErrors = 5 } = options
  let stopped = false
  let errors = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const tick = async () => {
    if (stopped) return
    try {
      const op = await getOperation(operationId)
      errors = 0
      onUpdate?.(op)
      if (TERMINAL.includes(op.status)) {
        stopped = true
        onTerminal?.(op)
        return
      }
    } catch {
      errors += 1
      if (errors >= maxErrors) {
        stopped = true
        return
      }
    }
    if (!stopped) timer = setTimeout(tick, intervalMs)
  }

  timer = setTimeout(tick, 0)
  return {
    stop: () => {
      stopped = true
      if (timer) clearTimeout(timer)
    },
  }
}
