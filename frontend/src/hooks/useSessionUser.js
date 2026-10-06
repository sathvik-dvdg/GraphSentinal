// The signed-in user as the UI needs it: who they are and what they may do.
//
// The role comes from Clerk's publicMetadata.role -- the same field the
// backend authorises with (backend/app/api/v1/deps.py), so a control is
// greyed out here exactly when the backend would refuse it. It used to be
// read from useAuthStore, which only the old operator login filled; under
// Clerk it was always empty, so every admin-only control was disabled for
// everyone, admins included.
import { useUser } from '@clerk/react'

export default function useSessionUser() {
  const { user } = useUser()
  return {
    role: user?.publicMetadata?.role ?? null,
    username: user?.username || user?.primaryEmailAddress?.emailAddress || null,
  }
}
