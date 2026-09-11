import { Link } from 'react-router-dom'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function NotFoundPage() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4 text-center">
      <h1 className="text-2xl font-medium">Page not found</h1>
      <Link to="/" className={cn(buttonVariants({ variant: 'outline' }))}>
        Back to the dashboard
      </Link>
    </main>
  )
}
