import { useQuery } from '@tanstack/react-query'
import { membersApi, type Member } from '../api/client'

// Role display config. When server-specific role customization is added,
// fetch this from the API and pass it as a prop with these values as fallback.
const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  owner: { label: 'Owner', color: '#f5a623' },
  admin: { label: 'Admin', color: '#63c5ff' },
  member: { label: '', color: '' },
}

const ROLE_ORDER = ['owner', 'admin', 'member']

interface Props {
  serverId: string
}

function avatarColor(username: string): string {
  const colors = ['#6c63ff', '#63c5ff', '#ff6b9d', '#51cf66', '#f5a623', '#ff6348']
  let hash = 0
  for (const ch of username) hash = (hash * 31 + ch.charCodeAt(0)) & 0xffffffff
  return colors[Math.abs(hash) % colors.length]
}

export default function MemberList({ serverId }: Props) {
  const { data: members = [] } = useQuery({
    queryKey: ['members', serverId],
    queryFn: () => membersApi.list(serverId),
    staleTime: 30_000,
  })

  const grouped = ROLE_ORDER.reduce<Record<string, Member[]>>((acc, role) => {
    acc[role] = members.filter((m) => m.role === role)
    return acc
  }, {})

  return (
    <div className="w-48 flex flex-col bg-surface-800 border-l border-surface-700 shrink-0">
      <div className="px-3 py-3 border-b border-surface-700">
        <span className="text-xs font-semibold uppercase text-ivory/50 tracking-wide">
          Members — {members.length}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin py-2">
        {ROLE_ORDER.map((role) => {
          const group = grouped[role]
          if (group.length === 0) return null
          const config = ROLE_CONFIG[role] ?? { label: role, color: '' }
          const sectionLabel = config.label
            ? `${config.label.toUpperCase()}S — ${group.length}`
            : `MEMBERS — ${group.length}`

          return (
            <div key={role} className="mb-3">
              <div className="px-3 mb-1">
                <span className="text-xs font-semibold uppercase text-ivory/40 tracking-wide">
                  {sectionLabel}
                </span>
              </div>
              {group.map((member) => {
                const cfg = ROLE_CONFIG[member.role] ?? { label: '', color: '' }
                return (
                  <div
                    key={member.user_id}
                    className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface-700/40 rounded mx-1"
                  >
                    <div
                      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                      style={{ background: avatarColor(member.username) }}
                    >
                      {member.username[0]?.toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs text-ivory truncate">{member.username}</div>
                      {cfg.label && (
                        <div className="text-xs truncate" style={{ color: cfg.color }}>
                          {cfg.label}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
