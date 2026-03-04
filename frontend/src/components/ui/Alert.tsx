type AlertVariant = 'error' | 'warning' | 'info'

const variants: Record<AlertVariant, string> = {
  error: 'bg-red-50 border-red-200 text-red-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
}

interface AlertProps {
  children: React.ReactNode
  variant?: AlertVariant
  className?: string
}

export function Alert({ children, variant = 'error', className = '' }: AlertProps) {
  return (
    <div className={`border rounded px-3 py-2 text-sm ${variants[variant]} ${className}`}>
      {children}
    </div>
  )
}
