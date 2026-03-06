import { NavLink } from 'react-router-dom'
import { BookOpen, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
  end?: boolean
}

function NavItem({ to, icon, label, end }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors',
          isActive
            ? 'bg-sidebar-accent text-foreground font-medium border-l-2 border-primary rounded-l-none -ml-px pl-[calc(0.75rem-1px)]'
            : 'text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50'
        )
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  )
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex flex-col w-[200px] shrink-0 h-screen bg-sidebar border-r border-border">
      {/* macOS 트래픽라이트 공간 + 앱 타이틀 */}
      <div
        className="pt-10 px-4 pb-3 select-none"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <span className="text-sm font-semibold text-foreground">EPUB Translate</span>
      </div>

      {/* 구분선 */}
      <div className="h-px bg-border mx-3 mb-2" />

      {/* 네비게이션 */}
      <nav className="flex flex-col flex-1 px-2 py-1 gap-0.5">
        <NavItem
          to="/"
          end
          icon={<BookOpen size={15} />}
          label="번역"
        />

        {/* 하단 고정 영역 */}
        <div className="mt-auto pb-2">
          <NavItem
            to="/settings"
            icon={<Settings size={15} />}
            label="설정"
          />
        </div>
      </nav>
    </aside>
  )
}
