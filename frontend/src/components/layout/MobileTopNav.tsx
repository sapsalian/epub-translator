import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface TabItemProps {
  to: string
  label: string
  end?: boolean
}

function TabItem({ to, label, end }: TabItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex flex-1 items-center justify-center text-sm transition-colors',
          isActive ? 'text-foreground font-medium' : 'text-muted-foreground'
        )
      }
    >
      {label}
    </NavLink>
  )
}

export function MobileTopNav() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 flex h-12 items-stretch bg-sidebar border-b border-border md:hidden">
      <TabItem to="/" end label="번역" />
      <TabItem to="/settings" label="설정" />
    </nav>
  )
}
