import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { UploadStatus } from "@/types/api"

const STATUS_STYLES: Record<UploadStatus, string> = {
  REQUESTED: "bg-muted text-muted-foreground",
  UPLOADED: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  PROCESSING: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  COMPLETED: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  FAILED: "bg-red-500/10 text-red-600 dark:text-red-400",
}

export function StatusBadge({ status }: { status: UploadStatus }) {
  return (
    <Badge variant="outline" className={cn("border-transparent", STATUS_STYLES[status])}>
      {status}
    </Badge>
  )
}
