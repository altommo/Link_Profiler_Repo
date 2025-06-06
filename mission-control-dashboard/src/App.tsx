import { useEffect, useState } from 'react'
import { io } from 'socket.io-client'

interface MissionData {
  active_jobs: any[]
  satellite_status: any[]
  queue_depth: number
  recent_discoveries: any[]
  api_quotas: Record<string, any>
  alerts: any[]
}

function App() {
  const [data, setData] = useState<MissionData | null>(null)

  useEffect(() => {
    const socket = io('/ws/mission-control', { path: '/ws/mission-control' })
    socket.on('connect', () => {
      console.log('connected')
    })
    socket.on('message', (msg: MissionData) => {
      setData(msg)
    })
    return () => {
      socket.close()
    }
  }, [])

  return (
    <div>
      <h1>Mission Control Dashboard</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}

export default App
