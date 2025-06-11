import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Briefcase, 
  FileText, 
  BarChart3, 
  User,
  Link,
  Search,
  Target,
  TrendingUp
} from 'lucide-react';

interface NavItem {
  path: string;
  icon: React.ComponentType<any>;
  label: string;
  description?: string;
}

const navigation: NavItem[] = [
  {
    path: '/',
    icon: LayoutDashboard,
    label: 'Dashboard',
    description: 'Overview and quick actions'
  },
  {
    path: '/jobs',
    icon: Briefcase,
    label: 'Jobs',
    description: 'Manage crawl and analysis jobs'
  },
  {
    path: '/reports',
    icon: FileText,
    label: 'Reports',
    description: 'View and download reports'
  },
  {
    path: '/analytics',
    icon: BarChart3,
    label: 'Analytics',
    description: 'Performance insights'
  },
];

const quickActions: NavItem[] = [
  {
    path: '/jobs/create?type=link_analysis',
    icon: Link,
    label: 'Link Analysis',
  },
  {
    path: '/jobs/create?type=domain_analysis',
    icon: Search,
    label: 'Domain Analysis',
  },
  {
    path: '/jobs/create?type=competitive_analysis',
    icon: Target,
    label: 'Competitive Analysis',
  },
  {
    path: '/analytics/trends',
    icon: TrendingUp,
    label: 'SEO Trends',
  },
];

const Sidebar: React.FC = () => {
  return (
    <aside className="fixed top-16 left-0 w-64 h-[calc(100vh-4rem)] bg-white border-r border-neutral-200 overflow-y-auto scrollbar-thin">
      <div className="p-6">
        {/* Main Navigation */}
        <nav className="space-y-2">
          <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">
            Main Navigation
          </div>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-brand-primary text-white shadow-sm'
                      : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
                  }`
                }
                end={item.path === '/'}
              >
                <Icon className="mr-3 h-5 w-5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="truncate">{item.label}</div>
                  {item.description && (
                    <div className="text-xs opacity-75 truncate">{item.description}</div>
                  )}
                </div>
              </NavLink>
            );
          })}
        </nav>

        {/* Quick Actions */}
        <div className="mt-8">
          <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">
            Quick Actions
          </div>
          <div className="space-y-2">
            {quickActions.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className="group flex items-center px-3 py-2 text-sm font-medium text-neutral-600 rounded-lg hover:bg-brand-light hover:text-brand-primary transition-all duration-200"
                >
                  <Icon className="mr-3 h-4 w-4 flex-shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </div>

        {/* Account Section */}
        <div className="mt-8 pt-6 border-t border-neutral-200">
          <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">
            Account
          </div>
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-brand-primary text-white'
                  : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
              }`
            }
          >
            <User className="mr-3 h-5 w-5 flex-shrink-0" />
            <span className="truncate">Profile & Settings</span>
          </NavLink>
        </div>

        {/* Usage Stats Card */}
        <div className="mt-8 p-4 bg-gradient-to-r from-brand-primary to-brand-secondary rounded-lg text-white">
          <div className="text-sm font-medium mb-2">This Month</div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="opacity-90">Jobs Completed</span>
              <span className="font-medium">24</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-90">Reports Generated</span>
              <span className="font-medium">8</span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-90">Domains Analyzed</span>
              <span className="font-medium">156</span>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/20">
            <button className="text-xs font-medium hover:underline">
              View Detailed Stats →
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
