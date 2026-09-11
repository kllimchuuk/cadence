import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { authApi } from '../api'

export function GoogleSignInButton() {
  return (
    <a
      href={authApi.googleLoginUrl()}
      className={cn(buttonVariants({ variant: 'outline' }), 'w-full')}
    >
      Continue with Google
    </a>
  )
}
