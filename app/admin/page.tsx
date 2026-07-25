import { redirect } from "next/navigation"

// Legacy evaluation URL. The product-facing page is deliberately named after
// the user goal, not the implementation detail.
export default function AdminPage() {
  redirect("/systemstatus")
}
