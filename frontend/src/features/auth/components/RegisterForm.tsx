import { useId, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/httpClient'
import { useAuth } from '../useAuth'

export function RegisterForm() {
  const { register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const firstNameId = useId()
  const lastNameId = useId()
  const nicknameId = useId()
  const emailId = useId()
  const passwordId = useId()
  const errorId = useId()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        nickname,
      })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to register')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor={firstNameId}>First name</Label>
          <Input
            id={firstNameId}
            autoComplete="given-name"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            minLength={1}
            maxLength={100}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            required
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={lastNameId}>Last name</Label>
          <Input
            id={lastNameId}
            autoComplete="family-name"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            minLength={1}
            maxLength={100}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            required
          />
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={nicknameId}>Nickname</Label>
        <Input
          id={nicknameId}
          value={nickname}
          onChange={(event) => setNickname(event.target.value)}
          minLength={2}
          maxLength={50}
          pattern="^[A-Za-z0-9_-]+$"
          title="Letters, digits, underscores and hyphens only"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          required
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={emailId}>Email</Label>
        <Input
          id={emailId}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          required
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={passwordId}>Password</Label>
        <Input
          id={passwordId}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
          maxLength={128}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          required
        />
      </div>
      {error && (
        <p role="alert" id={errorId} className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        Register
      </Button>
    </form>
  )
}
