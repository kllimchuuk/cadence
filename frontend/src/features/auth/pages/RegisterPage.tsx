import { Link } from 'react-router-dom'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { GoogleSignInButton } from '../components/GoogleSignInButton'
import { RegisterForm } from '../components/RegisterForm'

export function RegisterPage() {
  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Register</CardTitle>
          <CardDescription>Create your Cadence account.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <RegisterForm />
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            or
            <span className="h-px flex-1 bg-border" />
          </div>
          <GoogleSignInButton />
        </CardContent>
        <CardFooter className="justify-center text-sm">
          Already have an account?&nbsp;
          <Link
            to="/login"
            className="text-primary underline-offset-4 hover:underline"
          >
            Log in
          </Link>
        </CardFooter>
      </Card>
    </main>
  )
}
