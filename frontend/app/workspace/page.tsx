import { Suspense } from 'react'

import QuorumPipeline from '@/components/workspace/quorum-pipeline'

export default function WorkspacePage() {
  return (
    <Suspense fallback={null}>
      <QuorumPipeline />
    </Suspense>
  )
}
