# Link Profiler Customer Dashboard

A modern React-based customer dashboard for the Link Profiler system, built with TypeScript, Tailwind CSS, and Vite.

## Features

- **Authentication**: Secure login with JWT tokens
- **Dashboard Overview**: Real-time statistics and recent activity
- **Job Management**: Create, monitor, and manage crawl and analysis jobs
- **Reports**: Generate and download comprehensive SEO reports
- **Analytics**: Track performance metrics and trends
- **Profile Management**: User settings and preferences

## Technology Stack

- **React 18** - UI framework
- **TypeScript** - Type safety and better developer experience
- **Tailwind CSS** - Utility-first CSS framework
- **Vite** - Fast build tool and development server
- **React Router** - Client-side routing
- **Lucide React** - Beautiful icons
- **Zustand** - State management (if needed)

## Getting Started

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── layout/          # Layout components (Header, Sidebar, etc.)
│   └── ui/              # Basic UI components
├── contexts/            # React contexts (Auth, etc.)
├── hooks/               # Custom React hooks
├── pages/               # Main page components
├── stores/              # State management stores
├── types.ts             # TypeScript type definitions
├── config.ts            # Application configuration
└── index.css           # Global styles and Tailwind imports
```

## Key Components

### Authentication (`src/contexts/AuthContext.tsx`)
- Handles user login/logout
- JWT token management
- User role verification

### Dashboard (`src/pages/Dashboard.tsx`)
- Overview statistics
- Quick actions
- Recent activity feed

### Jobs (`src/pages/Jobs.tsx`)
- Job listing and filtering
- Job status monitoring
- Bulk operations

### Reports (`src/pages/Reports.tsx`)
- Report generation
- Download management
- Report history

### Analytics (`src/pages/Analytics.tsx`)
- Performance metrics
- Trend visualization
- Export capabilities

## Configuration

The dashboard connects to the Link Profiler API using configuration in `src/config.ts`:

```typescript
export const API_BASE_URL = '';  // Relative to same origin
export const WS_BASE_URL = window.location.protocol === 'https:' ? 
  `wss://${window.location.host}` : 
  `ws://${window.location.host}`;
```

## Building for Production

1. Build the application:
```bash
npm run build
```

2. The built files will be in the `dist/` directory

3. Deploy the `dist/` contents to your web server

## Integration with Backend

This dashboard is designed to work with the Link Profiler API backend. It expects:

- Authentication endpoints at `/token`, `/register`, `/users/me`
- Customer-specific API endpoints under `/jobs`, `/reports`, `/analytics`
- WebSocket connection for real-time updates

## Development

### Code Style
- Use TypeScript for all components
- Follow React best practices
- Use Tailwind CSS utility classes
- Maintain consistent file naming

### Adding New Features
1. Create components in appropriate directories
2. Add TypeScript types in `types.ts`
3. Update routing in `App.tsx`
4. Add navigation items in `Sidebar.tsx`

## License

Part of the Link Profiler system. See main project license.
