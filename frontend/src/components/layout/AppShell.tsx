import { MobileTopNav } from './MobileTopNav'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <MobileTopNav />
      <Sidebar />
      <main className="flex-1 overflow-auto min-w-0 pt-12 md:pt-0">
        {children}
      </main>
    </div>
  )
}
