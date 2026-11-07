import { TrainFront } from 'lucide-react'

import { cn } from '@/lib/utils'

/** MAIA's mark: a hi-vis tile, the colour of the vests and tags around a depot. */
export function Avatar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-lg bg-hivis text-hivis-foreground',
        className,
      )}
    >
      <TrainFront className="size-[60%]" aria-hidden />
    </div>
  )
}
